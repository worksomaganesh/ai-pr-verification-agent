"""Strict parser and JUnit reconciliation for per-test line/branch coverage evidence."""

from __future__ import annotations

import json
import re
from collections.abc import Hashable
from dataclasses import dataclass
from pathlib import PurePosixPath

from verification_core.domain.enums import EvidenceSufficiency, ExecutionOutcome
from verification_core.evidence import JUnitReport, assess_evidence_sufficiency

MAX_MANIFEST_BYTES = 5 * 1024 * 1024
MAX_COVERAGE_TESTS = 50_000
MAX_FILES_PER_TEST = 1_000
MAX_LOCATIONS_PER_TEST = 100_000
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_BRANCH_RE = re.compile(r"^[1-9][0-9]*:[0-9]+$")


class CoverageManifestError(ValueError):
    """Raised when a per-test coverage manifest is unsafe or inconsistent."""


@dataclass(frozen=True, slots=True)
class CoverageCase:
    """Coverage data for one exact test node ID."""

    node_id: str
    outcome: ExecutionOutcome
    lines_by_file: tuple[tuple[str, tuple[int, ...]], ...]
    branches_by_file: tuple[tuple[str, tuple[str, ...]], ...]
    behavioral_assertion_verified: bool

    def lines_for(self, path: str) -> frozenset[int]:
        """Return executed line numbers for one repository-relative path."""
        return frozenset(
            line
            for file_path, values in self.lines_by_file
            if file_path == path
            for line in values
        )

    def branches_for(self, path: str) -> frozenset[str]:
        """Return executed branch IDs for one repository-relative path."""
        return frozenset(
            branch
            for file_path, values in self.branches_by_file
            if file_path == path
            for branch in values
        )


@dataclass(frozen=True, slots=True)
class CoverageManifest:
    """Coverage manifest bound to a single source commit SHA."""

    version: int
    head_sha: str
    cases: tuple[CoverageCase, ...]

    def case_for(self, node_id: str) -> CoverageCase | None:
        """Find a test case by its exact node ID."""
        return next((case for case in self.cases if case.node_id == node_id), None)


@dataclass(frozen=True, slots=True)
class ReconciledTestEvidence:
    """JUnit outcome and target coverage reconciled for one test and commit."""

    node_id: str
    outcome: ExecutionOutcome
    target_lines_exercised: bool
    target_branches_exercised: bool
    behavioral_assertion_verified: bool
    sufficiency: EvidenceSufficiency


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise CoverageManifestError(f"Duplicate JSON object key: {key!r}.")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise CoverageManifestError(f"Non-finite JSON number {value!r} is forbidden.")


def _exact_keys(value: dict[str, object], expected: set[str], field: str) -> None:
    missing = expected - set(value)
    unknown = set(value) - expected
    if missing:
        raise CoverageManifestError(
            f"{field} is missing key(s): {', '.join(sorted(missing))}."
        )
    if unknown:
        raise CoverageManifestError(
            f"{field} has unknown key(s): {', '.join(sorted(unknown))}."
        )


def _safe_path(value: object, field: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 300:
        raise CoverageManifestError(
            f"{field} must be a non-empty path string of at most 300 chars."
        )
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or "\\" in value
        or ":" in value
        or value.startswith("-")
        or any(part in {"", ".", ".."} for part in value.split("/"))
    ):
        raise CoverageManifestError(f"{field} is not a safe repository-relative path.")
    return value


def _path_locations(
    value: object, field: str, *, branches: bool
) -> tuple[tuple[str, tuple[Hashable, ...]], ...]:
    if not isinstance(value, dict):
        raise CoverageManifestError(f"{field} must be an object keyed by file path.")
    if len(value) > MAX_FILES_PER_TEST:
        raise CoverageManifestError(f"{field} exceeds {MAX_FILES_PER_TEST} file paths.")
    parsed: list[tuple[str, tuple[Hashable, ...]]] = []
    total_locations = 0
    for raw_path, raw_values in value.items():
        path = _safe_path(raw_path, f"{field} path")
        if not isinstance(raw_values, list):
            raise CoverageManifestError(f"{field}[{path!r}] must be a list.")
        values: list[Hashable] = []
        if branches:
            for item in raw_values:
                if not isinstance(item, str) or not _BRANCH_RE.fullmatch(item):
                    raise CoverageManifestError(
                        f"{field}[{path!r}] branch IDs must use 'line:branch-index' notation."
                    )
                values.append(item)
        else:
            for item in raw_values:
                if type(item) is not int or item < 1:
                    raise CoverageManifestError(
                        f"{field}[{path!r}] line numbers must be positive integers."
                    )
                values.append(item)
        if len(set(values)) != len(values):
            raise CoverageManifestError(f"{field}[{path!r}] contains duplicate locations.")
        total_locations += len(values)
        if total_locations > MAX_LOCATIONS_PER_TEST:
            raise CoverageManifestError(f"{field} exceeds {MAX_LOCATIONS_PER_TEST} locations.")
        parsed.append((path, tuple(values)))
    return tuple(sorted(parsed))


def parse_coverage_manifest(text: str | bytes) -> CoverageManifest:
    """Parse bounded JSON; the manifest itself does not establish artifact authenticity."""
    if isinstance(text, str):
        try:
            raw = text.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise CoverageManifestError("Coverage manifest is not valid UTF-8.") from exc
    elif isinstance(text, bytes):
        raw = text
    else:
        raise CoverageManifestError("Coverage manifest input must be text or bytes.")
    if not raw:
        raise CoverageManifestError("Coverage manifest must not be empty.")
    if len(raw) > MAX_MANIFEST_BYTES:
        raise CoverageManifestError(f"Coverage manifest exceeds {MAX_MANIFEST_BYTES} bytes.")
    if b"\x00" in raw:
        raise CoverageManifestError("Coverage manifest contains NUL bytes.")
    try:
        document = json.loads(
            raw,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except CoverageManifestError:
        raise
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise CoverageManifestError("Coverage manifest JSON is malformed.") from exc
    if not isinstance(document, dict):
        raise CoverageManifestError("Coverage manifest root must be an object.")
    _exact_keys(document, {"version", "head_sha", "tests"}, "manifest")
    version = document["version"]
    if type(version) is not int or version != 1:
        raise CoverageManifestError("Coverage manifest version must be integer 1.")
    head_sha = document["head_sha"]
    if not isinstance(head_sha, str) or not _SHA_RE.fullmatch(head_sha):
        raise CoverageManifestError("head_sha must be a lowercase 40-character Git SHA.")
    raw_tests = document["tests"]
    if not isinstance(raw_tests, list) or not raw_tests:
        raise CoverageManifestError("tests must be a non-empty list.")
    if len(raw_tests) > MAX_COVERAGE_TESTS:
        raise CoverageManifestError(f"tests exceeds {MAX_COVERAGE_TESTS} test cases.")

    cases: list[CoverageCase] = []
    seen_node_ids: set[str] = set()
    for index, item in enumerate(raw_tests):
        field = f"tests[{index}]"
        if not isinstance(item, dict):
            raise CoverageManifestError(f"{field} must be an object.")
        _exact_keys(
            item,
            {
                "node_id",
                "outcome",
                "lines",
                "branches",
                "behavioral_assertion_verified",
            },
            field,
        )
        node_id = item["node_id"]
        if not isinstance(node_id, str) or not node_id.strip() or len(node_id) > 500:
            raise CoverageManifestError(
                f"{field}.node_id must be non-empty and at most 500 chars."
            )
        if node_id in seen_node_ids:
            raise CoverageManifestError(f"Duplicate test node ID: {node_id!r}.")
        seen_node_ids.add(node_id)
        outcome_value = item["outcome"]
        try:
            outcome = ExecutionOutcome(outcome_value)
        except (ValueError, TypeError) as exc:
            raise CoverageManifestError(
                f"{field}.outcome is not a supported execution outcome."
            ) from exc
        assertion_verified = item["behavioral_assertion_verified"]
        if type(assertion_verified) is not bool:
            raise CoverageManifestError(
                f"{field}.behavioral_assertion_verified must be a boolean."
            )
        lines = _path_locations(item["lines"], f"{field}.lines", branches=False)
        branches = _path_locations(item["branches"], f"{field}.branches", branches=True)
        if sum(len(values) for _, values in lines + branches) > MAX_LOCATIONS_PER_TEST:
            raise CoverageManifestError(f"{field} exceeds {MAX_LOCATIONS_PER_TEST} locations.")
        cases.append(
            CoverageCase(
                node_id=node_id,
                outcome=outcome,
                lines_by_file=tuple(
                    (path, tuple(int(value) for value in values)) for path, values in lines
                ),
                branches_by_file=tuple(
                    (path, tuple(str(value) for value in values)) for path, values in branches
                ),
                behavioral_assertion_verified=assertion_verified,
            )
        )
    return CoverageManifest(1, head_sha, tuple(cases))


def reconcile_test_coverage(
    *,
    junit_report: JUnitReport,
    manifest: CoverageManifest,
    expected_head_sha: str,
    node_id: str,
    target_lines: dict[str, set[int]],
    target_branches: dict[str, set[str]],
) -> ReconciledTestEvidence:
    """Reconcile one JUnit result with per-test coverage for the exact expected commit."""
    if not _SHA_RE.fullmatch(expected_head_sha):
        raise CoverageManifestError(
            "expected_head_sha must be a lowercase 40-character Git SHA."
        )
    if manifest.head_sha != expected_head_sha:
        raise CoverageManifestError("Coverage manifest head SHA does not match expected commit.")
    junit_case = next((case for case in junit_report.cases if case.node_id == node_id), None)
    if junit_case is None:
        raise CoverageManifestError(f"JUnit report has no exact test node {node_id!r}.")
    coverage_case = manifest.case_for(node_id)
    if coverage_case is None:
        raise CoverageManifestError(f"Coverage manifest has no exact test node {node_id!r}.")
    if junit_case.outcome != coverage_case.outcome:
        return ReconciledTestEvidence(
            node_id=node_id,
            outcome=junit_case.outcome,
            target_lines_exercised=False,
            target_branches_exercised=False,
            behavioral_assertion_verified=False,
            sufficiency=EvidenceSufficiency.CONTRADICTORY,
        )

    for path, lines in target_lines.items():
        _safe_path(path, "target line path")
        if any(type(line) is not int or line < 1 for line in lines):
            raise CoverageManifestError("target line numbers must be positive integers.")
    for path, branches in target_branches.items():
        _safe_path(path, "target branch path")
        if any(
            not isinstance(branch, str) or not _BRANCH_RE.fullmatch(branch)
            for branch in branches
        ):
            raise CoverageManifestError("target branch IDs must use 'line:branch-index' notation.")

    required_lines = {path: set(lines) for path, lines in target_lines.items()}
    required_branches = {path: set(branches) for path, branches in target_branches.items()}
    all_required_lines = {line for values in required_lines.values() for line in values}
    lines_exercised = bool(all_required_lines) and all(
        required <= coverage_case.lines_for(path)
        for path, required in required_lines.items()
        if required
    )
    all_required_branches = {
        branch for values in required_branches.values() for branch in values
    }
    branches_exercised = not all_required_branches or all(
        required <= coverage_case.branches_for(path)
        for path, required in required_branches.items()
        if required
    )
    if junit_case.outcome is not ExecutionOutcome.PASSED:
        sufficiency = EvidenceSufficiency.UNVERIFIED
    else:
        sufficiency = assess_evidence_sufficiency(
            total_tests=junit_report.total_tests,
            target_lines_exercised=lines_exercised,
            target_branches_exercised=branches_exercised,
            behavioral_assertion_verified=coverage_case.behavioral_assertion_verified,
        )
    return ReconciledTestEvidence(
        node_id=node_id,
        outcome=junit_case.outcome,
        target_lines_exercised=lines_exercised,
        target_branches_exercised=branches_exercised,
        behavioral_assertion_verified=coverage_case.behavioral_assertion_verified,
        sufficiency=sufficiency,
    )
