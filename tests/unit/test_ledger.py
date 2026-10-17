"""Deterministic ledger rendering and governance-separation tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from verification_core.domain.enums import ObligationSource, ObligationStatus, Severity
from verification_core.domain.models import HumanApprovalRecord, VerificationObligation
from verification_core.evidence import parse_junit
from verification_core.ledger import render_evidence_ledger

REPORT = parse_junit(
    '<testsuite tests="1"><testcase classname="tests.test_safe" name="test_safe"/></testsuite>'
)
STAMP = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)
SHA = "2" * 40


def obligation(
    obligation_id: str, status: ObligationStatus = ObligationStatus.PROPOSED
) -> VerificationObligation:
    values: dict[str, object] = {
        "obligation_id": obligation_id,
        "category": "authorization",
        "description": "A safe claim",
        "severity": Severity.CRITICAL,
        "source": ObligationSource.DETERMINISTIC_POLICY,
        "affected_files": ("src/auth.py",),
        "status": status,
    }
    if status is ObligationStatus.APPROVED_BY_HUMAN:
        values["human_approval"] = HumanApprovalRecord(
            reviewer_login="maintainer",
            review_id=7,
            approved_head_sha=SHA,
            rationale="Reviewed risk and accepted residual risk",
            approved_at=STAMP,
        )
    return VerificationObligation(**values)  # type: ignore[arg-type]


def render(items: tuple[VerificationObligation, ...]) -> str:
    return render_evidence_ledger(
        repository="example/service",
        head_sha=SHA,
        workflow_run_id=123,
        generated_at=STAMP,
        report=REPORT,
        obligations=items,
        conclusion="action_required",
    )


def test_ledger_is_deterministic_and_sorts_obligations() -> None:
    left = render((obligation("OBL-Z"), obligation("OBL-A")))
    assert left == render((obligation("OBL-A"), obligation("OBL-Z")))
    assert left.index("OBL-A") < left.index("OBL-Z")
    assert "| 1 | 1 | 0 | 0 | 0 |" in left


def test_ledger_scrubs_secrets_and_escapes_markdown_cells() -> None:
    item = VerificationObligation(
        obligation_id="OBL-SECRET",
        category="auth",
        description="safe",
        severity=Severity.CRITICAL,
        source=ObligationSource.DETERMINISTIC_POLICY,
        affected_files=("src/auth.py",),
        status_reason="api_key=supersecretvalue | leaked",
    )
    result = render((item,))
    assert "supersecretvalue" not in result
    assert "[REDACTED]" in result
    assert "\\|" in result


def test_ledger_distinguishes_human_approval_from_machine_pass() -> None:
    result = render((obligation("OBL-HUMAN", ObligationStatus.APPROVED_BY_HUMAN),))
    assert "Human approval (not machine verification)" in result
    assert "Machine-verified evidence" not in result


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"repository": ""}, "repository"),
        ({"head_sha": "BAD"}, "head_sha"),
        ({"workflow_run_id": 0}, "workflow_run_id"),
        ({"generated_at": datetime(2026, 1, 1)}, "timezone-aware"),
    ],
)
def test_ledger_rejects_invalid_metadata(overrides: dict[str, object], message: str) -> None:
    values: dict[str, object] = {
        "repository": "example/service",
        "head_sha": SHA,
        "workflow_run_id": 1,
        "generated_at": STAMP,
        "report": REPORT,
        "obligations": (),
        "conclusion": "success",
    }
    values.update(overrides)
    with pytest.raises(ValueError, match=message):
        render_evidence_ledger(**values)  # type: ignore[arg-type]
