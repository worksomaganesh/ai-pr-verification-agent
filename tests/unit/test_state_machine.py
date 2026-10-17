"""Unit and Hypothesis property-based tests for the verification state machine."""

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
    assert obl_human.status is ObligationStatus.APPROVED_BY_HUMAN
    # Human approval is a distinct governance state, never a machine-verified pass.

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
    """Verify the canonical 4-part PR scenario prevents a false-green conclusion."""
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


@settings(max_examples=5000, deadline=None)
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
        _build_obligation_from_spec(i, sev, status, commit) for i, (sev, status) in enumerate(specs)
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
