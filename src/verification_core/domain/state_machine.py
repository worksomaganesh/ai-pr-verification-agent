"""Deterministic obligation state machine and Check Run conclusion engine."""

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
    """Validate that transitioning from `current` to `target` is permitted."""
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
    """Transition a PROPOSED obligation to SCHEDULED with a validated test selector."""
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
    """Transition a PROPOSED or SCHEDULED obligation to BLOCKED due to policy violation."""
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
    """Transition a PROPOSED or SCHEDULED obligation to NOT_RUN."""
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
    """Reconcile a SCHEDULED obligation against platform-verified execution evidence."""
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
    if evidence.total_tests_in_report == 0 or evidence.sufficiency == EvidenceSufficiency.MALFORMED:
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
            status_reason=evidence.failure_summary or f"Test execution {evidence.outcome.value}.",
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
    """Apply an explicit, SHA-bound human approval to an unverified obligation."""
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

    if obligation.severity == Severity.HIGH and not policy_config.allow_human_approval_for_high:
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
    """Apply a static policy waiver to a non-critical/non-high obligation."""
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
    """Mark an obligation as STALE because a newer commit was pushed to the PR."""
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
    """Verify that any PASSED, APPROVED_BY_HUMAN, or WAIVED_BY_POLICY state matches `commit`."""
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
            obligation.severity == Severity.HIGH and not policy_config.allow_human_approval_for_high
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
    """Construct a non-stale VerificationRunEvaluation with explicit typing."""
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
    """Deterministically compute the internal run outcome and GitHub Check Run conclusion."""
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
                raise DomainValidationError("superseded_by_sha must differ from commit.head_sha.")
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
    if analysis_completeness != AnalysisCompleteness.COMPLETE or has_unsupported_critical_changes:
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
