"""SQLAlchemy-backed run and obligation ledger for SQLite or PostgreSQL deployments."""

from __future__ import annotations

import hashlib
import json
import re
import time
from collections.abc import Sequence
from typing import Protocol

from sqlalchemy import (
    Column,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    create_engine,
    delete,
    insert,
    select,
    update,
)
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from verification_core.delivery_store import DeliveryStoreError
from verification_core.domain import CommitIdentity, VerificationObligation

_RUN_KEY_RE = re.compile(r"^[0-9a-f]{64}$")
_ALLOWED_CONCLUSIONS = {
    "success",
    "neutral",
    "action_required",
    "failure",
    "cancelled",
    "timed_out",
    "skipped",
}

_METADATA = MetaData()
_RUNS = Table(
    "verification_runs",
    _METADATA,
    Column("run_key", String(64), primary_key=True),
    Column("repository_full_name", String(200), nullable=False),
    Column("pr_number", Integer, nullable=False),
    Column("base_sha", String(40), nullable=False),
    Column("head_sha", String(40), nullable=False),
    Column("policy_sha256", String(64), nullable=False),
    Column("analysis_completeness", String(80), nullable=False),
    Column("planner_mode", String(80), nullable=False),
    Column("conclusion", String(40), nullable=False),
    Column("summary", Text, nullable=False),
    Column("check_run_id", Integer, nullable=True),
    Column("created_at", Float, nullable=False),
    Column("updated_at", Float, nullable=False),
    UniqueConstraint(
        "repository_full_name",
        "pr_number",
        "base_sha",
        "head_sha",
        "policy_sha256",
        name="uq_verification_run_identity",
    ),
)
_OBLIGATIONS = Table(
    "verification_obligations",
    _METADATA,
    Column(
        "run_key",
        String(64),
        ForeignKey("verification_runs.run_key", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    ),
    Column("obligation_id", String(160), primary_key=True, nullable=False),
    Column("category", String(120), nullable=False),
    Column("severity", String(20), nullable=False),
    Column("source", String(40), nullable=False),
    Column("description", Text, nullable=False),
    Column("affected_files_json", Text, nullable=False),
    Column("status", String(40), nullable=False),
    Column("candidate_test_id", String(500), nullable=True),
    Column("status_reason", Text, nullable=True),
)


class VerificationRunLedger(Protocol):
    """Persistence port used by the Phase II processor."""

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
    ) -> str: ...

    def set_check_run_id(
        self, run_key: str, check_run_id: int, *, now: float | None = None
    ) -> None: ...

    def close(self) -> None: ...


class SQLAlchemyRunLedger:
    """Persist run summaries and obligation rows in SQLite or PostgreSQL.

    Use a PostgreSQL URL for multi-process run/obligation persistence. The SQLite
    delivery queue remains a separate single-host ingress queue unless a deployment
    supplies a shared queue implementation.
    """

    def __init__(self, database_url: str, *, pool_size: int = 5, max_overflow: int = 5) -> None:
        if not isinstance(database_url, str) or not database_url.strip():
            raise ValueError("database_url must not be empty")
        if not database_url.startswith(("postgresql+psycopg://", "sqlite:///")):
            raise ValueError("database_url must use postgresql+psycopg:// or sqlite:///")
        if type(pool_size) is not int or not 1 <= pool_size <= 50:
            raise ValueError("pool_size must be between 1 and 50")
        if type(max_overflow) is not int or not 0 <= max_overflow <= 100:
            raise ValueError("max_overflow must be between 0 and 100")
        try:
            if database_url.startswith("sqlite:///"):
                self._engine = create_engine(
                    database_url,
                    connect_args={"check_same_thread": False},
                    pool_pre_ping=True,
                )
            else:
                self._engine = create_engine(
                    database_url,
                    pool_pre_ping=True,
                    pool_size=pool_size,
                    max_overflow=max_overflow,
                )
            _METADATA.create_all(self._engine)
        except SQLAlchemyError:
            raise DeliveryStoreError(
                "Could not initialize the verification run database."
            ) from None

    @staticmethod
    def _run_key(commit: CommitIdentity) -> str:
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
        return hashlib.sha256(identity.encode("utf-8")).hexdigest()

    @staticmethod
    def _validate_run(
        analysis_completeness: str,
        planner_mode: str,
        conclusion: str,
        summary: str,
        obligations: Sequence[VerificationObligation],
    ) -> None:
        if not analysis_completeness or len(analysis_completeness) > 80:
            raise ValueError("analysis_completeness must contain 1-80 characters")
        if not planner_mode or len(planner_mode) > 80:
            raise ValueError("planner_mode must contain 1-80 characters")
        if conclusion not in _ALLOWED_CONCLUSIONS:
            raise ValueError("unsupported Check Run conclusion")
        if not isinstance(summary, str) or len(summary) > 60_000:
            raise ValueError("summary must not exceed 60000 characters")
        if len(obligations) > 500:
            raise ValueError("obligation ledger exceeds 500 records")

    @staticmethod
    def _obligation_row(run_key: str, obligation: VerificationObligation) -> dict[str, object]:
        return {
            "run_key": run_key,
            "obligation_id": obligation.obligation_id,
            "category": obligation.category,
            "severity": obligation.severity.value,
            "source": obligation.source.value,
            "description": obligation.description[:4000],
            "affected_files_json": json.dumps(obligation.affected_files, separators=(",", ":")),
            "status": obligation.status.value,
            "candidate_test_id": obligation.candidate_test_id,
            "status_reason": obligation.status_reason,
        }

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
        """Upsert the exact commit/policy run and atomically replace its obligation ledger."""
        self._validate_run(analysis_completeness, planner_mode, conclusion, summary, obligations)
        timestamp = time.time() if now is None else now
        run_key = self._run_key(commit)
        values: dict[str, object] = {
            "run_key": run_key,
            "repository_full_name": commit.repo_full_name,
            "pr_number": commit.pr_number,
            "base_sha": commit.base_sha,
            "head_sha": commit.head_sha,
            "policy_sha256": commit.policy_sha256,
            "analysis_completeness": analysis_completeness,
            "planner_mode": planner_mode,
            "conclusion": conclusion,
            "summary": summary,
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        update_values = {
            key: value
            for key, value in values.items()
            if key
            not in {
                "run_key",
                "repository_full_name",
                "pr_number",
                "base_sha",
                "head_sha",
                "policy_sha256",
                "created_at",
            }
        }
        try:
            with self._engine.begin() as connection:
                if self._engine.dialect.name == "postgresql":
                    statement = (
                        postgres_insert(_RUNS)
                        .values(**values)
                        .on_conflict_do_update(index_elements=[_RUNS.c.run_key], set_=update_values)
                    )
                    connection.execute(statement)
                elif self._engine.dialect.name == "sqlite":
                    statement = (
                        sqlite_insert(_RUNS)
                        .values(**values)
                        .on_conflict_do_update(index_elements=[_RUNS.c.run_key], set_=update_values)
                    )
                    connection.execute(statement)
                else:
                    existing = connection.execute(
                        select(_RUNS.c.run_key).where(_RUNS.c.run_key == run_key)
                    ).first()
                    if existing:
                        connection.execute(
                            update(_RUNS).where(_RUNS.c.run_key == run_key).values(**update_values)
                        )
                    else:
                        connection.execute(insert(_RUNS).values(**values))
                connection.execute(delete(_OBLIGATIONS).where(_OBLIGATIONS.c.run_key == run_key))
                if obligations:
                    connection.execute(
                        insert(_OBLIGATIONS),
                        [self._obligation_row(run_key, item) for item in obligations],
                    )
            return run_key
        except SQLAlchemyError:
            raise DeliveryStoreError(
                "Could not persist the verification run and obligations."
            ) from None

    def set_check_run_id(
        self, run_key: str, check_run_id: int, *, now: float | None = None
    ) -> None:
        if not isinstance(run_key, str) or not _RUN_KEY_RE.fullmatch(run_key):
            raise ValueError("run_key must be a SHA-256 hex digest")
        if type(check_run_id) is not int or check_run_id < 1:
            raise ValueError("check_run_id must be a positive integer")
        timestamp = time.time() if now is None else now
        try:
            with self._engine.begin() as connection:
                result = connection.execute(
                    update(_RUNS)
                    .where(_RUNS.c.run_key == run_key)
                    .values(check_run_id=check_run_id, updated_at=timestamp)
                )
                if result.rowcount != 1:
                    raise DeliveryStoreError(
                        "Cannot attach a Check Run to a missing verification run."
                    )
        except SQLAlchemyError:
            raise DeliveryStoreError("Could not attach the GitHub Check Run identifier.") from None

    def get_verification_run(self, run_key: str) -> dict[str, object] | None:
        if not isinstance(run_key, str) or not _RUN_KEY_RE.fullmatch(run_key):
            raise ValueError("run_key must be a SHA-256 hex digest")
        try:
            with self._engine.connect() as connection:
                row = (
                    connection.execute(select(_RUNS).where(_RUNS.c.run_key == run_key))
                    .mappings()
                    .first()
                )
                if row is None:
                    return None
                record = dict(row)
                rows = (
                    connection.execute(
                        select(_OBLIGATIONS)
                        .where(_OBLIGATIONS.c.run_key == run_key)
                        .order_by(_OBLIGATIONS.c.severity, _OBLIGATIONS.c.obligation_id)
                    )
                    .mappings()
                    .all()
                )
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
        except SQLAlchemyError:
            raise DeliveryStoreError("Could not read the persisted verification run.") from None

    def close(self) -> None:
        self._engine.dispose()
