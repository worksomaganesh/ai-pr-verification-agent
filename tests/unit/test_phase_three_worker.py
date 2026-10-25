"""Regression tests for Phase III trust-boundary helpers."""

from __future__ import annotations

import pytest

from verification_core.phase_three import (
    EvidenceIngestionServiceError,
    selector_to_junit_node_id,
)
from verification_core.phase_three_worker import _workflow_path


@pytest.mark.parametrize(
    ("selector", "expected"),
    [
        (
            "tests/unit/test_auth.py::test_denies_access",
            "tests.unit.test_auth::test_denies_access",
        ),
        (
            "tests/unit/test_auth.py::TestAuth::test_denies_access",
            "tests.unit.test_auth::TestAuth::test_denies_access",
        ),
        (
            "tests/unit/test_auth.py::test_user[role::admin]",
            "tests.unit.test_auth::test_user[role::admin]",
        ),
        ("test_auth.py::test_denies_access", "test_auth.py::test_denies_access"),
    ],
)
def test_selector_to_junit_node_id(selector: str, expected: str) -> None:
    assert selector_to_junit_node_id(selector) == expected


@pytest.mark.parametrize("selector", ["", "x" * 10_001])
def test_selector_to_junit_node_id_rejects_invalid_input(selector: str) -> None:
    with pytest.raises(EvidenceIngestionServiceError):
        selector_to_junit_node_id(selector)


@pytest.mark.parametrize(
    ("workflow_path", "expected"),
    [
        (".github/workflows/ci.yml@refs/heads/main", ".github/workflows/ci.yml"),
        (".github/workflows/ci.yml", ".github/workflows/ci.yml"),
        ("ci.yml", None),
        (".github/workflows/../evil.yml", None),
        ("", None),
        (None, None),
    ],
)
def test_workflow_path_is_normalized_and_confined(
    workflow_path: object, expected: str | None
) -> None:
    assert _workflow_path(workflow_path) == expected
