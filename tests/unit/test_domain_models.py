"""Unit tests for domain model immutability, SHA validation, and structural guards."""

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
