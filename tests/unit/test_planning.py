"""Tests for bounded Phase II diff analysis and hybrid planning."""

from __future__ import annotations

from typing import Any

import pytest

from verification_core.domain import (
    AnalysisCompleteness,
    CommitIdentity,
    ObligationSource,
    ObligationStatus,
    Severity,
)
from verification_core.planning import (
    ChangedFileInput,
    DiffAnalysisError,
    DiffLimits,
    PlannerOutputError,
    TestInventoryItem as InventoryItem,
    analyze_changed_files,
    deterministic_obligations,
    plan_verification,
    validate_model_hypotheses,
)


BASE = "1" * 40
HEAD = "2" * 40
POLICY = "a" * 64


def commit() -> CommitIdentity:
    return CommitIdentity(
        repo_full_name="example/service",
        pr_number=7,
        base_sha=BASE,
        head_sha=HEAD,
        policy_sha256=POLICY,
    )


def file(
    path: str = "src/service.py",
    *,
    status: str = "modified",
    additions: int = 2,
    deletions: int = 1,
    patch: str | None = "@@ -10,2 +10,3 @@\n context\n+new_value = 1\n+return new_value\n old_value = 0",
    binary: bool = False,
) -> ChangedFileInput:
    return ChangedFileInput(
        filename=path,
        status=status,
        additions=additions,
        deletions=deletions,
        patch=patch,
        is_binary=binary,
    )


def inventory(*selectors: str) -> tuple[InventoryItem, ...]:
    return tuple(
        InventoryItem(selector=selector, path=selector.split("::", 1)[0])
        for selector in selectors
    )


class FakeModel:
    def __init__(self, payload: object = None, error: Exception | None = None) -> None:
        self.payload = payload
        self.error = error
        self.calls = 0

    def propose_hypotheses(self, context: Any) -> object:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.payload


def test_diff_analysis_parses_added_line_ranges_and_binds_commit() -> None:
    result = analyze_changed_files(commit=commit(), changed_files=[file()])
    assert result.commit == commit()
    assert result.completeness is AnalysisCompleteness.COMPLETE
    assert result.analyzed_file_count == 1
    assert result.files[0].changed_line_ranges == ((11, 12),)
    assert result.files[0].deeply_analyzed is True


def test_diff_analysis_sorts_paths_deterministically() -> None:
    result = analyze_changed_files(
        commit=commit(),
        changed_files=[
            file("src/z.py"),
            file(".github/workflows/ci.yml", additions=1, deletions=0,
                 patch="@@ -1 +1,2 @@\n+run: untrusted"),
            file("src/authz.py"),
        ],
    )
    assert [item.filename for item in result.files] == [
        ".github/workflows/ci.yml",
        "src/authz.py",
        "src/z.py",
    ]


@pytest.mark.parametrize(
    "path",
    ["../secret.py", "/etc/passwd", "src//thing.py", "src/./thing.py", "src\\thing.py",
     "-option.py", "C:/temp.py", "src/\x00evil.py"],
)
def test_diff_analysis_rejects_unsafe_paths(path: str) -> None:
    with pytest.raises(DiffAnalysisError):
        analyze_changed_files(commit=commit(), changed_files=[file(path)])


def test_duplicate_changed_paths_are_rejected() -> None:
    with pytest.raises(DiffAnalysisError, match="Duplicate"):
        analyze_changed_files(commit=commit(), changed_files=[file(), file()])


def test_invalid_status_and_counts_are_rejected() -> None:
    with pytest.raises(DiffAnalysisError, match="status"):
        file(status="unknown")
    with pytest.raises(DiffAnalysisError, match="additions"):
        ChangedFileInput(filename="src/a.py", status="modified", additions=-1, deletions=0, patch="")


def test_input_file_limit_is_a_hard_error() -> None:
    limits = DiffLimits(max_input_files=2, max_files=2, max_changed_lines_per_file=10,
                        max_patch_chars_per_file=100, max_total_patch_chars=100)
    with pytest.raises(DiffAnalysisError, match="Input has"):
        analyze_changed_files(commit=commit(), changed_files=[file("a.py"), file("b.py"), file("c.py")],
                              limits=limits)


def test_file_count_limit_marks_analysis_truncated_and_prioritizes_harness() -> None:
    limits = DiffLimits(max_input_files=10, max_files=2, max_changed_lines_per_file=10,
                        max_patch_chars_per_file=100, max_total_patch_chars=100)
    result = analyze_changed_files(
        commit=commit(),
        changed_files=[file("docs/readme.md"), file("src/app.py"), file(".github/workflows/ci.yml")],
        limits=limits,
    )
    assert result.completeness is AnalysisCompleteness.TRUNCATED
    assert result.analyzed_paths == frozenset({".github/workflows/ci.yml", "src/app.py"})
    assert any("not deeply analyzed" in issue for issue in result.issues)


def test_missing_patch_marks_analysis_incomplete() -> None:
    result = analyze_changed_files(commit=commit(), changed_files=[file(patch=None)])
    assert result.completeness is AnalysisCompleteness.INCOMPLETE
    assert result.files[0].deeply_analyzed is False
    assert result.files[0].issue is not None


def test_changed_line_and_per_file_patch_limits_fail_closed() -> None:
    limits = DiffLimits(max_input_files=5, max_files=5, max_changed_lines_per_file=1,
                        max_patch_chars_per_file=100, max_total_patch_chars=100)
    result = analyze_changed_files(commit=commit(), changed_files=[file()], limits=limits)
    assert result.completeness is AnalysisCompleteness.TRUNCATED
    assert result.files[0].patch_excerpt is None

    limits2 = DiffLimits(max_input_files=5, max_files=5, max_changed_lines_per_file=10,
                         max_patch_chars_per_file=10, max_total_patch_chars=20)
    result2 = analyze_changed_files(commit=commit(), changed_files=[file()], limits=limits2)
    assert result2.completeness is AnalysisCompleteness.TRUNCATED


def test_unparseable_hunk_and_binary_file_are_explicit() -> None:
    malformed = file(patch="not a diff", additions=1, deletions=0)
    binary = file("assets/icon.bin", additions=0, deletions=0, patch=None, binary=True)
    result = analyze_changed_files(commit=commit(), changed_files=[malformed, binary])
    by_path = {item.filename: item for item in result.files}
    assert result.completeness is AnalysisCompleteness.INCOMPLETE
    assert by_path["src/service.py"].deeply_analyzed is False
    assert by_path["assets/icon.bin"].is_binary is True
    assert by_path["assets/icon.bin"].deeply_analyzed is True


def test_patch_context_scrubs_secrets_before_retaining_excerpt() -> None:
    patch = "@@ -1 +1,2 @@\n+api_key=ghp_" + "A" * 25 + "\n+safe = True"
    result = analyze_changed_files(
        commit=commit(),
        changed_files=[file(additions=2, deletions=0, patch=patch)],
    )
    excerpt = result.files[0].patch_excerpt
    assert excerpt is not None
    assert "ghp_" not in excerpt
    assert "[REDACTED]" in excerpt


def test_limits_validate_positive_and_consistent_values() -> None:
    with pytest.raises(ValueError):
        DiffLimits(max_input_files=0)
    with pytest.raises(ValueError, match="cannot exceed"):
        DiffLimits(max_input_files=2, max_files=3)
    with pytest.raises(ValueError, match="Per-file"):
        DiffLimits(max_patch_chars_per_file=200_000, max_total_patch_chars=100_000)


def test_harness_migration_auth_webhook_billing_and_dependency_rules() -> None:
    changed = [
        file(".verification-policy.yml", additions=1, deletions=0, patch="@@ -1 +1,2 @@\n+x: 1"),
        file("db/migrations/0042.sql", additions=1, deletions=0, patch="@@ -1 +1,2 @@\n+alter"),
        file("src/webhooks.py"),
        file("src/authz.py"),
        file("src/subscription_checkout.py"),
        file("uv.lock", additions=1, deletions=0, patch="@@ -1 +1,2 @@\n+package"),
        file("src/ordinary.py"),
    ]
    inv = inventory(
        "tests/test_webhooks.py::test_duplicate_event",
        "tests/test_authz.py::test_cross_user_access",
        "tests/test_subscription.py::test_checkout",
    )
    analysis = analyze_changed_files(commit=commit(), changed_files=changed)
    obligations = deterministic_obligations(analysis, test_inventory=inv)
    by_category = {item.category: item for item in obligations}
    assert by_category["governance_config_tamper"].severity is Severity.CRITICAL
    assert by_category["database_migration"].severity is Severity.CRITICAL
    assert by_category["webhook_idempotency"].severity is Severity.CRITICAL
    assert by_category["tenant_authorization"].severity is Severity.CRITICAL
    assert by_category["billing_regression"].severity is Severity.HIGH
    assert by_category["dependency_integrity"].severity is Severity.HIGH
    assert by_category["runtime_regression"].severity is Severity.MEDIUM
    assert all(item.status is ObligationStatus.PROPOSED for item in obligations)
    assert all(item.source is ObligationSource.DETERMINISTIC_POLICY for item in obligations)


def test_obligation_ids_are_stable_and_selector_requires_inventory_match() -> None:
    changed = [file("src/webhooks.py")]
    first = deterministic_obligations(analyze_changed_files(commit=commit(), changed_files=changed))
    second = deterministic_obligations(analyze_changed_files(commit=commit(), changed_files=changed))
    assert [item.obligation_id for item in first] == [item.obligation_id for item in second]
    assert first[0].candidate_test_id is None

    inv = inventory("tests/test_webhooks.py::test_duplicate_event")
    with_inventory = deterministic_obligations(
        analyze_changed_files(commit=commit(), changed_files=changed), test_inventory=inv
    )
    assert with_inventory[0].candidate_test_id == inv[0].selector


def test_test_inventory_rejects_mismatched_paths_and_duplicates() -> None:
    with pytest.raises(DiffAnalysisError, match="must equal"):
        InventoryItem(selector="tests/test_a.py::test_a", path="tests/test_b.py")
    duplicate = inventory("tests/test_a.py::test_a")
    with pytest.raises(DiffAnalysisError, match="duplicate"):
        deterministic_obligations(
            analyze_changed_files(commit=commit(), changed_files=[file()]),
            test_inventory=duplicate + duplicate,
        )


def test_model_hypotheses_must_reference_changed_paths_and_existing_selectors() -> None:
    analysis = analyze_changed_files(commit=commit(), changed_files=[file("src/authz.py")])
    inv = inventory("tests/test_authz.py::test_cross_user_access")
    valid = {
        "hypotheses": [{
            "category": "cross_tenant_boundary",
            "severity": "critical",
            "claim": "Cross-tenant access must be denied.",
            "affected_files": ["src/authz.py"],
            "candidate_test_selector": inv[0].selector,
        }]
    }
    parsed = validate_model_hypotheses(valid, analysis=analysis, test_inventory=inv)
    assert parsed[0].severity is Severity.CRITICAL

    invalid_path = {**valid, "hypotheses": [{**valid["hypotheses"][0], "affected_files": ["src/other.py"]}]}
    with pytest.raises(PlannerOutputError, match="outside"):
        validate_model_hypotheses(invalid_path, analysis=analysis, test_inventory=inv)

    invalid_selector = {**valid, "hypotheses": [{**valid["hypotheses"][0], "candidate_test_selector": "tests/test_other.py::test_x"}]}
    with pytest.raises(PlannerOutputError, match="inventory"):
        validate_model_hypotheses(invalid_selector, analysis=analysis, test_inventory=inv)


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {},
        {"hypotheses": "not-a-list"},
        {"hypotheses": [{"category": "x"}]},
        {"hypotheses": [{"category": "x", "severity": "critical", "claim": "x",
                         "affected_files": ["src/service.py"], "candidate_test_selector": None,
                         "status": "passed"}]},
        {"hypotheses": [{"category": "x", "severity": "critical", "claim": "x",
                         "affected_files": ["src/service.py", "src/service.py"],
                         "candidate_test_selector": None}]},
        {"hypotheses": [{"category": "x", "severity": "critical", "claim": "x",
                         "affected_files": [], "candidate_test_selector": None}]},
        {"hypotheses": [{"category": "x", "severity": "unknown", "claim": "x",
                         "affected_files": ["src/service.py"], "candidate_test_selector": None}]},
    ],
)
def test_model_schema_rejects_malformed_or_untrusted_payloads(payload: object) -> None:
    analysis = analyze_changed_files(commit=commit(), changed_files=[file()])
    with pytest.raises(PlannerOutputError):
        validate_model_hypotheses(payload, analysis=analysis, test_inventory=())


def test_model_hypothesis_count_is_bounded() -> None:
    analysis = analyze_changed_files(commit=commit(), changed_files=[file()])
    with pytest.raises(PlannerOutputError, match="more than"):
        validate_model_hypotheses(
            {"hypotheses": [{"category": "x", "severity": "low", "claim": "x",
                             "affected_files": ["src/service.py"], "candidate_test_selector": None}] * 2},
            analysis=analysis,
            test_inventory=(),
            max_hypotheses=1,
        )


def test_model_planner_augments_deterministic_rules_but_cannot_set_status() -> None:
    analysis = analyze_changed_files(commit=commit(), changed_files=[file("src/authz.py")])
    model = FakeModel({"hypotheses": [{
        "category": "cross_tenant_boundary",
        "severity": "critical",
        "claim": "Cross-tenant access must be denied.",
        "affected_files": ["src/authz.py"],
        "candidate_test_selector": None,
    }]})
    result = plan_verification(analysis, model=model)
    assert result.planner_mode == "hybrid"
    assert model.calls == 1
    assert {item.category for item in result.obligations} == {
        "tenant_authorization", "cross_tenant_boundary"
    }
    assert all(item.status is ObligationStatus.PROPOSED for item in result.obligations)
    assert all(item.source in {ObligationSource.DETERMINISTIC_POLICY, ObligationSource.LLM_HYPOTHESIS}
               for item in result.obligations)


def test_model_failure_falls_back_without_losing_deterministic_obligations() -> None:
    analysis = analyze_changed_files(commit=commit(), changed_files=[file("src/authz.py")])
    expected = deterministic_obligations(analysis)
    result = plan_verification(analysis, model=FakeModel(error=TimeoutError()))
    assert result.planner_mode == "deterministic_fallback"
    assert result.degradation_reason is not None
    assert result.obligations == expected
    assert result.analysis_completeness is analysis.completeness


def test_model_invalid_schema_falls_back_and_does_not_override_deterministic_result() -> None:
    analysis = analyze_changed_files(commit=commit(), changed_files=[file("src/authz.py")])
    expected = deterministic_obligations(analysis)
    result = plan_verification(analysis, model=FakeModel({"hypotheses": [{"status": "passed"}]}))
    assert result.planner_mode == "deterministic_fallback"
    assert result.obligations == expected


def test_model_duplicate_hypotheses_are_deduplicated() -> None:
    analysis = analyze_changed_files(commit=commit(), changed_files=[file("src/authz.py")])
    hypothesis = {
        "category": "cross_tenant_boundary",
        "severity": "critical",
        "claim": "Cross-tenant access must be denied.",
        "affected_files": ["src/authz.py"],
        "candidate_test_selector": None,
    }
    result = plan_verification(analysis, model=FakeModel({"hypotheses": [hypothesis, hypothesis]}))
    assert sum(item.category == "cross_tenant_boundary" for item in result.obligations) == 1


def test_incomplete_analysis_remains_incomplete_in_plan() -> None:
    analysis = analyze_changed_files(commit=commit(), changed_files=[file(patch=None)])
    result = plan_verification(analysis)
    assert result.analysis_completeness is AnalysisCompleteness.INCOMPLETE
    assert result.issues
