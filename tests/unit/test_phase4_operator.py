"""Tests for the staging-only Phase IV operator entry point."""

from __future__ import annotations

import hashlib
import json

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
        "PHASE4_GITHUB_TOKEN": "test-token",
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
    assert requests == ["/repos/acme/service/commits/phase-4%2Fstaging"]
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
