"""Worker-facing Phase III orchestration for authenticated Actions evidence.

This layer does not publish a Check Run or mark obligations passed. It verifies current PR
identity before and after network/download work, fetches the exact trusted workflow file from
the base SHA, rejects ambiguous artifacts, and returns validated evidence for reconciliation.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from typing import Protocol, cast

import yaml
from yaml.constructor import ConstructorError
from yaml.nodes import MappingNode

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
from verification_core.evidence import assess_evidence_sufficiency
from verification_core.security import scrub_secrets


class EvidenceIngestionServiceError(ValueError):
    """Raised when evidence collection is ambiguous, stale, or lacks trusted context."""


class _UniqueKeySafeLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate mapping keys instead of silently overriding them."""


def _construct_unique_mapping(
    loader: _UniqueKeySafeLoader, node: MappingNode, deep: bool = False
) -> dict[object, object]:
    mapping: dict[object, object] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in mapping
        except TypeError as exc:
            raise ConstructorError(
                None, None, "workflow YAML mapping keys must be hashable", key_node.start_mark
            ) from exc
        if duplicate:
            raise ConstructorError(
                None, None, f"duplicate workflow YAML key: {key!r}", key_node.start_mark
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeySafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_unique_mapping
)

_MAX_TRUSTED_WORKFLOW_BYTES = 256 * 1024
_PINNED_UPLOAD_ACTION = re.compile(r"actions/upload-artifact@[0-9a-f]{40}")
_PINNED_CHECKOUT_ACTION = re.compile(r"actions/checkout@[0-9a-f]{40}")
_REQUIRED_ARTIFACT_FILES = ("coverage-manifest.json", "junit.xml")
_REQUIRED_CHECKOUT_STEP = "Check out exact PR head"
_REQUIRED_TEST_STEP = "Run PR-head tests with per-test coverage"
_REQUIRED_EXPORT_STEP = "Export per-test evidence manifest"


def _workflow_mapping(value: object, field: str) -> Mapping[object, object]:
    if not isinstance(value, Mapping):
        raise EvidenceIngestionServiceError(f"Trusted workflow {field} must be a mapping.")
    return value


def _workflow_string_mapping(value: object, field: str) -> Mapping[str, object]:
    mapping = _workflow_mapping(value, field)
    if any(not isinstance(key, str) for key in mapping):
        raise EvidenceIngestionServiceError(
            f"Trusted workflow {field} must use string mapping keys."
        )
    return cast(Mapping[str, object], mapping)


def _validate_trusted_workflow_upload_contract(
    workflow_source: str, *, required_step_name: str, expected_artifact_name: str
) -> None:
    """Prove the base-SHA workflow has one pinned uploader for the exact evidence contract.

    This deliberately accepts a narrow workflow shape. Unknown YAML, duplicate keys, multiple
    uploaders, tag-based action references, dynamic artifact names, globs, and missing-file
    warning modes are rejected rather than guessed at.
    """
    if not isinstance(workflow_source, str) or not workflow_source:
        raise EvidenceIngestionServiceError("Trusted workflow source is missing.")
    try:
        source_bytes = workflow_source.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise EvidenceIngestionServiceError(
            "Trusted workflow source is not valid UTF-8 text."
        ) from exc
    if len(source_bytes) > _MAX_TRUSTED_WORKFLOW_BYTES:
        raise EvidenceIngestionServiceError("Trusted workflow source exceeds its size limit.")
    if (
        not isinstance(required_step_name, str)
        or not required_step_name.strip()
        or len(required_step_name) > 200
    ):
        raise EvidenceIngestionServiceError("Required evidence step name is invalid.")
    if (
        not isinstance(expected_artifact_name, str)
        or not expected_artifact_name.strip()
        or len(expected_artifact_name) > 200
    ):
        raise EvidenceIngestionServiceError("Expected evidence artifact name is invalid.")

    try:
        workflow_value = yaml.load(
            workflow_source,
            Loader=_UniqueKeySafeLoader,  # noqa: S506 — subclass of yaml.SafeLoader
        )
    except (yaml.YAMLError, RecursionError, TypeError, ValueError) as exc:
        raise EvidenceIngestionServiceError(
            "Trusted workflow YAML is malformed or ambiguous."
        ) from exc
    workflow = _workflow_mapping(workflow_value, "root")
    if "on" in workflow and True in workflow:
        raise EvidenceIngestionServiceError("Trusted workflow trigger declaration is ambiguous.")
    triggers = workflow.get("on", workflow.get(True))
    has_pull_request_trigger = (
        triggers == "pull_request"
        or (isinstance(triggers, list) and "pull_request" in triggers)
        or (
            isinstance(triggers, Mapping)
            and "pull_request" in triggers
            and triggers.get("pull_request") is not False
        )
    )
    if not has_pull_request_trigger:
        raise EvidenceIngestionServiceError("Trusted workflow must declare a pull_request trigger.")

    jobs = _workflow_string_mapping(workflow.get("jobs"), "jobs")
    if not jobs:
        raise EvidenceIngestionServiceError("Trusted workflow has no jobs.")
    named_steps: list[Mapping[str, object]] = []
    upload_steps: list[Mapping[str, object]] = []
    step_records: list[tuple[str, int, Mapping[str, object]]] = []
    for job_name, raw_job in jobs.items():
        job = _workflow_string_mapping(raw_job, f"job {job_name}")
        raw_steps = job.get("steps")
        if raw_steps is None:
            continue
        if not isinstance(raw_steps, list):
            raise EvidenceIngestionServiceError(
                f"Trusted workflow job {job_name} steps must be a list."
            )
        for index, raw_step in enumerate(raw_steps):
            step = _workflow_string_mapping(raw_step, f"job {job_name} step {index}")
            step_records.append((job_name, index, step))
            if step.get("name") == required_step_name:
                named_steps.append(step)
            uses = step.get("uses")
            if isinstance(uses, str) and (
                uses == "actions/upload-artifact" or uses.startswith("actions/upload-artifact@")
            ):
                upload_steps.append(step)

    if len(named_steps) != 1 or len(upload_steps) != 1 or named_steps[0] is not upload_steps[0]:
        raise EvidenceIngestionServiceError(
            "Trusted workflow must define exactly one required step and exactly one matching "
            "upload-artifact action."
        )
    upload_step = upload_steps[0]
    if "if" in upload_step:
        raise EvidenceIngestionServiceError("Trusted evidence upload step must not be conditional.")
    action_ref = upload_step.get("uses")
    if not isinstance(action_ref, str) or not _PINNED_UPLOAD_ACTION.fullmatch(action_ref):
        raise EvidenceIngestionServiceError(
            "Trusted upload-artifact action must be pinned to a full immutable commit SHA."
        )
    inputs = _workflow_string_mapping(upload_step.get("with"), "upload step inputs")
    if inputs.get("name") != expected_artifact_name:
        raise EvidenceIngestionServiceError(
            "Trusted upload step artifact name does not match the configured evidence name."
        )
    raw_path = inputs.get("path")
    if not isinstance(raw_path, str):
        raise EvidenceIngestionServiceError("Trusted upload step path must be a literal string.")
    paths = [line.strip() for line in raw_path.splitlines() if line.strip()]
    if sorted(paths) != sorted(_REQUIRED_ARTIFACT_FILES) or len(paths) != len(
        _REQUIRED_ARTIFACT_FILES
    ):
        raise EvidenceIngestionServiceError(
            "Trusted upload step must contain exactly junit.xml and coverage-manifest.json."
        )
    if inputs.get("if-no-files-found") != "error":
        raise EvidenceIngestionServiceError(
            "Trusted upload step must fail when an evidence file is missing."
        )
    # Trust the producer pipeline, not a standalone uploader. All steps must be unique,
    # ordered, unconditional, and co-located in one job so the uploaded files are derived
    # from the exact PR-head test invocation rather than another job or commit.
    records_by_name: dict[str, list[tuple[str, int, Mapping[str, object]]]] = {}
    required_names = (
        _REQUIRED_CHECKOUT_STEP,
        _REQUIRED_TEST_STEP,
        _REQUIRED_EXPORT_STEP,
        required_step_name,
    )
    for record in step_records:
        name = record[2].get("name")
        if name in required_names:
            records_by_name.setdefault(cast(str, name), []).append(record)
    if any(len(records_by_name.get(name, [])) != 1 for name in required_names):
        raise EvidenceIngestionServiceError(
            "Trusted workflow must define exactly one checkout, test, export, and upload step."
        )
    chain_records = [records_by_name[name][0] for name in required_names]
    if len({record[0] for record in chain_records}) != 1 or [
        record[1] for record in chain_records
    ] != sorted(record[1] for record in chain_records):
        raise EvidenceIngestionServiceError(
            "Trusted checkout, test, export, and upload steps must be ordered in one evidence job."
        )
    checkout_step, test_step, export_step, _ = (record[2] for record in chain_records)
    for step in (checkout_step, test_step, export_step):
        if "if" in step:
            raise EvidenceIngestionServiceError(
                "Trusted checkout, test, and export steps must not be conditional."
            )

    checkout_ref = checkout_step.get("uses")
    checkout_inputs = _workflow_string_mapping(
        checkout_step.get("with"), "exact-head checkout inputs"
    )
    if (
        not isinstance(checkout_ref, str)
        or not _PINNED_CHECKOUT_ACTION.fullmatch(checkout_ref)
        or checkout_inputs.get("repository")
        != "${{ github.event.pull_request.head.repo.full_name }}"
        or checkout_inputs.get("ref") != "${{ github.event.pull_request.head.sha }}"
        or checkout_inputs.get("persist-credentials") is not False
    ):
        raise EvidenceIngestionServiceError(
            "Trusted evidence job must check out the exact PR head with credentials disabled "
            "and a pinned checkout action."
        )

    test_command = test_step.get("run")
    if (
        not isinstance(test_command, str)
        or "pytest" not in test_command
        or "--cov-context=test" not in test_command
        or "--junitxml=junit.xml" not in test_command
    ):
        raise EvidenceIngestionServiceError(
            "Trusted evidence test step must run pytest with per-test coverage and junit.xml."
        )
    export_command = export_step.get("run")
    if (
        not isinstance(export_command, str)
        or "python -m verification_core.manifest_export" not in export_command
        or "--coverage-data .coverage" not in export_command
        or "--junit junit.xml" not in export_command
        or "${{ github.event.pull_request.head.sha }}" not in export_command
        or "--output coverage-manifest.json" not in export_command
    ):
        raise EvidenceIngestionServiceError(
            "Trusted evidence export step must create the manifest for the exact PR head."
        )


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


def _assert_workflow_run_unchanged(
    actions: ActionsReader,
    repository: str,
    workflow_run_id: int,
    original_run: Mapping[str, object],
) -> None:
    """Reject evidence collected across two different workflow-run attempts or identities."""
    original_attempt = original_run.get("run_attempt")
    if type(original_attempt) is not int or original_attempt < 1:
        raise EvidenceIngestionServiceError("Workflow run attempt is missing or invalid.")
    current_run = actions.get_workflow_run(repository, workflow_run_id)
    identity_fields = (
        "id",
        "workflow_id",
        "run_attempt",
        "path",
        "event",
        "status",
        "conclusion",
        "head_sha",
    )
    if any(current_run.get(field) != original_run.get(field) for field in identity_fields):
        raise EvidenceIngestionServiceError(
            "Workflow run identity or attempt changed during evidence ingestion; "
            "discard this evidence."
        )


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
        _validate_trusted_workflow_upload_contract(
            workflow_source,
            required_step_name=required_step_name,
            expected_artifact_name=expected_artifact_name,
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
        _assert_workflow_run_unchanged(actions, commit.repo_full_name, workflow_run_id, run_payload)
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

    __slots__ = ("check_run_id", "evaluation", "ledger_persisted")

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
        f"- `{obligation.obligation_id}`: `{obligation.status.value}`" for obligation in obligations
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
            "obligations": sorted((item.obligation_id, item.status.value) for item in obligations),
        }
        decision_digest = hashlib.sha256(
            json.dumps(decision_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
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
