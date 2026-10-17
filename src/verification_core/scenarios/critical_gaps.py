"""Adversarial scenario for missing critical verification obligations."""

from __future__ import annotations

from dataclasses import dataclass

from verification_core.domain.enums import AnalysisCompleteness, GitHubCheckConclusion, ObligationSource, Severity
from verification_core.domain.models import CommitIdentity, VerificationObligation
from verification_core.domain.state_machine import evaluate_verification_run


@dataclass(frozen=True, slots=True)
class ScenarioResult:
    """Outcome of the 140-unrelated-passes / two-critical-gaps scenario."""

    unrelated_passing_tests: int
    missing_critical_obligations: tuple[str, ...]
    conclusion: GitHubCheckConclusion
    summary_rationale: str


def run_missing_critical_obligations_scenario() -> ScenarioResult:
    """Passing unrelated tests cannot satisfy missing webhook and authorization obligations."""
    commit = CommitIdentity(
        repo_full_name="example/service",
        pr_number=42,
        base_sha="1" * 40,
        head_sha="2" * 40,
        policy_sha256="a" * 64,
    )
    obligations = (
        VerificationObligation.propose(
            obligation_id="OBL-WHK-01",
            category="webhook_idempotency",
            description="Duplicate webhook event IDs must not process an event twice.",
            severity=Severity.CRITICAL,
            source=ObligationSource.DETERMINISTIC_POLICY,
            affected_files=("src/webhooks.py",),
            candidate_test_id="tests/test_webhooks.py::test_duplicate_event_is_ignored",
        ),
        VerificationObligation.propose(
            obligation_id="OBL-AUTH-01",
            category="authorization",
            description="A user cannot access another user's subscription.",
            severity=Severity.CRITICAL,
            source=ObligationSource.DETERMINISTIC_POLICY,
            affected_files=("src/subscriptions.py",),
            candidate_test_id="tests/test_authz.py::test_cross_user_access_returns_403",
        ),
    )
    evaluation = evaluate_verification_run(
        commit=commit,
        obligations=obligations,
        analysis_completeness=AnalysisCompleteness.COMPLETE,
        policy_valid=True,
        has_unsupported_critical_changes=False,
    )
    return ScenarioResult(
        unrelated_passing_tests=140,
        missing_critical_obligations=tuple(sorted(evaluation.unverified_mandatory_ids)),
        conclusion=evaluation.github_conclusion,
        summary_rationale=evaluation.summary_rationale,
    )
