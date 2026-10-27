"""Regression tests for Phase III trust-boundary helpers and orchestration."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from types import SimpleNamespace
from typing import Any, cast

import pytest

from verification_core.domain.enums import (
    AnalysisCompleteness,
    ObligationSource,
    Severity,
)
from verification_core.domain.models import (
    CommitIdentity,
    ConclusionPolicyConfig,
    VerificationObligation,
)
from verification_core.phase_three import EvidenceIngestionServiceError, selector_to_junit_node_id
from verification_core.phase_three_worker import (
    PhaseThreeRunPending,
    _select_trusted_run,
    _target_lines_for_obligation,
    _trusted_assertion_bindings,
    _workflow_path,
    process_pull_request_evidence,
)
from verification_core.planning import AnalyzedFile, DiffAnalysis, PlanningResult
from verification_core.policy import ObligationRule, SeverityRule, VerificationPolicy

HEAD = "2" * 40
BASE = "1" * 40
POLICY_SHA = "a" * 64
REPO = "worksomaganesh/ai-pr-verification-agent"
SELECTOR = "tests/unit/test_phase_two.py::test_runtime"


def commit() -> CommitIdentity:
    return CommitIdentity(
        repo_full_name=REPO,
        pr_number=6,
        base_sha=BASE,
        head_sha=HEAD,
        policy_sha256=POLICY_SHA,
    )


def obligation() -> VerificationObligation:
    return VerificationObligation.propose(
        obligation_id="OBL-RUNTIME-01",
        category="runtime_regression",
        description="Runtime path must preserve safe verification behavior.",
        severity=Severity.MEDIUM,
        source=ObligationSource.DETERMINISTIC_POLICY,
        affected_files=("src/example.py",),
        candidate_test_id=SELECTOR,
    )


def analysis() -> DiffAnalysis:
    return DiffAnalysis(
        commit=commit(),
        files=(
            AnalyzedFile(
                filename="src/example.py",
                status="modified",
                additions=3,
                deletions=1,
                changed_line_ranges=((2, 4), (8, 8)),
                patch_excerpt=None,
                is_binary=False,
                harness_sensitive=False,
                deeply_analyzed=True,
            ),
        ),
        completeness=AnalysisCompleteness.COMPLETE,
        issues=(),
        input_file_count=1,
        analyzed_file_count=1,
        patch_chars_retained=0,
    )


def planning() -> PlanningResult:
    return PlanningResult(
        commit=commit(),
        analysis_completeness=AnalysisCompleteness.COMPLETE,
        obligations=(obligation(),),
        planner_mode="deterministic",
        degradation_reason=None,
        issues=(),
    )


def policy() -> VerificationPolicy:
    return VerificationPolicy(
        version=1,
        trusted_workflows=(".github/workflows/ci.yml",),
        runner_profiles=("pytest_targeted",),
        severity_rules=(
            SeverityRule(severity="critical", blocking=True, human_approval_allowed=True),
            SeverityRule(severity="high", blocking=True, human_approval_allowed=True),
            SeverityRule(severity="medium", blocking=False, human_approval_allowed=True),
            SeverityRule(severity="low", blocking=False, human_approval_allowed=True),
        ),
        harness_sensitive_paths=(".github/workflows/", "pyproject.toml"),
        obligations=(
            ObligationRule(
                obligation_id="OBL-RUNTIME-01",
                category="runtime_regression",
                severity="medium",
                claim="Runtime behavior remains safe.",
                runner_profile="pytest_targeted",
                selector=SELECTOR,
            ),
        ),
    )


def success_run() -> dict[str, object]:
    return {
        "id": 123,
        "event": "pull_request",
        "head_sha": HEAD,
        "path": ".github/workflows/ci.yml@refs/heads/main",
        "status": "completed",
        "conclusion": "success",
    }


def fake_actions(runs: Sequence[Mapping[str, object]]) -> object:
    return SimpleNamespace(list_pull_request_workflow_runs=lambda _repo, _sha: runs)


def fake_publication() -> object:
    return SimpleNamespace(ledger_persisted=True, check_run_id=567)


def test_selector_to_junit_node_id_normalizes_repo_relative_selector() -> None:
    assert selector_to_junit_node_id(SELECTOR) == "tests.unit.test_phase_two::test_runtime"


@pytest.mark.parametrize(
    "selector",
    ["", "x" * 10_001],
    ids=("empty-selector", "oversized-selector"),
)
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


def test_trusted_run_selection_requires_exact_head_event_and_workflow() -> None:
    eligible = success_run()
    assert (
        _select_trusted_run(
            runs=(eligible,), commit=commit(), trusted_paths=(".github/workflows/ci.yml",)
        )
        == eligible
    )
    assert (
        _select_trusted_run(
            runs=(eligible,), commit=commit(), trusted_paths=(".github/workflows/release.yml",)
        )
        is None
    )
    wrong_head = dict(eligible, head_sha="3" * 40)
    assert (
        _select_trusted_run(
            runs=(wrong_head,), commit=commit(), trusted_paths=(".github/workflows/ci.yml",)
        )
        is None
    )


def test_trusted_run_selection_fails_closed_on_ambiguity() -> None:
    with pytest.raises(EvidenceIngestionServiceError, match="More than one"):
        _select_trusted_run(
            runs=(success_run(), dict(success_run(), id=124)),
            commit=commit(),
            trusted_paths=(".github/workflows/ci.yml",),
        )


def test_target_lines_are_derived_only_from_analyzed_affected_files() -> None:
    assert _target_lines_for_obligation(obligation(), analysis()) == {
        "src/example.py": {2, 3, 4, 8}
    }


def test_trusted_assertion_binding_requires_policy_match_and_maps_junit_id() -> None:
    assert _trusted_assertion_bindings((obligation(),), policy()) == {
        "OBL-RUNTIME-01": "tests.unit.test_phase_two::test_runtime"
    }
    trusted = policy()
    wrong_rule = VerificationPolicy(
        version=trusted.version,
        trusted_workflows=trusted.trusted_workflows,
        runner_profiles=trusted.runner_profiles,
        severity_rules=trusted.severity_rules,
        harness_sensitive_paths=trusted.harness_sensitive_paths,
        obligations=(
            ObligationRule(
                obligation_id="OBL-RUNTIME-01",
                category="authorization",
                severity="medium",
                claim="Different claim.",
                runner_profile="pytest_targeted",
                selector=SELECTOR,
            ),
        ),
    )
    assert _trusted_assertion_bindings((obligation(),), wrong_rule) == {}


def test_worker_retries_when_no_exact_head_run_is_visible() -> None:
    with pytest.raises(PhaseThreeRunPending):
        process_pull_request_evidence(
            github=cast(Any, object()),
            actions=cast(Any, fake_actions(())),
            commit=commit(),
            planning=planning(),
            analysis=analysis(),
            policy=policy(),
            evidence_ledger=cast(Any, object()),
            policy_config=ConclusionPolicyConfig(),
            check_name="AI PR Verification",
        )


def test_worker_retries_when_trusted_run_is_in_progress() -> None:
    pending = dict(success_run(), status="in_progress", conclusion=None)
    with pytest.raises(PhaseThreeRunPending):
        process_pull_request_evidence(
            github=cast(Any, object()),
            actions=cast(Any, fake_actions((pending,))),
            commit=commit(),
            planning=planning(),
            analysis=analysis(),
            policy=policy(),
            evidence_ledger=cast(Any, object()),
            policy_config=ConclusionPolicyConfig(),
            check_name="AI PR Verification",
        )


def test_worker_publishes_inconclusive_for_failed_trusted_workflow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import verification_core.phase_three_worker as worker

    published: list[dict[str, Any]] = []

    def publish(**kwargs: Any) -> object:
        published.append(kwargs)
        return fake_publication()

    monkeypatch.setattr(worker, "publish_reconciled_verification", publish)
    result = process_pull_request_evidence(
        github=cast(Any, object()),
        actions=cast(Any, fake_actions((dict(success_run(), conclusion="failure"),))),
        commit=commit(),
        planning=planning(),
        analysis=analysis(),
        policy=policy(),
        evidence_ledger=cast(Any, object()),
        policy_config=ConclusionPolicyConfig(),
        check_name="AI PR Verification",
    )
    assert result.workflow_run_id == 123
    assert result.evidence_record_key is None
    assert "did not finish successfully" in result.summary
    assert len(published) == 1
    assert published[0]["analysis_completeness"] == AnalysisCompleteness.INCOMPLETE


def test_worker_reconciles_successful_authenticated_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import verification_core.phase_three_worker as worker

    ingestion_calls: list[dict[str, Any]] = []
    reconciliation_calls: list[dict[str, Any]] = []
    publication_calls: list[dict[str, Any]] = []

    def ingest(**kwargs: Any) -> object:
        ingestion_calls.append(kwargs)
        return SimpleNamespace(ledger_record_key="f" * 64, evidence=object())

    def reconcile(**kwargs: Any) -> VerificationObligation:
        reconciliation_calls.append(kwargs)
        return cast(VerificationObligation, kwargs["obligation"])

    def publish(**kwargs: Any) -> object:
        publication_calls.append(kwargs)
        return fake_publication()

    monkeypatch.setattr(worker, "ingest_pull_request_run", ingest)
    monkeypatch.setattr(worker, "reconcile_authenticated_obligation", reconcile)
    monkeypatch.setattr(worker, "publish_reconciled_verification", publish)

    result = process_pull_request_evidence(
        github=cast(Any, object()),
        actions=cast(Any, fake_actions((success_run(),))),
        commit=commit(),
        planning=planning(),
        analysis=analysis(),
        policy=policy(),
        evidence_ledger=cast(Any, object()),
        policy_config=ConclusionPolicyConfig(),
        check_name="AI PR Verification",
    )

    assert result.workflow_run_id == 123
    assert result.evidence_record_key == "f" * 64
    assert len(ingestion_calls) == 1
    assert ingestion_calls[0]["workflow_run_id"] == 123
    assert ingestion_calls[0]["changed_paths"] == ("src/example.py",)
    assert len(reconciliation_calls) == 1
    assert reconciliation_calls[0]["target_lines"] == {"src/example.py": {2, 3, 4, 8}}
    assert reconciliation_calls[0]["trusted_assertion_bindings"] == {
        "OBL-RUNTIME-01": "tests.unit.test_phase_two::test_runtime"
    }
    assert len(publication_calls) == 1
    assert result.publication.ledger_persisted is True
