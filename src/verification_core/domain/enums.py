"""Enumerations for obligation lifecycle, evidence sufficiency, and run conclusions."""

from __future__ import annotations

from enum import StrEnum


class Severity(StrEnum):
    """Risk severity of a behavioral verification obligation."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

    def is_mandatory_by_default(self) -> bool:
        """Return True if this severity blocks success unless verified or approved."""
        return self in (Severity.CRITICAL, Severity.HIGH)


class ObligationSource(StrEnum):
    """Origin of a proposed verification obligation."""

    DETERMINISTIC_POLICY = "deterministic_policy"
    LLM_HYPOTHESIS = "llm_hypothesis"
    GOVERNANCE_RULE = "governance_rule"


class ObligationStatus(StrEnum):
    """Finite states of a verification obligation."""

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
    """Raw test runner outcome for an executed check."""

    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    SKIPPED = "skipped"


class EvidenceSufficiency(StrEnum):
    """Evaluated quality and completeness of execution evidence for an obligation."""

    UNVERIFIED = "unverified"
    COVERAGE_MISS = "coverage_miss"
    WEAK_EVIDENCE = "weak_evidence"
    PARTIAL_EVIDENCE = "partial_evidence"
    SUFFICIENT = "sufficient"
    CONTRADICTORY = "contradictory"
    MALFORMED = "malformed"


class AnalysisCompleteness(StrEnum):
    """Status of diff and repository context collection during verification planning."""

    COMPLETE = "complete"
    TRUNCATED = "truncated"
    INCOMPLETE = "incomplete"
    ANALYZER_ERROR = "analyzer_error"


class InternalRunOutcome(StrEnum):
    """Internal domain conclusion for a verification run (includes STALE_SUPERSEDED)."""

    VERIFIED_SUCCESS = "verified_success"
    NEUTRAL_NO_BEHAVIORAL_CHANGE = "neutral_no_behavioral_change"
    NEUTRAL_ADVISORY_GAPS_ONLY = "neutral_advisory_gaps_only"
    ACTION_REQUIRED_MISSING_EVIDENCE = "action_required_missing_evidence"
    FAILED_VERIFICATION = "failed_verification"
    STALE_SUPERSEDED = "stale_superseded"


class GitHubCheckConclusion(StrEnum):
    """Valid user-settable GitHub Check Run API conclusion values.

    Note: GitHub reserves 'stale' for internal platform usage; superseded runs must
    use CANCELLED when publishing to the GitHub Checks API.
    """

    SUCCESS = "success"
    NEUTRAL = "neutral"
    ACTION_REQUIRED = "action_required"
    FAILURE = "failure"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    SKIPPED = "skipped"
