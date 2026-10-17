#!/usr/bin/env python3
"""Self-contained extractor and ZIP builder for AI PR Verification Agent (Phase 1A).

Usage:
    python extract_phase_1a.py [--target-dir .] [--zip-name ai-pr-verification-agent-phase-1a.zip]
"""

from __future__ import annotations

import argparse
import hashlib
import zipfile
from pathlib import Path

PHASE_1A_FILES: dict[str, str] = {
    "pyproject.toml": """\
[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.build_meta"

[project]
name = "ai-pr-verification-agent"
version = "0.1.0"
description = "Evidence-backed pull request verification control plane and deterministic core."
readme = "docs/verification-semantics.md"
requires-python = ">=3.12"
license = { text = "MIT" }
authors = [{ name = "Doddi Yashwanth Soma Ganesh" }]
dependencies = []

[project.optional-dependencies]
dev = [
    "hypothesis>=6.100.0",
    "mypy>=1.10.0",
    "pytest>=8.2.0",
    "pytest-cov>=5.0.0",
    "ruff>=0.5.0",
]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra -q --strict-markers --strict-config"

[tool.coverage.run]
branch = true
source = ["src/verification_core"]

[tool.coverage.report]
fail_under = 95
show_missing = true

[tool.ruff]
target-version = "py312"
line-length = 100
src = ["src", "tests"]

[tool.ruff.lint]
select = [
    "E",   # pycodestyle errors
    "W",   # pycodestyle warnings
    "F",   # pyflakes
    "I",   # isort
    "B",   # flake8-bugbear
    "C4",  # flake8-comprehensions
    "UP",  # pyupgrade
    "S",   # flake8-bandit security checks
    "SIM", # flake8-simplify
    "RUF", # Ruff-specific rules
]

[tool.ruff.lint.per-file-ignores]
"tests/**/*.py" = ["S101"] # Allow assert statements in pytest suite

[tool.mypy]
python_version = "3.12"
mypy_path = ["src"]
strict = true
warn_unreachable = true
disallow_any_unimported = true
disallow_any_expr = false
files = ["src", "tests"]
""",
    "src/verification_core/__init__.py": """\
\"\"\"AI PR Verification Agent — deterministic verification core package.\"\"\"

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"
""",
    "src/verification_core/domain/__init__.py": """\
\"\"\"Pure deterministic domain models, enums, and state machine for PR verification.\"\"\"

from __future__ import annotations

from verification_core.domain.enums import (
    AnalysisCompleteness,
    EvidenceSufficiency,
    ExecutionOutcome,
    GitHubCheckConclusion,
    InternalRunOutcome,
    ObligationSource,
    ObligationStatus,
    Severity,
)
from verification_core.domain.models import (
    CommitIdentity,
    ConclusionPolicyConfig,
    DomainValidationError,
    ExecutionEvidence,
    HumanApprovalRecord,
    InvalidStateTransitionError,
    PolicyWaiverRecord,
    VerificationObligation,
    VerificationRunEvaluation,
    WorkflowProvenance,
)
from verification_core.domain.state_machine import (
    ALLOWED_OBLIGATION_TRANSITIONS,
    apply_human_approval,
    apply_policy_waiver,
    block_obligation,
    evaluate_verification_run,
    mark_obligation_not_run,
    mark_obligation_stale,
    reconcile_obligation_evidence,
    schedule_obligation,
    validate_transition,
)

__all__ = [
    "ALLOWED_OBLIGATION_TRANSITIONS",
    "AnalysisCompleteness",
    "CommitIdentity",
    "ConclusionPolicyConfig",
    "DomainValidationError",
    "EvidenceSufficiency",
    "ExecutionEvidence",
    "ExecutionOutcome",
    "GitHubCheckConclusion",
    "HumanApprovalRecord",
    "InternalRunOutcome",
    "InvalidStateTransitionError",
    "ObligationSource",
    "ObligationStatus",
    "PolicyWaiverRecord",
    "Severity",
    "VerificationObligation",
    "VerificationRunEvaluation",
    "WorkflowProvenance",
    "apply_human_approval",
    "apply_policy_waiver",
    "block_obligation",
    "evaluate_verification_run",
    "mark_obligation_not_run",
    "mark_obligation_stale",
    "reconcile_obligation_evidence",
    "schedule_obligation",
    "validate_transition",
]
""",
    "src/verification_core/domain/enums.py": """\
\"\"\"Enumerations for obligation lifecycle, evidence sufficiency, and run conclusions.\"\"\"

from __future__ import annotations

from enum import StrEnum


class Severity(StrEnum):
    \"\"\"Risk severity of a behavioral verification obligation.\"\"\"

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

    def is_mandatory_by_default(self) -> bool:
        \"\"\"Return True if this severity blocks success unless verified or approved.\"\"\"
        return self in (Severity.CRITICAL, Severity.HIGH)


class ObligationSource(StrEnum):
    \"\"\"Origin of a proposed verification obligation.\"\"\"

    DETERMINISTIC_POLICY = "deterministic_policy"
    LLM_HYPOTHESIS = "llm_hypothesis"
    GOVERNANCE_RULE = "governance_rule"


class ObligationStatus(StrEnum):
    \"\"\"Finite states of a verification obligation.\"\"\"

    PROPOSED = "proposed"
    SCHEDULED = "scheduled"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"
    NOT_RUN = "not_run"
    INCONCLUSIVE = "inconclusive"
    STALE = "stale"
    APPROVED_BY_HUMAN = "approved_by_human"
    WAIVED_BY_POLICY = "waived_by_policy"


class ExecutionOutcome(StrEnum):
    \"\"\"Raw test runner outcome for an executed check.\"\"\"

    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    SKIPPED = "skipped"


class EvidenceSufficiency(StrEnum):
    \"\"\"Evaluated quality and completeness of execution evidence for an obligation.\"\"\"

    UNVERIFIED = "unverified"
    COVERAGE_MISS = "coverage_miss"
    WEAK_EVIDENCE = "weak_evidence"
    PARTIAL_EVIDENCE = "partial_evidence"
    SUFFICIENT = "sufficient"
    CONTRADICTORY = "contradictory"
    MALFORMED = "malformed"


class AnalysisCompleteness(StrEnum):
    \"\"\"Status of diff and repository context collection during verification planning.\"\"\"

    COMPLETE = "complete"
    TRUNCATED = "truncated"
    INCOMPLETE = "incomplete"
    ANALYZER_ERROR = "analyzer_error"


class InternalRunOutcome(StrEnum):
    \"\"\"Internal domain conclusion for a verification run (includes STALE_SUPERSEDED).\"\"\"

    VERIFIED_SUCCESS = "verified_success"
    NEUTRAL_NO_BEHAVIORAL_CHANGE = "neutral_no_behavioral_change"
    NEUTRAL_ADVISORY_GAPS_ONLY = "neutral_advisory_gaps_only"
    ACTION_REQUIRED_MISSING_EVIDENCE = "action_required_missing_evidence"
    FAILED_VERIFICATION = "failed_verification"
    STALE_SUPERSEDED = "stale_superseded"


class GitHubCheckConclusion(StrEnum):
    \"\"\"Valid user-settable GitHub Check Run API conclusion values.

    Note: GitHub reserves 'stale' for internal platform usage; superseded runs must
    use CANCELLED when publishing to the GitHub Checks API.
    \"\"\"

    SUCCESS = "success"
    NEUTRAL = "neutral"
    ACTION_REQUIRED = "action_required"
    FAILURE = "failure"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    SKIPPED = "skipped"
""",
    "src/verification_core/domain/models.py": """\
\"\"\"Immutable, strictly validated domain models for PR verification.\"\"\"

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from verification_core.domain.enums import (
    AnalysisCompleteness,
    EvidenceSufficiency,
    ExecutionOutcome,
    GitHubCheckConclusion,
    InternalRunOutcome,
    ObligationSource,
    ObligationStatus,
    Severity,
)

_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_REPO_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class DomainValidationError(ValueError):
    \"\"\"Raised when a domain object violates structural or security invariants.\"\"\"


class InvalidStateTransitionError(DomainValidationError):
    \"\"\"Raised when an invalid or forbidden state transition is attempted.\"\"\"


def validate_git_sha(value: str, field_name: str) -> None:
    \"\"\"Ensure value is a canonical 40-character lowercase hexadecimal Git SHA.\"\"\"
    if not _GIT_SHA_RE.match(value):
        raise DomainValidationError(
            f"{field_name} must be a 40-character lowercase hex SHA, got {value!r}."
        )


def validate_sha256(value: str, field_name: str) -> None:
    \"\"\"Ensure value is a canonical 64-character lowercase hexadecimal SHA-256 digest.\"\"\"
    if not _SHA256_RE.match(value):
        raise DomainValidationError(
            f"{field_name} must be a 64-character lowercase hex SHA-256, got {value!r}."
        )


def _require_non_empty(value: str, field_name: str) -> None:
    if not value or not value.strip():
        raise DomainValidationError(f"{field_name} must be a non-empty string.")


@dataclass(frozen=True, slots=True, kw_only=True)
class CommitIdentity:
    \"\"\"Immutable binding of a verification run to a repository, PR, commits, and policy.\"\"\"

    repo_full_name: str
    pr_number: int
    base_sha: str
    head_sha: str
    policy_sha256: str

    def __post_init__(self) -> None:
        if not _REPO_NAME_RE.match(self.repo_full_name):
            raise DomainValidationError(
                f"repo_full_name must match 'owner/repo', got {self.repo_full_name!r}."
            )
        if self.pr_number < 1:
            raise DomainValidationError(f"pr_number must be >= 1, got {self.pr_number}.")
        validate_git_sha(self.base_sha, "base_sha")
        validate_git_sha(self.head_sha, "head_sha")
        if self.base_sha == self.head_sha:
            raise DomainValidationError("base_sha and head_sha must be distinct commits.")
        validate_sha256(self.policy_sha256, "policy_sha256")


@dataclass(frozen=True, slots=True, kw_only=True)
class WorkflowProvenance:
    \"\"\"Platform-verified metadata from the GitHub Actions control plane.\"\"\"

    workflow_run_id: int
    workflow_head_sha: str
    workflow_base_sha: str
    workflow_path: str
    is_trusted_workflow_from_base: bool
    harness_untampered: bool
    step_completed_cleanly: bool
    recorded_at: datetime

    def __post_init__(self) -> None:
        if self.workflow_run_id < 1:
            raise DomainValidationError(
                f"workflow_run_id must be >= 1, got {self.workflow_run_id}."
            )
        validate_git_sha(self.workflow_head_sha, "workflow_head_sha")
        validate_git_sha(self.workflow_base_sha, "workflow_base_sha")
        _require_non_empty(self.workflow_path, "workflow_path")

    def matches_commit(self, commit: CommitIdentity) -> bool:
        \"\"\"Return True iff the workflow executed against the exact PR base and head SHAs.\"\"\"
        return (
            self.workflow_head_sha == commit.head_sha
            and self.workflow_base_sha == commit.base_sha
        )

    def is_authentic_and_trusted(self, commit: CommitIdentity) -> bool:
        \"\"\"Return True iff platform metadata matches the commit and passed integrity checks.\"\"\"
        return (
            self.matches_commit(commit)
            and self.is_trusted_workflow_from_base
            and self.harness_untampered
            and self.step_completed_cleanly
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class ExecutionEvidence:
    \"\"\"Immutable record of a test execution and its evaluated behavioral sufficiency.\"\"\"

    test_node_id: str
    outcome: ExecutionOutcome
    sufficiency: EvidenceSufficiency
    provenance: WorkflowProvenance
    target_lines_exercised: bool
    target_branches_exercised: bool
    behavioral_assertion_verified: bool
    total_tests_in_report: int
    failure_summary: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.test_node_id, "test_node_id")
        if self.total_tests_in_report < 0:
            raise DomainValidationError("total_tests_in_report must be >= 0.")
        if self.sufficiency == EvidenceSufficiency.SUFFICIENT:
            if self.total_tests_in_report == 0:
                raise DomainValidationError(
                    "EvidenceSufficiency.SUFFICIENT is forbidden when total_tests_in_report == 0."
                )
            if self.outcome != ExecutionOutcome.PASSED:
                raise DomainValidationError(
                    "EvidenceSufficiency.SUFFICIENT requires ExecutionOutcome.PASSED."
                )
            if not (
                self.target_lines_exercised
                and self.target_branches_exercised
                and self.behavioral_assertion_verified
            ):
                raise DomainValidationError(
                    "EvidenceSufficiency.SUFFICIENT requires target_lines_exercised, "
                    "target_branches_exercised, and behavioral_assertion_verified to all be True."
                )


@dataclass(frozen=True, slots=True, kw_only=True)
class HumanApprovalRecord:
    \"\"\"Explicit audit record of an authorized maintainer approving an unverified obligation.\"\"\"

    reviewer_login: str
    review_id: int
    approved_head_sha: str
    rationale: str
    approved_at: datetime

    def __post_init__(self) -> None:
        _require_non_empty(self.reviewer_login, "reviewer_login")
        if self.review_id < 1:
            raise DomainValidationError(f"review_id must be >= 1, got {self.review_id}.")
        validate_git_sha(self.approved_head_sha, "approved_head_sha")
        _require_non_empty(self.rationale, "rationale")


@dataclass(frozen=True, slots=True, kw_only=True)
class PolicyWaiverRecord:
    \"\"\"Audit record for a non-mandatory obligation waived by a base-branch policy rule.\"\"\"

    policy_rule_id: str
    policy_sha256: str
    rationale: str

    def __post_init__(self) -> None:
        _require_non_empty(self.policy_rule_id, "policy_rule_id")
        validate_sha256(self.policy_sha256, "policy_sha256")
        _require_non_empty(self.rationale, "rationale")


@dataclass(frozen=True, slots=True, kw_only=True)
class VerificationObligation:
    \"\"\"A specific behavioral claim that must be verified for a pull request.\"\"\"

    obligation_id: str
    category: str
    description: str
    severity: Severity
    source: ObligationSource
    affected_files: tuple[str, ...]
    status: ObligationStatus = ObligationStatus.PROPOSED
    candidate_test_id: str | None = None
    evidence: ExecutionEvidence | None = None
    human_approval: HumanApprovalRecord | None = None
    policy_waiver: PolicyWaiverRecord | None = None
    status_reason: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.obligation_id, "obligation_id")
        _require_non_empty(self.category, "category")
        _require_non_empty(self.description, "description")
        if not self.affected_files:
            raise DomainValidationError("affected_files must contain at least one file path.")
        for path in self.affected_files:
            _require_non_empty(path, "affected_files item")

        if self.status == ObligationStatus.SCHEDULED and not self.candidate_test_id:
            raise DomainValidationError(
                "SCHEDULED obligation requires a non-empty candidate_test_id."
            )

        if self.status == ObligationStatus.PASSED:
            if self.evidence is None:
                raise DomainValidationError(
                    "ObligationStatus.PASSED requires verified ExecutionEvidence."
                )
            if self.evidence.outcome != ExecutionOutcome.PASSED:
                raise DomainValidationError(
                    "ObligationStatus.PASSED requires ExecutionOutcome.PASSED."
                )
            if self.evidence.sufficiency != EvidenceSufficiency.SUFFICIENT:
                raise DomainValidationError(
                    "ObligationStatus.PASSED requires EvidenceSufficiency.SUFFICIENT."
                )
            if not (
                self.evidence.provenance.is_trusted_workflow_from_base
                and self.evidence.provenance.harness_untampered
                and self.evidence.provenance.step_completed_cleanly
            ):
                raise DomainValidationError(
                    "ObligationStatus.PASSED requires trusted, untampered workflow provenance."
                )
            if self.human_approval is not None or self.policy_waiver is not None:
                raise DomainValidationError(
                    "Machine-verified PASSED obligation must not carry human_approval or "
                    "policy_waiver records."
                )

        if self.status == ObligationStatus.APPROVED_BY_HUMAN and self.human_approval is None:
            raise DomainValidationError(
                "ObligationStatus.APPROVED_BY_HUMAN requires a HumanApprovalRecord."
            )

        if self.status == ObligationStatus.WAIVED_BY_POLICY:
            if self.policy_waiver is None:
                raise DomainValidationError(
                    "ObligationStatus.WAIVED_BY_POLICY requires a PolicyWaiverRecord."
                )
            if self.severity in (Severity.CRITICAL, Severity.HIGH):
                raise DomainValidationError(
                    f"Severity {self.severity.value} cannot be statically waived via "
                    "WAIVED_BY_POLICY."
                )

    @classmethod
    def propose(
        cls,
        *,
        obligation_id: str,
        category: str,
        description: str,
        severity: Severity,
        source: ObligationSource,
        affected_files: tuple[str, ...],
        candidate_test_id: str | None = None,
    ) -> VerificationObligation:
        \"\"\"Safe factory for creating newly proposed obligations in status PROPOSED.\"\"\"
        return cls(
            obligation_id=obligation_id,
            category=category,
            description=description,
            severity=severity,
            source=source,
            affected_files=affected_files,
            status=ObligationStatus.PROPOSED,
            candidate_test_id=candidate_test_id,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class ConclusionPolicyConfig:
    \"\"\"Policy parameters governing how obligation states map to run conclusions.\"\"\"

    strict_blocking_mode: bool = False
    treat_medium_as_mandatory: bool = False
    allow_human_approval_for_critical: bool = True
    allow_human_approval_for_high: bool = True
    advisory_gaps_return_neutral: bool = True

    def is_severity_mandatory(self, severity: Severity) -> bool:
        \"\"\"Return True if the given severity is mandatory under this policy.\"\"\"
        if severity in (Severity.CRITICAL, Severity.HIGH):
            return True
        return severity == Severity.MEDIUM and self.treat_medium_as_mandatory


@dataclass(frozen=True, slots=True, kw_only=True)
class VerificationRunEvaluation:
    \"\"\"Deterministic evaluation result for a pull request verification run.\"\"\"

    commit: CommitIdentity
    internal_outcome: InternalRunOutcome
    github_conclusion: GitHubCheckConclusion
    is_stale: bool
    superseded_by_sha: str | None
    analysis_completeness: AnalysisCompleteness
    obligations: tuple[VerificationObligation, ...]
    machine_verified_ids: tuple[str, ...]
    human_approved_ids: tuple[str, ...]
    policy_waived_ids: tuple[str, ...]
    failed_ids: tuple[str, ...]
    blocked_ids: tuple[str, ...]
    unverified_mandatory_ids: tuple[str, ...]
    unverified_advisory_ids: tuple[str, ...]
    summary_title: str
    summary_rationale: str

    def __post_init__(self) -> None:
        _require_non_empty(self.summary_title, "summary_title")
        _require_non_empty(self.summary_rationale, "summary_rationale")
        if self.superseded_by_sha is not None:
            validate_git_sha(self.superseded_by_sha, "superseded_by_sha")
        if self.is_stale:
            if self.internal_outcome != InternalRunOutcome.STALE_SUPERSEDED:
                raise DomainValidationError(
                    "Stale runs must have internal_outcome == InternalRunOutcome.STALE_SUPERSEDED."
                )
            if self.github_conclusion != GitHubCheckConclusion.CANCELLED:
                raise DomainValidationError(
                    "Stale runs must map to GitHubCheckConclusion.CANCELLED."
                )
""",
    "src/verification_core/domain/state_machine.py": """\
\"\"\"Deterministic obligation state machine and Check Run conclusion engine.\"\"\"

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

from verification_core.domain.enums import (
    AnalysisCompleteness,
    EvidenceSufficiency,
    ExecutionOutcome,
    GitHubCheckConclusion,
    InternalRunOutcome,
    ObligationStatus,
    Severity,
)
from verification_core.domain.models import (
    CommitIdentity,
    ConclusionPolicyConfig,
    DomainValidationError,
    ExecutionEvidence,
    HumanApprovalRecord,
    InvalidStateTransitionError,
    PolicyWaiverRecord,
    VerificationObligation,
    VerificationRunEvaluation,
    validate_git_sha,
)

ALLOWED_OBLIGATION_TRANSITIONS: dict[ObligationStatus, frozenset[ObligationStatus]] = {
    ObligationStatus.PROPOSED: frozenset(
        {
            ObligationStatus.SCHEDULED,
            ObligationStatus.BLOCKED,
            ObligationStatus.NOT_RUN,
            ObligationStatus.WAIVED_BY_POLICY,
            ObligationStatus.STALE,
        }
    ),
    ObligationStatus.SCHEDULED: frozenset(
        {
            ObligationStatus.PASSED,
            ObligationStatus.FAILED,
            ObligationStatus.SKIPPED,
            ObligationStatus.BLOCKED,
            ObligationStatus.NOT_RUN,
            ObligationStatus.INCONCLUSIVE,
            ObligationStatus.STALE,
        }
    ),
    ObligationStatus.NOT_RUN: frozenset(
        {
            ObligationStatus.APPROVED_BY_HUMAN,
            ObligationStatus.WAIVED_BY_POLICY,
            ObligationStatus.STALE,
        }
    ),
    ObligationStatus.SKIPPED: frozenset(
        {
            ObligationStatus.APPROVED_BY_HUMAN,
            ObligationStatus.WAIVED_BY_POLICY,
            ObligationStatus.STALE,
        }
    ),
    ObligationStatus.INCONCLUSIVE: frozenset(
        {
            ObligationStatus.APPROVED_BY_HUMAN,
            ObligationStatus.STALE,
        }
    ),
    ObligationStatus.PASSED: frozenset({ObligationStatus.STALE}),
    ObligationStatus.FAILED: frozenset({ObligationStatus.STALE}),
    ObligationStatus.BLOCKED: frozenset({ObligationStatus.STALE}),
    ObligationStatus.APPROVED_BY_HUMAN: frozenset({ObligationStatus.STALE}),
    ObligationStatus.WAIVED_BY_POLICY: frozenset({ObligationStatus.STALE}),
    ObligationStatus.STALE: frozenset({ObligationStatus.STALE}),
}


def validate_transition(current: ObligationStatus, target: ObligationStatus) -> None:
    \"\"\"Validate that transitioning from `current` to `target` is permitted.\"\"\"
    allowed = ALLOWED_OBLIGATION_TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        raise InvalidStateTransitionError(
            f"Illegal obligation state transition from {current.value!r} to {target.value!r}."
        )


def schedule_obligation(
    obligation: VerificationObligation,
    *,
    candidate_test_id: str | None = None,
) -> VerificationObligation:
    \"\"\"Transition a PROPOSED obligation to SCHEDULED with a validated test selector.\"\"\"
    validate_transition(obligation.status, ObligationStatus.SCHEDULED)
    resolved_selector = candidate_test_id or obligation.candidate_test_id
    if not resolved_selector or not resolved_selector.strip():
        raise InvalidStateTransitionError(
            f"Cannot schedule obligation {obligation.obligation_id!r} without a candidate_test_id."
        )
    return replace(
        obligation,
        status=ObligationStatus.SCHEDULED,
        candidate_test_id=resolved_selector,
        status_reason="Scheduled for execution against approved runner profile.",
    )


def block_obligation(
    obligation: VerificationObligation,
    *,
    reason: str,
) -> VerificationObligation:
    \"\"\"Transition a PROPOSED or SCHEDULED obligation to BLOCKED due to policy violation.\"\"\"
    validate_transition(obligation.status, ObligationStatus.BLOCKED)
    if not reason or not reason.strip():
        raise DomainValidationError("Blocking an obligation requires a non-empty reason.")
    return replace(
        obligation,
        status=ObligationStatus.BLOCKED,
        status_reason=reason,
    )


def mark_obligation_not_run(
    obligation: VerificationObligation,
    *,
    reason: str,
) -> VerificationObligation:
    \"\"\"Transition a PROPOSED or SCHEDULED obligation to NOT_RUN.\"\"\"
    validate_transition(obligation.status, ObligationStatus.NOT_RUN)
    if not reason or not reason.strip():
        raise DomainValidationError("Marking an obligation NOT_RUN requires a non-empty reason.")
    return replace(
        obligation,
        status=ObligationStatus.NOT_RUN,
        status_reason=reason,
    )


def reconcile_obligation_evidence(
    obligation: VerificationObligation,
    *,
    evidence: ExecutionEvidence,
    expected_commit: CommitIdentity,
) -> VerificationObligation:
    \"\"\"Reconcile a SCHEDULED obligation against platform-verified execution evidence.\"\"\"
    if obligation.status != ObligationStatus.SCHEDULED:
        raise InvalidStateTransitionError(
            f"Only SCHEDULED obligations can be reconciled with execution evidence; "
            f"current status is {obligation.status.value!r}."
        )

    # 1. Verify platform provenance and commit attribution
    if not evidence.provenance.matches_commit(expected_commit):
        validate_transition(obligation.status, ObligationStatus.INCONCLUSIVE)
        return replace(
            obligation,
            status=ObligationStatus.INCONCLUSIVE,
            evidence=evidence,
            status_reason=(
                f"Provenance SHA mismatch: expected head {expected_commit.head_sha[:7]}, "
                f"got {evidence.provenance.workflow_head_sha[:7]}."
            ),
        )

    if not evidence.provenance.is_authentic_and_trusted(expected_commit):
        validate_transition(obligation.status, ObligationStatus.INCONCLUSIVE)
        return replace(
            obligation,
            status=ObligationStatus.INCONCLUSIVE,
            evidence=evidence,
            status_reason=(
                "Workflow provenance untrusted: workflow not from base ref, "
                "test harness modified in PR, or step did not complete cleanly."
            ),
        )

    # 2. Fail closed on contradictory evidence across shards/runs
    if evidence.sufficiency == EvidenceSufficiency.CONTRADICTORY:
        validate_transition(obligation.status, ObligationStatus.FAILED)
        return replace(
            obligation,
            status=ObligationStatus.FAILED,
            evidence=evidence,
            status_reason="Contradictory execution outcomes across test shards (fail-closed).",
        )

    # 3. Handle malformed or empty test reports
    if (
        evidence.total_tests_in_report == 0
        or evidence.sufficiency == EvidenceSufficiency.MALFORMED
    ):
        validate_transition(obligation.status, ObligationStatus.INCONCLUSIVE)
        return replace(
            obligation,
            status=ObligationStatus.INCONCLUSIVE,
            evidence=evidence,
            status_reason="Test report contained zero executed tests or was malformed.",
        )

    # 4. Evaluate raw runner outcome
    if evidence.outcome in (ExecutionOutcome.FAILED, ExecutionOutcome.ERROR):
        validate_transition(obligation.status, ObligationStatus.FAILED)
        return replace(
            obligation,
            status=ObligationStatus.FAILED,
            evidence=evidence,
            status_reason=evidence.failure_summary
            or f"Test execution {evidence.outcome.value}.",
        )

    if evidence.outcome == ExecutionOutcome.SKIPPED:
        validate_transition(obligation.status, ObligationStatus.SKIPPED)
        return replace(
            obligation,
            status=ObligationStatus.SKIPPED,
            evidence=evidence,
            status_reason="Mapped test was skipped during execution.",
        )

    # 5. Outcome is PASSED: verify behavioral evidence sufficiency before granting PASSED
    if (
        evidence.sufficiency == EvidenceSufficiency.SUFFICIENT
        and evidence.target_lines_exercised
        and evidence.target_branches_exercised
        and evidence.behavioral_assertion_verified
    ):
        validate_transition(obligation.status, ObligationStatus.PASSED)
        return replace(
            obligation,
            status=ObligationStatus.PASSED,
            evidence=evidence,
            status_reason="Verified by passing test execution with sufficient behavioral evidence.",
        )

    validate_transition(obligation.status, ObligationStatus.INCONCLUSIVE)
    return replace(
        obligation,
        status=ObligationStatus.INCONCLUSIVE,
        evidence=evidence,
        status_reason=(
            f"Test passed superficially, but evidence sufficiency is "
            f"{evidence.sufficiency.value!r} (lines={evidence.target_lines_exercised}, "
            f"branches={evidence.target_branches_exercised}, "
            f"assertions={evidence.behavioral_assertion_verified})."
        ),
    )


def apply_human_approval(
    obligation: VerificationObligation,
    *,
    approval: HumanApprovalRecord,
    expected_commit: CommitIdentity,
    policy_config: ConclusionPolicyConfig = ConclusionPolicyConfig(),
) -> VerificationObligation:
    \"\"\"Apply an explicit, SHA-bound human approval to an unverified obligation.\"\"\"
    validate_transition(obligation.status, ObligationStatus.APPROVED_BY_HUMAN)

    if approval.approved_head_sha != expected_commit.head_sha:
        raise InvalidStateTransitionError(
            f"Human approval SHA {approval.approved_head_sha[:7]} does not match "
            f"current PR head SHA {expected_commit.head_sha[:7]}."
        )

    if (
        obligation.severity == Severity.CRITICAL
        and not policy_config.allow_human_approval_for_critical
    ):
        raise InvalidStateTransitionError(
            "Policy forbids human waiver/approval for CRITICAL obligations."
        )

    if (
        obligation.severity == Severity.HIGH
        and not policy_config.allow_human_approval_for_high
    ):
        raise InvalidStateTransitionError(
            "Policy forbids human waiver/approval for HIGH obligations."
        )

    return replace(
        obligation,
        status=ObligationStatus.APPROVED_BY_HUMAN,
        human_approval=approval,
        status_reason=(
            f"Approved by human reviewer @{approval.reviewer_login}: {approval.rationale}"
        ),
    )


def apply_policy_waiver(
    obligation: VerificationObligation,
    *,
    waiver: PolicyWaiverRecord,
    expected_commit: CommitIdentity,
) -> VerificationObligation:
    \"\"\"Apply a static policy waiver to a non-critical/non-high obligation.\"\"\"
    validate_transition(obligation.status, ObligationStatus.WAIVED_BY_POLICY)

    if waiver.policy_sha256 != expected_commit.policy_sha256:
        raise InvalidStateTransitionError(
            "Policy waiver SHA-256 does not match the active base-branch policy digest."
        )

    if obligation.severity in (Severity.CRITICAL, Severity.HIGH):
        raise InvalidStateTransitionError(
            f"Cannot apply static policy waiver to {obligation.severity.value} obligation."
        )

    return replace(
        obligation,
        status=ObligationStatus.WAIVED_BY_POLICY,
        policy_waiver=waiver,
        status_reason=f"Waived by policy rule {waiver.policy_rule_id}: {waiver.rationale}",
    )


def mark_obligation_stale(
    obligation: VerificationObligation,
    *,
    superseded_by_sha: str,
) -> VerificationObligation:
    \"\"\"Mark an obligation as STALE because a newer commit was pushed to the PR.\"\"\"
    validate_git_sha(superseded_by_sha, "superseded_by_sha")
    validate_transition(obligation.status, ObligationStatus.STALE)
    return replace(
        obligation,
        status=ObligationStatus.STALE,
        status_reason=f"Superseded by newer commit {superseded_by_sha[:7]}.",
    )


def _verify_obligation_commit_binding(
    obligation: VerificationObligation,
    commit: CommitIdentity,
    policy_config: ConclusionPolicyConfig,
) -> None:
    \"\"\"Verify that any PASSED, APPROVED_BY_HUMAN, or WAIVED_BY_POLICY state matches `commit`.\"\"\"
    if obligation.status == ObligationStatus.PASSED and (
        obligation.evidence is None
        or not obligation.evidence.provenance.is_authentic_and_trusted(commit)
    ):
        raise DomainValidationError(
            f"Obligation {obligation.obligation_id!r} is marked PASSED, but its provenance "
            f"does not match commit {commit.head_sha[:7]} or failed authenticity checks."
        )

    if obligation.status == ObligationStatus.APPROVED_BY_HUMAN:
        if (
            obligation.human_approval is None
            or obligation.human_approval.approved_head_sha != commit.head_sha
        ):
            raise DomainValidationError(
                f"Obligation {obligation.obligation_id!r} is marked APPROVED_BY_HUMAN, but its "
                f"approval SHA does not match commit {commit.head_sha[:7]}."
            )
        if (
            obligation.severity == Severity.CRITICAL
            and not policy_config.allow_human_approval_for_critical
        ) or (
            obligation.severity == Severity.HIGH
            and not policy_config.allow_human_approval_for_high
        ):
            raise DomainValidationError(
                f"Obligation {obligation.obligation_id!r} carries human approval disallowed "
                f"by active policy for severity {obligation.severity.value!r}."
            )

    if obligation.status == ObligationStatus.WAIVED_BY_POLICY and (
        obligation.policy_waiver is None
        or obligation.policy_waiver.policy_sha256 != commit.policy_sha256
    ):
        raise DomainValidationError(
            f"Obligation {obligation.obligation_id!r} carries a policy waiver bound to a "
            f"different policy digest."
        )


def _build_evaluation(
    *,
    commit: CommitIdentity,
    internal_outcome: InternalRunOutcome,
    github_conclusion: GitHubCheckConclusion,
    analysis_completeness: AnalysisCompleteness,
    obligations: tuple[VerificationObligation, ...],
    machine_verified_ids: tuple[str, ...],
    human_approved_ids: tuple[str, ...],
    policy_waived_ids: tuple[str, ...],
    failed_ids: tuple[str, ...],
    blocked_ids: tuple[str, ...],
    unverified_mandatory_ids: tuple[str, ...],
    unverified_advisory_ids: tuple[str, ...],
    summary_title: str,
    summary_rationale: str,
) -> VerificationRunEvaluation:
    \"\"\"Construct a non-stale VerificationRunEvaluation with explicit typing.\"\"\"
    return VerificationRunEvaluation(
        commit=commit,
        internal_outcome=internal_outcome,
        github_conclusion=github_conclusion,
        is_stale=False,
        superseded_by_sha=None,
        analysis_completeness=analysis_completeness,
        obligations=obligations,
        machine_verified_ids=machine_verified_ids,
        human_approved_ids=human_approved_ids,
        policy_waived_ids=policy_waived_ids,
        failed_ids=failed_ids,
        blocked_ids=blocked_ids,
        unverified_mandatory_ids=unverified_mandatory_ids,
        unverified_advisory_ids=unverified_advisory_ids,
        summary_title=summary_title,
        summary_rationale=summary_rationale,
    )


def evaluate_verification_run(
    *,
    commit: CommitIdentity,
    obligations: Sequence[VerificationObligation],
    analysis_completeness: AnalysisCompleteness = AnalysisCompleteness.COMPLETE,
    policy_config: ConclusionPolicyConfig = ConclusionPolicyConfig(),
    policy_valid: bool = True,
    has_unsupported_critical_changes: bool = False,
    superseded_by_sha: str | None = None,
) -> VerificationRunEvaluation:
    \"\"\"Deterministically compute the internal run outcome and GitHub Check Run conclusion.\"\"\"
    seen_ids: set[str] = set()
    for obl in obligations:
        if obl.obligation_id in seen_ids:
            raise DomainValidationError(
                f"Duplicate obligation_id {obl.obligation_id!r} in verification run."
            )
        seen_ids.add(obl.obligation_id)

    # Priority 1: Superseded / Stale Run
    any_obligation_stale = any(o.status == ObligationStatus.STALE for o in obligations)
    if superseded_by_sha is not None or any_obligation_stale:
        effective_superseded_sha = superseded_by_sha
        if effective_superseded_sha is not None:
            validate_git_sha(effective_superseded_sha, "superseded_by_sha")
            if effective_superseded_sha == commit.head_sha:
                raise DomainValidationError(
                    "superseded_by_sha must differ from commit.head_sha."
                )
            stale_obligations = tuple(
                mark_obligation_stale(o, superseded_by_sha=effective_superseded_sha)
                for o in obligations
            )
        else:
            stale_obligations = tuple(obligations)
            if not all(o.status == ObligationStatus.STALE for o in stale_obligations):
                raise DomainValidationError(
                    "Cannot mix STALE and non-STALE obligations without specifying "
                    "superseded_by_sha."
                )

        short_new = effective_superseded_sha[:7] if effective_superseded_sha else "newer commit"
        return VerificationRunEvaluation(
            commit=commit,
            internal_outcome=InternalRunOutcome.STALE_SUPERSEDED,
            github_conclusion=GitHubCheckConclusion.CANCELLED,
            is_stale=True,
            superseded_by_sha=effective_superseded_sha,
            analysis_completeness=analysis_completeness,
            obligations=stale_obligations,
            machine_verified_ids=(),
            human_approved_ids=(),
            policy_waived_ids=(),
            failed_ids=(),
            blocked_ids=(),
            unverified_mandatory_ids=(),
            unverified_advisory_ids=(),
            summary_title=f"Superseded by {short_new}",
            summary_rationale=(
                f"Verification for commit {commit.head_sha[:7]} is STALE because it was "
                f"superseded by {short_new}. Mapped to GitHub conclusion 'cancelled'."
            ),
        )

    for obl in obligations:
        _verify_obligation_commit_binding(obl, commit, policy_config)

    machine_verified_ids: list[str] = []
    human_approved_ids: list[str] = []
    policy_waived_ids: list[str] = []
    failed_ids: list[str] = []
    blocked_ids: list[str] = []
    unverified_mandatory_ids: list[str] = []
    unverified_advisory_ids: list[str] = []

    for obl in obligations:
        is_mandatory = policy_config.is_severity_mandatory(obl.severity)
        if obl.status == ObligationStatus.PASSED:
            machine_verified_ids.append(obl.obligation_id)
        elif obl.status == ObligationStatus.APPROVED_BY_HUMAN:
            human_approved_ids.append(obl.obligation_id)
        elif obl.status == ObligationStatus.WAIVED_BY_POLICY:
            policy_waived_ids.append(obl.obligation_id)
        elif obl.status == ObligationStatus.FAILED:
            failed_ids.append(obl.obligation_id)
        elif obl.status == ObligationStatus.BLOCKED:
            blocked_ids.append(obl.obligation_id)
        else:
            # PROPOSED, SCHEDULED, NOT_RUN, SKIPPED, INCONCLUSIVE
            if is_mandatory:
                unverified_mandatory_ids.append(obl.obligation_id)
            else:
                unverified_advisory_ids.append(obl.obligation_id)

    obligations_tuple = tuple(obligations)
    machine_tuple = tuple(machine_verified_ids)
    human_tuple = tuple(human_approved_ids)
    waived_tuple = tuple(policy_waived_ids)
    failed_tuple = tuple(failed_ids)
    blocked_tuple = tuple(blocked_ids)
    unverified_mand_tuple = tuple(unverified_mandatory_ids)
    unverified_adv_tuple = tuple(unverified_advisory_ids)

    # Priority 2: Invalid Policy Configuration
    if not policy_valid:
        return _build_evaluation(
            commit=commit,
            internal_outcome=InternalRunOutcome.FAILED_VERIFICATION,
            github_conclusion=GitHubCheckConclusion.FAILURE,
            analysis_completeness=analysis_completeness,
            obligations=obligations_tuple,
            machine_verified_ids=machine_tuple,
            human_approved_ids=human_tuple,
            policy_waived_ids=waived_tuple,
            failed_ids=failed_tuple,
            blocked_ids=blocked_tuple,
            unverified_mandatory_ids=unverified_mand_tuple,
            unverified_advisory_ids=unverified_adv_tuple,
            summary_title="Verification Failed: Invalid base-branch policy configuration",
            summary_rationale=(
                "The repository's verification policy could not be validated. "
                "Failing closed to prevent unverified changes from passing."
            ),
        )

    # Priority 3: Any FAILED or BLOCKED Obligation
    if failed_tuple or blocked_tuple:
        return _build_evaluation(
            commit=commit,
            internal_outcome=InternalRunOutcome.FAILED_VERIFICATION,
            github_conclusion=GitHubCheckConclusion.FAILURE,
            analysis_completeness=analysis_completeness,
            obligations=obligations_tuple,
            machine_verified_ids=machine_tuple,
            human_approved_ids=human_tuple,
            policy_waived_ids=waived_tuple,
            failed_ids=failed_tuple,
            blocked_ids=blocked_tuple,
            unverified_mandatory_ids=unverified_mand_tuple,
            unverified_advisory_ids=unverified_adv_tuple,
            summary_title=(
                f"Verification Failed: {len(failed_tuple)} failed, "
                f"{len(blocked_tuple)} blocked obligation(s)"
            ),
            summary_rationale=(
                f"Failed obligations: {list(failed_tuple) or 'none'}. "
                f"Blocked obligations: {list(blocked_tuple) or 'none'}."
            ),
        )

    # Priority 4: Incomplete/Truncated Context, Analyzer Error, or Unsupported Critical Changes
    if (
        analysis_completeness != AnalysisCompleteness.COMPLETE
        or has_unsupported_critical_changes
    ):
        conclusion = (
            GitHubCheckConclusion.FAILURE
            if policy_config.strict_blocking_mode
            else GitHubCheckConclusion.ACTION_REQUIRED
        )
        internal_outcome = (
            InternalRunOutcome.FAILED_VERIFICATION
            if policy_config.strict_blocking_mode
            else InternalRunOutcome.ACTION_REQUIRED_MISSING_EVIDENCE
        )
        return _build_evaluation(
            commit=commit,
            internal_outcome=internal_outcome,
            github_conclusion=conclusion,
            analysis_completeness=analysis_completeness,
            obligations=obligations_tuple,
            machine_verified_ids=machine_tuple,
            human_approved_ids=human_tuple,
            policy_waived_ids=waived_tuple,
            failed_ids=failed_tuple,
            blocked_ids=blocked_tuple,
            unverified_mandatory_ids=unverified_mand_tuple,
            unverified_advisory_ids=unverified_adv_tuple,
            summary_title=(
                "Verification Incomplete: Context truncated, analyzer error, "
                "or unsupported critical change"
            ),
            summary_rationale=(
                f"analysis_completeness={analysis_completeness.value!r}, "
                f"has_unsupported_critical_changes={has_unsupported_critical_changes}. "
                "Cannot return success or neutral when analysis is incomplete."
            ),
        )

    # Priority 5: Unverified Mandatory Obligations
    if unverified_mand_tuple:
        conclusion = (
            GitHubCheckConclusion.FAILURE
            if policy_config.strict_blocking_mode
            else GitHubCheckConclusion.ACTION_REQUIRED
        )
        internal_outcome = (
            InternalRunOutcome.FAILED_VERIFICATION
            if policy_config.strict_blocking_mode
            else InternalRunOutcome.ACTION_REQUIRED_MISSING_EVIDENCE
        )
        return _build_evaluation(
            commit=commit,
            internal_outcome=internal_outcome,
            github_conclusion=conclusion,
            analysis_completeness=analysis_completeness,
            obligations=obligations_tuple,
            machine_verified_ids=machine_tuple,
            human_approved_ids=human_tuple,
            policy_waived_ids=waived_tuple,
            failed_ids=failed_tuple,
            blocked_ids=blocked_tuple,
            unverified_mandatory_ids=unverified_mand_tuple,
            unverified_advisory_ids=unverified_adv_tuple,
            summary_title=(
                f"Evidence Required: {len(unverified_mand_tuple)} mandatory "
                "obligation(s) unverified"
            ),
            summary_rationale=(
                f"Unverified mandatory obligations: {list(unverified_mand_tuple)}. "
                f"Machine-verified: {len(machine_tuple)}, "
                f"Human-approved (not machine-tested): {len(human_tuple)}."
            ),
        )

    # Priority 6: Empty Obligation Set After Confirmed Complete Analysis
    if not obligations_tuple:
        return _build_evaluation(
            commit=commit,
            internal_outcome=InternalRunOutcome.NEUTRAL_NO_BEHAVIORAL_CHANGE,
            github_conclusion=GitHubCheckConclusion.NEUTRAL,
            analysis_completeness=analysis_completeness,
            obligations=obligations_tuple,
            machine_verified_ids=machine_tuple,
            human_approved_ids=human_tuple,
            policy_waived_ids=waived_tuple,
            failed_ids=failed_tuple,
            blocked_ids=blocked_tuple,
            unverified_mandatory_ids=unverified_mand_tuple,
            unverified_advisory_ids=unverified_adv_tuple,
            summary_title="No executable behavioral obligations required",
            summary_rationale=(
                "Complete analysis confirmed that this change introduces no executable "
                "behavioral obligations."
            ),
        )

    # Priority 7: Unverified Advisory Obligations (when configured to surface as NEUTRAL)
    if unverified_adv_tuple and policy_config.advisory_gaps_return_neutral:
        return _build_evaluation(
            commit=commit,
            internal_outcome=InternalRunOutcome.NEUTRAL_ADVISORY_GAPS_ONLY,
            github_conclusion=GitHubCheckConclusion.NEUTRAL,
            analysis_completeness=analysis_completeness,
            obligations=obligations_tuple,
            machine_verified_ids=machine_tuple,
            human_approved_ids=human_tuple,
            policy_waived_ids=waived_tuple,
            failed_ids=failed_tuple,
            blocked_ids=blocked_tuple,
            unverified_mandatory_ids=unverified_mand_tuple,
            unverified_advisory_ids=unverified_adv_tuple,
            summary_title=(
                f"Mandatory obligations satisfied; {len(unverified_adv_tuple)} "
                "advisory obligation(s) unverified"
            ),
            summary_rationale=(
                f"Machine-verified: {len(machine_tuple)}, "
                f"Human-approved (not machine-tested): {len(human_tuple)}, "
                f"Policy-waived: {len(waived_tuple)}. "
                f"Unverified advisory obligations: {list(unverified_adv_tuple)}."
            ),
        )

    # Priority 8: All Mandatory Obligations Satisfied
    return _build_evaluation(
        commit=commit,
        internal_outcome=InternalRunOutcome.VERIFIED_SUCCESS,
        github_conclusion=GitHubCheckConclusion.SUCCESS,
        analysis_completeness=analysis_completeness,
        obligations=obligations_tuple,
        machine_verified_ids=machine_tuple,
        human_approved_ids=human_tuple,
        policy_waived_ids=waived_tuple,
        failed_ids=failed_tuple,
        blocked_ids=blocked_tuple,
        unverified_mandatory_ids=unverified_mand_tuple,
        unverified_advisory_ids=unverified_adv_tuple,
        summary_title=(
            f"Verified: {len(machine_tuple)} machine-tested, "
            f"{len(human_tuple)} human-approved obligation(s)"
        ),
        summary_rationale=(
            f"Machine-verified obligations: {list(machine_tuple) or 'none'}. "
            f"Human-approved obligations (not machine-tested): {list(human_tuple) or 'none'}. "
            f"Policy-waived obligations: {list(waived_tuple) or 'none'}."
        ),
    )
""",
    "tests/unit/test_domain_models.py": """\
\"\"\"Unit tests for domain model immutability, SHA validation, and structural guards.\"\"\"

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from verification_core.domain import (
    AnalysisCompleteness,
    CommitIdentity,
    ConclusionPolicyConfig,
    DomainValidationError,
    EvidenceSufficiency,
    ExecutionEvidence,
    ExecutionOutcome,
    GitHubCheckConclusion,
    HumanApprovalRecord,
    InternalRunOutcome,
    ObligationSource,
    ObligationStatus,
    PolicyWaiverRecord,
    Severity,
    VerificationObligation,
    VerificationRunEvaluation,
    WorkflowProvenance,
)

BASE_SHA = "1" * 40
HEAD_SHA = "a" * 40
POLICY_SHA256 = "f" * 64
NOW = datetime(2026, 10, 17, 12, 0, 0, tzinfo=UTC)


def make_commit() -> CommitIdentity:
    return CommitIdentity(
        repo_full_name="worksomaganesh/ai-pr-verification-agent",
        pr_number=42,
        base_sha=BASE_SHA,
        head_sha=HEAD_SHA,
        policy_sha256=POLICY_SHA256,
    )


def make_provenance(*, trusted: bool = True, untampered: bool = True) -> WorkflowProvenance:
    return WorkflowProvenance(
        workflow_run_id=1001,
        workflow_head_sha=HEAD_SHA,
        workflow_base_sha=BASE_SHA,
        workflow_path=".github/workflows/ci.yml",
        is_trusted_workflow_from_base=trusted,
        harness_untampered=untampered,
        step_completed_cleanly=True,
        recorded_at=NOW,
    )


def test_severity_mandatory_helper_and_policy_config() -> None:
    assert Severity.CRITICAL.is_mandatory_by_default() is True
    assert Severity.HIGH.is_mandatory_by_default() is True
    assert Severity.MEDIUM.is_mandatory_by_default() is False
    assert Severity.LOW.is_mandatory_by_default() is False

    default_cfg = ConclusionPolicyConfig()
    assert default_cfg.is_severity_mandatory(Severity.MEDIUM) is False

    strict_med_cfg = ConclusionPolicyConfig(treat_medium_as_mandatory=True)
    assert strict_med_cfg.is_severity_mandatory(Severity.MEDIUM) is True


def test_commit_identity_validates_shas_and_immutability() -> None:
    commit = make_commit()
    with pytest.raises(FrozenInstanceError):
        commit.pr_number = 99  # type: ignore[misc]

    with pytest.raises(DomainValidationError, match="repo_full_name must match"):
        CommitIdentity(
            repo_full_name="invalid_repo_name",
            pr_number=1,
            base_sha=BASE_SHA,
            head_sha=HEAD_SHA,
            policy_sha256=POLICY_SHA256,
        )

    with pytest.raises(DomainValidationError, match="pr_number must be >= 1"):
        CommitIdentity(
            repo_full_name="owner/repo",
            pr_number=0,
            base_sha=BASE_SHA,
            head_sha=HEAD_SHA,
            policy_sha256=POLICY_SHA256,
        )

    with pytest.raises(DomainValidationError, match="base_sha and head_sha must be distinct"):
        CommitIdentity(
            repo_full_name="owner/repo",
            pr_number=1,
            base_sha=HEAD_SHA,
            head_sha=HEAD_SHA,
            policy_sha256=POLICY_SHA256,
        )

    with pytest.raises(DomainValidationError, match="40-character lowercase hex SHA"):
        CommitIdentity(
            repo_full_name="owner/repo",
            pr_number=1,
            base_sha="short_sha",
            head_sha=HEAD_SHA,
            policy_sha256=POLICY_SHA256,
        )

    with pytest.raises(DomainValidationError, match="64-character lowercase hex SHA-256"):
        CommitIdentity(
            repo_full_name="owner/repo",
            pr_number=1,
            base_sha=BASE_SHA,
            head_sha=HEAD_SHA,
            policy_sha256="bad_sha256",
        )


def test_workflow_provenance_validation() -> None:
    with pytest.raises(DomainValidationError, match="workflow_run_id must be >= 1"):
        WorkflowProvenance(
            workflow_run_id=0,
            workflow_head_sha=HEAD_SHA,
            workflow_base_sha=BASE_SHA,
            workflow_path=".github/workflows/ci.yml",
            is_trusted_workflow_from_base=True,
            harness_untampered=True,
            step_completed_cleanly=True,
            recorded_at=NOW,
        )


def test_untrusted_input_cannot_directly_instantiate_passed_obligation() -> None:
    with pytest.raises(DomainValidationError, match="requires verified ExecutionEvidence"):
        VerificationObligation(
            obligation_id="OBL-1",
            category="authz",
            description="Cross-tenant subscription access must return 403",
            severity=Severity.CRITICAL,
            source=ObligationSource.LLM_HYPOTHESIS,
            affected_files=("src/authz.py",),
            status=ObligationStatus.PASSED,
            evidence=None,
        )


def test_obligation_structural_guards() -> None:
    with pytest.raises(DomainValidationError, match="affected_files must contain at least one"):
        VerificationObligation.propose(
            obligation_id="OBL-1",
            category="authz",
            description="Desc",
            severity=Severity.HIGH,
            source=ObligationSource.DETERMINISTIC_POLICY,
            affected_files=(),
        )

    with pytest.raises(DomainValidationError, match="requires a non-empty candidate_test_id"):
        VerificationObligation(
            obligation_id="OBL-1",
            category="authz",
            description="Desc",
            severity=Severity.HIGH,
            source=ObligationSource.DETERMINISTIC_POLICY,
            affected_files=("src/authz.py",),
            status=ObligationStatus.SCHEDULED,
            candidate_test_id=None,
        )

    with pytest.raises(DomainValidationError, match="requires a HumanApprovalRecord"):
        VerificationObligation(
            obligation_id="OBL-1",
            category="authz",
            description="Desc",
            severity=Severity.HIGH,
            source=ObligationSource.DETERMINISTIC_POLICY,
            affected_files=("src/authz.py",),
            status=ObligationStatus.APPROVED_BY_HUMAN,
            human_approval=None,
        )

    with pytest.raises(DomainValidationError, match="requires a PolicyWaiverRecord"):
        VerificationObligation(
            obligation_id="OBL-1",
            category="docs",
            description="Desc",
            severity=Severity.LOW,
            source=ObligationSource.DETERMINISTIC_POLICY,
            affected_files=("README.md",),
            status=ObligationStatus.WAIVED_BY_POLICY,
            policy_waiver=None,
        )


def test_execution_evidence_forbids_sufficient_without_all_behavioral_criteria() -> None:
    prov = make_provenance()

    with pytest.raises(DomainValidationError, match="total_tests_in_report must be >= 0"):
        ExecutionEvidence(
            test_node_id="tests/test_authz.py::test_forbidden",
            outcome=ExecutionOutcome.PASSED,
            sufficiency=EvidenceSufficiency.UNVERIFIED,
            provenance=prov,
            target_lines_exercised=False,
            target_branches_exercised=False,
            behavioral_assertion_verified=False,
            total_tests_in_report=-1,
        )

    with pytest.raises(DomainValidationError, match="total_tests_in_report == 0"):
        ExecutionEvidence(
            test_node_id="tests/test_authz.py::test_forbidden",
            outcome=ExecutionOutcome.PASSED,
            sufficiency=EvidenceSufficiency.SUFFICIENT,
            provenance=prov,
            target_lines_exercised=True,
            target_branches_exercised=True,
            behavioral_assertion_verified=True,
            total_tests_in_report=0,
        )

    with pytest.raises(DomainValidationError, match="requires ExecutionOutcome.PASSED"):
        ExecutionEvidence(
            test_node_id="tests/test_authz.py::test_forbidden",
            outcome=ExecutionOutcome.FAILED,
            sufficiency=EvidenceSufficiency.SUFFICIENT,
            provenance=prov,
            target_lines_exercised=True,
            target_branches_exercised=True,
            behavioral_assertion_verified=True,
            total_tests_in_report=10,
        )

    with pytest.raises(
        DomainValidationError,
        match="requires target_lines_exercised, target_branches_exercised",
    ):
        ExecutionEvidence(
            test_node_id="tests/test_authz.py::test_happy_path",
            outcome=ExecutionOutcome.PASSED,
            sufficiency=EvidenceSufficiency.SUFFICIENT,
            provenance=prov,
            target_lines_exercised=True,
            target_branches_exercised=False,
            behavioral_assertion_verified=False,
            total_tests_in_report=140,
        )


def test_passed_obligation_rejects_untrusted_or_mixed_governance_records() -> None:
    tampered_prov = make_provenance(untampered=False)
    evidence_tampered = ExecutionEvidence(
        test_node_id="tests/test_checkout.py::test_create",
        outcome=ExecutionOutcome.PASSED,
        sufficiency=EvidenceSufficiency.SUFFICIENT,
        provenance=tampered_prov,
        target_lines_exercised=True,
        target_branches_exercised=True,
        behavioral_assertion_verified=True,
        total_tests_in_report=10,
    )
    with pytest.raises(
        DomainValidationError,
        match="requires trusted, untampered workflow provenance",
    ):
        VerificationObligation(
            obligation_id="OBL-CHK-1",
            category="checkout",
            description="Verify tier session creation",
            severity=Severity.HIGH,
            source=ObligationSource.DETERMINISTIC_POLICY,
            affected_files=("src/checkout.py",),
            status=ObligationStatus.PASSED,
            candidate_test_id="tests/test_checkout.py::test_create",
            evidence=evidence_tampered,
        )

    valid_evidence = ExecutionEvidence(
        test_node_id="tests/test_checkout.py::test_create",
        outcome=ExecutionOutcome.PASSED,
        sufficiency=EvidenceSufficiency.SUFFICIENT,
        provenance=make_provenance(),
        target_lines_exercised=True,
        target_branches_exercised=True,
        behavioral_assertion_verified=True,
        total_tests_in_report=10,
    )
    human_rec = HumanApprovalRecord(
        reviewer_login="lead",
        review_id=10,
        approved_head_sha=HEAD_SHA,
        rationale="Looks good",
        approved_at=NOW,
    )
    with pytest.raises(DomainValidationError, match="must not carry human_approval"):
        VerificationObligation(
            obligation_id="OBL-CHK-1",
            category="checkout",
            description="Verify tier session creation",
            severity=Severity.HIGH,
            source=ObligationSource.DETERMINISTIC_POLICY,
            affected_files=("src/checkout.py",),
            status=ObligationStatus.PASSED,
            candidate_test_id="tests/test_checkout.py::test_create",
            evidence=valid_evidence,
            human_approval=human_rec,
        )


def test_critical_and_high_obligations_forbid_static_policy_waiver() -> None:
    waiver = PolicyWaiverRecord(
        policy_rule_id="RULE-LOW-1",
        policy_sha256=POLICY_SHA256,
        rationale="Non-critical UI styling check waived",
    )
    with pytest.raises(DomainValidationError, match="cannot be statically waived"):
        VerificationObligation(
            obligation_id="OBL-CRIT-1",
            category="webhook_idempotency",
            description="Duplicate event_id must be ignored",
            severity=Severity.CRITICAL,
            source=ObligationSource.DETERMINISTIC_POLICY,
            affected_files=("src/webhooks.py",),
            status=ObligationStatus.WAIVED_BY_POLICY,
            policy_waiver=waiver,
        )


def test_human_approval_and_run_evaluation_guards() -> None:
    with pytest.raises(DomainValidationError, match="review_id must be >= 1"):
        HumanApprovalRecord(
            reviewer_login="staff-reviewer",
            review_id=0,
            approved_head_sha=HEAD_SHA,
            rationale="Verified manually.",
            approved_at=NOW,
        )

    commit = make_commit()
    with pytest.raises(DomainValidationError, match="Stale runs must have internal_outcome"):
        VerificationRunEvaluation(
            commit=commit,
            internal_outcome=InternalRunOutcome.VERIFIED_SUCCESS,
            github_conclusion=GitHubCheckConclusion.CANCELLED,
            is_stale=True,
            superseded_by_sha= None,
            analysis_completeness=AnalysisCompleteness.COMPLETE,
            obligations=(),
            machine_verified_ids=(),
            human_approved_ids=(),
            policy_waived_ids=(),
            failed_ids=(),
            blocked_ids=(),
            unverified_mandatory_ids=(),
            unverified_advisory_ids=(),
            summary_title="Stale",
            summary_rationale="Stale run",
        )

    with pytest.raises(DomainValidationError, match="Stale runs must map to GitHubCheckConclusion"):
        VerificationRunEvaluation(
            commit=commit,
            internal_outcome=InternalRunOutcome.STALE_SUPERSEDED,
            github_conclusion=GitHubCheckConclusion.SUCCESS,
            is_stale=True,
            superseded_by_sha=None,
            analysis_completeness=AnalysisCompleteness.COMPLETE,
            obligations=(),
            machine_verified_ids=(),
            human_approved_ids=(),
            policy_waived_ids=(),
            failed_ids=(),
            blocked_ids=(),
            unverified_mandatory_ids=(),
            unverified_advisory_ids=(),
            summary_title="Stale",
            summary_rationale="Stale run",
        )
""",
    "tests/unit/test_state_machine.py": """\
\"\"\"Unit and Hypothesis property-based tests for the verification state machine.\"\"\"

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from verification_core.domain import (
    ALLOWED_OBLIGATION_TRANSITIONS,
    AnalysisCompleteness,
    CommitIdentity,
    ConclusionPolicyConfig,
    DomainValidationError,
    EvidenceSufficiency,
    ExecutionEvidence,
    ExecutionOutcome,
    GitHubCheckConclusion,
    HumanApprovalRecord,
    InternalRunOutcome,
    InvalidStateTransitionError,
    ObligationSource,
    ObligationStatus,
    PolicyWaiverRecord,
    Severity,
    VerificationObligation,
    WorkflowProvenance,
    apply_human_approval,
    apply_policy_waiver,
    block_obligation,
    evaluate_verification_run,
    mark_obligation_not_run,
    mark_obligation_stale,
    reconcile_obligation_evidence,
    schedule_obligation,
    validate_transition,
)

BASE_SHA = "1" * 40
HEAD_SHA = "a" * 40
NEWER_SHA = "b" * 40
WRONG_SHA = "c" * 40
POLICY_SHA256 = "f" * 64
NOW = datetime(2026, 10, 17, 12, 0, 0, tzinfo=UTC)


def make_commit() -> CommitIdentity:
    return CommitIdentity(
        repo_full_name="worksomaganesh/ai-pr-verification-agent",
        pr_number=42,
        base_sha=BASE_SHA,
        head_sha=HEAD_SHA,
        policy_sha256=POLICY_SHA256,
    )


def make_provenance(
    head_sha: str = HEAD_SHA,
    *,
    trusted: bool = True,
) -> WorkflowProvenance:
    return WorkflowProvenance(
        workflow_run_id=9001,
        workflow_head_sha=head_sha,
        workflow_base_sha=BASE_SHA,
        workflow_path=".github/workflows/ci.yml",
        is_trusted_workflow_from_base=trusted,
        harness_untampered=True,
        step_completed_cleanly=True,
        recorded_at=NOW,
    )


def make_sufficient_evidence(
    test_node_id: str = "tests/test_checkout.py::test_create_session",
    head_sha: str = HEAD_SHA,
) -> ExecutionEvidence:
    return ExecutionEvidence(
        test_node_id=test_node_id,
        outcome=ExecutionOutcome.PASSED,
        sufficiency=EvidenceSufficiency.SUFFICIENT,
        provenance=make_provenance(head_sha=head_sha),
        target_lines_exercised=True,
        target_branches_exercised=True,
        behavioral_assertion_verified=True,
        total_tests_in_report=140,
    )


def make_proposed_obligation(
    obligation_id: str = "OBL-1",
    severity: Severity = Severity.CRITICAL,
    candidate_test_id: str | None = "tests/test_suite.py::test_case",
) -> VerificationObligation:
    return VerificationObligation.propose(
        obligation_id=obligation_id,
        category="security_and_billing",
        description=f"Verify behavioral obligation {obligation_id}",
        severity=severity,
        source=ObligationSource.DETERMINISTIC_POLICY,
        affected_files=("src/module.py",),
        candidate_test_id=candidate_test_id,
    )


# ---------------------------------------------------------------------------
# Scenario 1: A required obligation is FAILED -> conclusion must be failure.
# ---------------------------------------------------------------------------
def test_scenario_1_required_obligation_failed_returns_failure() -> None:
    commit = make_commit()
    obl_pass = schedule_obligation(make_proposed_obligation("OBL-1", Severity.HIGH))
    obl_pass = reconcile_obligation_evidence(
        obl_pass,
        evidence=make_sufficient_evidence("tests/test_a.py::test_ok"),
        expected_commit=commit,
    )

    obl_fail = schedule_obligation(make_proposed_obligation("OBL-2", Severity.CRITICAL))
    fail_evidence = ExecutionEvidence(
        test_node_id="tests/test_b.py::test_fail",
        outcome=ExecutionOutcome.FAILED,
        sufficiency=EvidenceSufficiency.UNVERIFIED,
        provenance=make_provenance(),
        target_lines_exercised=True,
        target_branches_exercised=False,
        behavioral_assertion_verified=False,
        total_tests_in_report=140,
        failure_summary="AssertionError: Expected 403 Forbidden, got 200 OK",
    )
    obl_fail = reconcile_obligation_evidence(
        obl_fail,
        evidence=fail_evidence,
        expected_commit=commit,
    )
    assert obl_fail.status == ObligationStatus.FAILED

    evaluation = evaluate_verification_run(
        commit=commit,
        obligations=(obl_pass, obl_fail),
    )
    assert evaluation.internal_outcome == InternalRunOutcome.FAILED_VERIFICATION
    assert evaluation.github_conclusion == GitHubCheckConclusion.FAILURE
    assert evaluation.failed_ids == ("OBL-2",)


# ---------------------------------------------------------------------------
# Scenario 2: A critical obligation is NOT_RUN -> conclusion must not be
#             success or neutral.
# ---------------------------------------------------------------------------
def test_scenario_2_critical_obligation_not_run_never_success_or_neutral() -> None:
    commit = make_commit()
    obl_passed = schedule_obligation(make_proposed_obligation("OBL-CHK-1", Severity.HIGH))
    obl_passed = reconcile_obligation_evidence(
        obl_passed,
        evidence=make_sufficient_evidence(),
        expected_commit=commit,
    )

    obl_not_run = mark_obligation_not_run(
        make_proposed_obligation("OBL-WHK-1", Severity.CRITICAL, candidate_test_id=None),
        reason="No test in repository exercises duplicate webhook event_id delivery.",
    )
    assert obl_not_run.status == ObligationStatus.NOT_RUN

    evaluation = evaluate_verification_run(
        commit=commit,
        obligations=(obl_passed, obl_not_run),
    )
    assert evaluation.github_conclusion not in (
        GitHubCheckConclusion.SUCCESS,
        GitHubCheckConclusion.NEUTRAL,
    )
    assert evaluation.github_conclusion == GitHubCheckConclusion.ACTION_REQUIRED
    assert evaluation.internal_outcome == InternalRunOutcome.ACTION_REQUIRED_MISSING_EVIDENCE
    assert evaluation.unverified_mandatory_ids == ("OBL-WHK-1",)


# ---------------------------------------------------------------------------
# Scenario 3: A high-risk obligation has WEAK_EVIDENCE -> conclusion must not
#             be success.
# ---------------------------------------------------------------------------
def test_scenario_3_high_risk_obligation_with_weak_evidence_blocks_success() -> None:
    commit = make_commit()
    obl_authz = schedule_obligation(
        make_proposed_obligation(
            "OBL-AUTH-1",
            Severity.HIGH,
            candidate_test_id="tests/test_authz.py::test_get_own_subscription",
        )
    )
    weak_evidence = ExecutionEvidence(
        test_node_id="tests/test_authz.py::test_get_own_subscription",
        outcome=ExecutionOutcome.PASSED,
        sufficiency=EvidenceSufficiency.WEAK_EVIDENCE,
        provenance=make_provenance(),
        target_lines_exercised=True,
        target_branches_exercised=False,
        behavioral_assertion_verified=False,
        total_tests_in_report=140,
    )
    reconciled_obl = reconcile_obligation_evidence(
        obl_authz,
        evidence=weak_evidence,
        expected_commit=commit,
    )
    assert reconciled_obl.status == ObligationStatus.INCONCLUSIVE

    evaluation = evaluate_verification_run(
        commit=commit,
        obligations=(reconciled_obl,),
    )
    assert evaluation.github_conclusion != GitHubCheckConclusion.SUCCESS
    assert evaluation.github_conclusion != GitHubCheckConclusion.NEUTRAL
    assert evaluation.github_conclusion == GitHubCheckConclusion.ACTION_REQUIRED
    assert evaluation.unverified_mandatory_ids == ("OBL-AUTH-1",)


# ---------------------------------------------------------------------------
# Scenario 4: A run is superseded -> internal status is STALE; external GitHub
#             conclusion is CANCELLED (never 'stale').
# ---------------------------------------------------------------------------
def test_scenario_4_superseded_run_sets_internal_stale_and_github_cancelled() -> None:
    commit = make_commit()
    obl = schedule_obligation(make_proposed_obligation("OBL-1", Severity.CRITICAL))
    obl = reconcile_obligation_evidence(
        obl,
        evidence=make_sufficient_evidence(),
        expected_commit=commit,
    )
    assert obl.status == ObligationStatus.PASSED

    evaluation = evaluate_verification_run(
        commit=commit,
        obligations=(obl,),
        superseded_by_sha=NEWER_SHA,
    )
    assert evaluation.is_stale is True
    assert evaluation.internal_outcome == InternalRunOutcome.STALE_SUPERSEDED
    assert evaluation.github_conclusion == GitHubCheckConclusion.CANCELLED
    assert evaluation.superseded_by_sha == NEWER_SHA
    assert all(o.status == ObligationStatus.STALE for o in evaluation.obligations)
    assert "stale" not in {c.value for c in GitHubCheckConclusion}

    # Pre-marked STALE obligations without superseded_by_sha parameter also evaluate cleanly
    pre_stale = mark_obligation_stale(obl, superseded_by_sha=NEWER_SHA)
    eval_pre_stale = evaluate_verification_run(commit=commit, obligations=(pre_stale,))
    assert eval_pre_stale.internal_outcome == InternalRunOutcome.STALE_SUPERSEDED
    assert eval_pre_stale.github_conclusion == GitHubCheckConclusion.CANCELLED


# ---------------------------------------------------------------------------
# Scenario 5: An authorized human waiver is permitted by policy -> display and
#             model it separately from machine verification.
# ---------------------------------------------------------------------------
def test_scenario_5_human_approval_is_distinct_from_machine_passed() -> None:
    commit = make_commit()
    obl_machine = schedule_obligation(make_proposed_obligation("OBL-1", Severity.HIGH))
    obl_machine = reconcile_obligation_evidence(
        obl_machine,
        evidence=make_sufficient_evidence("tests/test_checkout.py::test_tier"),
        expected_commit=commit,
    )

    obl_unverified = mark_obligation_not_run(
        make_proposed_obligation("OBL-2", Severity.CRITICAL, candidate_test_id=None),
        reason="No automated Stripe replay test in repo.",
    )
    human_record = HumanApprovalRecord(
        reviewer_login="principal-eng",
        review_id=7788,
        approved_head_sha=HEAD_SHA,
        rationale="Verified idempotency key constraint in staging database.",
        approved_at=NOW,
    )
    obl_human = apply_human_approval(
        obl_unverified,
        approval=human_record,
        expected_commit=commit,
    )
    assert obl_human.status == ObligationStatus.APPROVED_BY_HUMAN
    assert obl_human.status != ObligationStatus.PASSED

    evaluation = evaluate_verification_run(
        commit=commit,
        obligations=(obl_machine, obl_human),
    )
    assert evaluation.github_conclusion == GitHubCheckConclusion.SUCCESS
    assert evaluation.machine_verified_ids == ("OBL-1",)
    assert evaluation.human_approved_ids == ("OBL-2",)
    assert "1 machine-tested, 1 human-approved" in evaluation.summary_title
    assert "not machine-tested" in evaluation.summary_rationale

    strict_policy = ConclusionPolicyConfig(allow_human_approval_for_critical=False)
    with pytest.raises(InvalidStateTransitionError, match="forbids human waiver"):
        apply_human_approval(
            obl_unverified,
            approval=human_record,
            expected_commit=commit,
            policy_config=strict_policy,
        )


# ---------------------------------------------------------------------------
# Scenario 6: Empty obligations after confirmed complete docs-only analysis ->
#             neutral is permitted.
# ---------------------------------------------------------------------------
def test_scenario_6_empty_obligations_after_complete_analysis_returns_neutral() -> None:
    commit = make_commit()
    evaluation = evaluate_verification_run(
        commit=commit,
        obligations=(),
        analysis_completeness=AnalysisCompleteness.COMPLETE,
        policy_valid=True,
        has_unsupported_critical_changes=False,
    )
    assert evaluation.internal_outcome == InternalRunOutcome.NEUTRAL_NO_BEHAVIORAL_CHANGE
    assert evaluation.github_conclusion == GitHubCheckConclusion.NEUTRAL


# ---------------------------------------------------------------------------
# Scenario 7: Empty obligations caused by incomplete/truncated analysis ->
#             neutral is forbidden.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("completeness", "policy_valid", "unsupported_critical"),
    [
        (AnalysisCompleteness.TRUNCATED, True, False),
        (AnalysisCompleteness.INCOMPLETE, True, False),
        (AnalysisCompleteness.ANALYZER_ERROR, True, False),
        (AnalysisCompleteness.COMPLETE, False, False),
        (AnalysisCompleteness.COMPLETE, True, True),
    ],
)
def test_scenario_7_empty_obligations_with_incomplete_or_invalid_state_forbids_neutral(
    completeness: AnalysisCompleteness,
    policy_valid: bool,
    unsupported_critical: bool,
) -> None:
    commit = make_commit()
    evaluation = evaluate_verification_run(
        commit=commit,
        obligations=(),
        analysis_completeness=completeness,
        policy_valid=policy_valid,
        has_unsupported_critical_changes=unsupported_critical,
    )
    assert evaluation.github_conclusion not in (
        GitHubCheckConclusion.NEUTRAL,
        GitHubCheckConclusion.SUCCESS,
    )
    assert evaluation.github_conclusion in (
        GitHubCheckConclusion.ACTION_REQUIRED,
        GitHubCheckConclusion.FAILURE,
    )


# ---------------------------------------------------------------------------
# Scenario 8: All mandatory obligations have sufficient evidence ->
#             success may be returned.
# ---------------------------------------------------------------------------
def test_scenario_8_all_mandatory_obligations_with_sufficient_evidence_returns_success() -> None:
    commit = make_commit()
    obl_crit = schedule_obligation(make_proposed_obligation("OBL-CRIT", Severity.CRITICAL))
    obl_crit = reconcile_obligation_evidence(
        obl_crit,
        evidence=make_sufficient_evidence("tests/test_webhooks.py::test_idempotent"),
        expected_commit=commit,
    )
    obl_high = schedule_obligation(make_proposed_obligation("OBL-HIGH", Severity.HIGH))
    obl_high = reconcile_obligation_evidence(
        obl_high,
        evidence=make_sufficient_evidence("tests/test_authz.py::test_cross_tenant_403"),
        expected_commit=commit,
    )
    obl_low = apply_policy_waiver(
        make_proposed_obligation("OBL-LOW", Severity.LOW),
        waiver=PolicyWaiverRecord(
            policy_rule_id="RULE-DOCS",
            policy_sha256=POLICY_SHA256,
            rationale="Low severity changelog check waived by policy",
        ),
        expected_commit=commit,
    )

    evaluation = evaluate_verification_run(
        commit=commit,
        obligations=(obl_crit, obl_high, obl_low),
    )
    assert evaluation.internal_outcome == InternalRunOutcome.VERIFIED_SUCCESS
    assert evaluation.github_conclusion == GitHubCheckConclusion.SUCCESS
    assert evaluation.machine_verified_ids == ("OBL-CRIT", "OBL-HIGH")
    assert evaluation.policy_waived_ids == ("OBL-LOW",)


# ---------------------------------------------------------------------------
# Scenario 9: Contradictory or invalid state transitions fail safely.
# ---------------------------------------------------------------------------
def test_scenario_9_contradictory_and_malformed_evidence_fail_safely() -> None:
    commit = make_commit()
    obl = schedule_obligation(make_proposed_obligation("OBL-SHARD", Severity.HIGH))
    contradictory_evidence = ExecutionEvidence(
        test_node_id="tests/test_checkout.py::test_race",
        outcome=ExecutionOutcome.PASSED,
        sufficiency=EvidenceSufficiency.CONTRADICTORY,
        provenance=make_provenance(),
        target_lines_exercised=True,
        target_branches_exercised=True,
        behavioral_assertion_verified=True,
        total_tests_in_report=50,
    )
    reconciled = reconcile_obligation_evidence(
        obl,
        evidence=contradictory_evidence,
        expected_commit=commit,
    )
    assert reconciled.status == ObligationStatus.FAILED

    evaluation = evaluate_verification_run(commit=commit, obligations=(reconciled,))
    assert evaluation.github_conclusion == GitHubCheckConclusion.FAILURE

    # Malformed / 0-test report transitions to INCONCLUSIVE
    obl_malformed = schedule_obligation(make_proposed_obligation("OBL-MAL", Severity.HIGH))
    malformed_evidence = ExecutionEvidence(
        test_node_id="tests/test_checkout.py::test_empty",
        outcome=ExecutionOutcome.PASSED,
        sufficiency=EvidenceSufficiency.MALFORMED,
        provenance=make_provenance(),
        target_lines_exercised=False,
        target_branches_exercised=False,
        behavioral_assertion_verified=False,
        total_tests_in_report=0,
    )
    rec_malformed = reconcile_obligation_evidence(
        obl_malformed,
        evidence=malformed_evidence,
        expected_commit=commit,
    )
    assert rec_malformed.status == ObligationStatus.INCONCLUSIVE

    # Untrusted workflow provenance transitions to INCONCLUSIVE
    obl_untrusted = schedule_obligation(make_proposed_obligation("OBL-UNTRUST", Severity.HIGH))
    untrusted_evidence = ExecutionEvidence(
        test_node_id="tests/test_checkout.py::test_untrusted",
        outcome=ExecutionOutcome.PASSED,
        sufficiency=EvidenceSufficiency.UNVERIFIED,
        provenance=make_provenance(trusted=False),
        target_lines_exercised=True,
        target_branches_exercised=True,
        behavioral_assertion_verified=True,
        total_tests_in_report=10,
    )
    rec_untrusted = reconcile_obligation_evidence(
        obl_untrusted,
        evidence=untrusted_evidence,
        expected_commit=commit,
    )
    assert rec_untrusted.status == ObligationStatus.INCONCLUSIVE


def test_scenario_9_mismatched_provenance_and_guard_branches() -> None:
    commit = make_commit()
    obl_proposed = make_proposed_obligation("OBL-PROP", Severity.CRITICAL, candidate_test_id=None)

    with pytest.raises(InvalidStateTransitionError, match="without a candidate_test_id"):
        schedule_obligation(obl_proposed)

    with pytest.raises(InvalidStateTransitionError, match="Only SCHEDULED obligations"):
        reconcile_obligation_evidence(
            obl_proposed,
            evidence=make_sufficient_evidence(),
            expected_commit=commit,
        )

    with pytest.raises(DomainValidationError, match="requires a non-empty reason"):
        block_obligation(obl_proposed, reason="   ")

    with pytest.raises(DomainValidationError, match="requires a non-empty reason"):
        mark_obligation_not_run(obl_proposed, reason="")

    obl = schedule_obligation(make_proposed_obligation("OBL-SHA", Severity.CRITICAL))
    wrong_sha_evidence = make_sufficient_evidence(head_sha=WRONG_SHA)
    reconciled = reconcile_obligation_evidence(
        obl,
        evidence=wrong_sha_evidence,
        expected_commit=commit,
    )
    assert reconciled.status == ObligationStatus.INCONCLUSIVE
    assert "Provenance SHA mismatch" in (reconciled.status_reason or "")


def test_commit_binding_and_evaluation_edge_cases() -> None:
    commit = make_commit()
    other_commit = CommitIdentity(
        repo_full_name="worksomaganesh/ai-pr-verification-agent",
        pr_number=42,
        base_sha=BASE_SHA,
        head_sha=WRONG_SHA,
        policy_sha256=POLICY_SHA256,
    )

    # Obligation verified on other_commit must be rejected when evaluated against commit
    obl_other = schedule_obligation(make_proposed_obligation("OBL-OTHER", Severity.HIGH))
    obl_other = reconcile_obligation_evidence(
        obl_other,
        evidence=make_sufficient_evidence(head_sha=WRONG_SHA),
        expected_commit=other_commit,
    )
    with pytest.raises(DomainValidationError, match="does not match commit"):
        evaluate_verification_run(commit=commit, obligations=(obl_other,))

    # Duplicate obligation IDs rejected
    obl_a = make_proposed_obligation("OBL-DUP", Severity.LOW)
    with pytest.raises(DomainValidationError, match="Duplicate obligation_id"):
        evaluate_verification_run(commit=commit, obligations=(obl_a, obl_a))

    # Advisory gaps returning neutral vs success
    obl_adv = mark_obligation_not_run(
        make_proposed_obligation("OBL-ADV", Severity.LOW),
        reason="Optional check not run",
    )
    eval_neutral = evaluate_verification_run(
        commit=commit,
        obligations=(obl_adv,),
        policy_config=ConclusionPolicyConfig(advisory_gaps_return_neutral=True),
    )
    assert eval_neutral.github_conclusion == GitHubCheckConclusion.NEUTRAL
    assert eval_neutral.internal_outcome == InternalRunOutcome.NEUTRAL_ADVISORY_GAPS_ONLY

    eval_success = evaluate_verification_run(
        commit=commit,
        obligations=(obl_adv,),
        policy_config=ConclusionPolicyConfig(advisory_gaps_return_neutral=False),
    )
    assert eval_success.github_conclusion == GitHubCheckConclusion.SUCCESS


def test_scenario_9_exhaustive_invalid_state_transitions_raise_error() -> None:
    all_statuses = list(ObligationStatus)
    for current in all_statuses:
        allowed = ALLOWED_OBLIGATION_TRANSITIONS[current]
        for target in all_statuses:
            if target in allowed:
                validate_transition(current, target)
            else:
                with pytest.raises(InvalidStateTransitionError):
                    validate_transition(current, target)


def test_running_scenario_subscription_checkout_webhook_migration_authz() -> None:
    \"\"\"Verify the canonical 4-part PR scenario prevents a false-green conclusion.\"\"\"
    commit = make_commit()

    obl_checkout = schedule_obligation(
        make_proposed_obligation(
            "OBL-CHK-01",
            Severity.HIGH,
            "tests/test_checkout.py::test_create_session",
        )
    )
    obl_checkout = reconcile_obligation_evidence(
        obl_checkout,
        evidence=make_sufficient_evidence("tests/test_checkout.py::test_create_session"),
        expected_commit=commit,
    )

    obl_migration = schedule_obligation(
        make_proposed_obligation(
            "OBL-MIG-01",
            Severity.CRITICAL,
            "tests/test_migrations.py::test_0042_reversible",
        )
    )
    obl_migration = reconcile_obligation_evidence(
        obl_migration,
        evidence=make_sufficient_evidence("tests/test_migrations.py::test_0042_reversible"),
        expected_commit=commit,
    )

    obl_webhook = mark_obligation_not_run(
        make_proposed_obligation("OBL-WHK-01", Severity.CRITICAL, candidate_test_id=None),
        reason="No test verifies duplicate webhook delivery idempotency.",
    )

    obl_authz = schedule_obligation(
        make_proposed_obligation(
            "OBL-AUTH-01",
            Severity.CRITICAL,
            "tests/test_authz.py::test_get_own_subscription",
        )
    )
    obl_authz = reconcile_obligation_evidence(
        obl_authz,
        evidence=ExecutionEvidence(
            test_node_id="tests/test_authz.py::test_get_own_subscription",
            outcome=ExecutionOutcome.PASSED,
            sufficiency=EvidenceSufficiency.WEAK_EVIDENCE,
            provenance=make_provenance(),
            target_lines_exercised=True,
            target_branches_exercised=False,
            behavioral_assertion_verified=False,
            total_tests_in_report=140,
        ),
        expected_commit=commit,
    )

    evaluation = evaluate_verification_run(
        commit=commit,
        obligations=(obl_checkout, obl_migration, obl_webhook, obl_authz),
    )
    assert evaluation.github_conclusion == GitHubCheckConclusion.ACTION_REQUIRED
    assert evaluation.machine_verified_ids == ("OBL-CHK-01", "OBL-MIG-01")
    assert evaluation.unverified_mandatory_ids == ("OBL-WHK-01", "OBL-AUTH-01")


# ---------------------------------------------------------------------------
# Hypothesis Property-Based Invariant Tests
# ---------------------------------------------------------------------------
OBLIGATION_SPEC_STRATEGY = st.tuples(
    st.sampled_from(list(Severity)),
    st.sampled_from(
        [
            ObligationStatus.PROPOSED,
            ObligationStatus.SCHEDULED,
            ObligationStatus.PASSED,
            ObligationStatus.FAILED,
            ObligationStatus.SKIPPED,
            ObligationStatus.BLOCKED,
            ObligationStatus.NOT_RUN,
            ObligationStatus.INCONCLUSIVE,
            ObligationStatus.APPROVED_BY_HUMAN,
        ]
    ),
)


def _build_obligation_from_spec(
    idx: int,
    severity: Severity,
    target_status: ObligationStatus,
    commit: CommitIdentity,
) -> VerificationObligation:
    obl = make_proposed_obligation(f"OBL-{idx}", severity)
    if target_status == ObligationStatus.PROPOSED:
        return obl
    if target_status == ObligationStatus.NOT_RUN:
        return mark_obligation_not_run(obl, reason="No matching test")
    if target_status == ObligationStatus.BLOCKED:
        return block_obligation(obl, reason="Disallowed selector")

    sched = schedule_obligation(obl, candidate_test_id=f"tests/test_{idx}.py::test_fn")
    if target_status == ObligationStatus.SCHEDULED:
        return sched
    if target_status == ObligationStatus.PASSED:
        return reconcile_obligation_evidence(
            sched,
            evidence=make_sufficient_evidence(f"tests/test_{idx}.py::test_fn"),
            expected_commit=commit,
        )
    if target_status == ObligationStatus.FAILED:
        return reconcile_obligation_evidence(
            sched,
            evidence=ExecutionEvidence(
                test_node_id=f"tests/test_{idx}.py::test_fn",
                outcome=ExecutionOutcome.FAILED,
                sufficiency=EvidenceSufficiency.UNVERIFIED,
                provenance=make_provenance(),
                target_lines_exercised=False,
                target_branches_exercised=False,
                behavioral_assertion_verified=False,
                total_tests_in_report=10,
            ),
            expected_commit=commit,
        )
    if target_status == ObligationStatus.SKIPPED:
        return reconcile_obligation_evidence(
            sched,
            evidence=ExecutionEvidence(
                test_node_id=f"tests/test_{idx}.py::test_fn",
                outcome=ExecutionOutcome.SKIPPED,
                sufficiency=EvidenceSufficiency.UNVERIFIED,
                provenance=make_provenance(),
                target_lines_exercised=False,
                target_branches_exercised=False,
                behavioral_assertion_verified=False,
                total_tests_in_report=10,
            ),
            expected_commit=commit,
        )
    if target_status == ObligationStatus.INCONCLUSIVE:
        return reconcile_obligation_evidence(
            sched,
            evidence=ExecutionEvidence(
                test_node_id=f"tests/test_{idx}.py::test_fn",
                outcome=ExecutionOutcome.PASSED,
                sufficiency=EvidenceSufficiency.WEAK_EVIDENCE,
                provenance=make_provenance(),
                target_lines_exercised=True,
                target_branches_exercised=False,
                behavioral_assertion_verified=False,
                total_tests_in_report=10,
            ),
            expected_commit=commit,
        )
    if target_status == ObligationStatus.APPROVED_BY_HUMAN:
        inc = mark_obligation_not_run(obl, reason="Manual verification needed")
        return apply_human_approval(
            inc,
            approval=HumanApprovalRecord(
                reviewer_login="sec-lead",
                review_id=100 + idx,
                approved_head_sha=commit.head_sha,
                rationale="Reviewed manually",
                approved_at=NOW,
            ),
            expected_commit=commit,
        )
    raise AssertionError(f"Unhandled status: {target_status}")


@settings(max_examples=500, deadline=None)
@given(
    specs=st.lists(OBLIGATION_SPEC_STRATEGY, min_size=1, max_size=12),
    strict_mode=st.booleans(),
    completeness=st.sampled_from(list(AnalysisCompleteness)),
)
def test_property_no_unverified_critical_or_high_obligation_ever_yields_success_or_neutral(
    specs: list[tuple[Severity, ObligationStatus]],
    strict_mode: bool,
    completeness: AnalysisCompleteness,
) -> None:
    commit = make_commit()
    obligations = [
        _build_obligation_from_spec(i, sev, status, commit)
        for i, (sev, status) in enumerate(specs)
    ]
    policy = ConclusionPolicyConfig(strict_blocking_mode=strict_mode)

    evaluation = evaluate_verification_run(
        commit=commit,
        obligations=obligations,
        analysis_completeness=completeness,
        policy_config=policy,
    )

    has_failed_or_blocked = any(
        o.status in (ObligationStatus.FAILED, ObligationStatus.BLOCKED) for o in obligations
    )
    has_unverified_mandatory = any(
        o.severity in (Severity.CRITICAL, Severity.HIGH)
        and o.status not in (ObligationStatus.PASSED, ObligationStatus.APPROVED_BY_HUMAN)
        for o in obligations
    )

    if has_failed_or_blocked:
        assert evaluation.github_conclusion == GitHubCheckConclusion.FAILURE

    if has_unverified_mandatory or completeness != AnalysisCompleteness.COMPLETE:
        assert evaluation.github_conclusion not in (
            GitHubCheckConclusion.SUCCESS,
            GitHubCheckConclusion.NEUTRAL,
        )
""",
    "docs/verification-semantics.md": """\
# Verification Semantics & State Machine Specification (Phase 1A)

This document defines the deterministic verification semantics implemented in
`verification_core.domain`.

## 1. Core Invariants

1. **No Untrusted `PASSED` Assignment:** A `VerificationObligation` starts in `PROPOSED` and can
   reach `PASSED` only via `reconcile_obligation_evidence()` after verifying platform provenance
   (`workflow_head_sha == commit.head_sha`, `workflow_base_sha == commit.base_sha`, trusted base
   workflow, untampered test harness) and `EvidenceSufficiency.SUFFICIENT`.
2. **Coverage Is Necessary, Not Sufficient:** A passing test that fails to exercise modified target
   lines (`COVERAGE_MISS`), fails to exercise modified branches, or lacks behavioral assertion
   confirmation (`WEAK_EVIDENCE`) transitions to `INCONCLUSIVE`, never `PASSED`.
3. **Human Governance vs. Machine Proof:** `APPROVED_BY_HUMAN` and `WAIVED_BY_POLICY` are modeled
   and reported separately from machine-verified `PASSED` obligations. `CRITICAL` and `HIGH`
   obligations cannot be statically waived via `WAIVED_BY_POLICY`.
4. **Separation of Internal State and External GitHub API Conclusions:** Superseded runs transition
   internally to `InternalRunOutcome.STALE_SUPERSEDED` (and obligations to
   `ObligationStatus.STALE`), while mapping externally to `GitHubCheckConclusion.CANCELLED`
   (`"cancelled"`). The system never emits `"stale"` as a GitHub Check Run conclusion because
   GitHub reserves that value for internal platform use.
5. **Safe Empty-Obligation Handling:** `GitHubCheckConclusion.NEUTRAL` for an empty obligation set
   is permitted **only** when `analysis_completeness == AnalysisCompleteness.COMPLETE`,
   `policy_valid == True`, and `has_unsupported_critical_changes == False`.

## 2. Obligation State Transitions

| From State | Permitted Target States | Transition Guard |
| :--- | :--- | :--- |
| `PROPOSED` | `SCHEDULED`, `BLOCKED`, `NOT_RUN`, `WAIVED_BY_POLICY`, `STALE` | Scheduling requires a non-empty `candidate_test_id`; policy waivers forbid `CRITICAL`/`HIGH`. |
| `SCHEDULED` | `PASSED`, `FAILED`, `SKIPPED`, `BLOCKED`, `NOT_RUN`, `INCONCLUSIVE`, `STALE` | `PASSED` requires authentic commit-bound provenance + `ExecutionOutcome.PASSED` + `EvidenceSufficiency.SUFFICIENT`. Contradictory evidence fails closed to `FAILED`. |
| `NOT_RUN` / `SKIPPED` | `APPROVED_BY_HUMAN`, `WAIVED_BY_POLICY`, `STALE` | `APPROVED_BY_HUMAN` requires SHA-matching `HumanApprovalRecord` permitted by policy. |
| `INCONCLUSIVE` | `APPROVED_BY_HUMAN`, `STALE` | Requires SHA-matching `HumanApprovalRecord`. |
| `PASSED` / `FAILED` / `BLOCKED` / `APPROVED_BY_HUMAN` / `WAIVED_BY_POLICY` | `STALE` | Terminal unless superseded by a newer commit on the pull request. |

## 3. Conclusion Priority Order (`evaluate_verification_run`)

1. **Superseded Run (`superseded_by_sha` present or `STALE` obligations):** Internal
   `STALE_SUPERSEDED` -> GitHub `cancelled`.
2. **Invalid Base Policy (`policy_valid == False`):** Internal `FAILED_VERIFICATION` -> GitHub
   `failure`.
3. **Any `FAILED` or `BLOCKED` Obligation:** Internal `FAILED_VERIFICATION` -> GitHub `failure`.
4. **Incomplete/Truncated Context, Analyzer Error, or Unsupported Critical Change:** Internal
   `ACTION_REQUIRED_MISSING_EVIDENCE` (or `FAILED_VERIFICATION` in strict mode) -> GitHub
   `action_required` (or `failure`). Never `neutral` or `success`.
5. **Any Unverified Mandatory Obligation (`CRITICAL`/`HIGH` in `PROPOSED`, `SCHEDULED`, `NOT_RUN`,
   `SKIPPED`, or `INCONCLUSIVE`):** Internal `ACTION_REQUIRED_MISSING_EVIDENCE` (or
   `FAILED_VERIFICATION` in strict mode) -> GitHub `action_required` (or `failure`).
6. **Zero Obligations after Confirmed Complete Analysis:** Internal `NEUTRAL_NO_BEHAVIORAL_CHANGE`
   -> GitHub `neutral`.
7. **All Mandatory Satisfied, >=1 Unverified Advisory (`MEDIUM`/`LOW`):** Internal
   `NEUTRAL_ADVISORY_GAPS_ONLY` -> GitHub `neutral` (when `advisory_gaps_return_neutral=True`).
8. **All Mandatory Obligations Satisfied (`PASSED` or policy-permitted `APPROVED_BY_HUMAN`):**
   Internal `VERIFIED_SUCCESS` -> GitHub `success`.
""",
}


def extract_and_bundle(
    target_dir: Path,
    zip_name: str,
    create_zip: bool = True,
    overwrite: bool = False,
) -> None:
    """Extract the legacy Phase 1A bootstrap without silently clobbering newer work."""
    target_dir = target_dir.resolve()
    if not zip_name or Path(zip_name).name != zip_name:
        raise ValueError("zip_name must be a filename, not a path.")

    # Preflight every destination before writing anything. This script contains an
    # older Phase 1A snapshot and must not silently replace the current Phase 1B files.
    conflicts: list[str] = []
    for rel_path, content in PHASE_1A_FILES.items():
        dest_path = target_dir / rel_path
        if dest_path.exists() and dest_path.read_bytes() != content.encode("utf-8"):
            conflicts.append(rel_path)

    zip_path = target_dir / zip_name
    if create_zip and zip_path.exists() and not overwrite:
        conflicts.append(zip_name)

    if conflicts and not overwrite:
        listed = "\n".join(f"  - {name}" for name in conflicts)
        raise FileExistsError(
            "Refusing to overwrite existing project files. This extractor contains a "
            "legacy Phase 1A snapshot. Choose a clean --target-dir or pass "
            "--force-overwrite only if replacing these files is intentional.\n"
            f"Conflicting paths:\n{listed}"
        )

    target_dir.mkdir(parents=True, exist_ok=True)
    print(f"Extracting Phase 1A files into: {target_dir}\n")
    print(f"{'File Path':<48} | {'Size (B)':>8} | {'SHA-256 (first 12)'}")
    print("-" * 80)

    for rel_path, content in PHASE_1A_FILES.items():
        dest_path = target_dir / rel_path
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        encoded = content.encode("utf-8")
        if not dest_path.exists() or dest_path.read_bytes() != encoded:
            dest_path.write_bytes(encoded)
        digest = hashlib.sha256(encoded).hexdigest()[:12]
        print(f"{rel_path:<48} | {len(encoded):>8} | {digest}")

    if create_zip:
        with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for rel_path, content in PHASE_1A_FILES.items():
                zf.writestr(rel_path, content.encode("utf-8"))
        print("-" * 80)
        print(f"Created ZIP bundle: {zip_path} ({zip_path.stat().st_size} bytes)")

    print("\nNext steps to verify Phase 1A locally:")
    print("  1. python -m venv .venv")
    print("  2. .venv\\Scripts\\activate      # (Windows) or: source .venv/bin/activate (Linux/macOS)")
    print('  3. pip install -e ".[dev]"')
    print("  4. ruff format --check src tests && ruff check src tests")
    print("  5. mypy --strict src tests")
    print("  6. pytest --cov=src/verification_core --cov-report=term-missing")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract Phase 1A files and build a local ZIP archive."
    )
    parser.add_argument(
        "--target-dir",
        type=Path,
        default=Path("."),
        help="Directory where files and folders will be extracted (default: current directory).",
    )
    parser.add_argument(
        "--zip-name",
        type=str,
        default="ai-pr-verification-agent-phase-1a.zip",
        help="Filename for the generated ZIP archive.",
    )
    parser.add_argument(
        "--no-zip",
        action="store_true",
        help="Extract files and folders only without creating the .zip archive.",
    )
    parser.add_argument(
        "--force-overwrite",
        action="store_true",
        help="Explicitly allow overwriting conflicting files from the legacy Phase 1A snapshot.",
    )
    args = parser.parse_args()
    extract_and_bundle(
        target_dir=args.target_dir,
        zip_name=args.zip_name,
        create_zip=not args.no_zip,
        overwrite=args.force_overwrite,
    )


if __name__ == "__main__":
    main()
