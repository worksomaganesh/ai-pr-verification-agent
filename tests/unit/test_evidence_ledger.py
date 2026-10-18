"""Integration tests for durable authenticated evidence records."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from verification_core.actions_evidence import AuthenticatedEvidenceArtifact
from verification_core.coverage import CoverageCase, CoverageManifest
from verification_core.domain.enums import ExecutionOutcome
from verification_core.domain.models import CommitIdentity, WorkflowProvenance
from verification_core.evidence_ledger import EvidenceLedgerConflict, SQLAlchemyEvidenceLedger
from verification_core.evidence import JUnitCase, JUnitReport


BASE = "1" * 40
HEAD = "2" * 40
POLICY = "a" * 64


def make_commit() -> CommitIdentity:
    return CommitIdentity(
        repo_full_name="acme/service",
        pr_number=7,
        base_sha=BASE,
        head_sha=HEAD,
        policy_sha256=POLICY,
    )


def make_evidence() -> AuthenticatedEvidenceArtifact:
    provenance = WorkflowProvenance(
        workflow_run_id=99,
        workflow_head_sha=HEAD,
        workflow_base_sha=BASE,
        workflow_path=".github/workflows/ci.yml",
        is_trusted_workflow_from_base=True,
        harness_untampered=True,
        step_completed_cleanly=True,
        recorded_at=datetime.now(UTC),
    )
    junit = JUnitReport(
        total_tests=1,
        passed=1,
        failed=0,
        errors=0,
        skipped=0,
        cases=(
            JUnitCase(
                node_id="tests.test_auth::test_access",
                outcome=ExecutionOutcome.PASSED,
                duration_seconds=0.01,
                detail=None,
            ),
        ),
    )
    coverage = CoverageManifest(
        version=1,
        head_sha=HEAD,
        cases=(
            CoverageCase(
                node_id="tests.test_auth::test_access",
                outcome=ExecutionOutcome.PASSED,
                lines_by_file=(("src/auth.py", (10,)),),
                branches_by_file=(("src/auth.py", ("10:0",)),),
                behavioral_assertion_verified=True,
            ),
        ),
    )
    return AuthenticatedEvidenceArtifact(
        repository_full_name="acme/service",
        pull_request_number=7,
        base_sha=BASE,
        head_sha=HEAD,
        workflow_run_id=99,
        workflow_id=12,
        workflow_path=".github/workflows/ci.yml",
        workflow_attempt=1,
        artifact_id=55,
        artifact_name="verification-evidence",
        artifact_sha256="c" * 64,
        provenance=provenance,
        junit_report=junit,
        coverage_manifest=coverage,
    )


def make_ledger(tmp_path: Path) -> SQLAlchemyEvidenceLedger:
    return SQLAlchemyEvidenceLedger(f"sqlite:///{tmp_path / 'evidence.sqlite3'}")


def record_evidence(ledger: SQLAlchemyEvidenceLedger, *, now: float = 10) -> str:
    return ledger.record_ingestion(
        commit=make_commit(),
        evidence=make_evidence(),
        workflow_definition_sha256="d" * 64,
        now=now,
    )


def test_ledger_rejects_invalid_database_url() -> None:
    with pytest.raises(ValueError, match="database_url"):
        SQLAlchemyEvidenceLedger("")
    with pytest.raises(ValueError, match="database_url"):
        SQLAlchemyEvidenceLedger("mysql://invalid")


def test_ledger_recording_starts_inconclusive_and_is_idempotent(tmp_path: Path) -> None:
    ledger = make_ledger(tmp_path)
    first_key = record_evidence(ledger)
    second_key = record_evidence(ledger, now=11)
    assert first_key == second_key
    ledger.close()

    reopened = make_ledger(tmp_path)
    row = reopened.get_record(first_key)
    assert row is not None
    assert row["reconciliation_status"] == "INCONCLUSIVE"
    assert row["artifact_sha256"] == "c" * 64
    assert row["test_inventory_sha256"]
    reopened.close()


def test_ledger_rejects_same_identity_with_conflicting_artifact_digest(tmp_path: Path) -> None:
    ledger = make_ledger(tmp_path)
    record_evidence(ledger)
    conflicting = make_evidence()
    conflicting = AuthenticatedEvidenceArtifact(
        repository_full_name=conflicting.repository_full_name,
        pull_request_number=conflicting.pull_request_number,
        base_sha=conflicting.base_sha,
        head_sha=conflicting.head_sha,
        workflow_run_id=conflicting.workflow_run_id,
        workflow_id=conflicting.workflow_id,
        workflow_path=conflicting.workflow_path,
        workflow_attempt=conflicting.workflow_attempt,
        artifact_id=conflicting.artifact_id,
        artifact_name=conflicting.artifact_name,
        artifact_sha256="e" * 64,
        provenance=conflicting.provenance,
        junit_report=conflicting.junit_report,
        coverage_manifest=conflicting.coverage_manifest,
    )
    with pytest.raises(EvidenceLedgerConflict, match="conflicting contents"):
        ledger.record_ingestion(
            commit=make_commit(),
            evidence=conflicting,
            workflow_definition_sha256="d" * 64,
            now=12,
        )
    ledger.close()


def test_ledger_records_terminal_reconciliation_once(tmp_path: Path) -> None:
    ledger = make_ledger(tmp_path)
    key = record_evidence(ledger)
    digest = "b" * 64
    ledger.record_reconciliation(
        key, status="FAILED", reason="test failed", decision_sha256=digest, now=11
    )
    ledger.record_reconciliation(
        key, status="FAILED", reason="test failed", decision_sha256=digest, now=12
    )
    with pytest.raises(EvidenceLedgerConflict, match="immutable"):
        ledger.record_reconciliation(
            key, status="PASSED", reason="changed", decision_sha256="c" * 64, now=13
        )
    row = ledger.get_record(key)
    assert row is not None
    assert row["reconciliation_status"] == "FAILED"
    ledger.close()


def test_ledger_policy_digest_is_part_of_evidence_identity(tmp_path: Path) -> None:
    ledger = make_ledger(tmp_path)
    first = make_commit()
    first_key = ledger.record_ingestion(
        commit=first,
        evidence=make_evidence(),
        workflow_definition_sha256="d" * 64,
        now=10,
    )
    second = CommitIdentity(
        repo_full_name=first.repo_full_name,
        pr_number=first.pr_number,
        base_sha=first.base_sha,
        head_sha=first.head_sha,
        policy_sha256="b" * 64,
    )
    second_key = ledger.record_ingestion(
        commit=second,
        evidence=make_evidence(),
        workflow_definition_sha256="d" * 64,
        now=11,
    )
    assert first_key != second_key
    assert ledger.get_record(first_key) is not None
    assert ledger.get_record(second_key) is not None
    ledger.close()


@pytest.mark.parametrize("bad_now", [float("nan"), float("inf"), -1, True])
def test_ledger_rejects_invalid_timestamp(tmp_path: Path, bad_now: float) -> None:
    ledger = make_ledger(tmp_path)
    with pytest.raises(ValueError, match="finite non-negative"):
        ledger.record_ingestion(
            commit=make_commit(),
            evidence=make_evidence(),
            workflow_definition_sha256="d" * 64,
            now=bad_now,
        )
    ledger.close()


def test_ledger_rejects_evidence_that_does_not_match_commit(tmp_path: Path) -> None:
    ledger = make_ledger(tmp_path)
    stale = make_evidence()
    stale = AuthenticatedEvidenceArtifact(
        repository_full_name=stale.repository_full_name,
        pull_request_number=stale.pull_request_number,
        base_sha=stale.base_sha,
        head_sha="3" * 40,
        workflow_run_id=stale.workflow_run_id,
        workflow_id=stale.workflow_id,
        workflow_path=stale.workflow_path,
        workflow_attempt=stale.workflow_attempt,
        artifact_id=stale.artifact_id,
        artifact_name=stale.artifact_name,
        artifact_sha256=stale.artifact_sha256,
        provenance=stale.provenance,
        junit_report=stale.junit_report,
        coverage_manifest=stale.coverage_manifest,
    )
    with pytest.raises(ValueError, match="provenance"):
        ledger.record_ingestion(
            commit=make_commit(),
            evidence=stale,
            workflow_definition_sha256="d" * 64,
        )
    ledger.close()
