"""Adversarial tests for GitHub webhook authentication and event parsing."""

from __future__ import annotations

import hashlib
import hmac

import pytest

from verification_core.webhooks import (
    PullRequestWebhookEvent,
    WebhookPayloadError,
    parse_pull_request_webhook,
    verify_github_signature,
)

WEBHOOK_KEY = "test-webhook-secret"
BASE = "1" * 40
HEAD = "2" * 40


def signature(body: bytes, secret: str = WEBHOOK_KEY) -> str:
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
    assert verify_github_signature(body, signature(body), WEBHOOK_KEY)


@pytest.mark.parametrize(
    ("body", "header", "secret", "limit"),
    [
        (b"body", None, WEBHOOK_KEY, 100),
        (b"body", "sha256=bad", WEBHOOK_KEY, 100),
        (b"body", signature(b"other"), WEBHOOK_KEY, 100),
        (b"body", signature(b"body"), "wrong-secret", 100),
        (b"body", signature(b"body").upper(), WEBHOOK_KEY, 100),
        (b"body-too-large", signature(b"body-too-large"), WEBHOOK_KEY, 3),
        (b"body", signature(b"body"), "", 100),
    ],
)
def test_invalid_signature_inputs_fail_closed(
    body: bytes, header: str | None, secret: str, limit: int
) -> None:
    assert not verify_github_signature(body, header, secret, max_body_bytes=limit)


def test_signature_is_case_tolerant_only_for_hex_digest() -> None:
    body = b"payload"
    header = signature(body)
    assert verify_github_signature(body, header.upper().replace("SHA256=", "sha256="), WEBHOOK_KEY)


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


def test_malformed_base_sha_is_rejected() -> None:
    data = payload()
    pull_request = data["pull_request"]
    assert isinstance(pull_request, dict)
    base = pull_request["base"]
    assert isinstance(base, dict)
    base["sha"] = "not-a-sha"
    with pytest.raises(WebhookPayloadError, match="base_sha"):
        parse_pull_request_webhook(
            delivery_id="delivery-1",
            event_name="pull_request",
            payload=data,
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
    with pytest.raises(WebhookPayloadError, match=r"SHA|distinct"):
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
            payload=payload(number=True),
        )


def test_event_parser_does_not_authenticate_by_itself() -> None:
    # Authentication is a required HTTP-adapter precondition; parsing alone is not proof.
    event = parse_pull_request_webhook(
        delivery_id="delivery-1",
        event_name="pull_request",
        payload=payload(),
    )
    assert event is not None


@pytest.mark.parametrize(
    ("body", "header", "secret", "limit"),
    [
        (None, "sha256=" + "0" * 64, WEBHOOK_KEY, 100),
        (b"body", None, WEBHOOK_KEY, 100),
        (b"body", signature(b"body"), None, 100),
        (b"body", signature(b"body"), WEBHOOK_KEY, 0),
        (b"body", signature(b"body"), WEBHOOK_KEY, True),
    ],
)
def test_signature_type_and_limit_errors_fail_closed(
    body: object, header: object, secret: object, limit: object
) -> None:
    assert not verify_github_signature(
        body, header, secret, max_body_bytes=limit  # type: ignore[arg-type]
    )


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"delivery_id": "bad id"}, "delivery_id"),
        ({"action": "closed"}, "action"),
        ({"repository_full_name": "not-a-repo"}, "repository_full_name"),
        ({"pr_number": True}, "pr_number"),
        ({"base_sha": "A" * 40}, "base_sha"),
        ({"head_sha": BASE}, "distinct"),
        ({"base_ref": ""}, "base_ref"),
    ],
)
def test_event_record_rejects_invalid_identity_fields(
    kwargs: dict[str, object], message: str
) -> None:
    values: dict[str, object] = {
        "delivery_id": "delivery-1",
        "action": "opened",
        "repository_full_name": "acme/service",
        "pr_number": 1,
        "base_sha": BASE,
        "head_sha": HEAD,
        "base_ref": "main",
        "head_ref": "feature",
    }
    values.update(kwargs)
    with pytest.raises(WebhookPayloadError, match=message):
        PullRequestWebhookEvent(**values)  # type: ignore[arg-type]


def test_nul_in_required_payload_string_is_rejected() -> None:
    data = payload()
    repository = data["repository"]
    assert isinstance(repository, dict)
    repository["full_name"] = "acme/service\x00"
    with pytest.raises(WebhookPayloadError, match="NUL"):
        parse_pull_request_webhook(
            delivery_id="delivery-1",
            event_name="pull_request",
            payload=data,
        )


def test_invalid_repository_name_in_payload_is_rejected() -> None:
    with pytest.raises(WebhookPayloadError, match="owner/repository"):
        parse_pull_request_webhook(
            delivery_id="delivery-1",
            event_name="pull_request",
            payload=payload(repository_name="not-a-repository"),
        )


def test_non_string_action_is_ignored() -> None:
    data = payload()
    data["action"] = 7
    assert (
        parse_pull_request_webhook(
            delivery_id="delivery-1",
            event_name="pull_request",
            payload=data,
        )
        is None
    )
