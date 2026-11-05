"""Tests for the staging-only Phase IV operator entry point."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from _pytest.capture import CaptureFixture
from _pytest.monkeypatch import MonkeyPatch

import httpx
import pytest

from verification_core.phase4_operator import (
    _bind_expected_head_sha,
    _parse_input_schemas,
    load_staging_settings,
    verify_ref_head,
)

WORKFLOW = "phase4-staging-dispatch.yml"
SCHEMA = {
    WORKFLOW: {
        "verification_dispatch_id": {
            "required": True,
            "max_length": 32,
            "pattern": r"[0-9a-f]{32}",
        },
        "expected_head_sha": {
            "required": True,
            "max_length": 40,
            "pattern": r"[0-9a-f]{40}",
        },
    }
}


def environment() -> dict[str, str]:
    return {
        "PHASE4_ENVIRONMENT": "staging",
        "PHASE4_DISPATCH_ENABLED": "true",
        "PHASE4_GITHUB_TOKEN": hashlib.sha256(b"operator-fixture").hexdigest(),
        "PHASE4_REPOSITORY": "acme/service",
        "PHASE4_AUDIT_DATABASE_URL": "postgresql+psycopg://operator:password@db.example/audit",
        "PHASE4_ALLOWED_WORKFLOWS": WORKFLOW,
        "PHASE4_OPERATOR_ALLOWED_LOGINS": "operator",
        "PHASE4_ALLOWED_REVIEWERS": "maintainer",
        "PHASE4_WORKFLOW_INPUT_SCHEMAS": json.dumps(SCHEMA),
    }


def test_staging_settings_require_explicit_staging_opt_in_and_postgres() -> None:
    assert load_staging_settings(environment()).repository == "acme/service"
    wrong_environment = environment()
    wrong_environment["PHASE4_ENVIRONMENT"] = "production"
    with pytest.raises(ValueError, match="exactly 'staging'"):
        load_staging_settings(wrong_environment)
    disabled = environment()
    disabled["PHASE4_DISPATCH_ENABLED"] = "false"
    with pytest.raises(ValueError, match="explicitly set"):
        load_staging_settings(disabled)
    local_database = environment()
    local_database["PHASE4_AUDIT_DATABASE_URL"] = "sqlite:///audit.db"
    with pytest.raises(ValueError, match="managed PostgreSQL"):
        load_staging_settings(local_database)


def test_staging_settings_require_complete_allowlist_and_schemas() -> None:
    missing = environment()
    missing.pop("PHASE4_WORKFLOW_INPUT_SCHEMAS")
    with pytest.raises(ValueError, match="PHASE4_WORKFLOW_INPUT_SCHEMAS"):
        load_staging_settings(missing)
    malformed = environment()
    malformed["PHASE4_WORKFLOW_INPUT_SCHEMAS"] = "{}"
    with pytest.raises(ValueError, match="exactly the allowlisted workflows"):
        load_staging_settings(malformed)


def test_schema_requires_correlation_and_exact_head_inputs() -> None:
    assert set(
        _parse_input_schemas(json.dumps(SCHEMA), allowed_workflows=(WORKFLOW,))[WORKFLOW]
    ) == {"verification_dispatch_id", "expected_head_sha"}
    no_correlation = json.loads(json.dumps(SCHEMA))
    no_correlation[WORKFLOW].pop("verification_dispatch_id")
    with pytest.raises(ValueError, match="verification_dispatch_id"):
        _parse_input_schemas(json.dumps(no_correlation), allowed_workflows=(WORKFLOW,))
    bad_sha = json.loads(json.dumps(SCHEMA))
    bad_sha[WORKFLOW]["expected_head_sha"]["pattern"] = ".*"
    with pytest.raises(ValueError, match="expected_head_sha"):
        _parse_input_schemas(json.dumps(bad_sha), allowed_workflows=(WORKFLOW,))


def test_schema_rejects_unknown_rules_and_non_string_enumerations() -> None:
    bad_rule = json.loads(json.dumps(SCHEMA))
    bad_rule[WORKFLOW]["verification_dispatch_id"]["allow_anything"] = True
    with pytest.raises(ValueError, match="unknown rule keys"):
        _parse_input_schemas(json.dumps(bad_rule), allowed_workflows=(WORKFLOW,))
    bad_values = json.loads(json.dumps(SCHEMA))
    bad_values[WORKFLOW]["verification_dispatch_id"]["allowed_values"] = [1]
    with pytest.raises(ValueError, match="array of strings"):
        _parse_input_schemas(json.dumps(bad_values), allowed_workflows=(WORKFLOW,))


def test_ref_preflight_requires_exact_expected_sha() -> None:
    expected = "a" * 40
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.path)
        return httpx.Response(200, json={"sha": expected})

    client = httpx.Client(base_url="https://api.github.com", transport=httpx.MockTransport(handler))
    verify_ref_head(
        token=hashlib.sha256(b"operator-fixture").hexdigest(),
        repository="acme/service",
        ref="phase-4/staging",
        expected_head_sha=expected,
        http_client=client,
    )
    assert requests == ["/repos/acme/service/commits/phase-4/staging"]
    client.close()


def test_ref_preflight_fails_before_dispatch_on_stale_sha() -> None:
    client = httpx.Client(
        base_url="https://api.github.com",
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, json={"sha": "b" * 40})),
    )
    with pytest.raises(RuntimeError, match="no dispatch was sent"):
        verify_ref_head(
            token=hashlib.sha256(b"operator-fixture").hexdigest(),
            repository="acme/service",
            ref="staging",
            expected_head_sha="a" * 40,
            http_client=client,
        )
    client.close()


def test_ref_preflight_rejects_unavailable_remote_state() -> None:
    client = httpx.Client(
        base_url="https://api.github.com",
        transport=httpx.MockTransport(lambda _request: httpx.Response(503)),
    )
    with pytest.raises(RuntimeError, match="no dispatch was sent"):
        verify_ref_head(
            token=hashlib.sha256(b"operator-fixture").hexdigest(),
            repository="acme/service",
            ref="staging",
            expected_head_sha="a" * 40,
            http_client=client,
        )
    client.close()


def test_reconcile_and_review_can_run_with_dispatch_disabled() -> None:
    values = environment()
    values["PHASE4_DISPATCH_ENABLED"] = "false"
    settings = load_staging_settings(values, require_dispatch_enabled=False)
    assert settings.allowed_reviewers == ("maintainer",)
    with pytest.raises(ValueError, match="explicitly set"):
        load_staging_settings(values, require_dispatch_enabled=True)


def test_expected_sha_is_bound_to_ref_preflight_result() -> None:
    expected = "a" * 40
    assert _bind_expected_head_sha({"dry_run": "true"}, expected) == {
        "dry_run": "true",
        "expected_head_sha": expected,
    }
    assert (
        _bind_expected_head_sha({"expected_head_sha": expected}, expected)["expected_head_sha"]
        == expected
    )
    with pytest.raises(ValueError, match="match --expected-head-sha"):
        _bind_expected_head_sha({"expected_head_sha": "b" * 40}, expected)


def test_required_and_csv_helpers_reject_missing_empty_and_duplicate_values() -> None:
    from verification_core.phase4_operator import _csv_setting, _required

    with pytest.raises(ValueError, match="missing"):
        _required({}, "PHASE4_REPOSITORY")
    with pytest.raises(ValueError, match="at least one"):
        _csv_setting({"ALLOWLIST": " , "}, "ALLOWLIST")
    with pytest.raises(ValueError, match="duplicate"):
        _csv_setting({"ALLOWLIST": "Operator,operator"}, "ALLOWLIST")
    assert _csv_setting({"ALLOWLIST": "one, two"}, "ALLOWLIST") == ("one", "two")


def test_schema_parser_rejects_bad_types_and_invalid_rule_configuration() -> None:
    bad_required = json.loads(json.dumps(SCHEMA))
    bad_required[WORKFLOW]["verification_dispatch_id"]["required"] = "yes"
    with pytest.raises(ValueError, match="required must be a boolean"):
        _parse_input_schemas(json.dumps(bad_required), allowed_workflows=(WORKFLOW,))
    bad_max = json.loads(json.dumps(SCHEMA))
    bad_max[WORKFLOW]["verification_dispatch_id"]["max_length"] = 0
    with pytest.raises(ValueError, match="max_length"):
        _parse_input_schemas(json.dumps(bad_max), allowed_workflows=(WORKFLOW,))
    bad_pattern = json.loads(json.dumps(SCHEMA))
    bad_pattern[WORKFLOW]["dry_run"] = {"pattern": "["}
    with pytest.raises(ValueError, match="regular expression"):
        _parse_input_schemas(json.dumps(bad_pattern), allowed_workflows=(WORKFLOW,))


def test_staging_settings_reject_duplicate_allowlists_and_invalid_schemas() -> None:
    duplicate = environment()
    duplicate["PHASE4_OPERATOR_ALLOWED_LOGINS"] = "operator,OPERATOR"
    with pytest.raises(ValueError, match="duplicate"):
        load_staging_settings(duplicate)
    malformed = environment()
    malformed["PHASE4_WORKFLOW_INPUT_SCHEMAS"] = "{"
    with pytest.raises(ValueError, match="valid JSON"):
        load_staging_settings(malformed)
    bad_reviewers = environment()
    bad_reviewers["PHASE4_ALLOWED_REVIEWERS"] = "maintainer,MAINTAINER"
    with pytest.raises(ValueError, match="duplicate"):
        load_staging_settings(bad_reviewers)


def test_ref_preflight_rejects_bad_sha_malformed_json_and_oversized_response() -> None:
    with pytest.raises(ValueError, match="40-character"):
        verify_ref_head(
            token=hashlib.sha256(b"operator-fixture").hexdigest(),
            repository="acme/service",
            ref="staging",
            expected_head_sha="not-a-sha",
        )
    malformed = httpx.Client(
        base_url="https://api.github.com",
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, content=b"{")),
    )
    with pytest.raises(RuntimeError, match="malformed"):
        verify_ref_head(
            token=hashlib.sha256(b"operator-fixture").hexdigest(),
            repository="acme/service",
            ref="staging",
            expected_head_sha="a" * 40,
            http_client=malformed,
        )
    malformed.close()
    oversized = httpx.Client(
        base_url="https://api.github.com",
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, content=b"x" * (65 * 1024))
        ),
    )
    with pytest.raises(RuntimeError, match="size limit"):
        verify_ref_head(
            token=hashlib.sha256(b"operator-fixture").hexdigest(),
            repository="acme/service",
            ref="staging",
            expected_head_sha="a" * 40,
            http_client=oversized,
        )
    oversized.close()


def test_read_inputs_file_validates_size_json_and_string_mapping(tmp_path: Path) -> None:
    from verification_core.phase4_operator import _read_inputs_file

    valid = tmp_path / "inputs.json"
    valid.write_text(json.dumps({"dry_run": "true"}), encoding="utf-8")
    assert _read_inputs_file(str(valid)) == {"dry_run": "true"}
    invalid_json = tmp_path / "invalid.json"
    invalid_json.write_text("{", encoding="utf-8")
    with pytest.raises(ValueError, match="bounded JSON"):
        _read_inputs_file(str(invalid_json))
    invalid_values = tmp_path / "values.json"
    invalid_values.write_text(json.dumps({"dry_run": True}), encoding="utf-8")
    with pytest.raises(ValueError, match="string values"):
        _read_inputs_file(str(invalid_values))
    oversized = tmp_path / "large.json"
    oversized.write_text(json.dumps({"value": "x" * 17_000}), encoding="utf-8")
    with pytest.raises(ValueError, match="bounded JSON"):
        _read_inputs_file(str(oversized))


def test_bind_expected_sha_rejects_malformed_commit_identity() -> None:
    with pytest.raises(ValueError, match="40-character"):
        _bind_expected_head_sha({}, "not-a-sha")


def test_dispatch_operator_requires_confirmation_and_known_workflow() -> None:
    import argparse

    from verification_core import phase4_operator

    settings = load_staging_settings(environment())
    common = {
        "workflow": WORKFLOW,
        "ref": "staging",
        "expected_head_sha": "a" * 40,
        "inputs_file": None,
        "confirm_staging": False,
    }
    with pytest.raises(ValueError, match="--confirm-staging"):
        phase4_operator._dispatch(argparse.Namespace(**common), settings)
    unknown = dict(common, confirm_staging=True, workflow="not-allowed.yml")
    with pytest.raises(ValueError, match="not in PHASE4_ALLOWED_WORKFLOWS"):
        phase4_operator._dispatch(argparse.Namespace(**unknown), settings)
    invalid_sha = dict(common, confirm_staging=True, expected_head_sha="bad")
    with pytest.raises(ValueError, match="40-character"):
        phase4_operator._dispatch(argparse.Namespace(**invalid_sha), settings)


def test_dispatch_operator_binds_sha_and_closes_resources(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    import argparse

    from verification_core import phase4_operator
    from verification_core.dispatch_governance import DispatchReceipt

    expected = "a" * 40
    inputs_path = tmp_path / "operator-inputs.json"
    inputs_path.write_text(json.dumps({"dry_run": "true"}), encoding="utf-8")
    settings = load_staging_settings(environment())
    calls: dict[str, object] = {}
    closed: list[str] = []
    preflight_count = 0

    def preflight(**kwargs: object) -> None:
        nonlocal preflight_count
        preflight_count += 1
        assert kwargs["expected_head_sha"] == expected

    class FakeAuthenticator:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def close(self) -> None:
            closed.append("auth")

    class FakeAudit:
        def __init__(self, _url: str) -> None:
            pass

        def close(self) -> None:
            closed.append("audit")

    class FakeRunVerifier:
        def close(self) -> None:
            closed.append("verifier")

    class FakeCoordinator:
        def __init__(self, **kwargs: object) -> None:
            calls["coordinator_kwargs"] = kwargs

        def dispatch(self, **kwargs: object) -> DispatchReceipt:
            calls["dispatch_kwargs"] = kwargs
            inputs = kwargs["inputs"]
            assert isinstance(inputs, dict)
            assert inputs["expected_head_sha"] == expected
            assert inputs["dry_run"] == "true"
            return DispatchReceipt(
                dispatch_id=str(kwargs["dispatch_id"]),
                repository=str(kwargs["repository"]),
                workflow=str(kwargs["workflow"]),
                expected_head_sha=str(kwargs["expected_head_sha"]),
                operator_login="operator",
                state="submitted_unreconciled",
            )

    monkeypatch.setattr(phase4_operator, "verify_ref_head", preflight)
    monkeypatch.setattr(phase4_operator, "GitHubOperatorAuthenticator", FakeAuthenticator)
    monkeypatch.setattr(phase4_operator, "SQLAlchemyDispatchAuditLog", FakeAudit)
    monkeypatch.setattr(phase4_operator, "GitHubWorkflowRunVerifier", FakeRunVerifier)
    monkeypatch.setattr(phase4_operator, "WorkflowDispatchCoordinator", FakeCoordinator)
    args = argparse.Namespace(
        workflow=WORKFLOW,
        ref="staging",
        expected_head_sha=expected,
        inputs_file=str(inputs_path),
        confirm_staging=True,
    )
    assert phase4_operator._dispatch(args, settings) == 0
    assert preflight_count == 1
    assert closed == ["verifier", "audit", "auth"]
    output = capsys.readouterr().out
    assert "verification pending" in output
    assert "reconcile --dispatch-id" in output


def test_dispatch_operator_rejects_conflicting_sha_from_inputs_file(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    import argparse

    from verification_core import phase4_operator

    settings = load_staging_settings(environment())
    inputs_path = tmp_path / "conflicting.json"
    inputs_path.write_text(json.dumps({"expected_head_sha": "b" * 40}), encoding="utf-8")
    monkeypatch.setattr(
        phase4_operator,
        "verify_ref_head",
        lambda **_kwargs: None,
    )
    args = argparse.Namespace(
        workflow=WORKFLOW,
        ref="staging",
        expected_head_sha="a" * 40,
        inputs_file=str(inputs_path),
        confirm_staging=True,
    )
    with pytest.raises(ValueError, match="must match"):
        phase4_operator._dispatch(args, settings)


def test_reconcile_operator_handles_pending_and_successful_run(
    monkeypatch: MonkeyPatch, capsys: CaptureFixture[str]
) -> None:
    import argparse

    from verification_core import phase4_operator
    from verification_core.dispatch_governance import DispatchReceipt

    settings = load_staging_settings(environment())
    closed: list[str] = []
    run_visible = False

    class FakeAuthenticator:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def close(self) -> None:
            closed.append("auth")

    class FakeAudit:
        def __init__(self, _url: str) -> None:
            pass

        def get_dispatch(self, _dispatch_id: str) -> dict[str, object]:
            return {"workflow_run_id": 123}

        def close(self) -> None:
            closed.append("audit")

    class FakeRunVerifier:
        def close(self) -> None:
            closed.append("verifier")

    class FakeCoordinator:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def reconcile(self, **_kwargs: object) -> DispatchReceipt | None:
            if run_visible:
                return DispatchReceipt(
                    dispatch_id="d" * 32,
                    repository="acme/service",
                    workflow=WORKFLOW,
                    expected_head_sha="a" * 40,
                    operator_login="operator",
                    state="reconciled",
                )
            return None

    monkeypatch.setattr(phase4_operator, "GitHubOperatorAuthenticator", FakeAuthenticator)
    monkeypatch.setattr(phase4_operator, "SQLAlchemyDispatchAuditLog", FakeAudit)
    monkeypatch.setattr(phase4_operator, "GitHubWorkflowRunVerifier", FakeRunVerifier)
    monkeypatch.setattr(phase4_operator, "WorkflowDispatchCoordinator", FakeCoordinator)
    args = argparse.Namespace(dispatch_id="d" * 32, confirm_staging=False)
    with pytest.raises(ValueError, match="--confirm-staging"):
        phase4_operator._reconcile(args, settings)
    args.confirm_staging = True
    assert phase4_operator._reconcile(args, settings) == 3
    assert "not visible yet" in capsys.readouterr().out
    assert closed == ["verifier", "audit", "auth"]
    run_visible = True
    assert phase4_operator._reconcile(args, settings) == 0
    output = capsys.readouterr().out
    assert "run_id=123" in output
    assert "Phase III evidence ingestion is still required" in output


def test_reconcile_operator_rejects_invalid_dispatch_id_and_missing_record(
    monkeypatch: MonkeyPatch,
) -> None:
    import argparse

    from verification_core import phase4_operator

    settings = load_staging_settings(environment())
    args = argparse.Namespace(dispatch_id="../unsafe", confirm_staging=True)
    with pytest.raises(ValueError, match="32-character"):
        phase4_operator._reconcile(args, settings)

    class FakeAuthenticator:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def close(self) -> None:
            pass

    class FakeAudit:
        def __init__(self, _url: str) -> None:
            pass

        def get_dispatch(self, _dispatch_id: str) -> None:
            return None

        def close(self) -> None:
            pass

    class FakeRunVerifier:
        def close(self) -> None:
            pass

    class FakeCoordinator:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def reconcile(self, **_kwargs: object) -> DispatchReceipt:
            from verification_core.dispatch_governance import DispatchReceipt

            return DispatchReceipt(
                dispatch_id="d" * 32,
                repository="acme/service",
                workflow=WORKFLOW,
                expected_head_sha="a" * 40,
                operator_login="operator",
                state="reconciled",
            )

    monkeypatch.setattr(phase4_operator, "GitHubOperatorAuthenticator", FakeAuthenticator)
    monkeypatch.setattr(phase4_operator, "SQLAlchemyDispatchAuditLog", FakeAudit)
    monkeypatch.setattr(phase4_operator, "GitHubWorkflowRunVerifier", FakeRunVerifier)
    monkeypatch.setattr(phase4_operator, "WorkflowDispatchCoordinator", FakeCoordinator)
    args.dispatch_id = "d" * 32
    with pytest.raises(RuntimeError, match="could not be reloaded"):
        phase4_operator._reconcile(args, settings)


def test_verify_review_operator_requires_confirmation_and_records_approvals(
    monkeypatch: MonkeyPatch, capsys: CaptureFixture[str]
) -> None:
    import argparse
    from types import SimpleNamespace

    from verification_core import phase4_operator

    settings = load_staging_settings(environment())
    closed: list[str] = []
    recorded: list[object] = []
    approval = SimpleNamespace(
        reviewer_login="maintainer",
        review_id=77,
        head_sha="a" * 40,
    )

    class FakeVerifier:
        def __init__(self, **kwargs: object) -> None:
            assert kwargs["allowed_reviewers"] == ("maintainer",)

        def verify_current_approvals(self, **_kwargs: object) -> tuple[object, ...]:
            return (approval,)

        def close(self) -> None:
            closed.append("verifier")

    class FakeAudit:
        def __init__(self, _url: str) -> None:
            pass

        def record_approval(self, value: object, *, now: float) -> bool:
            recorded.append(value)
            assert now > 0
            return True

        def close(self) -> None:
            closed.append("audit")

    monkeypatch.setattr(phase4_operator, "GitHubReviewVerifier", FakeVerifier)
    monkeypatch.setattr(phase4_operator, "SQLAlchemyHumanReviewAuditLog", FakeAudit)
    args = argparse.Namespace(
        confirm_staging_review=False,
        pr_number=9,
        expected_base_sha="b" * 40,
        expected_head_sha="a" * 40,
    )
    with pytest.raises(ValueError, match="--confirm-staging-review"):
        phase4_operator._verify_review(args, settings)
    args.confirm_staging_review = True
    assert phase4_operator._verify_review(args, settings) == 0
    assert recorded == [approval]
    assert closed == ["audit", "verifier"]
    assert "1 new approval record" in capsys.readouterr().out


def test_verify_review_operator_reports_no_qualifying_approval(
    monkeypatch: MonkeyPatch, capsys: CaptureFixture[str]
) -> None:
    import argparse

    from verification_core import phase4_operator

    settings = load_staging_settings(environment())

    class FakeVerifier:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def verify_current_approvals(self, **_kwargs: object) -> tuple[()]:
            return ()

        def close(self) -> None:
            pass

    class FakeAudit:
        def __init__(self, _url: str) -> None:
            pass

        def close(self) -> None:
            pass

    monkeypatch.setattr(phase4_operator, "GitHubReviewVerifier", FakeVerifier)
    monkeypatch.setattr(phase4_operator, "SQLAlchemyHumanReviewAuditLog", FakeAudit)
    args = argparse.Namespace(
        confirm_staging_review=True,
        pr_number=9,
        expected_base_sha="b" * 40,
        expected_head_sha="a" * 40,
    )
    assert phase4_operator._verify_review(args, settings) == 4
    assert "No qualifying current approval" in capsys.readouterr().out


def test_main_dispatches_selected_command_and_sanitizes_operator_errors(
    monkeypatch: MonkeyPatch, capsys: CaptureFixture[str]
) -> None:
    from verification_core import phase4_operator

    settings = load_staging_settings(environment())
    requested: list[bool] = []

    def load(*, require_dispatch_enabled: bool) -> object:
        requested.append(require_dispatch_enabled)
        return settings

    monkeypatch.setattr(phase4_operator, "load_staging_settings", load)
    monkeypatch.setattr(phase4_operator, "_dispatch", lambda _args, _settings: 17)
    assert (
        phase4_operator.main(
            [
                "dispatch",
                "--workflow",
                WORKFLOW,
                "--ref",
                "staging",
                "--expected-head-sha",
                "a" * 40,
                "--confirm-staging",
            ]
        )
        == 17
    )
    assert requested == [True]

    def fail(*, require_dispatch_enabled: bool) -> object:
        raise ValueError("configuration rejected")

    monkeypatch.setattr(phase4_operator, "load_staging_settings", fail)
    assert phase4_operator.main(["reconcile", "--dispatch-id", "d" * 32]) == 2
    assert "configuration rejected" in capsys.readouterr().err
