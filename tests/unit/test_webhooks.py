"""Adversarial tests for GitHub webhook authentication and event parsing."""

from __future__ import annotations

import hashlib
import hmac

import pytest

from verification_core.webhooks import (
    WebhookPayloadError,
    parse_pull_request_webhook,
    verify_github_signature,
)

SECRET = "test-webhook-secret"
BASE = "1" * 40
HEAD = "2" * 40


def signature(body: bytes, secret: str = SECRET) -> str:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def payload(
    *,
    action: str = "opened",
    state: str = "open",
    repository_name: str = "acme/service",
    base_repository_name: str = "acme/service",
    number: int = 12,
    base_sha: str = BASE,
    head_sha: str = HEAD,
) -> dict[str, object]:
    return {
        "action": action,
        "repository": {"full_name": repository_name},
        "pull_request": {
            "number": number,
            "state": state,
            "base": {
                "sha": base_sha,
                "ref": "main",
                "repo": {"full_name": base_repository_name},
            },
            "head": {"sha": head_sha, "ref": "feature/security"},
        },
    }


def test_valid_signature_uses_raw_body() -> None:
    body = b'{"action":"opened","number":12}'
    assert verify_github_signature(body, signature(body), SECRET)


@pytest.mark.parametrize(
    ("body", "header", "secret", "limit"),
    [
        (b"body", None, SECRET, 100),
        (b"body", "sha256=bad", SECRET, 100),
        (b"body", signature(b"other"), SECRET, 100),
        (b"body", signature(b"body"), "wrong-secret", 100),
        (b"body", signature(b"body").upper(), SECRET, 100),
        (b"body-too-large", signature(b"body-too-large"), SECRET, 3),
        (b"body", signature(b"body"), "", 100),
    ],
)
def test_invalid_signature_inputs_fail_closed(
    body: bytes, header: str | None, secret: str, limit: int
) -> None:
    assert not verify_github_signature(
        body, header, secret, max_body_bytes=limit
    )


def test_signature_is_case_tolerant_only_for_hex_digest() -> None:
    body = b"payload"
    header = signature(body)
    assert verify_github_signature(body, header.upper().replace("SHA256=", "sha256="), SECRET)


def test_event_extracts_exact_commit_identity_and_idempotency_key() -> None:
    event = parse_pull_request_webhook(
        delivery_id="delivery-abc-123",
        event_name="pull_request",
        payload=payload(),
    )
    assert event is not None
    assert event.repository_full_name == "acme/service"
    assert event.pr_number == 12
    assert event.base_sha == BASE
    assert event.head_sha == HEAD
    assert event.idempotency_key == "github-delivery:delivery-abc-123"


@pytest.mark.parametrize(
    ("event_name", "action"),
    [
        ("issues", "opened"),
        ("pull_request", "closed"),
        ("pull_request", "edited"),
        ("pull_request", "labeled"),
    ],
)
def test_unhandled_event_or_action_is_ignored(event_name: str, action: str) -> None:
    assert (
        parse_pull_request_webhook(
            delivery_id="delivery-1",
            event_name=event_name,
            payload=payload(action=action),
        )
        is None
    )


def test_closed_pull_request_is_ignored() -> None:
    assert (
        parse_pull_request_webhook(
            delivery_id="delivery-1",
            event_name="pull_request",
            payload=payload(state="closed"),
        )
        is None
    )


@pytest.mark.parametrize(
    ("delivery_id", "changes", "message"),
    [
        ("bad id", {}, "delivery_id"),
        ("delivery-1", {"repository": None}, "repository"),
        ("delivery-1", {"pull_request": None}, "pull_request"),
        ("delivery-1", {"pull_request": {"number": True}}, "number"),
        ("delivery-1", {"pull_request": {"number": 0}}, "number"),
        (
            "delivery-1",
            {"repository": {"full_name": "attacker/repo"}},
            "base repository",
        ),
        ("delivery-1", {"pull_request": {"base": {"sha": "not-a-sha"}}}, "base_sha"),
    ],
)
def test_malformed_supported_payload_is_rejected(
    delivery_id: str, changes: dict[str, object], message: str
) -> None:
    data = payload()
    data.update(changes)
    with pytest.raises(WebhookPayloadError, match=message):
        parse_pull_request_webhook(
            delivery_id=delivery_id,
            event_name="pull_request",
            payload=data,
        )


def test_mismatched_base_repository_is_rejected() -> None:
    with pytest.raises(WebhookPayloadError, match="base repository"):
        parse_pull_request_webhook(
            delivery_id="delivery-1",
            event_name="pull_request",
            payload=payload(base_repository_name="attacker/fork"),
        )


@pytest.mark.parametrize(
    ("base_sha", "head_sha"),
    [
        ("x" * 40, HEAD),
        ("A" * 40, HEAD),
        (BASE, "not-a-sha"),
        (BASE, BASE),
    ],
)
def test_invalid_or_equal_commit_shas_are_rejected(base_sha: str, head_sha: str) -> None:
    with pytest.raises(WebhookPayloadError, match="SHA|distinct"):
        parse_pull_request_webhook(
            delivery_id="delivery-1",
            event_name="pull_request",
            payload=payload(base_sha=base_sha, head_sha=head_sha),
        )


def test_boolean_is_not_accepted_as_pr_number() -> None:
    with pytest.raises(WebhookPayloadError, match="positive integer"):
        parse_pull_request_webhook(
            delivery_id="delivery-1",
            event_name="pull_request",
            payload=payload(number=True),  # type: ignore[arg-type]
        )


def test_event_parser_does_not_authenticate_by_itself() -> None:
    # Authentication is a required HTTP-adapter precondition; parsing alone is not proof.
    event = parse_pull_request_webhook(
        delivery_id="delivery-1",
        event_name="pull_request",
        payload=payload(),
    )
    assert event is not None
