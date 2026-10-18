"""Integration tests for durable authenticated evidence records."""

from __future__ import annotations

from pathlib import Path

import pytest

from verification_core.evidence_ledger import (
    EvidenceLedgerConflict,
    SQLAlchemyEvidenceLedger,
)


def make_ledger(tmp_path: Path) -> SQLAlchemyEvidenceLedger:
    return SQLAlchemyEvidenceLedger(f"sqlite:///{tmp_path / 'evidence.sqlite3'}")


def test_ledger_rejects_invalid_database_url(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="database_url"):
        SQLAlchemyEvidenceLedger("")
    with pytest.raises(ValueError, match="database_url"):
        SQLAlchemyEvidenceLedger("mysql://invalid")


def test_ledger_recording_starts_inconclusive_and_persists(tmp_path: Path) -> None:
    """Ingestion rows must remain non-passing until a separate decision is recorded."""
    ledger = make_ledger(tmp_path)
    # A minimal fixture is assembled from the project's existing evidence test helpers below.
    from tests.unit.test_actions_evidence import _FakeActionsReader, _FakePRReader, identity
    from verification_core.phase_three import ingest_pull_request_run

    commit = identity()
    ingested = ingest_pull_request_run(
        github=_FakePRReader(),
        actions=_FakeActionsReader(),
        commit=commit,
        workflow_run_id=99,
        trusted_workflow_paths=(".github/workflows/ci.yml",),
        harness_sensitive_paths=(".github/workflows/", "conftest.py"),
        changed_paths=("src/auth.py",),
    )
    key = ledger.record_ingestion(
        commit=commit,
        evidence=ingested.evidence,
        workflow_definition_sha256=ingested.workflow_definition_sha256,
        now=10,
    )
    ledger.close()
    reopened = make_ledger(tmp_path)
    row = reopened.get_record(key)
    assert row is not None
    assert row["reconciliation_status"] == "INCONCLUSIVE"
    assert row["artifact_sha256"] == ingested.evidence.artifact_sha256
    assert row["test_inventory_sha256"]
    reopened.close()


def test_ledger_records_terminal_reconciliation_once(tmp_path: Path) -> None:
    ledger = make_ledger(tmp_path)
    from tests.unit.test_actions_evidence import _FakeActionsReader, _FakePRReader, identity
    from verification_core.phase_three import ingest_pull_request_run

    commit = identity()
    ingested = ingest_pull_request_run(
        github=_FakePRReader(),
        actions=_FakeActionsReader(),
        commit=commit,
        workflow_run_id=99,
        trusted_workflow_paths=(".github/workflows/ci.yml",),
        harness_sensitive_paths=(".github/workflows/", "conftest.py"),
        changed_paths=("src/auth.py",),
    )
    key = ledger.record_ingestion(
        commit=commit,
        evidence=ingested.evidence,
        workflow_definition_sha256=ingested.workflow_definition_sha256,
        now=10,
    )
    digest = "b" * 64
    ledger.record_reconciliation(key, status="FAILED", reason="test failed", decision_sha256=digest, now=11)
    ledger.record_reconciliation(key, status="FAILED", reason="test failed", decision_sha256=digest, now=12)
    with pytest.raises(EvidenceLedgerConflict, match="immutable"):
        ledger.record_reconciliation(
            key, status="PASSED", reason="changed", decision_sha256="c" * 64, now=13
        )
    row = ledger.get_record(key)
    assert row is not None
    assert row["reconciliation_status"] == "FAILED"
    ledger.close()
