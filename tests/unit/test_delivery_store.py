"""Adversarial tests for durable webhook delivery idempotency and retry leases."""

from __future__ import annotations

from pathlib import Path

import pytest

from verification_core.delivery_store import DeliveryStoreError, SQLiteDeliveryStore
from verification_core.domain import (
    CommitIdentity,
    ObligationSource,
    Severity,
    VerificationObligation,
)
from verification_core.webhooks import PullRequestWebhookEvent

BASE = "1" * 40
HEAD = "2" * 40


def event(delivery_id: str = "delivery-1", *, head: str = HEAD) -> PullRequestWebhookEvent:
    return PullRequestWebhookEvent(
        delivery_id=delivery_id,
        action="opened",
        repository_full_name="acme/service",
        pr_number=12,
        base_sha=BASE,
        head_sha=head,
        base_ref="main",
        head_ref="feature",
        installation_id=42,
    )


def store(tmp_path: Path) -> SQLiteDeliveryStore:
    return SQLiteDeliveryStore(str(tmp_path / "events.sqlite3"))


def test_enqueue_is_durable_and_idempotent(tmp_path: Path) -> None:
    ledger = store(tmp_path)
    first = ledger.enqueue(event(), now=10)
    second = ledger.enqueue(event(), now=11)
    assert first.accepted and not first.duplicate and first.status == "pending"
    assert not second.accepted and second.duplicate and second.status == "pending"
    claimed = ledger.claim_next(now=12)
    assert claimed is not None
    assert claimed.event.installation_id == 42
    assert claimed.attempts == 1
    assert ledger.get_status("delivery-1") == "processing"


def test_delivery_id_reuse_with_different_event_is_rejected(tmp_path: Path) -> None:
    ledger = store(tmp_path)
    ledger.enqueue(event(), now=1)
    with pytest.raises(DeliveryStoreError, match="reused"):
        ledger.enqueue(event(head="3" * 40), now=2)


def test_claim_returns_none_when_queue_empty(tmp_path: Path) -> None:
    assert store(tmp_path).claim_next(now=1) is None


def test_expired_lease_is_recovered_and_attempt_count_increases(tmp_path: Path) -> None:
    ledger = store(tmp_path)
    ledger.enqueue(event(), now=1)
    first = ledger.claim_next(now=2, lease_seconds=5)
    assert first is not None and first.attempts == 1
    assert ledger.claim_next(now=6) is None
    second = ledger.claim_next(now=7, lease_seconds=5)
    assert second is not None and second.attempts == 2


def test_failure_retries_with_backoff_then_can_complete(tmp_path: Path) -> None:
    ledger = store(tmp_path)
    ledger.enqueue(event(), now=1)
    claim = ledger.claim_next(now=2)
    assert claim is not None
    ledger.mark_failed("delivery-1", error_code="temporary_api_error", now=3)
    assert ledger.get_status("delivery-1") == "pending"
    assert ledger.claim_next(now=4) is None
    claim2 = ledger.claim_next(now=10)
    assert claim2 is not None
    ledger.mark_completed("delivery-1", now=11)
    assert ledger.get_status("delivery-1") == "completed"
    assert ledger.claim_next(now=12) is None


def test_failure_can_be_terminal(tmp_path: Path) -> None:
    ledger = store(tmp_path)
    ledger.enqueue(event(), now=1)
    assert ledger.claim_next(now=2) is not None
    ledger.mark_failed("delivery-1", error_code="invalid_event", retry=False, now=3)
    assert ledger.get_status("delivery-1") == "failed"
    assert ledger.claim_next(now=4) is None


@pytest.mark.parametrize(
    ("lease_seconds", "max_attempts"),
    [(0, 8), (3601, 8), (1, 0), (1, 101)],
)
def test_claim_rejects_unsafe_bounds(tmp_path: Path, lease_seconds: int, max_attempts: int) -> None:
    with pytest.raises(ValueError):
        store(tmp_path).claim_next(now=1, lease_seconds=lease_seconds, max_attempts=max_attempts)


def test_state_transitions_require_a_processing_lease(tmp_path: Path) -> None:
    ledger = store(tmp_path)
    with pytest.raises(DeliveryStoreError, match="processing"):
        ledger.mark_completed("missing", now=1)
    with pytest.raises(ValueError, match="error_code"):
        ledger.mark_failed("missing", error_code="bad code", now=1)


def test_retry_limit_marks_expired_delivery_failed(tmp_path: Path) -> None:
    ledger = store(tmp_path)
    ledger.enqueue(event(), now=1)
    assert ledger.claim_next(now=2, lease_seconds=1, max_attempts=1) is not None
    assert ledger.claim_next(now=4, lease_seconds=1, max_attempts=1) is None
    assert ledger.get_status("delivery-1") == "failed"


def test_store_rejects_invalid_configuration(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        SQLiteDeliveryStore(str(tmp_path / "x.sqlite"), busy_timeout_ms=0)


def test_store_rejects_in_memory_database(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="durable file path"):
        SQLiteDeliveryStore(":memory:")


def test_mark_failed_rejects_invalid_retry_limit(tmp_path: Path) -> None:
    ledger = store(tmp_path)
    ledger.enqueue(event(), now=1)
    assert ledger.claim_next(now=2) is not None
    with pytest.raises(ValueError, match="max_attempts"):
        ledger.mark_failed("delivery-1", error_code="temporary_error", max_attempts=0, now=3)


def make_commit() -> CommitIdentity:
    return CommitIdentity(
        repo_full_name="acme/service",
        pr_number=9,
        base_sha="1" * 40,
        head_sha="2" * 40,
        policy_sha256="a" * 64,
    )


def make_obligation() -> VerificationObligation:
    return VerificationObligation.propose(
        obligation_id="OBL-WHK-01",
        category="webhook_idempotency",
        description="Duplicate event delivery is idempotent.",
        severity=Severity.CRITICAL,
        source=ObligationSource.DETERMINISTIC_POLICY,
        affected_files=("src/webhooks.py",),
        candidate_test_id="tests/test_webhooks.py::test_duplicate_event",
    )


def test_verification_run_and_obligations_are_persisted_idempotently(tmp_path: Path) -> None:
    ledger = store(tmp_path)
    commit = make_commit()
    obligation = make_obligation()
    first_key = ledger.save_verification_run(
        commit=commit,
        analysis_completeness="complete",
        planner_mode="deterministic",
        conclusion="action_required",
        summary="The critical obligation has not been tested.",
        obligations=(obligation,),
        now=10,
    )
    second_key = ledger.save_verification_run(
        commit=commit,
        analysis_completeness="complete",
        planner_mode="deterministic_fallback",
        conclusion="action_required",
        summary="The model was unavailable; deterministic plan retained.",
        obligations=(obligation,),
        now=11,
    )
    assert first_key == second_key
    ledger.set_check_run_id(first_key, 1234, now=12)
    record = ledger.get_verification_run(first_key)
    assert record is not None
    assert record["conclusion"] == "action_required"
    assert record["planner_mode"] == "deterministic_fallback"
    assert record["check_run_id"] == 1234
    persisted = record["obligations"]
    assert isinstance(persisted, list) and len(persisted) == 1
    assert persisted[0]["obligation_id"] == "OBL-WHK-01"
    assert persisted[0]["status"] == "proposed"
    assert persisted[0]["affected_files"] == ["src/webhooks.py"]


def test_verification_run_rejects_invalid_inputs_and_missing_check_target(tmp_path: Path) -> None:
    ledger = store(tmp_path)
    commit = make_commit()
    with pytest.raises(ValueError, match="analysis_completeness"):
        ledger.save_verification_run(
            commit=commit,
            analysis_completeness="",
            planner_mode="deterministic",
            conclusion="action_required",
            summary="summary",
            obligations=(),
        )
    with pytest.raises(ValueError, match="conclusion"):
        ledger.save_verification_run(
            commit=commit,
            analysis_completeness="complete",
            planner_mode="deterministic",
            conclusion="stale",
            summary="summary",
            obligations=(),
        )
    with pytest.raises(ValueError, match="run_key"):
        ledger.set_check_run_id("bad", 1)
    with pytest.raises(ValueError, match="check_run_id"):
        ledger.set_check_run_id("a" * 64, 0)
    with pytest.raises(DeliveryStoreError, match="missing verification run"):
        ledger.set_check_run_id("b" * 64, 123)
