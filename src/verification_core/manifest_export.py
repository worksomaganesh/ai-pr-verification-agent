"""Export per-test coverage and JUnit outcomes to a bounded Phase III manifest.

This utility reports measured execution only. It never claims a behavioral assertion was
independently verified; the verifier must bind assertion semantics separately from base policy.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path, PurePosixPath

from coverage import Coverage, CoverageData

from verification_core.coverage import parse_coverage_manifest
from verification_core.evidence import parse_junit

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class ManifestExportError(ValueError):
    """Raised when per-test coverage cannot be safely correlated to the JUnit inventory."""


def _split_pytest_node_id(pytest_node_id: str) -> list[str]:
    """Separate the source file and scopes without parsing opaque parameter-ID contents."""
    marker = pytest_node_id.find(".py::")
    if marker < 0:
        raise ManifestExportError("Coverage context contains an invalid pytest node ID.")
    source_path = pytest_node_id[: marker + 3]
    remaining = pytest_node_id[marker + 5 :]
    if not remaining:
        raise ManifestExportError("Coverage context contains an invalid pytest node ID.")

    # Parameter IDs may contain arbitrary brackets and '::'. Only separators before the first
    # parameter opener belong to class/function scopes; the suffix must remain opaque.
    parameter_start = remaining.find("[")
    if parameter_start < 0:
        scope_text = remaining
        parameter_suffix = ""
    else:
        scope_text = remaining[:parameter_start]
        parameter_suffix = remaining[parameter_start:]
    scopes = scope_text.split("::")
    if not scopes or any(not scope for scope in scopes):
        raise ManifestExportError("Coverage context contains an invalid pytest node ID.")
    scopes[-1] += parameter_suffix
    return [source_path, *scopes]


def _junit_node_id(pytest_node_id: str, root: Path) -> str:
    """Translate pytest's file::class::test ID into JUnit's classname::name ID."""
    parts = _split_pytest_node_id(pytest_node_id)
    if len(parts) < 2 or not parts[-1] or not parts[0]:
        raise ManifestExportError("Coverage context contains an invalid pytest node ID.")
    test_path = PurePosixPath(parts[0])
    if (
        test_path.is_absolute()
        or "\\" in parts[0]
        or any(part in {"", ".", ".."} for part in test_path.parts)
        or test_path.suffix != ".py"
    ):
        raise ManifestExportError("Coverage context contains an unsafe or non-Python test path.")
    resolved = (root / Path(*test_path.parts)).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ManifestExportError("Coverage context escapes the repository root.") from exc

    # The trusted workflow uses pytest's JUnit XML format, which preserves the repository-
    # relative path as a dotted classname (for example, tests.unit.test_auth).
    module_name = test_path.with_suffix("").as_posix().replace("/", ".")
    scopes = parts[1:-1]
    classname = module_name if not scopes else f"{module_name}.{'.'.join(scopes)}"
    return f"{classname}::{parts[-1]}"


def _repository_path(filename: str, root: Path) -> str | None:
    resolved = Path(filename).resolve()
    try:
        relative = resolved.relative_to(root)
    except ValueError:
        return None
    if relative.suffix != ".py":
        return None
    return relative.as_posix()


def _branch_indices(
    coverage: Coverage, filenames: tuple[str, ...], root: Path
) -> dict[str, dict[int, dict[int, int]]]:
    """Map each static branch arc to a stable index sorted by destination line.

    The ID format line:index is independent of which individual test hit the branch. The target
    location analyzer must use this same rule when it derives branch obligations.
    """
    output: dict[str, dict[int, dict[int, int]]] = {}
    for filename in filenames:
        analysis = coverage._analyze(filename)
        stats = analysis.branch_stats()
        executed = analysis.executed_branch_arcs()
        missing = analysis.missing_branch_arcs()
        per_line: dict[int, dict[int, int]] = {}
        for line, (total_exits, _taken_exits) in stats.items():
            if total_exits < 2:
                continue
            destinations = sorted(set(executed.get(line, ())) | set(missing.get(line, ())))
            if len(destinations) < 2:
                continue
            per_line[line] = {destination: index for index, destination in enumerate(destinations)}
        path = _repository_path(filename, root)
        if path is not None and per_line:
            output[path] = per_line
    return output


def build_coverage_manifest(
    *,
    coverage_data_path: Path,
    junit_xml_path: Path,
    head_sha: str,
    repository_root: Path | None = None,
) -> dict[str, object]:
    """Build a manifest only when run-phase coverage contexts exactly map to JUnit cases."""
    if not isinstance(head_sha, str) or not _SHA_RE.fullmatch(head_sha):
        raise ManifestExportError("head_sha must be a lowercase 40-character Git SHA.")
    root = (repository_root or Path.cwd()).resolve()
    try:
        junit_report = parse_junit(junit_xml_path.read_bytes())
    except OSError as exc:
        raise ManifestExportError("JUnit report could not be read.") from exc

    try:
        coverage = Coverage(data_file=str(coverage_data_path))
        coverage.load()
        data: CoverageData = coverage.get_data()
    except Exception as exc:
        raise ManifestExportError("Coverage data could not be loaded.") from exc
    if not data.measured_files():
        raise ManifestExportError("Coverage data contains no measured files.")
    if not data.has_arcs():
        raise ManifestExportError("Coverage data has no branch arcs; branch coverage is required.")

    files_by_name: dict[str, str] = {}
    for filename in sorted(data.measured_files()):
        relative = _repository_path(filename, root)
        if relative is not None:
            files_by_name[relative] = filename
    if not files_by_name:
        raise ManifestExportError(
            "Coverage data contains no measured Python files in the repository."
        )
    filenames = tuple(files_by_name.values())
    branches_by_file = _branch_indices(coverage, filenames, root)

    junit_by_node = {case.node_id: case for case in junit_report.cases}
    if len(junit_by_node) != len(junit_report.cases):
        raise ManifestExportError("JUnit report contains duplicate testcase node IDs.")

    run_context_by_junit_node: dict[str, str] = {}
    for raw_context in data.measured_contexts():
        if not raw_context:
            continue
        pytest_node_id, separator, phase = raw_context.rpartition("|")
        if not separator or phase != "run":
            continue
        junit_node_id = _junit_node_id(pytest_node_id, root)
        if junit_node_id not in junit_by_node:
            raise ManifestExportError(
                "A per-test coverage context has no matching JUnit testcase; "
                f"context node ID {pytest_node_id!r} mapped to {junit_node_id!r}; "
                "refusing partial evidence."
            )
        if junit_node_id in run_context_by_junit_node:
            raise ManifestExportError("JUnit testcase maps to multiple run-phase contexts.")
        run_context_by_junit_node[junit_node_id] = raw_context

    if not run_context_by_junit_node:
        raise ManifestExportError(
            "Coverage data contains no run-phase contexts matching the JUnit inventory."
        )

    output_cases: list[dict[str, object]] = []
    for case in junit_report.cases:
        # JUnit is the full test inventory. A test may execute no tracked production code;
        # preserve its outcome with empty measured coverage rather than fabricating evidence.
        run_context = run_context_by_junit_node.get(case.node_id)
        lines_by_path: dict[str, set[int]] = {}
        branches_by_path: dict[str, set[str]] = {}
        if run_context is not None:
            data.set_query_context(run_context)
            for path, filename in files_by_name.items():
                lines = data.lines(filename) or []
                if lines:
                    lines_by_path[path] = {line for line in lines if type(line) is int and line > 0}
                arcs = data.arcs(filename) or []
                file_branch_map = branches_by_file.get(path, {})
                executed_branches: set[str] = set()
                for source_line, destination_line in arcs:
                    destination_indices = file_branch_map.get(source_line)
                    if destination_indices is None:
                        continue
                    branch_index = destination_indices.get(destination_line)
                    if branch_index is not None:
                        executed_branches.add(f"{source_line}:{branch_index}")
                if executed_branches:
                    branches_by_path[path] = executed_branches

        output_cases.append(
            {
                "node_id": case.node_id,
                "outcome": case.outcome.value,
                "lines": {
                    path: sorted(lines) for path, lines in sorted(lines_by_path.items()) if lines
                },
                "branches": {
                    path: sorted(branches)
                    for path, branches in sorted(branches_by_path.items())
                    if branches
                },
                # Assertion sufficiency is never inferred from coverage or from this exporter.
                "behavioral_assertion_verified": False,
            }
        )

    document: dict[str, object] = {"version": 1, "head_sha": head_sha, "tests": output_cases}
    parse_coverage_manifest(json.dumps(document, sort_keys=True, separators=(",", ":")))
    return document


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coverage-data", type=Path, default=Path(".coverage"))
    parser.add_argument("--junit", type=Path, default=Path("junit.xml"))
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--output", type=Path, default=Path("coverage-manifest.json"))
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    try:
        document = build_coverage_manifest(
            coverage_data_path=args.coverage_data,
            junit_xml_path=args.junit,
            head_sha=args.head_sha,
            repository_root=args.repo_root,
        )
        args.output.write_text(
            json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
    except (ManifestExportError, OSError, ValueError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
