"""Tests for the SQLAlchemy run ledger, including SQLite-backed integration tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from verification_core.delivery_store import DeliveryStoreError
from verification_core.domain import (
    CommitIdentity,
    ObligationSource,
    Severity,
    VerificationObligation,
)
from verification_core.run_ledger import SQLAlchemyRunLedger


def make_commit() -> CommitIdentity:
    return CommitIdentity(
        repo_full_name="acme/service",
        pr_number=17,
        base_sha="1" * 40,
        head_sha="2" * 40,
        policy_sha256="a" * 64,
    )


def make_obligation() -> VerificationObligation:
    return VerificationObligation.propose(
        obligation_id="OBL-AUTH-01",
        category="authorization",
        description="Cross-user access must be denied.",
        severity=Severity.CRITICAL,
        source=ObligationSource.DETERMINISTIC_POLICY,
        affected_files=("src/authz.py",),
        candidate_test_id="tests/test_authz.py::test_cross_user_access_returns_403",
    )


def make_ledger(tmp_path: Path) -> SQLAlchemyRunLedger:
    return SQLAlchemyRunLedger(f"sqlite:///{tmp_path / 'runs.sqlite3'}")


def test_sqlalchemy_ledger_persists_run_and_obligations_across_instances(
    tmp_path: Path,
) -> None:
    ledger = make_ledger(tmp_path)
    commit = make_commit()
    run_key = ledger.save_verification_run(
        commit=commit,
        analysis_completeness="complete",
        planner_mode="deterministic",
        conclusion="action_required",
        summary="A critical behavior remains unverified.",
        obligations=(make_obligation(),),
        now=10,
    )
    ledger.set_check_run_id(run_key, 9001, now=11)
    ledger.close()

    reopened = make_ledger(tmp_path)
    record = reopened.get_verification_run(run_key)
    assert record is not None
    assert record["repository_full_name"] == "acme/service"
    assert record["head_sha"] == "2" * 40
    assert record["check_run_id"] == 9001
    obligations = record["obligations"]
    assert isinstance(obligations, list) and len(obligations) == 1
    assert obligations[0]["obligation_id"] == "OBL-AUTH-01"
    assert obligations[0]["affected_files"] == ["src/authz.py"]
    reopened.close()


def test_sqlalchemy_ledger_upserts_without_erasing_check_run_id(tmp_path: Path) -> None:
    ledger = make_ledger(tmp_path)
    commit = make_commit()
    run_key = ledger.save_verification_run(
        commit=commit,
        analysis_completeness="complete",
        planner_mode="deterministic",
        conclusion="action_required",
        summary="first",
        obligations=(make_obligation(),),
        now=10,
    )
    ledger.set_check_run_id(run_key, 9002, now=11)
    same_key = ledger.save_verification_run(
        commit=commit,
        analysis_completeness="complete",
        planner_mode="deterministic_fallback",
        conclusion="action_required",
        summary="updated after provider fallback",
        obligations=(make_obligation(),),
        now=12,
    )
    record = ledger.get_verification_run(same_key)
    assert record is not None
    assert record["check_run_id"] == 9002
    assert record["planner_mode"] == "deterministic_fallback"
    assert record["summary"] == "updated after provider fallback"
    ledger.close()


def test_sqlalchemy_ledger_validates_inputs_and_missing_records(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="database_url"):
        SQLAlchemyRunLedger("")
    with pytest.raises(ValueError, match="database_url"):
        SQLAlchemyRunLedger("mysql://user:pass@localhost/db")
    with pytest.raises(ValueError, match="pool_size"):
        SQLAlchemyRunLedger(f"sqlite:///{tmp_path / 'invalid.sqlite3'}", pool_size=0)

    ledger = make_ledger(tmp_path)
    with pytest.raises(ValueError, match="conclusion"):
        ledger.save_verification_run(
            commit=make_commit(),
            analysis_completeness="complete",
            planner_mode="deterministic",
            conclusion="stale",
            summary="summary",
            obligations=(),
        )
    with pytest.raises(ValueError, match="run_key"):
        ledger.get_verification_run("bad")
    with pytest.raises(ValueError, match="run_key"):
        ledger.set_check_run_id("bad", 123)
    with pytest.raises(ValueError, match="check_run_id"):
        ledger.set_check_run_id("a" * 64, 0)
    with pytest.raises(DeliveryStoreError, match="missing verification run"):
        ledger.set_check_run_id("b" * 64, 123)
    assert ledger.get_verification_run("c" * 64) is None
    ledger.close()
