"""Durable SQLite-backed webhook delivery ledger and retry queue.

Only authenticated, normalized event metadata is persisted. Raw webhook bodies,
installation tokens, private keys, and PR diff contents are never stored here.
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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
        if busy_timeout_ms < 1 or busy_timeout_ms > 60_000:
            raise ValueError("busy_timeout_ms must be between 1 and 60000")
        self._busy_timeout_ms = busy_timeout_ms
        if self._path != ":memory:":
            Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
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
        import hashlib

        fingerprint = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        try:
            with self._connect() as connection:
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
            with self._connect() as connection:
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
                except (TypeError, ValueError, json.JSONDecodeError):
                    self.mark_failed(str(row["delivery_id"]), error_code="stored_event_invalid", retry=False, now=timestamp)
                    raise DeliveryStoreError("Stored webhook event failed schema validation.") from None
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
        timestamp = time.time() if now is None else now
        try:
            with self._connect() as connection:
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

    def _transition_processing(
        self, delivery_id: str, *, status: str, now: float | None
    ) -> None:
        timestamp = time.time() if now is None else now
        try:
            with self._connect() as connection:
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
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT status FROM deliveries WHERE delivery_id=?", (delivery_id,)
                ).fetchone()
                return str(row["status"]) if row else None
        except sqlite3.Error:
            raise DeliveryStoreError("Could not read webhook delivery status.") from None

    def close(self) -> None:
        """Compatibility hook; connections are scoped to individual operations."""
