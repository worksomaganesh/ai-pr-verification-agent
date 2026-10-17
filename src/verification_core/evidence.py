"""Bounded, fail-closed JUnit ingestion and deterministic evidence sufficiency."""

from __future__ import annotations

from dataclasses import dataclass

from defusedxml import ElementTree  # type: ignore[import-untyped]

from verification_core.domain.enums import EvidenceSufficiency, ExecutionOutcome
from verification_core.security import scrub_secrets

MAX_JUNIT_BYTES = 5 * 1024 * 1024
MAX_TEST_CASES = 50_000
MAX_FIELD_LENGTH = 2_000


class EvidenceParseError(ValueError):
    """Raised when an evidence artifact is malformed or inconsistent."""


@dataclass(frozen=True, slots=True)
class JUnitCase:
    """Normalized test-case result; detail is scrubbed before it leaves the parser."""

    node_id: str
    outcome: ExecutionOutcome
    duration_seconds: float | None
    detail: str | None


@dataclass(frozen=True, slots=True)
class JUnitReport:
    """Immutable JUnit report with aggregate counts reconciled against parsed cases."""

    total_tests: int
    passed: int
    failed: int
    errors: int
    skipped: int
    cases: tuple[JUnitCase, ...]


def _bounded_text(value: str | None, field: str) -> str:
    normalized = (value or "").strip()
    if len(normalized) > MAX_FIELD_LENGTH:
        raise EvidenceParseError(f"{field} exceeds the {MAX_FIELD_LENGTH}-character limit.")
    return normalized


def _root_count(root: object, attribute: str, expected: int) -> None:
    raw = root.get(attribute)  # type: ignore[attr-defined]
    if raw is None:
        return
    try:
        count = int(raw)
    except ValueError as exc:
        raise EvidenceParseError(f"JUnit root {attribute} attribute must be an integer.") from exc
    if count < 0 or count != expected:
        raise EvidenceParseError(
            f"JUnit declared {attribute} count ({count}) does not match parsed cases ({expected})."
        )


def parse_junit(xml_text: str | bytes) -> JUnitReport:
    """Parse bounded JUnit XML; authenticity must be verified out-of-band."""
    if isinstance(xml_text, str):
        try:
            raw = xml_text.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise EvidenceParseError("JUnit input is not valid UTF-8.") from exc
    elif isinstance(xml_text, bytes):
        raw = xml_text
    else:
        raise EvidenceParseError("JUnit input must be text or bytes.")
    if not raw:
        raise EvidenceParseError("JUnit report must not be empty.")
    if len(raw) > MAX_JUNIT_BYTES:
        raise EvidenceParseError(f"JUnit report exceeds {MAX_JUNIT_BYTES} bytes.")
    if b"\x00" in raw:
        raise EvidenceParseError("JUnit report contains NUL bytes.")
    try:
        root = ElementTree.fromstring(raw)
    except Exception as exc:
        raise EvidenceParseError("JUnit XML is malformed or contains forbidden XML features.") from exc
    if root.tag not in {"testsuite", "testsuites"}:
        raise EvidenceParseError("JUnit root element must be testsuite or testsuites.")

    raw_cases = list(root.iter("testcase"))
    if len(raw_cases) > MAX_TEST_CASES:
        raise EvidenceParseError(f"JUnit report exceeds {MAX_TEST_CASES} test cases.")
    if not raw_cases:
        raise EvidenceParseError("JUnit report contains no testcase entries.")

    cases: list[JUnitCase] = []
    failed = errors = skipped = 0
    for index, case in enumerate(raw_cases):
        name = _bounded_text(case.get("name"), f"testcase[{index}].name")
        classname = _bounded_text(case.get("classname"), f"testcase[{index}].classname")
        if not name:
            raise EvidenceParseError(f"testcase[{index}] is missing a name.")
        node_id = f"{classname}::{name}" if classname else name
        duration: float | None = None
        raw_duration = case.get("time")
        if raw_duration is not None:
            try:
                duration = float(raw_duration)
            except ValueError as exc:
                raise EvidenceParseError(f"testcase[{index}].time must be numeric.") from exc
            if duration < 0 or duration != duration or duration in (float("inf"), float("-inf")):
                raise EvidenceParseError(f"testcase[{index}].time must be finite and non-negative.")

        outcome_nodes = [
            child for child in case if child.tag in {"failure", "error", "skipped", "skip"}
        ]
        if len(outcome_nodes) > 1:
            raise EvidenceParseError(f"testcase[{index}] has conflicting outcome elements.")
        outcome_node = outcome_nodes[0] if outcome_nodes else None
        if outcome_node is None:
            outcome = ExecutionOutcome.PASSED
            detail_raw = ""
        elif outcome_node.tag == "failure":
            outcome = ExecutionOutcome.FAILED
            failed += 1
            detail_raw = outcome_node.get("message") or outcome_node.text or "Test failed."
        elif outcome_node.tag == "error":
            outcome = ExecutionOutcome.ERROR
            errors += 1
            detail_raw = outcome_node.get("message") or outcome_node.text or "Test errored."
        else:
            outcome = ExecutionOutcome.SKIPPED
            skipped += 1
            detail_raw = outcome_node.get("message") or outcome_node.text or "Test skipped."
        detail = scrub_secrets(_bounded_text(detail_raw, f"testcase[{index}].detail")) or None
        cases.append(JUnitCase(node_id, outcome, duration, detail))

    total = len(cases)
    _root_count(root, "tests", total)
    _root_count(root, "failures", failed)
    _root_count(root, "errors", errors)
    _root_count(root, "skipped", skipped)
    return JUnitReport(total, total - failed - errors - skipped, failed, errors, skipped, tuple(cases))


def assess_evidence_sufficiency(
    *,
    total_tests: int,
    target_lines_exercised: bool,
    target_branches_exercised: bool,
    behavioral_assertion_verified: bool,
    report_well_formed: bool = True,
    outcomes_consistent: bool = True,
) -> EvidenceSufficiency:
    """Apply negative filters; coverage alone is never treated as behavioral proof."""
    if not report_well_formed or total_tests <= 0:
        return EvidenceSufficiency.MALFORMED
    if not outcomes_consistent:
        return EvidenceSufficiency.CONTRADICTORY
    if not target_lines_exercised or not target_branches_exercised:
        return EvidenceSufficiency.COVERAGE_MISS
    if not behavioral_assertion_verified:
        return EvidenceSufficiency.WEAK_EVIDENCE
    return EvidenceSufficiency.SUFFICIENT
