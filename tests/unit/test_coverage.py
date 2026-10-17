"""Adversarial tests for per-test coverage manifests and JUnit reconciliation."""

from __future__ import annotations

import json

import pytest

from verification_core.coverage import (
    CoverageManifestError,
    parse_coverage_manifest,
    reconcile_test_coverage,
)
from verification_core.domain.enums import EvidenceSufficiency, ExecutionOutcome
from verification_core.evidence import parse_junit

SHA = "a" * 40
NODE = "tests.test_auth::test_cross_user_access"
XML = (
    '<testsuite tests="1"><testcase classname="tests.test_auth" '
    'name="test_cross_user_access" /></testsuite>'
)


def manifest_text(
    *,
    outcome: str = "passed",
    lines: dict[str, list[int]] | None = None,
    branches: dict[str, list[str]] | None = None,
    assertion: bool = True,
    node_id: str = NODE,
    head_sha: str = SHA,
) -> str:
    return json.dumps(
        {
            "version": 1,
            "head_sha": head_sha,
            "tests": [
                {
                    "node_id": node_id,
                    "outcome": outcome,
                    "lines": lines if lines is not None else {"src/auth.py": [10, 11]},
                    "branches": (
                        branches if branches is not None else {"src/auth.py": ["10:0", "10:1"]}
                    ),
                    "behavioral_assertion_verified": assertion,
                }
            ],
        }
    )


def test_parse_manifest_normalizes_and_sorts_coverage() -> None:
    manifest = parse_coverage_manifest(
        manifest_text(
            lines={"z.py": [3, 1], "a.py": [9]},
            branches={"z.py": ["3:0"], "a.py": ["9:1"]},
        )
    )
    case = manifest.case_for(NODE)
    assert manifest.head_sha == SHA
    assert case is not None
    assert case.lines_for("z.py") == frozenset({1, 3})
    assert case.branches_for("a.py") == frozenset({"9:1"})
    assert case.behavioral_assertion_verified is True


@pytest.mark.parametrize(
    "payload",
    [
        "",
        "not json",
        "[]",
        '{"version":1,"version":1}',
        '{"version":1,"head_sha":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","tests":[NaN]}',
        '{"version":1,"head_sha":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","tests":[]}',
    ],
)
def test_invalid_manifest_json_and_shape_fail_closed(payload: str) -> None:
    with pytest.raises(CoverageManifestError):
        parse_coverage_manifest(payload)


def test_manifest_rejects_version_sha_and_unknown_keys() -> None:
    with pytest.raises(CoverageManifestError, match="version"):
        parse_coverage_manifest(manifest_text().replace('"version": 1', '"version": true'))
    with pytest.raises(CoverageManifestError, match="head_sha"):
        parse_coverage_manifest(manifest_text(head_sha="BAD"))
    with pytest.raises(CoverageManifestError, match="unknown key"):
        parse_coverage_manifest(manifest_text().replace('"version": 1', '"version": 1, "extra": 2'))


def test_manifest_rejects_types_empty_input_nul_and_oversize() -> None:
    for value in (None, 7):
        with pytest.raises(CoverageManifestError, match="text or bytes"):
            parse_coverage_manifest(value)  # type: ignore[arg-type]
    with pytest.raises(CoverageManifestError, match="NUL"):
        parse_coverage_manifest(b"{}\x00")
    with pytest.raises(CoverageManifestError, match="exceeds"):
        parse_coverage_manifest(b" " * (5 * 1024 * 1024 + 1))
    with pytest.raises(CoverageManifestError, match="UTF-8"):
        parse_coverage_manifest("\ud800")


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"node_id": ""}, "node_id"),
        ({"outcome": "unknown"}, "outcome"),
        ({"assertion": "yes"}, "must be a boolean"),
        ({"lines": []}, "keyed by file path"),
        ({"lines": {"../secret.py": [1]}}, "safe repository-relative path"),
        ({"lines": {"src/a.py": [0]}}, "positive integers"),
        ({"lines": {"src/a.py": [True]}}, "positive integers"),
        ({"lines": {"src/a.py": [1, 1]}}, "duplicate locations"),
        ({"branches": {"src/a.py": ["bad"]}}, "branch IDs"),
        ({"branches": {"src/a.py": ["10:0", "10:0"]}}, "duplicate locations"),
    ],
)
def test_manifest_rejects_invalid_case_data(change: dict[str, object], message: str) -> None:
    values: dict[str, object] = {
        "outcome": "passed",
        "lines": {"src/auth.py": [10, 11]},
        "branches": {"src/auth.py": ["10:0", "10:1"]},
        "assertion": True,
        "node_id": NODE,
        "head_sha": SHA,
    }
    values.update(change)
    with pytest.raises(CoverageManifestError, match=message):
        parse_coverage_manifest(manifest_text(**values))  # type: ignore[arg-type]


def test_manifest_rejects_duplicate_test_nodes() -> None:
    payload = json.loads(manifest_text())
    payload["tests"].append(payload["tests"][0])
    with pytest.raises(CoverageManifestError, match="Duplicate test node ID"):
        parse_coverage_manifest(json.dumps(payload))


def test_reconciliation_requires_exact_commit_and_matching_test_nodes() -> None:
    report = parse_junit(XML)
    manifest = parse_coverage_manifest(manifest_text())
    with pytest.raises(CoverageManifestError, match="does not match expected commit"):
        reconcile_test_coverage(
            junit_report=report,
            manifest=manifest,
            expected_head_sha="b" * 40,
            node_id=NODE,
            target_lines={"src/auth.py": {10, 11}},
            target_branches={"src/auth.py": {"10:0", "10:1"}},
        )
    with pytest.raises(CoverageManifestError, match="no exact test node"):
        reconcile_test_coverage(
            junit_report=report,
            manifest=manifest,
            expected_head_sha=SHA,
            node_id="missing::test",
            target_lines={"src/auth.py": {10}},
            target_branches={},
        )
    with pytest.raises(CoverageManifestError, match="expected_head_sha"):
        reconcile_test_coverage(
            junit_report=report,
            manifest=manifest,
            expected_head_sha="BAD",
            node_id=NODE,
            target_lines={"src/auth.py": {10}},
            target_branches={},
        )


def test_reconciliation_marks_sufficient_only_when_target_lines_and_branches_hit() -> None:
    result = reconcile_test_coverage(
        junit_report=parse_junit(XML),
        manifest=parse_coverage_manifest(manifest_text()),
        expected_head_sha=SHA,
        node_id=NODE,
        target_lines={"src/auth.py": {10, 11}},
        target_branches={"src/auth.py": {"10:0", "10:1"}},
    )
    assert result.outcome is ExecutionOutcome.PASSED
    assert result.target_lines_exercised is True
    assert result.target_branches_exercised is True
    assert result.sufficiency is EvidenceSufficiency.SUFFICIENT


def test_reconciliation_detects_line_miss_branch_miss_and_weak_assertions() -> None:
    report = parse_junit(XML)
    lines_missed = reconcile_test_coverage(
        junit_report=report,
        manifest=parse_coverage_manifest(manifest_text(lines={"src/auth.py": [10]})),
        expected_head_sha=SHA,
        node_id=NODE,
        target_lines={"src/auth.py": {10, 11}},
        target_branches={"src/auth.py": {"10:0", "10:1"}},
    )
    assert lines_missed.sufficiency is EvidenceSufficiency.COVERAGE_MISS

    branches_missed = reconcile_test_coverage(
        junit_report=report,
        manifest=parse_coverage_manifest(manifest_text(branches={"src/auth.py": ["10:0"]})),
        expected_head_sha=SHA,
        node_id=NODE,
        target_lines={"src/auth.py": {10}},
        target_branches={"src/auth.py": {"10:0", "10:1"}},
    )
    assert branches_missed.sufficiency is EvidenceSufficiency.COVERAGE_MISS

    weak = reconcile_test_coverage(
        junit_report=report,
        manifest=parse_coverage_manifest(manifest_text(assertion=False)),
        expected_head_sha=SHA,
        node_id=NODE,
        target_lines={"src/auth.py": {10, 11}},
        target_branches={"src/auth.py": {"10:0", "10:1"}},
    )
    assert weak.sufficiency is EvidenceSufficiency.WEAK_EVIDENCE


def test_reconciliation_detects_outcome_mismatch_and_missing_coverage_case() -> None:
    report = parse_junit(XML)
    mismatch = reconcile_test_coverage(
        junit_report=report,
        manifest=parse_coverage_manifest(manifest_text(outcome="failed")),
        expected_head_sha=SHA,
        node_id=NODE,
        target_lines={"src/auth.py": {10}},
        target_branches={},
    )
    assert mismatch.sufficiency is EvidenceSufficiency.CONTRADICTORY
    with pytest.raises(CoverageManifestError, match="Coverage manifest has no exact test node"):
        reconcile_test_coverage(
            junit_report=report,
            manifest=parse_coverage_manifest(manifest_text(node_id="different::test")),
            expected_head_sha=SHA,
            node_id=NODE,
            target_lines={"src/auth.py": {10}},
            target_branches={},
        )



def test_manifest_rejects_missing_keys_and_invalid_path_variants() -> None:
    missing = {"version": 1, "head_sha": SHA}
    with pytest.raises(CoverageManifestError, match="missing key"):
        parse_coverage_manifest(json.dumps(missing))

    for unsafe_path in ("/absolute.py", "src\\\\auth.py", "-option.py", "module:stream.py", "x" * 301):
        with pytest.raises(CoverageManifestError, match="safe repository-relative path|path string"):
            parse_coverage_manifest(manifest_text(lines={unsafe_path: [1]}))


def test_manifest_rejects_non_list_locations_and_too_many_files() -> None:
    with pytest.raises(CoverageManifestError, match="must be a list"):
        parse_coverage_manifest(manifest_text(lines={"src/auth.py": "10"}))

    many_files = {f"src/module_{index}.py": [1] for index in range(1001)}
    with pytest.raises(CoverageManifestError, match="exceeds 1000 file paths"):
        parse_coverage_manifest(manifest_text(lines=many_files))


def test_manifest_rejects_location_count_limits() -> None:
    many_lines = list(range(1, 100_002))
    with pytest.raises(CoverageManifestError, match="exceeds 100000 locations"):
        parse_coverage_manifest(manifest_text(lines={"src/auth.py": many_lines}))

    lines = list(range(1, 60_001))
    branches = [f"{index}:0" for index in range(1, 40_002)]
    with pytest.raises(CoverageManifestError, match="exceeds 100000 locations"):
        parse_coverage_manifest(
            manifest_text(lines={"src/auth.py": lines}, branches={"src/auth.py": branches})
        )


def test_manifest_rejects_too_many_tests_and_bad_test_object_keys() -> None:
    oversized = json.dumps({"version": 1, "head_sha": SHA, "tests": [None] * 50_001})
    with pytest.raises(CoverageManifestError, match="exceeds 50000"):
        parse_coverage_manifest(oversized)

    payload = json.loads(manifest_text())
    del payload["tests"][0]["branches"]
    with pytest.raises(CoverageManifestError, match="missing key"):
        parse_coverage_manifest(json.dumps(payload))

    payload = json.loads(manifest_text())
    payload["tests"][0]["extra"] = "untrusted"
    with pytest.raises(CoverageManifestError, match="unknown key"):
        parse_coverage_manifest(json.dumps(payload))


def test_reconciliation_rejects_invalid_targets_and_unpassed_outcome() -> None:
    report = parse_junit(XML)
    manifest = parse_coverage_manifest(manifest_text())
    common = {
        "junit_report": report,
        "manifest": manifest,
        "expected_head_sha": SHA,
        "node_id": NODE,
        "target_branches": {},
    }
    with pytest.raises(CoverageManifestError, match="safe repository-relative path"):
        reconcile_test_coverage(
            **common, target_lines={"../secret.py": {10}}  # type: ignore[arg-type]
        )
    with pytest.raises(CoverageManifestError, match="positive integers"):
        reconcile_test_coverage(
            **common, target_lines={"src/auth.py": {0}}  # type: ignore[arg-type]
        )
    with pytest.raises(CoverageManifestError, match="branch IDs"):
        reconcile_test_coverage(
            **common, target_lines={"src/auth.py": {10}},
            target_branches={"src/auth.py": {"bad"}},  # type: ignore[typeddict-item]
        )

    failed_xml = (
        '<testsuite tests="1" failures="1"><testcase classname="tests.test_auth" '
        'name="test_cross_user_access"><failure>denied</failure></testcase></testsuite>'
    )
    failed = reconcile_test_coverage(
        junit_report=parse_junit(failed_xml),
        manifest=parse_coverage_manifest(manifest_text(outcome="failed")),
        expected_head_sha=SHA,
        node_id=NODE,
        target_lines={"src/auth.py": {10, 11}},
        target_branches={"src/auth.py": {"10:0", "10:1"}},
    )
    assert failed.sufficiency is EvidenceSufficiency.UNVERIFIED
