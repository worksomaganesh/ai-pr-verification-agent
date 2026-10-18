"""Tests for authenticated, bounded FastAPI webhook ingress."""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path

from fastapi.testclient import TestClient

from verification_core.delivery_store import SQLiteDeliveryStore
from verification_core.webhook_app import create_webhook_app

SIGNING_VALUE = "unit-test-webhook-secret"
BASE = "1" * 40
HEAD = "2" * 40


def raw_payload(*, action: str = "opened", installation_id: int = 42) -> bytes:
    payload = {
        "action": action,
        "installation": {"id": installation_id},
        "repository": {"full_name": "acme/service"},
        "pull_request": {
            "number": 7,
            "state": "open",
            "base": {
                "sha": BASE,
                "ref": "main",
                "repo": {"full_name": "acme/service"},
            },
            "head": {"sha": HEAD, "ref": "feature"},
        },
    }
    return json.dumps(payload, separators=(",", ":")).encode()


def sign(body: bytes) -> str:
    digest = hmac.new(SIGNING_VALUE.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def headers(
    body: bytes, *, event_name: str = "pull_request", delivery: str = "delivery-7"
) -> dict[str, str]:
    return {
        "content-type": "application/json",
        "x-hub-signature-256": sign(body),
        "x-github-delivery": delivery,
        "x-github-event": event_name,
    }


def client(tmp_path: Path, *, max_body_bytes: int = 1_048_576) -> TestClient:
    path = str(tmp_path / "deliveries.sqlite3")  # type: ignore[operator]
    app = create_webhook_app(
        webhook_secret=SIGNING_VALUE,
        delivery_store=SQLiteDeliveryStore(path),
        max_body_bytes=max_body_bytes,
    )
    return TestClient(app)


def test_valid_event_is_durably_accepted_and_duplicate_is_idempotent(tmp_path: Path) -> None:
    test_client = client(tmp_path)
    body = raw_payload()
    first = test_client.post("/webhooks/github", content=body, headers=headers(body))
    second = test_client.post("/webhooks/github", content=body, headers=headers(body))
    assert first.status_code == 202
    assert first.json()["accepted"] is True
    assert second.status_code == 202
    assert second.json()["duplicate"] is True


def test_invalid_signature_is_rejected_before_payload_parsing(tmp_path: Path) -> None:
    test_client = client(tmp_path)
    response = test_client.post(
        "/webhooks/github",
        content=b"not json",
        headers={"x-hub-signature-256": "sha256=" + "0" * 64},
    )
    assert response.status_code == 401


def test_missing_headers_are_rejected_after_signature_validation(tmp_path: Path) -> None:
    test_client = client(tmp_path)
    body = raw_payload()
    response = test_client.post(
        "/webhooks/github",
        content=body,
        headers={"x-hub-signature-256": sign(body)},
    )
    assert response.status_code == 400


def test_oversized_body_is_rejected(tmp_path: Path) -> None:
    test_client = client(tmp_path, max_body_bytes=20)
    body = raw_payload()
    response = test_client.post("/webhooks/github", content=body, headers=headers(body))
    assert response.status_code == 413


def test_unsupported_event_is_ignored(tmp_path: Path) -> None:
    test_client = client(tmp_path)
    body = raw_payload()
    response = test_client.post(
        "/webhooks/github", content=body, headers=headers(body, event_name="push")
    )
    assert response.status_code == 204


def test_event_without_installation_identity_is_rejected(tmp_path: Path) -> None:
    test_client = client(tmp_path)
    body = raw_payload(installation_id=0)
    response = test_client.post("/webhooks/github", content=body, headers=headers(body))
    assert response.status_code == 400


def test_closed_pull_request_event_is_ignored(tmp_path: Path) -> None:
    test_client = client(tmp_path)
    payload = json.loads(raw_payload())
    payload["pull_request"]["state"] = "closed"
    body = json.dumps(payload).encode()
    response = test_client.post("/webhooks/github", content=body, headers=headers(body))
    assert response.status_code == 204


def test_duplicate_json_keys_are_rejected(tmp_path: Path) -> None:
    test_client = client(tmp_path)
    body = b'{"action":"opened","action":"synchronize"}'
    response = test_client.post("/webhooks/github", content=body, headers=headers(body))
    assert response.status_code == 400


def test_health_endpoint_does_not_expose_configuration(tmp_path: Path) -> None:
    response = client(tmp_path).get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_empty_secret_and_invalid_body_bound_are_rejected(tmp_path: Path) -> None:
    store = SQLiteDeliveryStore(str(tmp_path / "store.sqlite3"))
    try:
        create_webhook_app(webhook_secret="", delivery_store=store)
    except ValueError:
        pass
    else:
        raise AssertionError("empty secret should be rejected")
    try:
        create_webhook_app(webhook_secret=SIGNING_VALUE, delivery_store=store, max_body_bytes=0)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid body limit should be rejected")
