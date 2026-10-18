"""Worker-facing Phase III orchestration for authenticated Actions evidence.

This layer does not publish a Check Run or mark obligations passed. It verifies current PR
identity before and after network/download work, fetches the exact trusted workflow file from
the base SHA, rejects ambiguous artifacts, and returns validated evidence for reconciliation.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from typing import Protocol

from verification_core.actions_evidence import (
    ActionsEvidenceError,
    AuthenticatedEvidenceArtifact,
    ingest_authenticated_artifact,
)
from verification_core.domain.models import CommitIdentity


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


def _assert_current_pull_request(github: PullRequestReader, commit: CommitIdentity) -> None:
    pr = _mapping(github.get_pull_request(commit.repo_full_name, commit.pr_number), "pull request")
    base = _mapping(pr.get("base"), "pull request base")
    head = _mapping(pr.get("head"), "pull request head")
    if pr.get("state") != "open":
        raise EvidenceIngestionServiceError("Pull request is no longer open.")
    if base.get("sha") != commit.base_sha or head.get("sha") != commit.head_sha:
        raise EvidenceIngestionServiceError(
            "Pull request commits changed during evidence ingestion; discard this evidence."
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
