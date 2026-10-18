"""Durable, idempotent ledger for authenticated Phase III evidence.

Ingestion records are immutable snapshots. They are never interpreted as a passing verification
decision; reconciliation starts INCONCLUSIVE and must be recorded separately by the verifier.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import time
from typing import Any

from sqlalchemy import (
    Column,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    create_engine,
    select,
    update,
)
from sqlalchemy.exc import SQLAlchemyError

from verification_core.actions_evidence import AuthenticatedEvidenceArtifact
from verification_core.delivery_store import DeliveryStoreError
from verification_core.domain.models import CommitIdentity

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_RUN_IDENTITY_RE = re.compile(r"^[0-9a-f]{64}$")
_ALLOWED_RECONCILIATION = {"INCONCLUSIVE", "PASSED", "FAILED", "STALE", "CONFLICT"}
_METADATA = MetaData()
_EVIDENCE = Table(
    "authenticated_evidence_records",
    _METADATA,
    Column("record_key", String(64), primary_key=True),
    Column("repository_full_name", String(200), nullable=False),
    Column("pr_number", Integer, nullable=False),
    Column("base_sha", String(40), nullable=False),
    Column("head_sha", String(40), nullable=False),
    Column("policy_sha256", String(64), nullable=False),
    Column("workflow_run_id", Integer, nullable=False),
    Column("workflow_id", Integer, nullable=False),
    Column("workflow_attempt", Integer, nullable=False),
    Column("workflow_path", String(1000), nullable=False),
    Column("workflow_definition_sha256", String(64), nullable=False),
    Column("artifact_id", Integer, nullable=False),
    Column("artifact_name", String(200), nullable=False),
    Column("artifact_sha256", String(64), nullable=False),
    Column("junit_total", Integer, nullable=False),
    Column("junit_passed", Integer, nullable=False),
    Column("junit_failed", Integer, nullable=False),
    Column("junit_errors", Integer, nullable=False),
    Column("junit_skipped", Integer, nullable=False),
    Column("coverage_test_count", Integer, nullable=False),
    Column("test_inventory_sha256", String(64), nullable=False),
    Column("reconciliation_status", String(32), nullable=False),
    Column("reconciliation_reason", Text, nullable=False),
    Column("decision_sha256", String(64), nullable=True),
    Column("created_at", Float, nullable=False),
    Column("updated_at", Float, nullable=False),
    UniqueConstraint(
        "repository_full_name",
        "pr_number",
        "base_sha",
        "head_sha",
        "policy_sha256",
        "workflow_run_id",
        "workflow_attempt",
        "artifact_id",
        name="uq_authenticated_evidence_identity",
    ),
)


class EvidenceLedgerConflict(DeliveryStoreError):
    """Raised when an existing evidence identity is presented with different contents."""


class SQLAlchemyEvidenceLedger:
    """Persist authenticated evidence provenance and separately recorded reconciliation.

    Supports SQLite for local/single-host use and PostgreSQL for shared deployments. The
    artifact itself and signed URLs are deliberately not stored; only bounded metadata,
    digests, and normalized test inventory are persisted.
    """

    def __init__(self, database_url: str) -> None:
        if not isinstance(database_url, str) or not database_url.strip():
            raise ValueError("database_url must not be empty")
        if not database_url.startswith(("postgresql+psycopg://", "sqlite:///")):
            raise ValueError("database_url must use postgresql+psycopg:// or sqlite:///")
        try:
            self._engine = create_engine(
                database_url,
                connect_args={"check_same_thread": False}
                if database_url.startswith("sqlite:///")
                else {},
                pool_pre_ping=True,
            )
            _METADATA.create_all(self._engine)
        except SQLAlchemyError:
            raise DeliveryStoreError("Could not initialize the evidence ledger.") from None

    @staticmethod
    def _validate_digest(value: str, field: str) -> None:
        if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
            raise ValueError(f"{field} must be a lowercase SHA-256 digest")

    @staticmethod
    def _identity_key(commit: CommitIdentity, evidence: AuthenticatedEvidenceArtifact) -> str:
        identity = [
            commit.repo_full_name,
            commit.pr_number,
            commit.base_sha,
            commit.head_sha,
            commit.policy_sha256,
            evidence.workflow_run_id,
            evidence.workflow_attempt,
            evidence.artifact_id,
        ]
        return hashlib.sha256(
            json.dumps(identity, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        ).hexdigest()

    def record_ingestion(
        self,
        *,
        commit: CommitIdentity,
        evidence: AuthenticatedEvidenceArtifact,
        workflow_definition_sha256: str,
        now: float | None = None,
    ) -> str:
        """Record an authenticated artifact idempotently, never marking it PASSED."""
        self._validate_digest(workflow_definition_sha256, "workflow_definition_sha256")
        if (
            evidence.repository_full_name != commit.repo_full_name
            or evidence.pull_request_number != commit.pr_number
            or evidence.base_sha != commit.base_sha
            or evidence.head_sha != commit.head_sha
            or evidence.coverage_manifest.head_sha != commit.head_sha
            or not evidence.provenance.is_authentic_and_trusted(commit)
        ):
            raise ValueError("evidence provenance does not match the supplied commit identity")
        if evidence.provenance.workflow_path != evidence.workflow_path:
            raise ValueError("workflow path does not match authenticated provenance")
        case_ids = [case.node_id for case in evidence.junit_report.cases]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("JUnit test inventory contains duplicate node IDs")
        coverage_ids = [case.node_id for case in evidence.coverage_manifest.cases]
        if len(coverage_ids) != len(set(coverage_ids)):
            raise ValueError("coverage test inventory contains duplicate node IDs")
        if set(case_ids) != set(coverage_ids):
            raise ValueError("JUnit and coverage test inventories differ")
        inventory = json.dumps(sorted(case_ids), separators=(",", ":"), ensure_ascii=True)
        inventory_digest = hashlib.sha256(inventory.encode("utf-8")).hexdigest()
        key = self._identity_key(commit, evidence)
        timestamp = time.time() if now is None else now
        if type(timestamp) not in (int, float) or not math.isfinite(timestamp) or timestamp < 0:
            raise ValueError("now must be a finite non-negative timestamp")
        values: dict[str, Any] = {
            "record_key": key,
            "repository_full_name": commit.repo_full_name,
            "pr_number": commit.pr_number,
            "base_sha": commit.base_sha,
            "head_sha": commit.head_sha,
            "policy_sha256": commit.policy_sha256,
            "workflow_run_id": evidence.workflow_run_id,
            "workflow_id": evidence.workflow_id,
            "workflow_attempt": evidence.workflow_attempt,
            "workflow_path": evidence.workflow_path,
            "workflow_definition_sha256": workflow_definition_sha256,
            "artifact_id": evidence.artifact_id,
            "artifact_name": evidence.artifact_name,
            "artifact_sha256": evidence.artifact_sha256,
            "junit_total": evidence.junit_report.total_tests,
            "junit_passed": evidence.junit_report.passed,
            "junit_failed": evidence.junit_report.failed,
            "junit_errors": evidence.junit_report.errors,
            "junit_skipped": evidence.junit_report.skipped,
            "coverage_test_count": len(evidence.coverage_manifest.cases),
            "test_inventory_sha256": inventory_digest,
            "reconciliation_status": "INCONCLUSIVE",
            "reconciliation_reason": "Evidence ingested; obligation reconciliation has not run.",
            "decision_sha256": None,
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        try:
            with self._engine.begin() as connection:
                existing = (
                    connection.execute(select(_EVIDENCE).where(_EVIDENCE.c.record_key == key))
                    .mappings()
                    .first()
                )
                if existing is not None:
                    immutable = (
                        "repository_full_name",
                        "pr_number",
                        "base_sha",
                        "head_sha",
                        "policy_sha256",
                        "workflow_run_id",
                        "workflow_id",
                        "workflow_attempt",
                        "workflow_path",
                        "workflow_definition_sha256",
                        "artifact_id",
                        "artifact_name",
                        "artifact_sha256",
                        "junit_total",
                        "junit_passed",
                        "junit_failed",
                        "junit_errors",
                        "junit_skipped",
                        "coverage_test_count",
                        "test_inventory_sha256",
                    )
                    if any(existing[field] != values[field] for field in immutable):
                        raise EvidenceLedgerConflict(
                            "The same evidence identity was replayed with conflicting contents."
                        )
                    return key
                connection.execute(_EVIDENCE.insert().values(**values))
        except EvidenceLedgerConflict:
            raise
        except SQLAlchemyError:
            raise DeliveryStoreError("Could not persist authenticated evidence.") from None
        return key

    def record_reconciliation(
        self,
        record_key: str,
        *,
        status: str,
        reason: str,
        decision_sha256: str,
        now: float | None = None,
    ) -> None:
        """Persist a separate deterministic decision; ingestion never changes status to PASSED."""
        if not isinstance(record_key, str) or not _RUN_IDENTITY_RE.fullmatch(record_key):
            raise ValueError("record_key must be a lowercase SHA-256 digest")
        if status not in _ALLOWED_RECONCILIATION or status == "INCONCLUSIVE":
            raise ValueError("status must be a terminal reconciliation result")
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 10_000:
            raise ValueError("reason must contain 1-10000 characters")
        self._validate_digest(decision_sha256, "decision_sha256")
        timestamp = time.time() if now is None else now
        if not isinstance(timestamp, (int, float)) or timestamp < 0:
            raise ValueError("now must be a non-negative timestamp")
        try:
            with self._engine.begin() as connection:
                row = (
                    connection.execute(
                        select(_EVIDENCE).where(_EVIDENCE.c.record_key == record_key)
                    )
                    .mappings()
                    .first()
                )
                if row is None:
                    raise DeliveryStoreError("missing evidence record")
                if row["reconciliation_status"] != "INCONCLUSIVE":
                    if (
                        row["reconciliation_status"] == status
                        and row["decision_sha256"] == decision_sha256
                        and row["reconciliation_reason"] == reason
                    ):
                        return
                    raise EvidenceLedgerConflict(
                        "Reconciliation is immutable once a terminal decision is recorded."
                    )
                result = connection.execute(
                    update(_EVIDENCE)
                    .where(
                        _EVIDENCE.c.record_key == record_key,
                        _EVIDENCE.c.reconciliation_status == "INCONCLUSIVE",
                    )
                    .values(
                        reconciliation_status=status,
                        reconciliation_reason=reason,
                        decision_sha256=decision_sha256,
                        updated_at=timestamp,
                    )
                )
                if result.rowcount != 1:
                    raise EvidenceLedgerConflict(
                        "Reconciliation was concurrently updated; reload before retrying."
                    )
        except (DeliveryStoreError, EvidenceLedgerConflict):
            raise
        except SQLAlchemyError:
            raise DeliveryStoreError("Could not persist evidence reconciliation.") from None

    def get_record(self, record_key: str) -> dict[str, object] | None:
        if not isinstance(record_key, str) or not _RUN_IDENTITY_RE.fullmatch(record_key):
            raise ValueError("record_key must be a lowercase SHA-256 digest")
        try:
            with self._engine.connect() as connection:
                row = (
                    connection.execute(
                        select(_EVIDENCE).where(_EVIDENCE.c.record_key == record_key)
                    )
                    .mappings()
                    .first()
                )
                return dict(row) if row is not None else None
        except SQLAlchemyError:
            raise DeliveryStoreError("Could not read authenticated evidence.") from None

    def close(self) -> None:
        """Release database resources."""
        self._engine.dispose()
