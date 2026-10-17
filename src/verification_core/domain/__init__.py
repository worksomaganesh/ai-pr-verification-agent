"""Pure deterministic domain models, enums, and state machine for PR verification."""

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
