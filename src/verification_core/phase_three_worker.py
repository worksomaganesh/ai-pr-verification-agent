"""Runtime orchestration joining authenticated Actions evidence to deterministic decisions.

This module coordinates existing Phase III primitives. It fails closed when the workflow is
unavailable, ambiguous, untrusted, or fails; only a single successful trusted workflow run can
supply evidence for obligation reconciliation.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Protocol

from verification_core.domain.enums import AnalysisCompleteness, ObligationStatus
from verification_core.domain.models import (
    CommitIdentity,
    ConclusionPolicyConfig,
    VerificationObligation,
)
from verification_core.domain.state_machine import schedule_obligation
from verification_core.phase_three import (
    ActionsReader,
    CheckRunPublisher,
    EvidenceIngestionServiceError,
    ReconciliationLedgerPort,
    EvidenceLedgerPort,
    PhaseThreePublicationResult,
    ingest_pull_request_run,
    publish_reconciled_verification,
    reconcile_authenticated_obligation,
)
from verification_core.planning import DiffAnalysis, PlanningResult
from verification_core.policy import VerificationPolicy
from verification_core.security import scrub_secrets


class PhaseThreeLedgerPort(EvidenceLedgerPort, ReconciliationLedgerPort, Protocol):
    """Evidence ledger supporting ingestion, terminal decision recording, and cleanup."""

    def close(self) -> None: ...


class WorkflowRunListingPort(ActionsReader, Protocol):
    """Additional Actions endpoint required for exact-head run discovery."""

    def list_pull_request_workflow_runs(
        self, repository: str, head_sha: str
    ) -> Sequence[Mapping[str, object]]: ...


class PhaseThreeRunPending(ValueError):
    """No exact-head workflow run is visible yet; retry the queued delivery."""


@dataclass(frozen=True, slots=True)
class PhaseThreeWorkerResult:
    """Final worker outcome plus evidence provenance useful to the run audit log."""

    publication: PhaseThreePublicationResult
    workflow_run_id: int | None
    evidence_record_key: str | None
    summary: str


def _workflow_path(value: object) -> str | None:
    if not isinstance(value, str) or not value or len(value) > 2_000:
        return None
    path = value.split("@", maxsplit=1)[0]
    if not path.startswith(".github/workflows/") or ".." in path.split("/"):
        return None
    return path


def _select_trusted_run(
    *,
    runs: Sequence[Mapping[str, object]],
    commit: CommitIdentity,
    trusted_paths: Sequence[str],
) -> Mapping[str, object] | None:
    """Return one exact-head trusted PR run; ambiguity is never resolved by guessing."""
    eligible = [
        run
        for run in runs
        if run.get("event") == "pull_request"
        and run.get("head_sha") == commit.head_sha
        and _workflow_path(run.get("path")) in trusted_paths
    ]
    if not eligible:
        return None
    if len(eligible) != 1:
        raise EvidenceIngestionServiceError(
            "More than one trusted workflow run matches this PR head; refusing to merge runs."
        )
    return eligible[0]


def _target_lines_for_obligation(
    obligation: VerificationObligation, analysis: DiffAnalysis
) -> dict[str, set[int]]:
    """Build added-line targets only from the bounded diff analyzed by the control plane."""
    affected = set(obligation.affected_files)
    targets: dict[str, set[int]] = {}
    for item in analysis.files:
        if item.filename not in affected:
            continue
        lines: set[int] = set()
        for start, end in item.changed_line_ranges:
            if type(start) is int and type(end) is int and 1 <= start <= end:
                lines.update(range(start, end + 1))
        if lines:
            targets[item.filename] = lines
    return targets


def _trusted_assertion_bindings(
    obligations: Sequence[VerificationObligation], policy: VerificationPolicy
) -> dict[str, str]:
    """Bind an obligation to a test only when trusted base policy matches selector/category/severity."""
    bindings: dict[str, str] = {}
    rules_by_selector = {rule.selector: rule for rule in policy.obligations}
    for obligation in obligations:
        selector = obligation.candidate_test_id
        if selector is None:
            continue
        rule = rules_by_selector.get(selector)
        if rule is None:
            continue
        if rule.category != obligation.category or rule.severity != obligation.severity.value:
            continue
        bindings[obligation.obligation_id] = selector
    return bindings


def _publish_without_accepted_evidence(
    *,
    github: CheckRunPublisher,
    commit: CommitIdentity,
    planning: PlanningResult,
    policy_config: ConclusionPolicyConfig,
    reason: str,
    workflow_run_id: int | None,
    check_name: str,
) -> PhaseThreeWorkerResult:
    """Publish an inconclusive/action-required outcome without treating missing evidence as pass."""
    safe_reason = scrub_secrets(reason)[:1_500]
    run_text = (
        f"Trusted workflow run: {workflow_run_id}. "
        if workflow_run_id is not None
        else "Trusted workflow run: unavailable. "
    )
    summary = (
        "Phase III did not accept execution evidence for this exact PR head. "
        + run_text
        + "Machine verification is withheld. Reason: "
        + safe_reason
    )
    publication = publish_reconciled_verification(
        github=github,
        commit=commit,
        obligations=planning.obligations,
        analysis_completeness=AnalysisCompleteness.INCOMPLETE,
        policy_config=policy_config,
        policy_valid=True,
        check_name=check_name,
        summary_context=summary,
    )
    return PhaseThreeWorkerResult(
        publication=publication,
        workflow_run_id=workflow_run_id,
        evidence_record_key=None,
        summary=summary,
    )


def process_pull_request_evidence(
    *,
    github: CheckRunPublisher,
    actions: WorkflowRunListingPort,
    commit: CommitIdentity,
    planning: PlanningResult,
    analysis: DiffAnalysis,
    policy: VerificationPolicy,
    evidence_ledger: PhaseThreeLedgerPort,
    policy_config: ConclusionPolicyConfig,
    check_name: str,
) -> PhaseThreeWorkerResult:
    """Run the complete one-run Phase III pipeline for a currently open, exact-head PR."""
    runs = actions.list_pull_request_workflow_runs(commit.repo_full_name, commit.head_sha)
    if not runs:
        raise PhaseThreeRunPending("No workflow run is visible for the exact PR head yet.")

    try:
        selected = _select_trusted_run(
            runs=runs,
            commit=commit,
            trusted_paths=policy.trusted_workflows,
        )
    except EvidenceIngestionServiceError as exc:
        return _publish_without_accepted_evidence(
            github=github,
            commit=commit,
            planning=planning,
            policy_config=policy_config,
            reason=str(exc),
            workflow_run_id=None,
            check_name=check_name,
        )

    if selected is None:
        return _publish_without_accepted_evidence(
            github=github,
            commit=commit,
            planning=planning,
            policy_config=policy_config,
            reason="No run used a workflow allowed by policy at the exact PR-head SHA.",
            workflow_run_id=None,
            check_name=check_name,
        )

    run_id = selected.get("id")
    if type(run_id) is not int or run_id < 1:
        return _publish_without_accepted_evidence(
            github=github,
            commit=commit,
            planning=planning,
            policy_config=policy_config,
            reason="The GitHub Actions API returned an invalid workflow-run ID.",
            workflow_run_id=None,
            check_name=check_name,
        )

    status = selected.get("status")
    if status in {"queued", "in_progress", "requested", "waiting", "pending"}:
        raise PhaseThreeRunPending("The trusted workflow run has not completed yet.")
    if status != "completed" or selected.get("conclusion") != "success":
        return _publish_without_accepted_evidence(
            github=github,
            commit=commit,
            planning=planning,
            policy_config=policy_config,
            reason="The trusted workflow did not finish successfully; no evidence can pass.",
            workflow_run_id=run_id,
            check_name=check_name,
        )

    changed_paths = tuple(item.filename for item in analysis.files)
    try:
        ingested = ingest_pull_request_run(
            github=github,
            actions=actions,
            commit=commit,
            workflow_run_id=run_id,
            trusted_workflow_paths=policy.trusted_workflows,
            harness_sensitive_paths=policy.harness_sensitive_paths,
            changed_paths=changed_paths,
            evidence_ledger=evidence_ledger,
        )
    except EvidenceIngestionServiceError as exc:
        # A completed but malformed/untrusted artifact is a terminal fail-closed result.
        # Transport/API errors are intentionally not swallowed and are eligible for retry.
        return _publish_without_accepted_evidence(
            github=github,
            commit=commit,
            planning=planning,
            policy_config=policy_config,
            reason=f"Authenticated evidence was rejected: {exc}",
            workflow_run_id=run_id,
            check_name=check_name,
        )

    reconciled: list[VerificationObligation] = []
    trusted_bindings = _trusted_assertion_bindings(planning.obligations, policy)
    for original in planning.obligations:
        if original.status == ObligationStatus.PROPOSED and original.candidate_test_id:
            scheduled = schedule_obligation(original)
        elif original.status == ObligationStatus.SCHEDULED:
            scheduled = original
        else:
            reconciled.append(original)
            continue
        try:
            reconciled.append(
                reconcile_authenticated_obligation(
                    ingested=ingested,
                    obligation=scheduled,
                    expected_commit=commit,
                    target_lines=_target_lines_for_obligation(scheduled, analysis),
                    # Branch targets are intentionally empty until the analyzer supplies
                    # trusted changed-branch identities; artifact claims cannot define them.
                    target_branches={},
                    trusted_assertion_bindings=trusted_bindings,
                )
            )
        except EvidenceIngestionServiceError as exc:
            reconciled.append(
                replace(
                    scheduled,
                    status=ObligationStatus.INCONCLUSIVE,
                    evidence=None,
                    status_reason=scrub_secrets(str(exc))[:1_000],
                )
            )

    evidence_summary = (
        f"Authenticated workflow run {run_id} supplied evidence bound to "
        f"head {commit.head_sha}; evidence record {ingested.ledger_record_key or 'not persisted'}. "
        "Obligations were reconciled independently. An artifact's own assertion flag is not trusted."
    )
    publication = publish_reconciled_verification(
        github=github,
        commit=commit,
        obligations=tuple(reconciled),
        analysis_completeness=planning.analysis_completeness,
        policy_config=policy_config,
        policy_valid=True,
        check_name=check_name,
        summary_context=evidence_summary,
        decision_ledger=evidence_ledger,
        ledger_record_key=ingested.ledger_record_key,
    )
    if ingested.ledger_record_key is not None and publication.ledger_persisted is False:
        # Publication is idempotent by external ID. Retrying lets the durable decision be recorded.
        raise EvidenceIngestionServiceError(
            "Check Run was published but durable reconciliation recording needs a retry."
        )
    return PhaseThreeWorkerResult(
        publication=publication,
        workflow_run_id=run_id,
        evidence_record_key=ingested.ledger_record_key,
        summary=evidence_summary,
    )
