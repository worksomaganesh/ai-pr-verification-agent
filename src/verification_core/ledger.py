"""Stable Markdown evidence ledger rendering with secret scrubbing."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime

from verification_core.domain.models import VerificationObligation
from verification_core.evidence import JUnitReport
from verification_core.security import scrub_secrets


def _safe_cell(value: object) -> str:
    return (
        scrub_secrets(str(value)).replace("|", "\\|").replace("\r", " ").replace("\n", " ").strip()
    )


def render_evidence_ledger(
    *,
    repository: str,
    head_sha: str,
    workflow_run_id: int,
    generated_at: datetime,
    report: JUnitReport,
    obligations: Iterable[VerificationObligation],
    conclusion: str,
) -> str:
    """Render deterministic Markdown; callers provide a fixed timestamp for reproducibility."""
    if not repository.strip():
        raise ValueError("repository must not be empty")
    if len(head_sha) != 40 or any(char not in "0123456789abcdef" for char in head_sha):
        raise ValueError("head_sha must be a lowercase 40-character Git SHA")
    if workflow_run_id < 1:
        raise ValueError("workflow_run_id must be positive")
    if generated_at.tzinfo is None or generated_at.utcoffset() is None:
        raise ValueError("generated_at must be timezone-aware")

    items = sorted(obligations, key=lambda item: item.obligation_id)
    lines = [
        "# Verification Evidence Ledger",
        "",
        f"- Repository: {_safe_cell(repository)}",
        f"- Head SHA: `{head_sha}`",
        f"- Workflow run ID: {workflow_run_id}",
        f"- Generated at (UTC): {generated_at.astimezone(UTC).isoformat()}",
        f"- GitHub conclusion candidate: **{_safe_cell(conclusion)}**",
        "",
        "## Test report summary",
        "",
        "| Total | Passed | Failed | Errors | Skipped |",
        "| ---: | ---: | ---: | ---: | ---: |",
        f"| {report.total_tests} | {report.passed} | {report.failed} | "
        f"{report.errors} | {report.skipped} |",
        "",
        "## Individual test evidence",
        "",
        "| Test node | Outcome | Duration (s) | Detail |",
        "| --- | --- | ---: | --- |",
    ]
    for case in sorted(report.cases, key=lambda item: (item.node_id, item.outcome.value)):
        duration = "" if case.duration_seconds is None else f"{case.duration_seconds:.6f}"
        lines.append(
            f"| {_safe_cell(case.node_id)} | {_safe_cell(case.outcome.value)} | "
            f"{duration} | {_safe_cell(case.detail or '')} |"
        )
    lines.extend(
        [
            "",
            "## Verification obligations",
            "",
            "| Obligation | Severity | State | Evidence / governance |",
            "| --- | --- | --- | --- |",
        ]
    )
    for item in items:
        if item.status.value == "passed":
            governance = "Machine-verified evidence"
        elif item.status.value == "approved_by_human":
            governance = "Human approval (not machine verification)"
        elif item.status.value == "waived_by_policy":
            governance = "Policy waiver (not machine verification)"
        else:
            governance = item.status_reason or "No sufficient evidence recorded"
        lines.append(
            f"| {_safe_cell(item.obligation_id)} | {_safe_cell(item.severity.value)} | "
            f"{_safe_cell(item.status.value)} | {_safe_cell(governance)} |"
        )
    lines.extend(
        [
            "",
            "> A passing test suite is not proof that every obligation was exercised. "
            "Human approval and policy waivers are not machine-verified passes.",
            "",
        ]
    )
    return "\n".join(lines)
