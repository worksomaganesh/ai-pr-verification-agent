"""Security and behavior tests for Phase 1B policy validation and runner allowlisting."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from verification_core.policy import (
    RUNNER_PROFILES,
    PolicyValidationError,
    command_for,
    validate_policy_text,
    validate_test_selector,
)

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = (ROOT / ".verification-policy.example.yml").read_text(encoding="utf-8")


def valid_policy_text() -> str:
    """Return the checked-in policy example as the schema's baseline fixture."""
    return EXAMPLE


def replace_once(text: str, old: str, new: str) -> str:
    """Replace a required fragment and fail if the fixture ever drifts."""
    assert old in text
    return text.replace(old, new, 1)


def test_checked_in_example_is_valid_and_immutable() -> None:
    policy = validate_policy_text(valid_policy_text())
    assert policy.version == 1
    assert policy.trusted_workflows == (".github/workflows/ci.yml",)
    assert policy.runner_profiles == ("pytest_targeted",)
    assert [item.obligation_id for item in policy.obligations] == [
        "OBL-WHK-01",
        "OBL-AUTH-01",
    ]
    assert policy.severity_rule("critical").blocking is True
    with pytest.raises(FrozenInstanceError):
        policy.version = 2  # type: ignore[misc]


def test_runner_registry_has_fixed_argv_without_shell() -> None:
    policy = validate_policy_text(valid_policy_text())
    argv = command_for(policy, "pytest_targeted", "tests/test_authz.py::test_cross_user_access_returns_403")
    assert argv[:2] == RUNNER_PROFILES["pytest_targeted"].argv_prefix[:2]
    assert argv[-1] == "tests/test_authz.py::test_cross_user_access_returns_403"
    assert all(isinstance(arg, str) for arg in argv)
    assert "shell" not in " ".join(argv).lower()


def test_full_runner_is_fixed_and_rejects_selectors() -> None:
    text = replace_once(
        valid_policy_text(),
        "runner_profiles:\n  - pytest_targeted",
        "runner_profiles:\n  - pytest_targeted\n  - pytest_full",
    )
    policy = validate_policy_text(text)
    argv = command_for(policy, "pytest_full")
    assert argv[-1] == "tests"
    with pytest.raises(PolicyValidationError, match="does not accept a selector"):
        command_for(policy, "pytest_full", "tests/test_authz.py::test_case")


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("", "mapping"),
        ("version: 1\nversion: 1", "Duplicate YAML key"),
        (replace_once(EXAMPLE, "version: 1", "version: true"), "integer 1"),
        (replace_once(EXAMPLE, "version: 1", "version: 2"), "integer 1"),
        (replace_once(EXAMPLE, "version: 1", "version: 1\nextra: yes"), "unknown key"),
        (replace_once(EXAMPLE, "version: 1", "version: 1\n"), "missing required key"),
        (replace_once(EXAMPLE, "version: 1", "version: 1\n"), "missing required key"),
        (EXAMPLE.replace("runner_profiles:\n  - pytest_targeted", "runner_profiles:\n  - shell_exec"), "Unknown fixed runner profile"),
        (EXAMPLE.replace(".github/workflows/ci.yml", "../ci.yml"), "trusted_workflows"),
        (EXAMPLE.replace("blocking: true", "blocking: false", 1), "must remain blocking"),
        (EXAMPLE.replace("harness_sensitive_paths:\n", "harness_sensitive_paths:\n  - safe.txt\n", 1), "omits mandatory protection"),
        (EXAMPLE.replace("severity: critical", "severity: urgent", 1), "severity must be one of"),
        (EXAMPLE.replace("runner_profile: pytest_targeted", "runner_profile: not_enabled", 1), "not enabled"),
        (EXAMPLE.replace("selector: tests/test_webhooks.py::test_duplicate_event_is_ignored", "selector: --help", 1), "selector"),
    ],
)
def test_invalid_policies_fail_closed(text: str, message: str) -> None:
    with pytest.raises(PolicyValidationError, match=message):
        validate_policy_text(text)


def test_yaml_aliases_and_anchors_are_rejected() -> None:
    with pytest.raises(PolicyValidationError, match="anchors and aliases"):
        validate_policy_text("base: &base value\nalias: *base")


def test_yaml_merge_keys_are_rejected() -> None:
    with pytest.raises(PolicyValidationError, match="merge keys"):
        validate_policy_text(
            "root: &base {version: 1}\npolicy:\n  <<: *base"
        )


def test_invalid_yaml_and_unknown_yaml_tags_are_rejected() -> None:
    with pytest.raises(PolicyValidationError, match="Invalid policy YAML"):
        validate_policy_text("version: [unterminated")
    with pytest.raises(PolicyValidationError, match="Invalid policy YAML"):
        validate_policy_text("version: !!python/object/apply:os.system ['echo unsafe']")


@pytest.mark.parametrize(
    "selector",
    [
        "--help",
        "../tests/test_authz.py::test_case",
        "/tmp/test_authz.py::test_case",
        "tests/../test_authz.py::test_case",
        "tests\\test_authz.py::test_case",
        "tests/test_authz.py -k test_case",
        "tests/test_authz.py;touch",
        "tests/test_authz.py::bad-node!",
        "test_authz.py::test_case",
        "tests/test_authz.txt::test_case",
    ],
)
def test_unsafe_or_ambiguous_selectors_are_rejected(selector: str) -> None:
    with pytest.raises(PolicyValidationError):
        validate_test_selector(selector)


def test_valid_selector_with_multiple_node_ids_is_accepted() -> None:
    assert (
        validate_test_selector("tests/test_authz.py::TestAuthorization::test_cross_user")
        == "tests/test_authz.py::TestAuthorization::test_cross_user"
    )


def test_command_rejects_disabled_profile_and_missing_selector() -> None:
    policy = validate_policy_text(valid_policy_text())
    with pytest.raises(PolicyValidationError, match="not enabled"):
        command_for(policy, "pytest_full")
    with pytest.raises(PolicyValidationError, match="requires a selector"):
        command_for(policy, "pytest_targeted")


@pytest.mark.parametrize(
    "invalid_text",
    [
        "x" * (256 * 1024 + 1),
        "version: 1\x00",
        "\ud800",
    ],
)
def test_input_size_nul_and_invalid_unicode_are_rejected(invalid_text: str) -> None:
    with pytest.raises(PolicyValidationError):
        validate_policy_text(invalid_text)


def test_non_text_input_is_rejected() -> None:
    with pytest.raises(PolicyValidationError, match="must be text"):
        validate_policy_text(None)  # type: ignore[arg-type]


def test_non_string_keys_and_wrong_field_shapes_are_rejected() -> None:
    with pytest.raises(PolicyValidationError, match="string keys"):
        validate_policy_text("1: foo")
    with pytest.raises(PolicyValidationError, match="trusted_workflows must be a list"):
        validate_policy_text(EXAMPLE.replace("trusted_workflows:\n  - .github/workflows/ci.yml", "trusted_workflows: nope"))


def test_duplicate_obligation_id_is_rejected() -> None:
    second = EXAMPLE[EXAMPLE.index("  - id: OBL-AUTH-01"):]
    duplicated = EXAMPLE + "\n" + second
    with pytest.raises(PolicyValidationError, match="Duplicate obligation id"):
        validate_policy_text(duplicated)


def test_invalid_selector_is_rejected_inside_policy() -> None:
    text = EXAMPLE.replace(
        "tests/test_authz.py::test_cross_user_access_returns_403",
        "tests/test_authz.py::test_case[untrusted]",
    )
    with pytest.raises(PolicyValidationError, match="simple Python identifiers"):
        validate_policy_text(text)


def test_policy_sensitive_paths_and_workflow_entries_require_unique_safe_paths() -> None:
    with pytest.raises(PolicyValidationError, match="must not contain duplicates"):
        validate_policy_text(EXAMPLE.replace(
            "trusted_workflows:\n  - .github/workflows/ci.yml",
            "trusted_workflows:\n  - .github/workflows/ci.yml\n  - .github/workflows/ci.yml",
        ))
    with pytest.raises(PolicyValidationError, match="safe repository-relative path"):
        validate_policy_text(EXAMPLE.replace("  - package.json", "  - ../package.json"))
