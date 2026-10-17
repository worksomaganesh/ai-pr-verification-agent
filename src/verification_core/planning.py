"""Bounded pull-request diff analysis and fail-closed verification planning.

This module is Phase II's pure planning foundation. It performs no network I/O,
executes no repository code, and never treats a model response as execution evidence.
The caller must bind inputs to the requested base/head SHAs and load policy from the
trusted base commit before calling these functions.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Protocol

from verification_core.domain.enums import (
    AnalysisCompleteness,
    ObligationSource,
    Severity,
)
from verification_core.domain.models import CommitIdentity, VerificationObligation
from verification_core.policy import VerificationPolicy, validate_test_selector
from verification_core.security import scrub_secrets

_CATEGORY_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")
_SOURCE_SUFFIXES = frozenset(
    {".c", ".cc", ".cpp", ".cs", ".go", ".java", ".js", ".jsx", ".mjs",
     ".php", ".py", ".rb", ".rs", ".sql", ".swift", ".ts", ".tsx", ".vue"}
)
_DOCUMENT_SUFFIXES = frozenset({".md", ".mdx", ".rst", ".txt", ".adoc"})
_LOCKFILE_NAMES = frozenset(
    {"package-lock.json", "pnpm-lock.yaml", "yarn.lock", "poetry.lock", "uv.lock",
     "pipfile.lock", "cargo.lock", "gemfile.lock", "composer.lock"}
)
_DEFAULT_HARNESS_PATHS = (
    ".verification-policy.yml",
    ".github/workflows/",
    "conftest.py",
    "pytest.ini",
    "pyproject.toml",
    "package.json",
)


class DiffAnalysisError(ValueError):
    """Raised when the changed-file input is structurally unsafe or unbounded."""


class PlannerOutputError(ValueError):
    """Raised when an untrusted model response violates the planner output contract."""


@dataclass(frozen=True, slots=True)
class DiffLimits:
    """Hard bounds for GitHub changed-file records and patch context."""

    max_input_files: int = 1_000
    max_files: int = 50
    max_changed_lines_per_file: int = 1_500
    max_patch_chars_per_file: int = 30_000
    max_total_patch_chars: int = 150_000

    def __post_init__(self) -> None:
        values = (
            self.max_input_files,
            self.max_files,
            self.max_changed_lines_per_file,
            self.max_patch_chars_per_file,
            self.max_total_patch_chars,
        )
        if any(type(value) is not int or value < 1 for value in values):
            raise ValueError("All diff limits must be positive integers.")
        if self.max_files > self.max_input_files:
            raise ValueError("max_files cannot exceed max_input_files.")
        if self.max_patch_chars_per_file > self.max_total_patch_chars:
            raise ValueError("Per-file patch limit cannot exceed the total patch limit.")


@dataclass(frozen=True, slots=True)
class ChangedFileInput:
    """A normalized record returned by a paginated pull-request-files API adapter."""

    filename: str
    status: str
    additions: int
    deletions: int
    patch: str | None
    is_binary: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.filename, str) or not self.filename.strip():
            raise DiffAnalysisError("filename must be a non-empty string.")
        if self.status not in {"added", "modified", "removed", "renamed", "copied", "changed"}:
            raise DiffAnalysisError(f"Unsupported changed-file status: {self.status!r}.")
        if type(self.additions) is not int or self.additions < 0:
            raise DiffAnalysisError("additions must be a non-negative integer.")
        if type(self.deletions) is not int or self.deletions < 0:
            raise DiffAnalysisError("deletions must be a non-negative integer.")
        if self.patch is not None and not isinstance(self.patch, str):
            raise DiffAnalysisError("patch must be text or None.")
        if type(self.is_binary) is not bool:
            raise DiffAnalysisError("is_binary must be a boolean.")


@dataclass(frozen=True, slots=True)
class AnalyzedFile:
    """Bounded analysis result for one changed path.

    patch_excerpt is secret-scrubbed and held for in-memory planning only; callers
    must not persist it. An empty line-range tuple does not mean the file is safe.
    """

    filename: str
    status: str
    additions: int
    deletions: int
    changed_line_ranges: tuple[tuple[int, int], ...]
    patch_excerpt: str | None
    is_binary: bool
    harness_sensitive: bool
    deeply_analyzed: bool
    issue: str | None = None


@dataclass(frozen=True, slots=True)
class DiffAnalysis:
    """Analysis tied to one exact base/head/policy identity."""

    commit: CommitIdentity
    files: tuple[AnalyzedFile, ...]
    completeness: AnalysisCompleteness
    issues: tuple[str, ...]
    input_file_count: int
    analyzed_file_count: int
    patch_chars_retained: int

    @property
    def analyzed_paths(self) -> frozenset[str]:
        """Return paths present in this bounded result, including explicitly partial ones."""
        return frozenset(item.filename for item in self.files)


@dataclass(frozen=True, slots=True)
class TestInventoryItem:
    """A repository test selector confirmed to exist in the bounded test inventory."""

    selector: str
    path: str

    def __post_init__(self) -> None:
        normalized = validate_test_selector(self.selector)
        if normalized != self.selector:
            raise DiffAnalysisError("test selector must already be normalized.")
        selector_path = self.selector.split("::", 1)[0]
        if self.path != selector_path:
            raise DiffAnalysisError("test inventory path must equal the selector's file path.")


@dataclass(frozen=True, slots=True)
class RiskHypothesis:
    """A model-proposed behavioral claim; never contains status or executable commands."""

    category: str
    severity: Severity
    claim: str
    affected_files: tuple[str, ...]
    candidate_test_selector: str | None


@dataclass(frozen=True, slots=True)
class PlannerContext:
    """Bounded in-memory context offered to an optional model adapter."""

    analysis: DiffAnalysis
    test_inventory: tuple[TestInventoryItem, ...]


class VerificationModelPort(Protocol):
    """Provider-agnostic boundary for optional model-assisted risk hypothesis generation."""

    def propose_hypotheses(self, context: PlannerContext) -> object:
        """Return a structured candidate payload; its contents are always treated as untrusted."""
        ...


@dataclass(frozen=True, slots=True)
class PlanningResult:
    """Deterministic obligations plus optional validated model hypotheses."""

    commit: CommitIdentity
    analysis_completeness: AnalysisCompleteness
    obligations: tuple[VerificationObligation, ...]
    planner_mode: str
    degradation_reason: str | None
    issues: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _RiskRule:
    category: str
    severity: Severity
    claim: str


_RISK_RULES: tuple[_RiskRule, ...] = (
    _RiskRule(
        "governance_config_tamper",
        Severity.CRITICAL,
        "Verification policy, workflow, or test-harness configuration changed and requires trusted-policy review.",
    ),
    _RiskRule(
        "database_migration",
        Severity.CRITICAL,
        "Database schema or migration behavior must be checked for forward and rollback safety.",
    ),
    _RiskRule(
        "webhook_idempotency",
        Severity.CRITICAL,
        "Repeated delivery of the same external event must not apply the business operation twice.",
    ),
    _RiskRule(
        "tenant_authorization",
        Severity.CRITICAL,
        "A caller must not access another user's or tenant's protected resource.",
    ),
    _RiskRule(
        "billing_regression",
        Severity.HIGH,
        "Billing, checkout, payment, or subscription behavior must preserve its business contract.",
    ),
    _RiskRule(
        "dependency_integrity",
        Severity.HIGH,
        "Dependency changes must be reviewed and verified for unintended supply-chain or runtime impact.",
    ),
)
_CATEGORY_TEST_TERMS: dict[str, tuple[str, ...]] = {
    "governance_config_tamper": ("policy", "workflow", "harness", "config"),
    "database_migration": ("migration", "schema", "database", "db"),
    "webhook_idempotency": ("webhook", "event", "idempotency", "duplicate"),
    "tenant_authorization": ("auth", "permission", "tenant", "access", "forbidden"),
    "billing_regression": ("billing", "payment", "checkout", "subscription", "invoice"),
    "dependency_integrity": ("dependency", "dependencies", "package", "lockfile"),
    "runtime_regression": ("integration", "regression", "behavior"),
}


def _safe_repo_path(path: str) -> None:
    """Reject non-canonical paths before any matching or context collection."""
    candidate = PurePosixPath(path)
    if (
        not path
        or len(path) > 1_000
        or candidate.is_absolute()
        or "\\" in path
        or "\x00" in path
        or ":" in path
        or any(part in {"", ".", ".."} for part in path.split("/"))
        or path.startswith("-")
    ):
        raise DiffAnalysisError(f"Unsafe repository-relative path: {path!r}.")


def _is_harness_sensitive(path: str, policy_paths: Sequence[str]) -> bool:
    """Match exact protected files and explicit directory-prefix rules."""
    base = PurePosixPath(path).name
    for item in policy_paths:
        if item.endswith("/"):
            if path.startswith(item):
                return True
        elif path == item or base == item:
            return True
    return False


def _path_priority(path: str, policy_paths: Sequence[str]) -> int:
    """Prioritize high-risk paths when the diff must be truncated."""
    lower = path.lower()
    if _is_harness_sensitive(path, policy_paths):
        return 0
    if any(token in lower for token in ("migration", "webhook", "auth", "permission")):
        return 1
    if any(token in lower for token in ("billing", "payment", "checkout", "subscription")):
        return 2
    if PurePosixPath(path).suffix.lower() in _SOURCE_SUFFIXES:
        return 3
    return 4


def _line_ranges(patch: str) -> tuple[tuple[tuple[int, int], ...], bool]:
    """Return contiguous new-file line ranges touched by additions and whether a hunk parsed."""
    added_lines: list[int] = []
    new_line = 0
    saw_hunk = False
    for line in patch.splitlines():
        if line.startswith("@@"):
            match = _HUNK_RE.match(line)
            if match is None:
                new_line = 0
                continue
            new_line = int(match.group(1))
            saw_hunk = True
        elif new_line > 0 and line.startswith("+++"):
            continue
        elif new_line > 0 and line.startswith("+"):
            added_lines.append(new_line)
            new_line += 1
        elif new_line > 0 and line.startswith("---"):
            continue
        elif new_line > 0 and line.startswith("-"):
            continue
        elif new_line > 0 and line.startswith("\\"):
            continue
        elif new_line > 0 and line.startswith(" "):
            new_line += 1

    if not added_lines:
        return (), saw_hunk
    ordered = sorted(set(added_lines))
    ranges: list[tuple[int, int]] = []
    first = last = ordered[0]
    for line_number in ordered[1:]:
        if line_number == last + 1:
            last = line_number
        else:
            ranges.append((first, last))
            first = last = line_number
    ranges.append((first, last))
    return tuple(ranges), saw_hunk


def analyze_changed_files(
    *,
    commit: CommitIdentity,
    changed_files: Sequence[ChangedFileInput],
    policy: VerificationPolicy | None = None,
    limits: DiffLimits = DiffLimits(),
) -> DiffAnalysis:
    """Analyze a bounded changed-file list without trusting patch contents.

    The caller must pass every page returned by the source API. If any part is
    omitted or exceeds a limit, completeness is downgraded so the conclusion engine
    cannot mistake partial analysis for proof that no risky behavior changed.
    """
    records = tuple(changed_files)
    if len(records) > limits.max_input_files:
        raise DiffAnalysisError(
            f"Input has {len(records)} files; limit is {limits.max_input_files}."
        )

    seen: set[str] = set()
    for item in records:
        _safe_repo_path(item.filename)
        if item.filename in seen:
            raise DiffAnalysisError(f"Duplicate changed-file path: {item.filename!r}.")
        seen.add(item.filename)

    policy_paths = policy.harness_sensitive_paths if policy is not None else _DEFAULT_HARNESS_PATHS
    prioritized = sorted(
        records,
        key=lambda item: (_path_priority(item.filename, policy_paths), item.filename),
    )
    issues: list[str] = []
    analyzed: list[AnalyzedFile] = []
    retained_chars = 0
    saw_truncation = False
    saw_incomplete = False

    if len(prioritized) > limits.max_files:
        omitted = len(prioritized) - limits.max_files
        issues.append(f"File limit exceeded; {omitted} lower-priority file(s) were not deeply analyzed.")
        saw_truncation = True

    for item in prioritized[: limits.max_files]:
        sensitive = _is_harness_sensitive(item.filename, policy_paths)
        changed_lines = item.additions + item.deletions
        issue: str | None = None
        ranges: tuple[tuple[int, int], ...] = ()
        excerpt: str | None = None
        deep = True

        if item.is_binary:
            analyzed.append(
                AnalyzedFile(
                    filename=item.filename,
                    status=item.status,
                    additions=item.additions,
                    deletions=item.deletions,
                    changed_line_ranges=(),
                    patch_excerpt=None,
                    is_binary=True,
                    harness_sensitive=sensitive,
                    deeply_analyzed=True,
                )
            )
            continue

        if changed_lines > limits.max_changed_lines_per_file:
            issue = "Per-file changed-line limit exceeded; patch was not deeply analyzed."
            deep = False
            saw_truncation = True
        elif item.patch is None:
            issue = "Patch is unavailable; behavioral analysis is incomplete."
            deep = False
            saw_incomplete = True
        elif len(item.patch) > limits.max_patch_chars_per_file:
            issue = "Per-file patch character limit exceeded; patch was not deeply analyzed."
            deep = False
            saw_truncation = True
        elif retained_chars + len(item.patch) > limits.max_total_patch_chars:
            issue = "Total patch character limit exceeded; patch was not deeply analyzed."
            deep = False
            saw_truncation = True
        else:
            ranges, has_hunk = _line_ranges(item.patch)
            if changed_lines > 0 and not has_hunk:
                issue = "Patch contained no parseable unified-diff hunk."
                deep = False
                saw_incomplete = True
            else:
                excerpt = scrub_secrets(item.patch)
                retained_chars += len(item.patch)

        if issue:
            issues.append(f"{item.filename}: {issue}")
        analyzed.append(
            AnalyzedFile(
                filename=item.filename,
                status=item.status,
                additions=item.additions,
                deletions=item.deletions,
                changed_line_ranges=ranges,
                patch_excerpt=excerpt,
                is_binary=False,
                harness_sensitive=sensitive,
                deeply_analyzed=deep,
                issue=issue,
            )
        )

    completeness = AnalysisCompleteness.COMPLETE
    if saw_truncation:
        completeness = AnalysisCompleteness.TRUNCATED
    elif saw_incomplete:
        completeness = AnalysisCompleteness.INCOMPLETE

    return DiffAnalysis(
        commit=commit,
        files=tuple(analyzed),
        completeness=completeness,
        issues=tuple(issues),
        input_file_count=len(records),
        analyzed_file_count=len(analyzed),
        patch_chars_retained=retained_chars,
    )


def _risk_rules_for_path(path: str, harness_sensitive: bool) -> tuple[_RiskRule, ...]:
    """Apply conservative path rules; multiple independent risk classes may match."""
    lower = path.lower()
    parts = {part.lower() for part in PurePosixPath(path).parts}
    name = PurePosixPath(path).name.lower()
    rules: list[_RiskRule] = []

    if harness_sensitive:
        rules.append(_RISK_RULES[0])
    if (
        any(part in {"migration", "migrations", "schema", "db_migrate"} for part in parts)
        or name.endswith(".sql")
    ):
        rules.append(_RISK_RULES[1])
    if "webhook" in lower or "webhooks" in parts or "events" in parts and "webhook" in lower:
        rules.append(_RISK_RULES[2])
    if any(
        part in {"auth", "authz", "authorization", "permissions", "access_control"}
        for part in parts
    ) or name.startswith(("auth", "permission", "access_control")):
        rules.append(_RISK_RULES[3])
    if any(token in lower for token in ("billing", "payment", "checkout", "subscription", "invoice")):
        rules.append(_RISK_RULES[4])
    if name in _LOCKFILE_NAMES or name.startswith(("requirements", "constraints")) and name.endswith(".txt"):
        rules.append(_RISK_RULES[5])

    if not rules and PurePosixPath(path).suffix.lower() in _SOURCE_SUFFIXES:
        rules.append(
            _RiskRule(
                "runtime_regression",
                Severity.MEDIUM,
                "Changed executable code must preserve its observable behavior and error handling.",
            )
        )
    return tuple(rules)


def _selector_score(
    category: str,
    affected_path: str,
    item: TestInventoryItem,
) -> int:
    """Score only known test selectors; the result never authorizes execution by itself."""
    source_stem = PurePosixPath(affected_path).stem.lower()
    test_stem = PurePosixPath(item.path).stem.lower()
    if test_stem.startswith("test_"):
        test_stem = test_stem[5:]
    if test_stem.endswith("_test"):
        test_stem = test_stem[:-5]

    score = 0
    if source_stem == test_stem:
        score += 10
    elif source_stem in test_stem or test_stem in source_stem:
        score += 6

    terms = _CATEGORY_TEST_TERMS.get(category, ())
    selector_lower = item.selector.lower()
    score += sum(2 for term in terms if term in selector_lower)
    return score


def _candidate_selector(
    category: str,
    affected_path: str,
    inventory: Sequence[TestInventoryItem],
) -> str | None:
    scored = [
        (_selector_score(category, affected_path, item), item.selector)
        for item in inventory
    ]
    positive = sorted((score, selector) for score, selector in scored if score > 0)
    return positive[0][1] if positive else None


def _obligation_id(category: str, paths: Sequence[str], claim: str) -> str:
    digest = hashlib.sha256(f"{category}\0{'|'.join(paths)}\0{claim}".encode()).hexdigest()[:10]
    return f"OBL-{category.upper()}-{digest.upper()}"


def _validate_inventory(inventory: Sequence[TestInventoryItem]) -> tuple[TestInventoryItem, ...]:
    items = tuple(inventory)
    selectors = [item.selector for item in items]
    if len(set(selectors)) != len(selectors):
        raise DiffAnalysisError("Test inventory contains duplicate selectors.")
    return tuple(sorted(items, key=lambda item: item.selector))


def deterministic_obligations(
    analysis: DiffAnalysis,
    *,
    test_inventory: Sequence[TestInventoryItem] = (),
) -> tuple[VerificationObligation, ...]:
    """Generate stable path-risk obligations; no obligation starts as verified."""
    inventory = _validate_inventory(test_inventory)
    obligations: list[VerificationObligation] = []
    seen: set[tuple[str, str]] = set()

    for item in analysis.files:
        for rule in _risk_rules_for_path(item.filename, item.harness_sensitive):
            key = (rule.category, item.filename)
            if key in seen:
                continue
            seen.add(key)
            selector = _candidate_selector(rule.category, item.filename, inventory)
            obligations.append(
                VerificationObligation.propose(
                    obligation_id=_obligation_id(rule.category, (item.filename,), rule.claim),
                    category=rule.category,
                    description=rule.claim,
                    severity=rule.severity,
                    source=ObligationSource.DETERMINISTIC_POLICY,
                    affected_files=(item.filename,),
                    candidate_test_id=selector,
                )
            )

    return tuple(sorted(obligations, key=lambda item: (item.category, item.affected_files, item.obligation_id)))


def validate_model_hypotheses(
    payload: object,
    *,
    analysis: DiffAnalysis,
    test_inventory: Sequence[TestInventoryItem],
    max_hypotheses: int = 100,
) -> tuple[RiskHypothesis, ...]:
    """Strictly validate model output and constrain paths/selectors to known PR context."""
    if type(max_hypotheses) is not int or max_hypotheses < 1:
        raise ValueError("max_hypotheses must be a positive integer.")
    if not isinstance(payload, dict) or set(payload) != {"hypotheses"}:
        raise PlannerOutputError("Model response must be an object with exactly one 'hypotheses' key.")
    raw_hypotheses = payload["hypotheses"]
    if not isinstance(raw_hypotheses, list):
        raise PlannerOutputError("'hypotheses' must be a list.")
    if len(raw_hypotheses) > max_hypotheses:
        raise PlannerOutputError(f"Model returned more than {max_hypotheses} hypotheses.")

    allowed_paths = analysis.analyzed_paths
    inventory = _validate_inventory(test_inventory)
    allowed_selectors = {item.selector for item in inventory}
    result: list[RiskHypothesis] = []
    seen: set[tuple[str, tuple[str, ...], str]] = set()
    expected_keys = {
        "category",
        "severity",
        "claim",
        "affected_files",
        "candidate_test_selector",
    }

    for index, raw in enumerate(raw_hypotheses):
        if not isinstance(raw, dict) or set(raw) != expected_keys:
            raise PlannerOutputError(f"hypotheses[{index}] has missing or unknown fields.")
        category = raw["category"]
        if not isinstance(category, str) or not _CATEGORY_RE.fullmatch(category):
            raise PlannerOutputError(f"hypotheses[{index}].category is invalid.")
        severity_value = raw["severity"]
        if not isinstance(severity_value, str):
            raise PlannerOutputError(f"hypotheses[{index}].severity must be a string.")
        try:
            severity = Severity(severity_value)
        except ValueError as exc:
            raise PlannerOutputError(f"hypotheses[{index}].severity is invalid.") from exc
        claim = raw["claim"]
        if not isinstance(claim, str) or not claim.strip() or len(claim.strip()) > 1_000:
            raise PlannerOutputError(f"hypotheses[{index}].claim must be 1-1000 characters.")
        claim = claim.strip()

        affected = raw["affected_files"]
        if not isinstance(affected, list) or not affected or any(
            not isinstance(path, str) for path in affected
        ):
            raise PlannerOutputError(f"hypotheses[{index}].affected_files must be a non-empty string list.")
        affected_files = tuple(sorted(set(affected)))
        if len(affected_files) != len(affected) or any(
            path not in allowed_paths for path in affected_files
        ):
            raise PlannerOutputError(
                f"hypotheses[{index}].affected_files contains duplicates or paths outside the bounded diff."
            )

        selector = raw["candidate_test_selector"]
        if selector is not None:
            if not isinstance(selector, str) or selector not in allowed_selectors:
                raise PlannerOutputError(
                    f"hypotheses[{index}].candidate_test_selector must match the existing test inventory."
                )
            try:
                validate_test_selector(selector)
            except ValueError as exc:
                raise PlannerOutputError(
                    f"hypotheses[{index}].candidate_test_selector is invalid."
                ) from exc

        identity = (category, affected_files, claim)
        if identity in seen:
            continue
        seen.add(identity)
        result.append(
            RiskHypothesis(
                category=category,
                severity=severity,
                claim=claim,
                affected_files=affected_files,
                candidate_test_selector=selector,
            )
        )
    return tuple(result)


def _hypothesis_obligation(hypothesis: RiskHypothesis) -> VerificationObligation:
    return VerificationObligation.propose(
        obligation_id=_obligation_id(hypothesis.category, hypothesis.affected_files, hypothesis.claim),
        category=hypothesis.category,
        description=hypothesis.claim,
        severity=hypothesis.severity,
        source=ObligationSource.LLM_HYPOTHESIS,
        affected_files=hypothesis.affected_files,
        candidate_test_id=hypothesis.candidate_test_selector,
    )


def plan_verification(
    analysis: DiffAnalysis,
    *,
    test_inventory: Sequence[TestInventoryItem] = (),
    model: VerificationModelPort | None = None,
    max_hypotheses: int = 100,
) -> PlanningResult:
    """Run deterministic rules first, then optionally add validated model hypotheses.

    Any model exception or schema violation degrades to Stage A only. Existing
    deterministic obligations are never replaced or weakened by model output.
    """
    inventory = _validate_inventory(test_inventory)
    deterministic = deterministic_obligations(analysis, test_inventory=inventory)
    if model is None:
        return PlanningResult(
            commit=analysis.commit,
            analysis_completeness=analysis.completeness,
            obligations=deterministic,
            planner_mode="deterministic",
            degradation_reason=None,
            issues=analysis.issues,
        )

    context = PlannerContext(analysis=analysis, test_inventory=inventory)
    try:
        payload = model.propose_hypotheses(context)
        hypotheses = validate_model_hypotheses(
            payload,
            analysis=analysis,
            test_inventory=inventory,
            max_hypotheses=max_hypotheses,
        )
        existing = {
            (obligation.category, obligation.affected_files, obligation.description)
            for obligation in deterministic
        }
        extras = [
            _hypothesis_obligation(item)
            for item in hypotheses
            if (item.category, item.affected_files, item.claim) not in existing
        ]
    except Exception as exc:
        reason = f"Model planning unavailable or rejected: {type(exc).__name__}."
        return PlanningResult(
            commit=analysis.commit,
            analysis_completeness=analysis.completeness,
            obligations=deterministic,
            planner_mode="deterministic_fallback",
            degradation_reason=reason,
            issues=analysis.issues + (reason,),
        )

    combined = tuple(
        sorted(
            (*deterministic, *extras),
            key=lambda item: (item.category, item.affected_files, item.obligation_id),
        )
    )
    return PlanningResult(
        commit=analysis.commit,
        analysis_completeness=analysis.completeness,
        obligations=combined,
        planner_mode="hybrid",
        degradation_reason=None,
        issues=analysis.issues,
    )
