"""Worker-facing Phase III orchestration for authenticated Actions evidence.

This layer does not publish a Check Run or mark obligations passed. It verifies current PR
identity before and after network/download work, fetches the exact trusted workflow file from
the base SHA, rejects ambiguous artifacts, and returns validated evidence for reconciliation.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Protocol

from verification_core.actions_evidence import (
    ActionsEvidenceError,
    AuthenticatedEvidenceArtifact,
    ingest_authenticated_artifact,
)
from verification_core.coverage import CoverageManifestError, reconcile_test_coverage
from verification_core.domain.enums import (
    AnalysisCompleteness,
    EvidenceSufficiency,
    ExecutionOutcome,
    GitHubCheckConclusion,
    ObligationStatus,
)
from verification_core.domain.models import (
    CommitIdentity,
    ConclusionPolicyConfig,
    ExecutionEvidence,
    VerificationObligation,
    VerificationRunEvaluation,
)
from verification_core.domain.state_machine import (
    evaluate_verification_run,
    reconcile_obligation_evidence,
)
from verification_core.security import scrub_secrets
from verification_core.evidence import assess_evidence_sufficiency


class EvidenceIngestionServiceError(ValueError):
    """Raised when evidence collection is ambiguous, stale, or lacks trusted context."""


class PullRequestReader(Protocol):
    """Minimal GitHub read port used to validate PR identity and workflow source."""

    def get_pull_request(self, repository: str, pr_number: int) -> Mapping[str, object]: ...

    def get_file_content(self, repository: str, path: str, ref: str) -> str | None: ...


class ActionsReader(Protocol):
    """Minimal authenticated Actions API port needed for collecting one run's evidence."""

    def get_workflow_run(self, repository: str, run_id: int) -> Mapping[str, object]: ...

    def list_workflow_run_jobs(
        self, repository: str, run_id: int
    ) -> Sequence[Mapping[str, object]]: ...

    def list_workflow_run_artifacts(
        self, repository: str, run_id: int
    ) -> Sequence[Mapping[str, object]]: ...

    def download_workflow_artifact(self, repository: str, artifact_id: int) -> bytes: ...


class EvidenceLedgerPort(Protocol):
    """Persistence port for authenticated evidence; ingestion must never mark it passed."""

    def record_ingestion(
        self,
        *,
        commit: CommitIdentity,
        evidence: AuthenticatedEvidenceArtifact,
        workflow_definition_sha256: str,
        now: float | None = None,
    ) -> str: ...


class IngestedPullRequestEvidence:
    """Output carrying validated evidence and the digest of its base-commit workflow source."""

    __slots__ = ("evidence", "ledger_record_key", "workflow_definition_sha256")

    def __init__(
        self,
        evidence: AuthenticatedEvidenceArtifact,
        workflow_definition_sha256: str,
        ledger_record_key: str | None = None,
    ) -> None:
        if len(workflow_definition_sha256) != 64 or any(
            char not in "0123456789abcdef" for char in workflow_definition_sha256
        ):
            raise ValueError("workflow_definition_sha256 must be a lowercase SHA-256 digest")
        self.evidence = evidence
        self.workflow_definition_sha256 = workflow_definition_sha256
        self.ledger_record_key = ledger_record_key


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise EvidenceIngestionServiceError(f"{field} must be an object with string keys.")
    return value


def _assert_current_pull_request(
    github: PullRequestReader, commit: CommitIdentity
) -> Mapping[str, object]:
    pr = _mapping(github.get_pull_request(commit.repo_full_name, commit.pr_number), "pull request")
    base = _mapping(pr.get("base"), "pull request base")
    head = _mapping(pr.get("head"), "pull request head")
    if pr.get("state") != "open":
        raise EvidenceIngestionServiceError("Pull request is no longer open.")
    if base.get("sha") != commit.base_sha or head.get("sha") != commit.head_sha:
        raise EvidenceIngestionServiceError(
            "Pull request commits changed during evidence ingestion; discard this evidence."
        )
    return pr


def ingest_pull_request_run(
    *,
    github: PullRequestReader,
    actions: ActionsReader,
    commit: CommitIdentity,
    workflow_run_id: int,
    trusted_workflow_paths: Sequence[str],
    harness_sensitive_paths: Sequence[str],
    changed_paths: Sequence[str],
    expected_artifact_name: str = "verification-evidence",
    required_step_name: str = "Upload verification evidence",
    evidence_ledger: EvidenceLedgerPort | None = None,
    ledger_now: float | None = None,
) -> IngestedPullRequestEvidence:
    """Collect one run and bind it to the still-current PR commit.

    The github argument must be an authenticated read client; actions must be an authenticated
    Actions API client. Trusted workflow and sensitive paths must come from the validated policy
    read at commit.base_sha, never PR-head policy or artifact content.
    """
    if type(workflow_run_id) is not int or workflow_run_id < 1:
        raise EvidenceIngestionServiceError("workflow_run_id must be a positive integer.")
    if not trusted_workflow_paths:
        raise EvidenceIngestionServiceError("Trusted workflow policy is empty.")
    _assert_current_pull_request(github, commit)

    try:
        run_payload = actions.get_workflow_run(commit.repo_full_name, workflow_run_id)
        raw_path = run_payload.get("path")
        if not isinstance(raw_path, str) or not raw_path:
            raise EvidenceIngestionServiceError("Workflow run path is missing.")
        workflow_path = raw_path.split("@", maxsplit=1)[0]
        if workflow_path not in trusted_workflow_paths:
            raise EvidenceIngestionServiceError(
                "Workflow run path is not present in the trusted base policy."
            )
        workflow_source = github.get_file_content(
            commit.repo_full_name, workflow_path, commit.base_sha
        )
        if not isinstance(workflow_source, str) or not workflow_source:
            raise EvidenceIngestionServiceError(
                "Trusted workflow file does not exist at the exact base SHA."
            )
        workflow_digest = hashlib.sha256(workflow_source.encode("utf-8")).hexdigest()

        jobs = actions.list_workflow_run_jobs(commit.repo_full_name, workflow_run_id)
        artifacts = actions.list_workflow_run_artifacts(commit.repo_full_name, workflow_run_id)
        matching = [
            artifact for artifact in artifacts if artifact.get("name") == expected_artifact_name
        ]
        if len(matching) != 1:
            raise EvidenceIngestionServiceError(
                "Evidence collection requires exactly one artifact with the configured name."
            )
        metadata = matching[0]
        artifact_id = metadata.get("id")
        if type(artifact_id) is not int or artifact_id < 1:
            raise EvidenceIngestionServiceError("Evidence artifact has an invalid identifier.")
        archive_bytes = actions.download_workflow_artifact(commit.repo_full_name, artifact_id)
        evidence = ingest_authenticated_artifact(
            commit=commit,
            run_payload=run_payload,
            jobs=jobs,
            artifact_metadata=metadata,
            archive_bytes=archive_bytes,
            trusted_workflow_paths=trusted_workflow_paths,
            harness_sensitive_paths=harness_sensitive_paths,
            changed_paths=changed_paths,
            expected_artifact_name=expected_artifact_name,
            expected_run_id=workflow_run_id,
            required_step_name=required_step_name,
        )
        _assert_current_pull_request(github, commit)
        ledger_record_key = None
        if evidence_ledger is not None:
            ledger_record_key = evidence_ledger.record_ingestion(
                commit=commit,
                evidence=evidence,
                workflow_definition_sha256=workflow_digest,
                now=ledger_now,
            )
        return IngestedPullRequestEvidence(
            evidence, workflow_digest, ledger_record_key=ledger_record_key
        )
    except ActionsEvidenceError as exc:
        raise EvidenceIngestionServiceError("Authenticated evidence failed validation.") from exc


def reconcile_authenticated_obligation(
    *,
    ingested: IngestedPullRequestEvidence,
    obligation: VerificationObligation,
    expected_commit: CommitIdentity,
    target_lines: dict[str, set[int]],
    target_branches: dict[str, set[str]],
    trusted_assertion_bindings: Mapping[str, str],
) -> VerificationObligation:
    """Reconcile one scheduled obligation using exact test identity and trusted assertion binding.

    Target locations must be derived from trusted diff/source analysis, not the artifact. The
    trusted_assertion_bindings mapping must come from independently validated base-policy or
    deterministic analysis; a manifest's own behavioral_assertion_verified boolean is never
    accepted as authority to mark an obligation passed.
    """
    if obligation.candidate_test_id is None:
        raise EvidenceIngestionServiceError(
            "Obligation has no exact candidate test selector; evidence cannot be reconciled."
        )
    node_id = obligation.candidate_test_id
    evidence = ingested.evidence
    if not evidence.provenance.is_authentic_and_trusted(expected_commit):
        raise EvidenceIngestionServiceError(
            "Evidence provenance is not authentic and bound to the expected commit."
        )
    try:
        reconciled = reconcile_test_coverage(
            junit_report=evidence.junit_report,
            manifest=evidence.coverage_manifest,
            expected_head_sha=expected_commit.head_sha,
            node_id=node_id,
            target_lines=target_lines,
            target_branches=target_branches,
        )
    except CoverageManifestError as exc:
        raise EvidenceIngestionServiceError(
            "Evidence cannot be reconciled against the expected test and target locations."
        ) from exc

    # Contradictions must never be overwritten by an optimistic assertion binding.
    if reconciled.sufficiency is EvidenceSufficiency.CONTRADICTORY:
        sufficiency = EvidenceSufficiency.CONTRADICTORY
        assertion_verified = False
    else:
        assertion_verified = trusted_assertion_bindings.get(obligation.obligation_id) == node_id
        sufficiency = (
        assess_evidence_sufficiency(
            total_tests=evidence.junit_report.total_tests,
            target_lines_exercised=reconciled.target_lines_exercised,
            target_branches_exercised=reconciled.target_branches_exercised,
            behavioral_assertion_verified=assertion_verified,
        )
            if reconciled.outcome is ExecutionOutcome.PASSED
            else EvidenceSufficiency.UNVERIFIED
        )
    execution = ExecutionEvidence(
        test_node_id=node_id,
        outcome=reconciled.outcome,
        sufficiency=sufficiency,
        provenance=evidence.provenance,
        target_lines_exercised=(
            reconciled.target_lines_exercised
            if sufficiency is not EvidenceSufficiency.CONTRADICTORY
            else False
        ),
        target_branches_exercised=(
            reconciled.target_branches_exercised
            if sufficiency is not EvidenceSufficiency.CONTRADICTORY
            else False
        ),
        behavioral_assertion_verified=assertion_verified,
        total_tests_in_report=evidence.junit_report.total_tests,
        failure_summary=None,
    )
    return reconcile_obligation_evidence(
        obligation,
        evidence=execution,
        expected_commit=expected_commit,
    )



class CheckRunPublisher(PullRequestReader, Protocol):
    """GitHub adapter that can re-read PR state and publish a completed Check Run."""

    def publish_check_run(
        self,
        *,
        repository: str,
        head_sha: str,
        name: str,
        conclusion: str,
        title: str,
        summary: str,
        external_id: str,
        details_url: str | None = None,
    ) -> int: ...


class ReconciliationLedgerPort(Protocol):
    """Optional durable sink for a verifier-computed terminal decision."""

    def record_reconciliation(
        self,
        record_key: str,
        *,
        status: str,
        reason: str,
        decision_sha256: str,
        now: float | None = None,
    ) -> None: ...


class PhaseThreePublicationResult:
    """Result of a deterministic final evaluation and its Check Run publication."""

    __slots__ = ("evaluation", "check_run_id", "ledger_persisted")

    def __init__(
        self,
        *,
        evaluation: VerificationRunEvaluation,
        check_run_id: int,
        ledger_persisted: bool | None,
    ) -> None:
        self.evaluation = evaluation
        self.check_run_id = check_run_id
        self.ledger_persisted = ledger_persisted


def publish_reconciled_verification(
    *,
    github: CheckRunPublisher,
    commit: CommitIdentity,
    obligations: Sequence[VerificationObligation],
    analysis_completeness: AnalysisCompleteness = AnalysisCompleteness.COMPLETE,
    policy_config: ConclusionPolicyConfig | None = None,
    policy_valid: bool = True,
    has_unsupported_critical_changes: bool = False,
    check_name: str = "AI PR Verification Agent",
    summary_context: str = "",
    decision_ledger: ReconciliationLedgerPort | None = None,
    ledger_record_key: str | None = None,
) -> PhaseThreePublicationResult:
    """Evaluate reconciled obligations and publish only after a last-moment PR SHA check.

    The caller must reconcile every obligation against authenticated evidence first. This function
    never reads a conclusion from the artifact or a model: the Phase I state machine is the only
    source of the GitHub conclusion. If PR base/head/state changed, no Check Run is published.
    A terminal ledger decision is written only after the Check Run API call succeeds.
    """
    if not isinstance(check_name, str) or not check_name.strip() or len(check_name) > 100:
        raise EvidenceIngestionServiceError("Check Run name must contain 1-100 characters.")
    if len(summary_context) > 30_000:
        raise EvidenceIngestionServiceError("Check Run summary context exceeds its size limit.")

    evaluation = evaluate_verification_run(
        commit=commit,
        obligations=obligations,
        analysis_completeness=analysis_completeness,
        policy_config=policy_config or ConclusionPolicyConfig(),
        policy_valid=policy_valid,
        has_unsupported_critical_changes=has_unsupported_critical_changes,
    )
    obligation_lines = [
        f"- `{obligation.obligation_id}`: `{obligation.status.value}`"
        for obligation in obligations
    ]
    summary_parts = [evaluation.summary_rationale]
    if obligation_lines:
        summary_parts.append("## Obligation states\n" + "\n".join(obligation_lines))
    if summary_context.strip():
        summary_parts.append(scrub_secrets(summary_context.strip()))
    summary = scrub_secrets("\n\n".join(summary_parts))[:60_000]
    external_id = f"ai-pr-verification-agent:phase3:{commit.pr_number}:{commit.head_sha}"

    # This must remain immediately adjacent to the external publish call. Do not insert ledger,
    # network, model, or other slow work between this exact-SHA check and publishing.
    fresh_pr = _assert_current_pull_request(github, commit)
    raw_url = fresh_pr.get("html_url")
    details_url = (
        raw_url
        if isinstance(raw_url, str)
        and raw_url.startswith("https://github.com/")
        and len(raw_url) <= 2_000
        else None
    )
    check_run_id = github.publish_check_run(
        repository=commit.repo_full_name,
        head_sha=commit.head_sha,
        name=check_name,
        conclusion=evaluation.github_conclusion.value,
        title=evaluation.summary_title,
        summary=summary,
        external_id=external_id,
        details_url=details_url,
    )
    if type(check_run_id) is not int or check_run_id < 1:
        raise EvidenceIngestionServiceError("GitHub returned an invalid Check Run identifier.")

    ledger_persisted: bool | None = None
    status_by_conclusion = {
        GitHubCheckConclusion.SUCCESS: "PASSED",
        GitHubCheckConclusion.FAILURE: "FAILED",
        GitHubCheckConclusion.CANCELLED: "STALE",
    }
    ledger_status = status_by_conclusion.get(evaluation.github_conclusion)
    if decision_ledger is not None and ledger_record_key is not None and ledger_status is not None:
        decision_payload = {
            "repo_full_name": commit.repo_full_name,
            "pr_number": commit.pr_number,
            "base_sha": commit.base_sha,
            "head_sha": commit.head_sha,
            "policy_sha256": commit.policy_sha256,
            "conclusion": evaluation.github_conclusion.value,
            "obligations": sorted(
                (item.obligation_id, item.status.value) for item in obligations
            ),
        }
        decision_digest = hashlib.sha256(
            json.dumps(
                decision_payload, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        ).hexdigest()
        try:
            decision_ledger.record_reconciliation(
                ledger_record_key,
                status=ledger_status,
                reason=evaluation.summary_rationale[:10_000],
                decision_sha256=decision_digest,
            )
            ledger_persisted = True
        except Exception:
            # The Check Run was already published. Keep the result visible and explicitly report
            # that durable decision recording needs an idempotent retry; do not leak exception text.
            ledger_persisted = False

    return PhaseThreePublicationResult(
        evaluation=evaluation,
        check_run_id=check_run_id,
        ledger_persisted=ledger_persisted,
    )
