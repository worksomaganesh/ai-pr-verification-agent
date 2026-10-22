"""Tests for the trusted per-test coverage-manifest exporter."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import cast

import pytest
from coverage import Coverage, CoverageData

from verification_core.manifest_export import (
    ManifestExportError,
    _junit_node_id,
    build_coverage_manifest,
)

HEAD = "a" * 40


def _prepare_run(tmp_path: Path) -> tuple[Path, Path]:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    source = tests_dir / "test_sample.py"
    source.write_text(
        "def choose(flag):\n    if flag:\n        return 'yes'\n    return 'no'\n",
        encoding="utf-8",
    )
    junit = tmp_path / "junit.xml"
    junit.write_text(
        '<testsuite tests="2">'
        '<testcase classname="tests.test_sample" name="test_choose[true]"/>'
        '<testcase classname="tests.test_sample" name="test_choose[false]"/>'
        "</testsuite>",
        encoding="utf-8",
    )
    spec = importlib.util.spec_from_file_location("test_sample", source)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    coverage_path = tmp_path / ".coverage"
    coverage = Coverage(data_file=str(coverage_path), branch=True, source=[str(tests_dir)])
    coverage.start()
    coverage.switch_context("tests/test_sample.py::test_choose[true]|run")
    module.choose(True)
    coverage.switch_context("tests/test_sample.py::test_choose[false]|run")
    module.choose(False)
    coverage.stop()
    coverage.save()
    return coverage_path, junit


def test_exporter_emits_exact_per_test_lines_and_stable_branch_ids(tmp_path: Path) -> None:
    coverage_path, junit = _prepare_run(tmp_path)
    document = build_coverage_manifest(
        coverage_data_path=coverage_path,
        junit_xml_path=junit,
        head_sha=HEAD,
        repository_root=tmp_path,
    )
    raw_cases = cast(list[dict[str, object]], document["tests"])
    cases = {str(item["node_id"]): item for item in raw_cases}
    true_case = cases["tests.test_sample::test_choose[true]"]
    false_case = cases["tests.test_sample::test_choose[false]"]
    assert true_case["outcome"] == "passed"
    assert false_case["outcome"] == "passed"
    assert true_case["behavioral_assertion_verified"] is False
    assert false_case["behavioral_assertion_verified"] is False
    true_lines = cast(dict[str, list[int]], true_case["lines"])["tests/test_sample.py"]
    false_lines = cast(dict[str, list[int]], false_case["lines"])["tests/test_sample.py"]
    assert 3 in true_lines
    assert 4 not in true_lines
    assert 4 in false_lines
    assert 3 not in false_lines
    true_branches = cast(dict[str, list[str]], true_case["branches"])["tests/test_sample.py"]
    false_branches = cast(dict[str, list[str]], false_case["branches"])["tests/test_sample.py"]
    assert true_branches
    assert false_branches
    assert true_branches != false_branches


def test_junit_node_id_preserves_scope_separator_inside_parameter_id(tmp_path: Path) -> None:
    assert (
        _junit_node_id(
            "tests/unit/test_policy.py::test_selector[tests/test_authz.txt::test_case]",
            tmp_path,
        )
        == "tests.unit.test_policy::test_selector[tests/test_authz.txt::test_case]"
    )


@pytest.mark.parametrize(
    "parameter_suffix",
    [
        "[unclosed",
        "[nested[brackets::and separators]]",
        "[closing]]",
    ],
    ids=("open-bracket-in-value", "nested-brackets-and-separator", "closing-bracket-in-value"),
)
def test_junit_node_id_treats_parameter_suffix_as_opaque(
    parameter_suffix: str, tmp_path: Path
) -> None:
    node_id = f"tests/unit/test_policy.py::test_selector{parameter_suffix}"
    assert _junit_node_id(node_id, tmp_path) == (
        f"tests.unit.test_policy::test_selector{parameter_suffix}"
    )


def test_exporter_rejects_invalid_sha_and_missing_junit_context_match(tmp_path: Path) -> None:
    coverage_path, junit = _prepare_run(tmp_path)
    with pytest.raises(ManifestExportError, match="40-character Git SHA"):
        build_coverage_manifest(
            coverage_data_path=coverage_path,
            junit_xml_path=junit,
            head_sha="BAD",
            repository_root=tmp_path,
        )

    junit.write_text(
        '<testsuite tests="1">'
        '<testcase classname="tests.test_sample" name="test_missing"/>'
        "</testsuite>",
        encoding="utf-8",
    )
    with pytest.raises(ManifestExportError, match="no matching JUnit testcase"):
        build_coverage_manifest(
            coverage_data_path=coverage_path,
            junit_xml_path=junit,
            head_sha=HEAD,
            repository_root=tmp_path,
        )


def test_exporter_rejects_missing_data_and_bad_junit_files(tmp_path: Path) -> None:
    coverage_path, junit = _prepare_run(tmp_path)
    with pytest.raises(ManifestExportError, match="JUnit report could not be read"):
        build_coverage_manifest(
            coverage_data_path=coverage_path,
            junit_xml_path=tmp_path / "missing.xml",
            head_sha=HEAD,
            repository_root=tmp_path,
        )
    with pytest.raises(ManifestExportError, match="no measured files"):
        build_coverage_manifest(
            coverage_data_path=tmp_path / ".no-data",
            junit_xml_path=junit,
            head_sha=HEAD,
            repository_root=tmp_path,
        )


def test_exporter_rejects_coverage_without_branch_data(tmp_path: Path) -> None:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    source = tests_dir / "plain.py"
    source.write_text("value = 1\n", encoding="utf-8")
    junit = tmp_path / "junit.xml"
    junit.write_text(
        '<testsuite tests="1"><testcase classname="tests.plain" name="test_plain"/></testsuite>',
        encoding="utf-8",
    )
    cov_path = tmp_path / ".coverage-no-branches"
    data = CoverageData(basename=str(cov_path))
    data.set_context("tests/plain.py::test_plain|run")
    data.add_lines({str(source): {1}})
    data.write()
    with pytest.raises(ManifestExportError, match="no branch arcs"):
        build_coverage_manifest(
            coverage_data_path=cov_path,
            junit_xml_path=junit,
            head_sha=HEAD,
            repository_root=tmp_path,
        )


def test_exporter_rejects_unsafe_context_path(tmp_path: Path) -> None:
    with pytest.raises(ManifestExportError, match="unsafe or non-Python test path"):
        _junit_node_id("tests/../escape.py::test_evil", tmp_path)
