"""Read-only GitHub context adapter contracts and bounded PR-context assembly.

A concrete HTTP client can implement GitHubReadClient using an installation token.
This module intentionally receives that client as a dependency: no global token,
network calls, or provider SDK are hidden inside the deterministic core.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any, Protocol, TypeGuard

from verification_core.domain.models import CommitIdentity
from verification_core.planning import ChangedFileInput, DiffLimits
from verification_core.policy import PolicyValidationError, VerificationPolicy, validate_policy_text
from verification_core.webhooks import PullRequestWebhookEvent

POLICY_PATH = ".verification-policy.yml"
DEFAULT_FILES_PER_PAGE = 100
MAX_FILES_API_PAGES = 30
_DEFAULT_DIFF_LIMITS = DiffLimits()


class GitHubContextError(ValueError):
    """Raised when trusted GitHub context cannot be assembled safely."""


class GitHubReadClient(Protocol):
    """Minimum read-only GitHub API surface needed for planning."""

    def get_pull_request(self, repository: str, pr_number: int) -> Mapping[str, Any]:
        """Return normalized PR metadata including base/head SHA and base ref."""

    def get_file_content(self, repository: str, path: str, ref: str) -> str | None:
        """Return text content at an exact commit ref, or None when absent."""

    def list_pull_request_files(
        self, repository: str, pr_number: int, *, page: int, per_page: int
    ) -> Sequence[Mapping[str, Any]]:
        """Return one page from GET /pulls/{number}/files."""


@dataclass(frozen=True, slots=True)
class PullRequestContext:
    """Immutable planning input assembled from the base policy and current PR head."""

    commit: CommitIdentity
    policy: VerificationPolicy
    changed_files: tuple[ChangedFileInput, ...]
    files_complete: bool
    pages_read: int
    policy_source_ref: str

    def __post_init__(self) -> None:
        if self.policy_source_ref != self.commit.base_sha:
            raise GitHubContextError("Policy must be loaded from the exact base SHA.")
        if not self.files_complete:
            raise GitHubContextError("Incomplete changed-file inventory cannot be marked complete.")
        if self.pages_read < 1:
            raise GitHubContextError("At least one changed-file page must be read.")


def _mapping(value: object, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or any(not isinstance(k, str) for k in value):
        raise GitHubContextError(f"{field} must be an object with string keys.")
    return value


def _is_file_page(value: object) -> TypeGuard[Sequence[Mapping[str, Any]]]:
    """Reject text-like sequences even if a broken client violates its protocol."""
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))


def _positive_int(value: object, field: str) -> int:
    if type(value) is not int or value < 1:
        raise GitHubContextError(f"{field} must be a positive integer.")
    return value


def _nonnegative_int(value: object, field: str) -> int:
    if type(value) is not int or value < 0:
        raise GitHubContextError(f"{field} must be a non-negative integer.")
    return value


def _required_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise GitHubContextError(f"{field} must be a non-empty string without NUL.")
    return value


def assemble_pull_request_context(
    event: PullRequestWebhookEvent,
    client: GitHubReadClient,
    *,
    diff_limits: DiffLimits = _DEFAULT_DIFF_LIMITS,
    files_per_page: int = DEFAULT_FILES_PER_PAGE,
    policy_path: str = POLICY_PATH,
) -> PullRequestContext:
    """Fetch and validate policy and changed-file context for the event's exact commits.

    The adapter re-reads PR metadata to detect a force-push/race after webhook delivery.
    Policy is always read from base_sha, never the untrusted head. All changed-file pages
    must be consumed; any API/schema/truncation failure raises instead of returning a
    deceptively complete context. The client must authenticate via a least-privilege
    GitHub App installation token and enforce response-size/timeouts.
    """
    if type(files_per_page) is not int or not 1 <= files_per_page <= 100:
        raise GitHubContextError("files_per_page must be between 1 and 100.")
    if policy_path != POLICY_PATH:
        raise GitHubContextError("Only the canonical .verification-policy.yml path is allowed.")

    pr = _mapping(
        client.get_pull_request(event.repository_full_name, event.pr_number),
        "pull_request",
    )
    base = _mapping(pr.get("base"), "pull_request.base")
    head = _mapping(pr.get("head"), "pull_request.head")
    base_sha = _required_string(base.get("sha"), "pull_request.base.sha")
    head_sha = _required_string(head.get("sha"), "pull_request.head.sha")
    base_ref = _required_string(base.get("ref"), "pull_request.base.ref")
    state = pr.get("state")
    if state != "open":
        raise GitHubContextError("Pull request is no longer open.")
    if base_sha != event.base_sha or head_sha != event.head_sha or base_ref != event.base_ref:
        raise GitHubContextError(
            "Pull request commits changed after webhook delivery; event is stale."
        )
    if head_sha == base_sha:
        raise GitHubContextError("Base and head commits must be distinct.")

    raw_policy = client.get_file_content(event.repository_full_name, policy_path, event.base_sha)
    if raw_policy is None:
        raise GitHubContextError(
            "Trusted base commit has no .verification-policy.yml; refusing to infer policy."
        )
    if not isinstance(raw_policy, str):
        raise GitHubContextError("Policy content must be decoded UTF-8 text.")
    try:
        policy = validate_policy_text(raw_policy)
    except PolicyValidationError as exc:
        raise GitHubContextError(f"Trusted base policy is invalid: {exc}") from exc

    policy_digest = hashlib.sha256(raw_policy.encode("utf-8")).hexdigest()
    commit = CommitIdentity(
        repo_full_name=event.repository_full_name,
        pr_number=event.pr_number,
        base_sha=event.base_sha,
        head_sha=event.head_sha,
        policy_sha256=policy_digest,
    )

    changed_files: list[ChangedFileInput] = []
    seen_paths: set[str] = set()
    pages_read = 0
    total_api_records = 0
    for page in range(1, MAX_FILES_API_PAGES + 1):
        records = client.list_pull_request_files(
            event.repository_full_name,
            event.pr_number,
            page=page,
            per_page=files_per_page,
        )
        if not _is_file_page(records):
            raise GitHubContextError("Changed-file API page must be a sequence of file objects.")
        pages_read += 1
        total_api_records += len(records)
        if total_api_records > diff_limits.max_input_files:
            raise GitHubContextError(
                "Changed-file API response exceeds the configured input limit."
            )

        for index, record in enumerate(records):
            item = _mapping(record, f"changed_files[{page}:{index}]")
            filename = _required_string(item.get("filename"), "changed_file.filename")
            path = PurePosixPath(filename)
            if (
                path.is_absolute()
                or "\\" in filename
                or any(part in {"", ".", ".."} for part in path.parts)
                or filename.startswith("-")
            ):
                raise GitHubContextError(
                    "changed_file.filename must be a normalized repository-relative path."
                )
            if filename in seen_paths:
                raise GitHubContextError(
                    f"Duplicate changed-file path returned by API: {filename!r}."
                )
            seen_paths.add(filename)
            status = _required_string(item.get("status"), "changed_file.status")
            additions = _nonnegative_int(item.get("additions"), "changed_file.additions")
            deletions = _nonnegative_int(item.get("deletions"), "changed_file.deletions")
            patch = item.get("patch")
            if patch is not None and not isinstance(patch, str):
                raise GitHubContextError("changed_file.patch must be text or absent.")
            is_binary = item.get("is_binary", False)
            if type(is_binary) is not bool:
                raise GitHubContextError("changed_file.is_binary must be a boolean.")
            changed_files.append(
                ChangedFileInput(
                    filename=filename,
                    status=status,
                    additions=additions,
                    deletions=deletions,
                    patch=patch,
                    is_binary=is_binary,
                )
            )

        if len(records) < files_per_page:
            break
    else:
        raise GitHubContextError("Changed-file pagination exceeded the configured page limit.")

    if not changed_files:
        raise GitHubContextError("No changed files were returned for an open pull request.")
    if len(changed_files) > diff_limits.max_input_files:
        raise GitHubContextError("Changed-file inventory exceeds the configured input limit.")

    return PullRequestContext(
        commit=commit,
        policy=policy,
        changed_files=tuple(changed_files),
        files_complete=True,
        pages_read=pages_read,
        policy_source_ref=event.base_sha,
    )
