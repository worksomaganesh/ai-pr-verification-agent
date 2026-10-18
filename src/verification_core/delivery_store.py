"""Durable SQLite-backed webhook delivery ledger and retry queue.

Only authenticated, normalized event metadata is persisted. Raw webhook bodies,
installation tokens, private keys, and PR diff contents are never stored here.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from verification_core.domain import CommitIdentity, VerificationObligation
from verification_core.webhooks import PullRequestWebhookEvent

_SCHEMA = """
CREATE TABLE IF NOT EXISTS deliveries (
    delivery_id TEXT PRIMARY KEY,
    event_json TEXT NOT NULL,
    event_fingerprint TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    received_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    lease_until REAL,
    next_attempt_at REAL NOT NULL DEFAULT 0,
    last_error_code TEXT
);
CREATE INDEX IF NOT EXISTS deliveries_ready
ON deliveries(status, next_attempt_at, received_at);
CREATE TABLE IF NOT EXISTS verification_runs (
    run_key TEXT PRIMARY KEY,
    repository_full_name TEXT NOT NULL,
    pr_number INTEGER NOT NULL CHECK (pr_number >= 1),
    base_sha TEXT NOT NULL,
    head_sha TEXT NOT NULL,
    policy_sha256 TEXT NOT NULL,
    analysis_completeness TEXT NOT NULL,
    planner_mode TEXT NOT NULL,
    conclusion TEXT NOT NULL,
    summary TEXT NOT NULL,
    check_run_id INTEGER,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    UNIQUE(repository_full_name, pr_number, base_sha, head_sha, policy_sha256)
);
CREATE TABLE IF NOT EXISTS verification_obligations (
    run_key TEXT NOT NULL REFERENCES verification_runs(run_key) ON DELETE CASCADE,
    obligation_id TEXT NOT NULL,
    category TEXT NOT NULL,
    severity TEXT NOT NULL,
    source TEXT NOT NULL,
    description TEXT NOT NULL,
    affected_files_json TEXT NOT NULL,
    status TEXT NOT NULL,
    candidate_test_id TEXT,
    status_reason TEXT,
    PRIMARY KEY(run_key, obligation_id)
);
CREATE INDEX IF NOT EXISTS verification_runs_pr
ON verification_runs(repository_full_name, pr_number, created_at);
"""


class DeliveryStoreError(RuntimeError):
    """The durable webhook delivery ledger could not safely complete an operation."""


@dataclass(frozen=True, slots=True)
class EnqueueResult:
    """Outcome of idempotently accepting a webhook delivery."""

    accepted: bool
    duplicate: bool
    status: str


@dataclass(frozen=True, slots=True)
class QueuedDelivery:
    """Claimed event metadata for one bounded processing attempt."""

    event: PullRequestWebhookEvent
    attempts: int


class SQLiteDeliveryStore:
    """Transactional delivery ledger safe for duplicate and concurrent webhook retries."""

    def __init__(self, database_path: str | Path, *, busy_timeout_ms: int = 5_000) -> None:
        self._path = str(database_path)
        if self._path == ":memory:":
            raise ValueError("SQLiteDeliveryStore requires a durable file path, not :memory:.")
        if busy_timeout_ms < 1 or busy_timeout_ms > 60_000:
            raise ValueError("busy_timeout_ms must be between 1 and 60000")
        self._busy_timeout_ms = busy_timeout_ms
        if self._path != ":memory:":
            Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self._path,
            timeout=self._busy_timeout_ms / 1000,
            isolation_level=None,
        )
        connection.row_factory = sqlite3.Row
        connection.execute(f"PRAGMA busy_timeout = {self._busy_timeout_ms}")
        connection.execute("PRAGMA foreign_keys = ON")
        if self._path != ":memory:":
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA synchronous = FULL")
        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        """Scope and close each SQLite connection, including exceptional paths."""
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    @staticmethod
    def _event_json(event: PullRequestWebhookEvent) -> str:
        return json.dumps(
            {
                "delivery_id": event.delivery_id,
                "action": event.action,
                "repository_full_name": event.repository_full_name,
                "pr_number": event.pr_number,
                "base_sha": event.base_sha,
                "head_sha": event.head_sha,
                "base_ref": event.base_ref,
                "head_ref": event.head_ref,
                "installation_id": event.installation_id,
            },
            sort_keys=True,
            separators=(",", ":"),
        )

    def enqueue(self, event: PullRequestWebhookEvent, *, now: float | None = None) -> EnqueueResult:
        """Insert once. Reused delivery IDs with different content are rejected."""
        timestamp = time.time() if now is None else now
        if timestamp < 0:
            raise ValueError("now must be non-negative")
        serialized = self._event_json(event)
        fingerprint = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        try:
            with self._connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT event_fingerprint, status FROM deliveries WHERE delivery_id = ?",
                    (event.delivery_id,),
                ).fetchone()
                if row is not None:
                    connection.commit()
                    if row["event_fingerprint"] != fingerprint:
                        raise DeliveryStoreError(
                            "A GitHub delivery ID was reused with different event content."
                        )
                    return EnqueueResult(False, True, str(row["status"]))
                connection.execute(
                    """
                    INSERT INTO deliveries
                    (delivery_id, event_json, event_fingerprint, status, attempts,
                     received_at, updated_at, next_attempt_at)
                    VALUES (?, ?, ?, 'pending', 0, ?, ?, 0)
                    """,
                    (event.delivery_id, serialized, fingerprint, timestamp, timestamp),
                )
                connection.commit()
                return EnqueueResult(True, False, "pending")
        except sqlite3.Error:
            raise DeliveryStoreError("Could not durably enqueue the webhook delivery.") from None

    def claim_next(
        self, *, now: float | None = None, lease_seconds: int = 120, max_attempts: int = 8
    ) -> QueuedDelivery | None:
        """Atomically claim one ready delivery, recovering expired worker leases."""
        timestamp = time.time() if now is None else now
        if type(lease_seconds) is not int or not 1 <= lease_seconds <= 3600:
            raise ValueError("lease_seconds must be between 1 and 3600")
        if type(max_attempts) is not int or not 1 <= max_attempts <= 100:
            raise ValueError("max_attempts must be between 1 and 100")
        try:
            with self._connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    """
                    UPDATE deliveries
                    SET status='pending', lease_until=NULL, updated_at=?
                    WHERE status='processing' AND lease_until <= ? AND attempts < ?
                    """,
                    (timestamp, timestamp, max_attempts),
                )
                connection.execute(
                    """
                    UPDATE deliveries
                    SET status='failed', lease_until=NULL, updated_at=?,
                        last_error_code='retry_limit_exceeded'
                    WHERE status IN ('pending', 'processing') AND attempts >= ?
                    """,
                    (timestamp, max_attempts),
                )
                row = connection.execute(
                    """
                    SELECT delivery_id, event_json, attempts FROM deliveries
                    WHERE status='pending' AND next_attempt_at <= ?
                    ORDER BY received_at, delivery_id LIMIT 1
                    """,
                    (timestamp,),
                ).fetchone()
                if row is None:
                    connection.commit()
                    return None
                attempts = int(row["attempts"]) + 1
                connection.execute(
                    """
                    UPDATE deliveries SET status='processing', attempts=?, updated_at=?,
                        lease_until=?, last_error_code=NULL WHERE delivery_id=?
                    """,
                    (attempts, timestamp, timestamp + lease_seconds, row["delivery_id"]),
                )
                connection.commit()
                try:
                    payload: Any = json.loads(row["event_json"])
                    event = PullRequestWebhookEvent(**payload)
                except (TypeError, ValueError):
                    self.mark_failed(
                        str(row["delivery_id"]),
                        error_code="stored_event_invalid",
                        retry=False,
                        now=timestamp,
                    )
                    raise DeliveryStoreError(
                        "Stored webhook event failed schema validation."
                    ) from None
                return QueuedDelivery(event=event, attempts=attempts)
        except sqlite3.Error:
            raise DeliveryStoreError("Could not claim a webhook delivery safely.") from None

    def mark_completed(self, delivery_id: str, *, now: float | None = None) -> None:
        self._transition_processing(delivery_id, status="completed", now=now)

    def mark_failed(
        self,
        delivery_id: str,
        *,
        error_code: str,
        retry: bool = True,
        now: float | None = None,
        max_attempts: int = 8,
    ) -> None:
        if not error_code or len(error_code) > 80 or not error_code.replace("_", "").isalnum():
            raise ValueError("error_code must be a short alphanumeric snake_case code")
        if type(max_attempts) is not int or not 1 <= max_attempts <= 100:
            raise ValueError("max_attempts must be between 1 and 100")
        timestamp = time.time() if now is None else now
        try:
            with self._connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT attempts FROM deliveries WHERE delivery_id=? AND status='processing'",
                    (delivery_id,),
                ).fetchone()
                if row is None:
                    raise DeliveryStoreError("Only a processing delivery can be marked failed.")
                attempts = int(row["attempts"])
                can_retry = retry and attempts < max_attempts
                delay = min(300, 2 ** min(attempts, 8))
                connection.execute(
                    """
                    UPDATE deliveries SET status=?, updated_at=?, lease_until=NULL,
                        next_attempt_at=?, last_error_code=? WHERE delivery_id=?
                    """,
                    (
                        "pending" if can_retry else "failed",
                        timestamp,
                        timestamp + delay if can_retry else timestamp,
                        error_code,
                        delivery_id,
                    ),
                )
                connection.commit()
        except sqlite3.Error:
            raise DeliveryStoreError("Could not record webhook processing failure.") from None

    def _transition_processing(self, delivery_id: str, *, status: str, now: float | None) -> None:
        timestamp = time.time() if now is None else now
        try:
            with self._connection() as connection:
                cursor = connection.execute(
                    """
                    UPDATE deliveries SET status=?, updated_at=?, lease_until=NULL,
                        last_error_code=NULL
                    WHERE delivery_id=? AND status='processing'
                    """,
                    (status, timestamp, delivery_id),
                )
                if cursor.rowcount != 1:
                    raise DeliveryStoreError(
                        "Delivery state transition rejected; no processing lease was held."
                    )
        except sqlite3.Error:
            raise DeliveryStoreError("Could not update webhook delivery state.") from None

    def get_status(self, delivery_id: str) -> str | None:
        try:
            with self._connection() as connection:
                row = connection.execute(
                    "SELECT status FROM deliveries WHERE delivery_id=?", (delivery_id,)
                ).fetchone()
                return str(row["status"]) if row else None
        except sqlite3.Error:
            raise DeliveryStoreError("Could not read webhook delivery status.") from None

    def save_verification_run(
        self,
        *,
        commit: CommitIdentity,
        analysis_completeness: str,
        planner_mode: str,
        conclusion: str,
        summary: str,
        obligations: Sequence[VerificationObligation],
        now: float | None = None,
    ) -> str:
        """Atomically persist a planning run and its obligation ledger, idempotently by identity."""
        if not analysis_completeness or len(analysis_completeness) > 80:
            raise ValueError("analysis_completeness must contain 1-80 characters")
        if not planner_mode or len(planner_mode) > 80:
            raise ValueError("planner_mode must contain 1-80 characters")
        if conclusion not in {
            "success",
            "neutral",
            "action_required",
            "failure",
            "cancelled",
            "timed_out",
            "skipped",
        }:
            raise ValueError("unsupported Check Run conclusion")
        if not isinstance(summary, str) or len(summary) > 60_000:
            raise ValueError("summary must not exceed 60000 characters")
        if len(obligations) > 500:
            raise ValueError("obligation ledger exceeds 500 records")
        timestamp = time.time() if now is None else now
        identity = json.dumps(
            [
                commit.repo_full_name,
                commit.pr_number,
                commit.base_sha,
                commit.head_sha,
                commit.policy_sha256,
            ],
            separators=(",", ":"),
        )
        run_key = hashlib.sha256(identity.encode("utf-8")).hexdigest()
        try:
            with self._connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    """
                    INSERT INTO verification_runs (
                        run_key, repository_full_name, pr_number, base_sha, head_sha,
                        policy_sha256, analysis_completeness, planner_mode, conclusion,
                        summary, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(run_key) DO UPDATE SET
                        analysis_completeness=excluded.analysis_completeness,
                        planner_mode=excluded.planner_mode,
                        conclusion=excluded.conclusion,
                        summary=excluded.summary,
                        updated_at=excluded.updated_at
                    """,
                    (
                        run_key,
                        commit.repo_full_name,
                        commit.pr_number,
                        commit.base_sha,
                        commit.head_sha,
                        commit.policy_sha256,
                        analysis_completeness,
                        planner_mode,
                        conclusion,
                        summary,
                        timestamp,
                        timestamp,
                    ),
                )
                connection.execute(
                    "DELETE FROM verification_obligations WHERE run_key = ?", (run_key,)
                )
                for obligation in obligations:
                    connection.execute(
                        """
                        INSERT INTO verification_obligations (
                            run_key, obligation_id, category, severity, source, description,
                            affected_files_json, status, candidate_test_id, status_reason
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            run_key,
                            obligation.obligation_id,
                            obligation.category,
                            obligation.severity.value,
                            obligation.source.value,
                            obligation.description[:4000],
                            json.dumps(obligation.affected_files, separators=(",", ":")),
                            obligation.status.value,
                            obligation.candidate_test_id,
                            obligation.status_reason,
                        ),
                    )
                connection.commit()
                return run_key
        except sqlite3.Error:
            raise DeliveryStoreError(
                "Could not persist the verification run and obligations."
            ) from None

    def set_check_run_id(
        self, run_key: str, check_run_id: int, *, now: float | None = None
    ) -> None:
        """Attach the platform Check Run ID after successful publication."""
        if not run_key or len(run_key) != 64:
            raise ValueError("run_key must be a SHA-256 hex digest")
        if type(check_run_id) is not int or check_run_id < 1:
            raise ValueError("check_run_id must be a positive integer")
        timestamp = time.time() if now is None else now
        try:
            with self._connection() as connection:
                cursor = connection.execute(
                    "UPDATE verification_runs SET check_run_id = ?, updated_at = ? "
                    "WHERE run_key = ?",
                    (check_run_id, timestamp, run_key),
                )
                if cursor.rowcount != 1:
                    raise DeliveryStoreError(
                        "Cannot attach a Check Run to a missing verification run."
                    )
        except sqlite3.Error:
            raise DeliveryStoreError("Could not attach the GitHub Check Run identifier.") from None

    def get_verification_run(self, run_key: str) -> dict[str, object] | None:
        """Return a persisted run and its obligations for audit and tests."""
        try:
            with self._connection() as connection:
                row = connection.execute(
                    "SELECT * FROM verification_runs WHERE run_key = ?", (run_key,)
                ).fetchone()
                if row is None:
                    return None
                record: dict[str, object] = dict(row)
                rows = connection.execute(
                    """
                    SELECT obligation_id, category, severity, source, description,
                           affected_files_json, status, candidate_test_id, status_reason
                    FROM verification_obligations WHERE run_key = ?
                    ORDER BY severity, obligation_id
                    """,
                    (run_key,),
                ).fetchall()
                obligations: list[dict[str, object]] = []
                for item in rows:
                    obligation = dict(item)
                    try:
                        obligation["affected_files"] = json.loads(
                            str(obligation.pop("affected_files_json"))
                        )
                    except (TypeError, ValueError):
                        raise DeliveryStoreError(
                            "Persisted obligation file list failed schema validation."
                        ) from None
                    obligations.append(obligation)
                record["obligations"] = obligations
                return record
        except sqlite3.Error:
            raise DeliveryStoreError("Could not read the persisted verification run.") from None

    def close(self) -> None:
        """Compatibility hook; connections are scoped to individual operations."""
