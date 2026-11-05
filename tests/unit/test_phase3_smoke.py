"""Pure helper checks for the explicit Phase III deployment smoke test."""

from __future__ import annotations

import hashlib
import hmac

import pytest
from scripts.phase3_deployment_smoke import (
    SmokeTestError,
    _artifact_sha256,
    _eligible_run,
    _record_key_from_summary,
    _signed_webhook,
)


def test_artifact_digest_is_normalized_and_validated() -> None:
    digest = "a" * 64
    assert _artifact_sha256({"digest": f"sha256:{digest}"}) == digest


@pytest.mark.parametrize(
    "metadata",
    [
        {},
        {"digest": "sha1:" + ("a" * 40)},
        {"digest": "sha256:" + ("A" * 64)},
        {"digest": "sha256:invalid"},
    ],
)
def test_artifact_digest_rejects_missing_or_malformed_metadata(
    metadata: dict[str, object],
) -> None:
    with pytest.raises(SmokeTestError, match="SHA-256"):
        _artifact_sha256(metadata)


def test_check_summary_must_bind_to_a_persisted_record_key() -> None:
    key = "b" * 64
    assert _record_key_from_summary(f"Evidence record {key}. Obligations reconciled.") == key
    with pytest.raises(SmokeTestError, match="persisted evidence record"):
        _record_key_from_summary("Evidence record not persisted.")


def test_webhook_signature_is_over_exact_serialized_bytes() -> None:
    signing_key = "phase3-smoke-fixture-key"
    payload: dict[str, object] = {"action": "synchronize", "pull_request": {"number": 5}}
    delivery_id = "phase3-smoke-test"
    body, headers = _signed_webhook(signing_key, delivery_id, payload)
    expected = hmac.new(signing_key.encode(), body, hashlib.sha256).hexdigest()
    assert headers["x-hub-signature-256"] == f"sha256={expected}"
    assert headers["x-github-delivery"] == delivery_id
    assert headers["x-github-event"] == "pull_request"


def test_eligible_workflow_run_requires_success_exact_head_and_target_pr() -> None:
    run: dict[str, object] = {
        "path": ".github/workflows/ci.yml@refs/heads/main",
        "head_sha": "a" * 40,
        "event": "pull_request",
        "status": "completed",
        "conclusion": "success",
        "pull_requests": [{"number": 5}],
    }
    assert _eligible_run(run, pr_number=5, head_sha="a" * 40)
    assert not _eligible_run(run, pr_number=5, head_sha="b" * 40)
    assert not _eligible_run({**run, "status": "in_progress"}, pr_number=5, head_sha="a" * 40)
    assert not _eligible_run({**run, "conclusion": "failure"}, pr_number=5, head_sha="a" * 40)
    assert not _eligible_run(
        {**run, "path": ".github/workflows/untrusted.yml"}, pr_number=5, head_sha="a" * 40
    )
    assert not _eligible_run(
        {**run, "pull_requests": [{"number": 6}]}, pr_number=5, head_sha="a" * 40
    )
    assert not _eligible_run({**run, "path": None}, pr_number=5, head_sha="a" * 40)
