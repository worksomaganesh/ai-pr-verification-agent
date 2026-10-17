"""Immutable, strictly validated domain models for PR verification."""

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
    """Raised when a domain object violates structural or security invariants."""


class InvalidStateTransitionError(DomainValidationError):
    """Raised when an invalid or forbidden state transition is attempted."""


def validate_git_sha(value: str, field_name: str) -> None:
    """Ensure value is a canonical 40-character lowercase hexadecimal Git SHA."""
    if not _GIT_SHA_RE.match(value):
        raise DomainValidationError(
            f"{field_name} must be a 40-character lowercase hex SHA, got {value!r}."
        )


def validate_sha256(value: str, field_name: str) -> None:
    """Ensure value is a canonical 64-character lowercase hexadecimal SHA-256 digest."""
    if not _SHA256_RE.match(value):
        raise DomainValidationError(
            f"{field_name} must be a 64-character lowercase hex SHA-256, got {value!r}."
        )


def _require_non_empty(value: str, field_name: str) -> None:
    if not value or not value.strip():
        raise DomainValidationError(f"{field_name} must be a non-empty string.")


@dataclass(frozen=True, slots=True, kw_only=True)
class CommitIdentity:
    """Immutable binding of a verification run to a repository, PR, commits, and policy."""

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
    """Platform-verified metadata from the GitHub Actions control plane."""

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
        """Return True iff the workflow executed against the exact PR base and head SHAs."""
        return (
            self.workflow_head_sha == commit.head_sha
            and self.workflow_base_sha == commit.base_sha
        )

    def is_authentic_and_trusted(self, commit: CommitIdentity) -> bool:
        """Return True iff platform metadata matches the commit and passed integrity checks."""
        return (
            self.matches_commit(commit)
            and self.is_trusted_workflow_from_base
            and self.harness_untampered
            and self.step_completed_cleanly
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class ExecutionEvidence:
    """Immutable record of a test execution and its evaluated behavioral sufficiency."""

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
    """Explicit audit record of an authorized maintainer approving an unverified obligation."""

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
    """Audit record for a non-mandatory obligation waived by a base-branch policy rule."""

    policy_rule_id: str
    policy_sha256: str
    rationale: str

    def __post_init__(self) -> None:
        _require_non_empty(self.policy_rule_id, "policy_rule_id")
        validate_sha256(self.policy_sha256, "policy_sha256")
        _require_non_empty(self.rationale, "rationale")


@dataclass(frozen=True, slots=True, kw_only=True)
class VerificationObligation:
    """A specific behavioral claim that must be verified for a pull request."""

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
        """Safe factory for creating newly proposed obligations in status PROPOSED."""
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
    """Policy parameters governing how obligation states map to run conclusions."""

    strict_blocking_mode: bool = False
    treat_medium_as_mandatory: bool = False
    allow_human_approval_for_critical: bool = True
    allow_human_approval_for_high: bool = True
    advisory_gaps_return_neutral: bool = True

    def is_severity_mandatory(self, severity: Severity) -> bool:
        """Return True if the given severity is mandatory under this policy."""
        if severity in (Severity.CRITICAL, Severity.HIGH):
            return True
        return severity == Severity.MEDIUM and self.treat_medium_as_mandatory


@dataclass(frozen=True, slots=True, kw_only=True)
class VerificationRunEvaluation:
    """Deterministic evaluation result for a pull request verification run."""

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
