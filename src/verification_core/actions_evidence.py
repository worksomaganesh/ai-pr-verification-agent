"""Phase III trust-boundary checks for Actions metadata and test-evidence artifacts.

Metadata must come from GitHub's authenticated Actions API. ZIP contents, JUnit, and coverage
manifests remain untrusted until this module binds them to that metadata and the exact PR commit.
"""

from __future__ import annotations

import hashlib
import io
import re
import stat
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import PurePosixPath

from verification_core.coverage import (
    CoverageManifest,
    CoverageManifestError,
    parse_coverage_manifest,
)
from verification_core.domain.models import CommitIdentity, WorkflowProvenance
from verification_core.evidence import EvidenceParseError, JUnitReport, parse_junit

MAX_ARTIFACT_ARCHIVE_BYTES = 20 * 1024 * 1024
MAX_ARTIFACT_MEMBERS = 16
MAX_ARTIFACT_MEMBER_BYTES = 5 * 1024 * 1024
MAX_ARTIFACT_EXPANDED_BYTES = 25 * 1024 * 1024
MAX_COMPRESSION_RATIO = 100
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_DIGEST_RE = re.compile(r"^sha256:([0-9a-f]{64})$")
_REQUIRED_MEMBERS = frozenset({"junit.xml", "coverage-manifest.json"})


class ActionsEvidenceError(ValueError):
    """Raised when Actions metadata or an artifact cannot be safely bound to a PR commit."""


@dataclass(frozen=True, slots=True)
class AuthenticatedEvidenceArtifact:
    """Artifact bytes parsed only after API metadata, digest, archive, and commit checks pass."""

    repository_full_name: str
    pull_request_number: int
    base_sha: str
    head_sha: str
    workflow_run_id: int
    workflow_id: int
    workflow_path: str
    workflow_attempt: int
    artifact_id: int
    artifact_name: str
    artifact_sha256: str
    provenance: WorkflowProvenance
    junit_report: JUnitReport
    coverage_manifest: CoverageManifest


def _object(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise ActionsEvidenceError(f"{field} must be an object.")
    return value


def _positive_integer(value: object, field: str) -> int:
    if type(value) is not int or value < 1:
        raise ActionsEvidenceError(f"{field} must be a positive integer.")
    return value


def _safe_repository_path(value: object, field: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 1000
        or value.startswith("/")
        or "\\" in value
        or "\x00" in value
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
        or any(part in {"", ".", ".."} for part in value.split("/"))
    ):
        raise ActionsEvidenceError(f"{field} is not a safe repository-relative path.")
    return value


def _matches_policy_path(path: str, rule: str) -> bool:
    if not rule or "\\" in rule or rule.startswith("/"):
        return False
    if rule.endswith("/"):
        return path.startswith(rule)
    return path == rule


def _run_workflow_path(value: object) -> str:
    if not isinstance(value, str) or not value or len(value) > 2000:
        raise ActionsEvidenceError("Workflow run path is missing or malformed.")
    # GitHub run payloads may suffix the workflow path with @ref. Trust the path separately
    # from commit identity, which is verified from the same authenticated response.
    path = value.split("@", maxsplit=1)[0]
    return _safe_repository_path(path, "workflow path")


def _find_pr_binding(run: Mapping[str, object], commit: CommitIdentity) -> None:
    raw_prs = run.get("pull_requests")
    if not isinstance(raw_prs, list):
        raise ActionsEvidenceError("Workflow run has no pull-request association list.")
    for raw_pr in raw_prs:
        item = _object(raw_pr, "workflow pull request")
        if item.get("number") != commit.pr_number:
            continue
        base = _object(item.get("base"), "workflow pull-request base")
        head = _object(item.get("head"), "workflow pull-request head")
        if base.get("sha") == commit.base_sha and head.get("sha") == commit.head_sha:
            return
    raise ActionsEvidenceError(
        "Workflow run is stale or is not bound to the exact PR base/head SHAs."
    )


def _validate_jobs(jobs: Sequence[Mapping[str, object]], required_step_name: str) -> None:
    if not required_step_name or len(required_step_name) > 200:
        raise ActionsEvidenceError("Required evidence step name is invalid.")
    for job in jobs:
        if job.get("status") != "completed" or job.get("conclusion") != "success":
            continue
        raw_steps = job.get("steps")
        if not isinstance(raw_steps, list):
            continue
        matching_steps = [
            _object(step, "workflow job step")
            for step in raw_steps
            if isinstance(step, Mapping) and step.get("name") == required_step_name
        ]
        if any(
            step.get("status") == "completed" and step.get("conclusion") == "success"
            for step in matching_steps
        ):
            return
    raise ActionsEvidenceError(
        "No successful completed Actions job contains the required evidence-upload step."
    )


def verify_workflow_provenance(
    *,
    run_payload: Mapping[str, object],
    jobs: Sequence[Mapping[str, object]],
    commit: CommitIdentity,
    trusted_workflow_paths: Sequence[str],
    harness_sensitive_paths: Sequence[str],
    changed_paths: Sequence[str],
    expected_run_id: int | None = None,
    required_step_name: str = "Upload verification evidence",
    recorded_at: datetime | None = None,
) -> WorkflowProvenance:
    """Validate API-sourced run/job metadata against policy and exact PR commit identity."""
    run = _object(run_payload, "workflow run")
    run_id = _positive_integer(run.get("id"), "workflow run id")
    _positive_integer(run.get("workflow_id"), "workflow id")
    _positive_integer(run.get("run_attempt"), "workflow run attempt")
    if expected_run_id is not None and run_id != expected_run_id:
        raise ActionsEvidenceError("Workflow run ID does not match the requested run.")
    repository = _object(run.get("repository"), "workflow repository")
    if repository.get("full_name") != commit.repo_full_name:
        raise ActionsEvidenceError("Workflow run belongs to a different repository.")
    if run.get("event") != "pull_request":
        raise ActionsEvidenceError("Only pull_request workflow runs can supply this evidence.")
    if run.get("status") != "completed" or run.get("conclusion") != "success":
        raise ActionsEvidenceError("Workflow run has not completed successfully.")
    if run.get("head_sha") != commit.head_sha:
        raise ActionsEvidenceError("Workflow run head SHA does not match the expected PR commit.")
    _find_pr_binding(run, commit)
    workflow_path = _run_workflow_path(run.get("path"))
    trusted_paths = tuple(
        _safe_repository_path(path, "trusted workflow policy path")
        for path in trusted_workflow_paths
    )
    sensitive_paths = tuple(
        rule
        for rule in harness_sensitive_paths
        if isinstance(rule, str) and rule and len(rule) <= 1000
    )
    if not trusted_paths or workflow_path not in trusted_paths:
        raise ActionsEvidenceError("Workflow path is not permitted by the trusted base policy.")
    if not sensitive_paths or not any(
        _matches_policy_path(workflow_path, rule) for rule in sensitive_paths
    ):
        raise ActionsEvidenceError(
            "Trusted workflow must also be protected by harness-sensitive policy."
        )
    normalized_changes = tuple(
        _safe_repository_path(path, "changed path") for path in changed_paths
    )
    touched = [
        change
        for change in normalized_changes
        if any(_matches_policy_path(change, rule) for rule in sensitive_paths)
    ]
    if touched:
        raise ActionsEvidenceError(
            "Evidence rejected because a harness-sensitive path changed in this pull request."
        )
    _validate_jobs(jobs, required_step_name)
    timestamp = recorded_at or datetime.now(UTC)
    if timestamp.tzinfo is None:
        raise ActionsEvidenceError("recorded_at must be timezone-aware.")
    return WorkflowProvenance(
        workflow_run_id=run_id,
        workflow_head_sha=commit.head_sha,
        workflow_base_sha=commit.base_sha,
        workflow_path=workflow_path,
        is_trusted_workflow_from_base=True,
        harness_untampered=True,
        step_completed_cleanly=True,
        recorded_at=timestamp,
    )


def _validate_artifact_metadata(
    *,
    artifact: Mapping[str, object],
    run_payload: Mapping[str, object],
    expected_run_id: int,
    expected_name: str,
) -> tuple[int, int, str]:
    artifact_id = _positive_integer(artifact.get("id"), "artifact id")
    if not expected_name or len(expected_name) > 200 or artifact.get("name") != expected_name:
        raise ActionsEvidenceError("Artifact name does not match the configured evidence artifact.")
    if artifact.get("expired") is not False:
        raise ActionsEvidenceError("Expired or malformed evidence artifacts are rejected.")
    size = artifact.get("size_in_bytes")
    if type(size) is not int or not 1 <= size <= MAX_ARTIFACT_ARCHIVE_BYTES:
        raise ActionsEvidenceError(
            "Artifact metadata size is invalid or exceeds the configured limit."
        )
    digest = artifact.get("digest")
    match = _DIGEST_RE.fullmatch(digest) if isinstance(digest, str) else None
    if match is None:
        raise ActionsEvidenceError("Artifact metadata has no valid GitHub SHA-256 digest.")
    workflow_run = _object(artifact.get("workflow_run"), "artifact workflow run")
    if workflow_run.get("id") != expected_run_id:
        raise ActionsEvidenceError("Artifact belongs to a different workflow run.")
    run_repository = _object(run_payload.get("repository"), "workflow repository")
    artifact_repository_id = workflow_run.get("repository_id")
    run_repository_id = run_repository.get("id")
    if (
        artifact_repository_id is not None
        and run_repository_id is not None
        and artifact_repository_id != run_repository_id
    ):
        raise ActionsEvidenceError("Artifact repository identity does not match the workflow run.")
    return artifact_id, size, match.group(1)


def _read_zip_members(archive_bytes: bytes) -> dict[str, bytes]:
    if not isinstance(archive_bytes, bytes) or not archive_bytes:
        raise ActionsEvidenceError("Artifact archive must be non-empty bytes.")
    if len(archive_bytes) > MAX_ARTIFACT_ARCHIVE_BYTES:
        raise ActionsEvidenceError("Artifact archive exceeds the download size limit.")
    try:
        zip_file = zipfile.ZipFile(io.BytesIO(archive_bytes))
    except (zipfile.BadZipFile, OSError, ValueError) as exc:
        raise ActionsEvidenceError("Artifact download is not a valid ZIP archive.") from exc

    contents: dict[str, bytes] = {}
    expanded_total = 0
    try:
        members = zip_file.infolist()
        if not members or len(members) > MAX_ARTIFACT_MEMBERS:
            raise ActionsEvidenceError("Artifact archive has an invalid number of members.")
        for member in members:
            raw_name = member.filename
            if not raw_name or len(raw_name) > 300 or "\\" in raw_name or "\x00" in raw_name:
                raise ActionsEvidenceError("Artifact archive contains an unsafe member path.")
            path = PurePosixPath(raw_name)
            if path.is_absolute() or any(
                part in {"", ".", ".."} for part in raw_name.rstrip("/").split("/")
            ):
                raise ActionsEvidenceError("Artifact archive contains a path-traversal member.")
            mode = (member.external_attr >> 16) & 0o170000
            if mode == stat.S_IFLNK or mode not in {0, stat.S_IFREG, stat.S_IFDIR}:
                raise ActionsEvidenceError("Artifact archive contains a non-regular file.")
            if member.flag_bits & 0x1:
                raise ActionsEvidenceError("Encrypted artifact archive members are forbidden.")
            if member.is_dir():
                continue
            if raw_name not in _REQUIRED_MEMBERS:
                raise ActionsEvidenceError("Artifact archive contains an unexpected file.")
            if raw_name in contents:
                raise ActionsEvidenceError("Artifact archive contains duplicate file names.")
            if member.file_size < 1 or member.file_size > MAX_ARTIFACT_MEMBER_BYTES:
                raise ActionsEvidenceError(
                    "Artifact file is empty or exceeds its configured size limit."
                )
            if (
                member.compress_size == 0
                or member.file_size / member.compress_size > MAX_COMPRESSION_RATIO
            ):
                raise ActionsEvidenceError("Artifact member exceeds the allowed compression ratio.")
            expanded_total += member.file_size
            if expanded_total > MAX_ARTIFACT_EXPANDED_BYTES:
                raise ActionsEvidenceError(
                    "Artifact archive expands beyond the configured size limit."
                )
            try:
                data = zip_file.read(member)
            except (zipfile.BadZipFile, OSError, RuntimeError) as exc:
                raise ActionsEvidenceError(
                    "Artifact ZIP member failed integrity validation."
                ) from exc
            if len(data) != member.file_size:
                raise ActionsEvidenceError("Artifact member size disagrees with its ZIP metadata.")
            contents[raw_name] = data
    finally:
        zip_file.close()
    if set(contents) != _REQUIRED_MEMBERS:
        raise ActionsEvidenceError(
            "Artifact archive must contain junit.xml and coverage-manifest.json."
        )
    return contents


def ingest_authenticated_artifact(
    *,
    commit: CommitIdentity,
    run_payload: Mapping[str, object],
    jobs: Sequence[Mapping[str, object]],
    artifact_metadata: Mapping[str, object],
    archive_bytes: bytes,
    trusted_workflow_paths: Sequence[str],
    harness_sensitive_paths: Sequence[str],
    changed_paths: Sequence[str],
    expected_artifact_name: str = "verification-evidence",
    expected_run_id: int | None = None,
    required_step_name: str = "Upload verification evidence",
    recorded_at: datetime | None = None,
) -> AuthenticatedEvidenceArtifact:
    """Bind GitHub API metadata, archive digest, JUnit, and per-test coverage to one commit.

    The caller must obtain run_payload, jobs, and artifact_metadata directly from an
    authenticated GitHub Actions API client. Webhook fields or artifact-embedded identity fields
    are not authority.
    """
    run = _object(run_payload, "workflow run")
    run_id = _positive_integer(run.get("id"), "workflow run id")
    if expected_run_id is not None and expected_run_id != run_id:
        raise ActionsEvidenceError("Workflow run ID does not match the requested run.")
    provenance = verify_workflow_provenance(
        run_payload=run,
        jobs=jobs,
        commit=commit,
        trusted_workflow_paths=trusted_workflow_paths,
        harness_sensitive_paths=harness_sensitive_paths,
        changed_paths=changed_paths,
        expected_run_id=run_id,
        required_step_name=required_step_name,
        recorded_at=recorded_at,
    )
    artifact_id, _reported_size, expected_digest = _validate_artifact_metadata(
        artifact=artifact_metadata,
        run_payload=run,
        expected_run_id=run_id,
        expected_name=expected_artifact_name,
    )
    actual_digest = hashlib.sha256(archive_bytes).hexdigest()
    if actual_digest != expected_digest:
        raise ActionsEvidenceError(
            "Downloaded artifact bytes do not match GitHub's SHA-256 digest."
        )
    files = _read_zip_members(archive_bytes)
    try:
        junit_report = parse_junit(files["junit.xml"])
        coverage_manifest = parse_coverage_manifest(files["coverage-manifest.json"])
    except (EvidenceParseError, CoverageManifestError) as exc:
        raise ActionsEvidenceError(
            "Artifact contains a malformed JUnit or coverage report."
        ) from exc
    if coverage_manifest.head_sha != commit.head_sha:
        raise ActionsEvidenceError("Coverage manifest is stale or bound to a different commit.")
    junit_nodes: dict[str, object] = {}
    for case in junit_report.cases:
        if case.node_id in junit_nodes:
            raise ActionsEvidenceError("JUnit report contains duplicate test node IDs.")
        junit_nodes[case.node_id] = case
    manifest_nodes = {case.node_id: case for case in coverage_manifest.cases}
    if set(junit_nodes) != set(manifest_nodes):
        raise ActionsEvidenceError("JUnit and coverage manifest test inventories do not match.")
    if any(
        junit_nodes[node_id].outcome != manifest_nodes[node_id].outcome for node_id in junit_nodes
    ):
        raise ActionsEvidenceError("JUnit and coverage manifest outcomes contradict each other.")
    return AuthenticatedEvidenceArtifact(
        repository_full_name=commit.repo_full_name,
        pull_request_number=commit.pr_number,
        base_sha=commit.base_sha,
        head_sha=commit.head_sha,
        workflow_run_id=run_id,
        workflow_id=_positive_integer(run.get("workflow_id"), "workflow id"),
        workflow_path=provenance.workflow_path,
        workflow_attempt=_positive_integer(run.get("run_attempt"), "workflow run attempt"),
        artifact_id=artifact_id,
        artifact_name=expected_artifact_name,
        artifact_sha256=actual_digest,
        provenance=provenance,
        junit_report=junit_report,
        coverage_manifest=coverage_manifest,
    )
