"""Unit tests for Phase IV operator dispatch governance and reconciliation."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from verification_core.dispatch_governance import (
    DispatchAuthorizationError,
    DispatchAuditError,
    DuplicateDispatchError,
    ExactHeadMismatchError,
    GitHubOperator,
    GitHubOperatorAuthenticator,
    GitHubWorkflowRunVerifier,
    SQLAlchemyDispatchAuditLog,
    WorkflowDispatchCoordinator,
)

REPOSITORY = "acme/service"
WORKFLOW = "manual-verification.yml"
ACCESS = "example-user-access"
DISPATCH_ID = "a" * 32
HEAD = "b" * 40
OTHER_HEAD = "c" * 40


class FakeDispatcher:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.requests: list[dict[str, Any]] = []
        self.closed = False

    def dispatch(self, **kwargs: Any) -> None:
        self.requests.append(kwargs)
        if self.error:
            raise self.error

    def close(self) -> None:
        self.closed = True


def payload(*, sha: str = HEAD, run_id: int = 100, created: float = 1_000) -> dict[str, Any]:
    return {
        "id": run_id,
        "workflow_id": 77,
        "event": "workflow_dispatch",
        "display_title": f"verification-dispatch:{DISPATCH_ID}",
        "head_sha": sha,
        "head_branch": "phase-4-staging",
        "created_at": datetime.fromtimestamp(created, UTC).isoformat(),
        "actor": {"login": "operator"},
    }


def transport(
    *, permission: str = "write", login: str = "operator", runs: list[dict[str, Any]] | None = None
) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/user":
            return httpx.Response(200, json={"login": login})
        if request.url.path == f"/repos/{REPOSITORY}/collaborators/{login}/permission":
            return httpx.Response(200, json={"permission": permission})
        if request.url.path == f"/repos/{REPOSITORY}/actions/workflows/{WORKFLOW}":
            return httpx.Response(200, json={"id": 77})
        if request.url.path == f"/repos/{REPOSITORY}/actions/workflows/77/runs":
            return httpx.Response(200, json={"workflow_runs": runs or []})
        return httpx.Response(404, json={"message": "not found"})
    return httpx.MockTransport(handler)


def setup(
    tmp_path: Path,
    *,
    permission: str = "write",
    runs: list[dict[str, Any]] | None = None,
    dispatcher: FakeDispatcher | None = None,
) -> tuple[WorkflowDispatchCoordinator, SQLAlchemyDispatchAuditLog, FakeDispatcher]:
    mock = transport(permission=permission, runs=runs)
    auth_client = httpx.Client(base_url="https://api.github.com", transport=mock)
    verifier_client = httpx.Client(base_url="https://api.github.com", transport=mock)
    auth = GitHubOperatorAuthenticator(allowed_logins=("operator",), http_client=auth_client)
    verifier = GitHubWorkflowRunVerifier(http_client=verifier_client)
    audit = SQLAlchemyDispatchAuditLog(f"sqlite:///{tmp_path / 'audit.sqlite3'}")
    actual = dispatcher or FakeDispatcher()
    coordinator = WorkflowDispatchCoordinator(
        authenticator=auth,
        audit_log=audit,
        dispatcher_factory=lambda _access: actual,
        run_verifier=verifier,
    )
    return coordinator, audit, actual


def dispatch(coordinator: WorkflowDispatchCoordinator, *, now: float = 1_000) -> Any:
    return coordinator.dispatch(
        access_token=ACCESS,
        dispatch_id=DISPATCH_ID,
        repository=REPOSITORY,
        workflow=WORKFLOW,
        ref="phase-4-staging",
        expected_head_sha=HEAD,
        inputs={"dry_run": "true"},
        now=now,
    )


def test_authenticator_requires_allowlisted_login_and_write_permission() -> None:
    client = httpx.Client(base_url="https://api.github.com", transport=transport())
    auth = GitHubOperatorAuthenticator(allowed_logins=("operator",), http_client=client)
    assert auth.authenticate(ACCESS, REPOSITORY) == GitHubOperator("operator", "write")
    client.close()
    read_client = httpx.Client(
        base_url="https://api.github.com", transport=transport(permission="read")
    )
    read_auth = GitHubOperatorAuthenticator(allowed_logins=("operator",), http_client=read_client)
    with pytest.raises(DispatchAuthorizationError, match="write, maintain, or admin"):
        read_auth.authenticate(ACCESS, REPOSITORY)
    read_client.close()


def test_authenticator_rejects_non_allowlisted_identity() -> None:
    client = httpx.Client(
        base_url="https://api.github.com", transport=transport(login="intruder")
    )
    auth = GitHubOperatorAuthenticator(allowed_logins=("operator",), http_client=client)
    with pytest.raises(DispatchAuthorizationError, match="not an allowed operator"):
        auth.authenticate(ACCESS, REPOSITORY)
    client.close()


def test_dispatch_is_write_ahead_audited_and_correlated(tmp_path: Path) -> None:
    coordinator, audit, fake = setup(tmp_path)
    receipt = dispatch(coordinator)
    record = audit.get_dispatch(DISPATCH_ID)
    assert receipt.state == "submitted_unreconciled"
    assert record is not None and record["state"] == "submitted_unreconciled"
    assert record["operator_login"] == "operator" and record["expected_head_sha"] == HEAD
    assert ACCESS not in str(record) and "dry_run" not in str(record)
    assert fake.closed
    assert fake.requests[0]["inputs"] == {
        "dry_run": "true",
        "verification_dispatch_id": DISPATCH_ID
    }
    audit.close()


def test_duplicate_dispatch_id_never_repeats_external_side_effect(tmp_path: Path) -> None:
    coordinator, audit, fake = setup(tmp_path)
    dispatch(coordinator)
    with pytest.raises(DuplicateDispatchError):
        dispatch(coordinator)
    assert len(fake.requests) == 1
    audit.close()


def test_dispatch_timeout_is_recorded_unknown_and_not_retried(tmp_path: Path) -> None:
    fake = FakeDispatcher(TimeoutError("synthetic timeout"))
    coordinator, audit, _ = setup(tmp_path, dispatcher=fake)
    with pytest.raises(TimeoutError):
        dispatch(coordinator)
    record = audit.get_dispatch(DISPATCH_ID)
    assert record is not None and record["state"] == "dispatch_outcome_unknown"
    assert len(fake.requests) == 1
    audit.close()


def test_dispatch_reconciles_exact_sha(tmp_path: Path) -> None:
    coordinator, audit, _ = setup(tmp_path, runs=[payload()])
    dispatch(coordinator)
    receipt = coordinator.reconcile(access_token=ACCESS, dispatch_id=DISPATCH_ID, now=1_001)
    record = audit.get_dispatch(DISPATCH_ID)
    assert receipt is not None and receipt.state == "reconciled"
    assert record is not None and record["state"] == "reconciled"
    assert record["workflow_run_id"] == 100 and record["observed_head_sha"] == HEAD
    audit.close()


def test_dispatch_mismatched_sha_fails_closed(tmp_path: Path) -> None:
    coordinator, audit, _ = setup(tmp_path, runs=[payload(sha=OTHER_HEAD)])
    dispatch(coordinator)
    with pytest.raises(ExactHeadMismatchError, match="different commit"):
        coordinator.reconcile(access_token=ACCESS, dispatch_id=DISPATCH_ID, now=1_001)
    record = audit.get_dispatch(DISPATCH_ID)
    assert record is not None and record["state"] == "head_mismatch"
    assert record["observed_head_sha"] == OTHER_HEAD
    audit.close()


def test_reconcile_waits_when_run_not_yet_visible(tmp_path: Path) -> None:
    coordinator, audit, _ = setup(tmp_path)
    dispatch(coordinator)
    assert coordinator.reconcile(access_token=ACCESS, dispatch_id=DISPATCH_ID) is None
    record = audit.get_dispatch(DISPATCH_ID)
    assert record is not None and record["state"] == "submitted_unreconciled"
    audit.close()


def test_audit_survives_store_reopen_and_transitions_are_guarded(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'durable.sqlite3'}"
    first = SQLAlchemyDispatchAuditLog(url)
    first.record_authorized(
        dispatch_id=DISPATCH_ID,
        repository=REPOSITORY,
        workflow=WORKFLOW,
        ref="main",
        expected_head_sha=HEAD,
        inputs_sha256="d" * 64,
        operator=GitHubOperator("operator", "write"),
        now=10,
    )
    first.mark_submitted(DISPATCH_ID, now=11)
    first.close()
    second = SQLAlchemyDispatchAuditLog(url)
    record = second.get_dispatch(DISPATCH_ID)
    assert record is not None and record["state"] == "submitted_unreconciled"
    with pytest.raises(DispatchAuditError, match="invalid state transition"):
        second.mark_submitted(DISPATCH_ID, now=12)
    second.close()


def test_duplicate_identifier_conflict_is_never_overwritten(tmp_path: Path) -> None:
    audit = SQLAlchemyDispatchAuditLog(f"sqlite:///{tmp_path / 'conflict.sqlite3'}")
    operator = GitHubOperator("operator", "write")
    audit.record_authorized(
        dispatch_id=DISPATCH_ID,
        repository=REPOSITORY,
        workflow=WORKFLOW,
        ref="main",
        expected_head_sha=HEAD,
        inputs_sha256="d" * 64,
        operator=operator,
        now=10,
    )
    with pytest.raises(DuplicateDispatchError):
        audit.record_authorized(
            dispatch_id=DISPATCH_ID,
            repository=REPOSITORY,
            workflow=WORKFLOW,
            ref="main",
            expected_head_sha=OTHER_HEAD,
            inputs_sha256="e" * 64,
            operator=operator,
            now=10,
        )
    audit.close()


def test_multiple_runs_matching_one_correlation_are_rejected(tmp_path: Path) -> None:
    client = httpx.Client(
        base_url="https://api.github.com",
        transport=transport(runs=[payload(run_id=1), payload(run_id=2)]),
    )
    verifier = GitHubWorkflowRunVerifier(http_client=client)
    with pytest.raises(Exception, match="Multiple workflow runs"):
        verifier.find_dispatch_run(
            access_token=ACCESS,
            repository=REPOSITORY,
            workflow=WORKFLOW,
            dispatch_id=DISPATCH_ID,
            operator_login="operator",
            created_after=1_000,
        )
    client.close()


@pytest.mark.parametrize("identifier", ["", "a" * 31, "A" * 32, "../" + "a" * 29])
def test_dispatch_rejects_invalid_id_before_side_effect(tmp_path: Path, identifier: str) -> None:
    coordinator, audit, fake = setup(tmp_path)
    with pytest.raises(ValueError, match="dispatch_id"):
        coordinator.dispatch(
            access_token=ACCESS,
            dispatch_id=identifier,
            repository=REPOSITORY,
            workflow=WORKFLOW,
            ref="main",
            expected_head_sha=HEAD,
            inputs={},
        )
    assert fake.requests == []
    audit.close()

