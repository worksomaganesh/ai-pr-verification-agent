"""End-to-end mocked Phase II queue -> context -> plan -> Check Run orchestration."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from types import SimpleNamespace
from typing import Any, cast

import pytest

import verification_core.phase_two as phase_two
from verification_core.delivery_store import SQLiteDeliveryStore
from verification_core.github_app import GitHubAPIError, InstallationToken
from verification_core.planning import InventoryEntry
from verification_core.webhooks import PullRequestWebhookEvent

BASE = "1" * 40
SAMPLE_CREDENTIAL_VALUE = "sample-installation-value"
HEAD = "2" * 40
POLICY = """version: 1
trusted_workflows:
  - .github/workflows/ci.yml
runner_profiles:
  - pytest_targeted
severity_rules:
  critical:
    blocking: true
    human_approval_allowed: true
  high:
    blocking: true
    human_approval_allowed: true
  medium:
    blocking: false
    human_approval_allowed: true
  low:
    blocking: false
    human_approval_allowed: true
harness_sensitive_paths:
  - .verification-policy.yml
  - .github/workflows/
  - conftest.py
  - pytest.ini
  - pyproject.toml
  - package.json
obligations:
  - id: OBL-WHK-01
    category: webhook_idempotency
    severity: critical
    claim: Duplicate webhook event IDs must not process the same event twice.
    runner_profile: pytest_targeted
    selector: tests/test_webhooks.py::test_duplicate_event_is_ignored
"""


def event(
    delivery_id: str = "phase-two-1", *, installation_id: int | None = 42
) -> PullRequestWebhookEvent:
    return PullRequestWebhookEvent(
        delivery_id=delivery_id,
        action="opened",
        repository_full_name="acme/service",
        pr_number=7,
        base_sha=BASE,
        head_sha=HEAD,
        base_ref="main",
        head_ref="feature",
        installation_id=installation_id,
    )


class FakeAuthenticator:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.installations: list[int] = []

    def create_installation_token(self, installation_id: int) -> InstallationToken:
        self.installations.append(installation_id)
        if self.error:
            raise self.error
        from datetime import UTC, datetime, timedelta

        return InstallationToken(
            token=SAMPLE_CREDENTIAL_VALUE,
            expires_at=datetime.now(UTC) + timedelta(minutes=10),
        )


class FakeRESTClient:
    def __init__(self) -> None:
        self.pr_calls = 0
        self.published: list[dict[str, Any]] = []
        self.closed = False

    def get_pull_request(self, repository: str, pr_number: int) -> Mapping[str, Any]:
        self.pr_calls += 1
        if self.pr_calls == 1:
            return {
                "state": "open",
                "base": {"sha": BASE, "ref": "main"},
                "head": {"sha": HEAD, "ref": "feature"},
            }
        return {"html_url": "https://github.com/acme/service/pull/7"}

    def get_file_content(self, repository: str, path: str, ref: str) -> str | None:
        assert ref == BASE
        return POLICY if path == ".verification-policy.yml" else None

    def list_pull_request_files(
        self, repository: str, pr_number: int, *, page: int, per_page: int
    ) -> Sequence[Mapping[str, Any]]:
        if page == 1:
            return (
                {
                    "filename": "src/webhooks.py",
                    "status": "modified",
                    "additions": 1,
                    "deletions": 0,
                    "patch": "@@ -1,1 +1,2 @@\n old\n+new",
                },
            )
        return ()

    def list_test_inventory(self, repository: str, head_sha: str) -> tuple[InventoryEntry, ...]:
        return (
            InventoryEntry(
                selector="tests/test_webhooks.py::test_duplicate_event",
                path="tests/test_webhooks.py",
            ),
        )

    def publish_check_run(self, **kwargs: Any) -> int:
        self.published.append(kwargs)
        return 1234

    def close(self) -> None:
        self.closed = True


def make_store(tmp_path: Any, delivery: PullRequestWebhookEvent) -> SQLiteDeliveryStore:
    store = SQLiteDeliveryStore(str(tmp_path / "phase-two.sqlite3"))
    store.enqueue(delivery, now=10)
    return store


def test_processor_publishes_action_required_for_unexecuted_critical_obligations(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = make_store(tmp_path, event())
    auth = FakeAuthenticator()
    fake_client = FakeRESTClient()
    monkeypatch.setattr(phase_two, "GitHubRESTClient", lambda _token: fake_client)
    processor = phase_two.PhaseTwoProcessor(store=store, authenticator=auth)
    result = processor.process_next()
    assert result is not None
    assert result.status == "completed"
    assert result.conclusion == "action_required"
    assert result.check_run_id == 1234
    assert result.run_key is not None
    persisted_run = store.get_verification_run(result.run_key)
    assert persisted_run is not None
    assert persisted_run["check_run_id"] == 1234
    assert persisted_run["conclusion"] == "action_required"
    assert isinstance(persisted_run["obligations"], list)
    assert store.get_status("phase-two-1") == "completed"
    assert auth.installations == [42]
    assert fake_client.closed
    assert fake_client.published[0]["head_sha"] == HEAD
    assert fake_client.published[0]["conclusion"] == "action_required"
    assert "No test commands were run" in fake_client.published[0]["summary"]
    assert "proposed; not executed" in fake_client.published[0]["summary"]


def test_processor_returns_none_when_queue_is_empty(tmp_path: Any) -> None:
    store = SQLiteDeliveryStore(str(tmp_path / "empty.sqlite3"))
    result = phase_two.PhaseTwoProcessor(
        store=store, authenticator=FakeAuthenticator()
    ).process_next()
    assert result is None


def test_processor_retries_missing_installation_identity(tmp_path: Any) -> None:
    store = make_store(tmp_path, event("missing-installation", installation_id=None))
    processor = phase_two.PhaseTwoProcessor(store=store, authenticator=FakeAuthenticator())
    result = processor.process_next()
    assert result is not None
    assert result.status == "retrying"
    assert result.reason_code == "processing_failed"
    assert store.get_status("missing-installation") == "pending"


def test_processor_sanitizes_github_auth_failures(tmp_path: Any) -> None:
    store = make_store(tmp_path, event("api-failure"))
    processor = phase_two.PhaseTwoProcessor(
        store=store,
        authenticator=FakeAuthenticator(error=GitHubAPIError("private token detail")),
    )
    result = processor.process_next()
    assert result is not None
    assert result.status == "retrying"
    assert result.reason_code == "processing_failed"
    assert store.get_status("api-failure") == "pending"


def test_processor_uses_deterministic_fallback_when_model_factory_fails(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = make_store(tmp_path, event("model-failure"))
    fake_client = FakeRESTClient()
    monkeypatch.setattr(phase_two, "GitHubRESTClient", lambda _token: fake_client)

    class BrokenModel:
        def propose_hypotheses(self, _context: Any) -> object:
            raise RuntimeError("provider unavailable")

    def broken_model_factory() -> Any:
        return BrokenModel()

    processor = phase_two.PhaseTwoProcessor(
        store=store,
        authenticator=FakeAuthenticator(),
        model_factory=broken_model_factory,
    )
    result = processor.process_next()
    assert result is not None and result.status == "completed"
    assert fake_client.published
    assert "deterministic" in fake_client.published[0]["summary"].lower()


def test_processor_rejects_invalid_check_name(tmp_path: Any) -> None:
    store = SQLiteDeliveryStore(str(tmp_path / "empty.sqlite3"))
    with pytest.raises(ValueError):
        phase_two.PhaseTwoProcessor(store=store, authenticator=FakeAuthenticator(), check_name="")


def test_phase_three_worker_is_opt_in_and_requests_actions_read(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = make_store(tmp_path, event("phase-three-enabled"))
    fake_client = FakeRESTClient()
    monkeypatch.setattr(phase_two, "GitHubRESTClient", lambda _token: fake_client)

    class PhaseThreeAuthenticator(FakeAuthenticator):
        def __init__(self) -> None:
            super().__init__()
            self.actions_read_requested = False

        def create_installation_token(
            self, installation_id: int, *, include_actions_read: bool = False
        ) -> InstallationToken:
            self.actions_read_requested = include_actions_read
            return super().create_installation_token(installation_id)

    class FakeActionsClient:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

    class FakeEvidenceLedger:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

    auth = PhaseThreeAuthenticator()
    actions = FakeActionsClient()
    evidence_ledger = FakeEvidenceLedger()
    calls: list[dict[str, Any]] = []

    def fake_phase_three_worker(**kwargs: Any) -> Any:
        calls.append(kwargs)
        planning = kwargs["planning"]
        evaluation = phase_two.evaluate_verification_run(
            commit=kwargs["commit"],
            obligations=planning.obligations,
            analysis_completeness=planning.analysis_completeness,
            policy_config=kwargs["policy_config"],
            policy_valid=True,
        )
        return SimpleNamespace(
            publication=SimpleNamespace(evaluation=evaluation, check_run_id=5678),
            summary="Mocked Phase III evidence reconciliation result.",
        )

    monkeypatch.setattr(phase_two, "process_pull_request_evidence", fake_phase_three_worker)
    processor = phase_two.PhaseTwoProcessor(
        store=store,
        authenticator=auth,
        phase_three_enabled=True,
        evidence_ledger=cast(Any, evidence_ledger),
        actions_client_factory=cast(Any, lambda _token: actions),
    )
    result = processor.process_next()

    assert result is not None
    assert result.status == "completed"
    assert result.check_run_id == 5678
    assert auth.actions_read_requested is True
    assert len(calls) == 1
    assert calls[0]["evidence_ledger"] is evidence_ledger
    assert actions.closed is True
    processor.close()
    assert evidence_ledger.closed is True


def test_phase_three_pending_run_is_retried_and_client_closed(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = make_store(tmp_path, event("phase-three-pending"))
    fake_client = FakeRESTClient()
    monkeypatch.setattr(phase_two, "GitHubRESTClient", lambda _token: fake_client)

    class PhaseThreeAuthenticator(FakeAuthenticator):
        def create_installation_token(
            self, installation_id: int, *, include_actions_read: bool = False
        ) -> InstallationToken:
            assert include_actions_read is True
            return super().create_installation_token(installation_id)

    class FakeActionsClient:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

    actions = FakeActionsClient()

    def pending_worker(**_kwargs: Any) -> Any:
        raise phase_two.PhaseThreeRunPending("workflow still running")

    monkeypatch.setattr(phase_two, "process_pull_request_evidence", pending_worker)
    processor = phase_two.PhaseTwoProcessor(
        store=store,
        authenticator=PhaseThreeAuthenticator(),
        phase_three_enabled=True,
        evidence_ledger=cast(Any, object()),
        actions_client_factory=cast(Any, lambda _token: actions),
    )
    result = processor.process_next()

    assert result is not None
    assert result.status == "retrying"
    assert result.reason_code == "phase3_run_pending"
    assert store.get_status("phase-three-pending") == "pending"
    assert actions.closed is True
