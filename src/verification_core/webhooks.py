"""Minimal, fail-closed parsing and signature verification for GitHub webhooks.

Callers must verify the raw request body before parsing event payloads. This module
does not handle HTTP, persistence, retries, or GitHub API authentication.
"""

from __future__ import annotations

import hashlib
import hmac
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

_DELIVERY_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{0,127}$")
_REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_SIGNATURE_RE = re.compile(r"^sha256=([0-9a-fA-F]{64})$")
_SUPPORTED_ACTIONS = frozenset({"opened", "reopened", "synchronize"})
DEFAULT_MAX_WEBHOOK_BODY_BYTES = 1_048_576


class WebhookPayloadError(ValueError):
    """Raised when a supported webhook payload violates the expected schema."""


@dataclass(frozen=True, slots=True)
class PullRequestWebhookEvent:
    """Minimal identity of a supported pull-request event.

    It is a delivery/event identity, not proof that the request is authentic. The
    HTTP adapter must call verify_github_signature on the original request bytes
    before constructing this record.
    """

    delivery_id: str
    action: str
    repository_full_name: str
    pr_number: int
    base_sha: str
    head_sha: str
    base_ref: str
    head_ref: str
    installation_id: int | None = None

    def __post_init__(self) -> None:
        if not _DELIVERY_ID_RE.fullmatch(self.delivery_id):
            raise WebhookPayloadError("delivery_id has an invalid format.")
        if self.action not in _SUPPORTED_ACTIONS:
            raise WebhookPayloadError("action is not a supported pull-request trigger.")
        if not _REPOSITORY_RE.fullmatch(self.repository_full_name):
            raise WebhookPayloadError("repository_full_name must match owner/repository.")
        if type(self.pr_number) is not int or self.pr_number < 1:
            raise WebhookPayloadError("pr_number must be a positive integer.")
        if not _GIT_SHA_RE.fullmatch(self.base_sha) or not _GIT_SHA_RE.fullmatch(self.head_sha):
            raise WebhookPayloadError(
                "base_sha and head_sha must be lowercase 40-character Git SHAs."
            )
        if self.base_sha == self.head_sha:
            raise WebhookPayloadError("base_sha and head_sha must be distinct.")
        if not self.base_ref.strip() or not self.head_ref.strip():
            raise WebhookPayloadError("base_ref and head_ref must be non-empty.")
        if self.installation_id is not None and (
            type(self.installation_id) is not int or self.installation_id < 1
        ):
            raise WebhookPayloadError("installation_id must be a positive integer when present.")

    @property
    def idempotency_key(self) -> str:
        """Return a stable key for deduplicating retries of the same GitHub delivery."""
        return f"github-delivery:{self.delivery_id}"


def verify_github_signature(
    raw_body: bytes,
    signature_header: str | None,
    secret: str,
    *,
    max_body_bytes: int = DEFAULT_MAX_WEBHOOK_BODY_BYTES,
) -> bool:
    """Verify X-Hub-Signature-256 using HMAC-SHA256 and constant-time comparison.

    The caller must supply the exact raw HTTP request bytes, not re-serialized JSON.
    Invalid types, blank secrets, malformed headers, and oversized bodies fail closed.
    """
    if not isinstance(raw_body, bytes) or not isinstance(signature_header, str):
        return False
    if not isinstance(secret, str) or not secret:
        return False
    if type(max_body_bytes) is not int or max_body_bytes < 1:
        return False
    if len(raw_body) > max_body_bytes:
        return False
    match = _SIGNATURE_RE.fullmatch(signature_header)
    if match is None:
        return False

    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, match.group(1).lower())


def _mapping(value: object, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise WebhookPayloadError(f"{field} must be an object with string keys.")
    return value


def _required_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise WebhookPayloadError(f"{field} must be a non-empty string.")
    if "\x00" in value:
        raise WebhookPayloadError(f"{field} must not contain NUL characters.")
    return value


def parse_pull_request_webhook(
    *,
    delivery_id: str,
    event_name: str,
    payload: object,
) -> PullRequestWebhookEvent | None:
    """Parse only opened/reopened/synchronize events, returning None for other events.

    This function validates shape and identity but does not authenticate the payload.
    Verify the signature first. Event delivery de-duplication must use the returned
    idempotency_key in a durable store before starting side effects.
    """
    if not isinstance(event_name, str) or event_name != "pull_request":
        return None

    top = _mapping(payload, "payload")
    action = top.get("action")
    if not isinstance(action, str) or action not in _SUPPORTED_ACTIONS:
        return None

    delivery = _required_string(delivery_id, "delivery_id")
    if not _DELIVERY_ID_RE.fullmatch(delivery):
        raise WebhookPayloadError("delivery_id has an invalid format.")

    repository = _mapping(top.get("repository"), "repository")
    repository_full_name = _required_string(repository.get("full_name"), "repository.full_name")
    if not _REPOSITORY_RE.fullmatch(repository_full_name):
        raise WebhookPayloadError("repository.full_name must match owner/repository.")

    installation_value = top.get("installation")
    installation_id: int | None = None
    if installation_value is not None:
        installation = _mapping(installation_value, "installation")
        candidate_id = installation.get("id")
        if type(candidate_id) is not int or candidate_id < 1:
            raise WebhookPayloadError("installation.id must be a positive integer.")
        installation_id = candidate_id

    pull_request = _mapping(top.get("pull_request"), "pull_request")
    number = pull_request.get("number")
    if type(number) is not int or number < 1:
        raise WebhookPayloadError("pull_request.number must be a positive integer.")
    if pull_request.get("state") != "open":
        return None

    base = _mapping(pull_request.get("base"), "pull_request.base")
    head = _mapping(pull_request.get("head"), "pull_request.head")
    base_repo = _mapping(base.get("repo"), "pull_request.base.repo")
    if base_repo.get("full_name") != repository_full_name:
        raise WebhookPayloadError(
            "repository.full_name must match the pull request's base repository."
        )

    return PullRequestWebhookEvent(
        delivery_id=delivery,
        action=action,
        repository_full_name=repository_full_name,
        pr_number=number,
        base_sha=_required_string(base.get("sha"), "pull_request.base.sha"),
        head_sha=_required_string(head.get("sha"), "pull_request.head.sha"),
        base_ref=_required_string(base.get("ref"), "pull_request.base.ref"),
        head_ref=_required_string(head.get("ref"), "pull_request.head.ref"),
        installation_id=installation_id,
    )
