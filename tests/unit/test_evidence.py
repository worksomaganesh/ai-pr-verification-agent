"""Adversarial tests for JUnit parsing and evidence sufficiency."""

from __future__ import annotations

import pytest

from verification_core.domain.enums import EvidenceSufficiency, ExecutionOutcome
from verification_core.evidence import EvidenceParseError, assess_evidence_sufficiency, parse_junit

VALID = """<testsuite tests="3" failures="1" errors="0" skipped="1">
<testcase classname="tests.test_auth" name="test_good" time="0.1" />
<testcase classname="tests.test_auth" name="test_bad" time="0.2"><failure message="token=ghp_abcdefghijklmnopqrstuvwxyz0123456789">failed</failure></testcase>
<testcase classname="tests.test_auth" name="test_skip"><skipped message="not ready" /></testcase>
</testsuite>"""


def test_parse_junit_counts_and_scrubs_secrets() -> None:
    report = parse_junit(VALID)
    assert (report.total_tests, report.passed, report.failed, report.errors, report.skipped) == (3, 1, 1, 0, 1)
    assert report.cases[0].outcome is ExecutionOutcome.PASSED
    assert report.cases[1].outcome is ExecutionOutcome.FAILED
    assert "[REDACTED]" in (report.cases[1].detail or "")
    assert "ghp_abcdefghijklmnopqrstuvwxyz" not in (report.cases[1].detail or "")


def test_testsuites_root_is_supported() -> None:
    report = parse_junit('<testsuites tests="1"><testsuite><testcase name="ok"/></testsuite></testsuites>')
    assert report.total_tests == report.passed == 1


@pytest.mark.parametrize("payload", [
    "", "not xml", "<testsuite><testcase name='x'></testsuite>",
    "<root><testcase name='x'/></root>", "<testsuite />",
    '<!DOCTYPE foo [<!ENTITY x "expansion">]><testsuite tests="1"><testcase name="&x;"/></testsuite>',
    '<testsuite tests="-1"><testcase name="x"/></testsuite>',
    '<testsuite tests="2"><testcase name="x"/></testsuite>',
    '<testsuite tests="1" failures="1"><testcase name="x"/></testsuite>',
    '<testsuite tests="1" errors="1"><testcase name="x"/></testsuite>',
    '<testsuite tests="1" skipped="1"><testcase name="x"/></testsuite>',
    '<testsuite><testcase /></testsuite>',
    '<testsuite><testcase name="x" time="nan"/></testsuite>',
    '<testsuite><testcase name="x" time="-1"/></testsuite>',
    '<testsuite><testcase name="x"><failure/><error/></testcase></testsuite>',
    '<testsuite><testcase name="x" time="nope"/></testsuite>',
    '<testsuite><testcase name="x"><failure/><skipped/></testcase></testsuite>',
])
def test_invalid_or_inconsistent_junit_fails_closed(payload: str) -> None:
    with pytest.raises(EvidenceParseError):
        parse_junit(payload)


def test_junit_rejects_types_empty_nul_and_oversize() -> None:
    for value in (None, 4):
        with pytest.raises(EvidenceParseError, match="text or bytes"):
            parse_junit(value)  # type: ignore[arg-type]
    with pytest.raises(EvidenceParseError, match="empty"):
        parse_junit(b"")
    with pytest.raises(EvidenceParseError, match="NUL"):
        parse_junit(b"<testsuite>\x00</testsuite>")
    with pytest.raises(EvidenceParseError, match="exceeds"):
        parse_junit(b" " * (5 * 1024 * 1024 + 1))


def test_junit_rejects_invalid_unicode_and_overlong_fields() -> None:
    with pytest.raises(EvidenceParseError, match="UTF-8"):
        parse_junit("\ud800")
    with pytest.raises(EvidenceParseError, match="name exceeds"):
        parse_junit(f'<testsuite><testcase name="{"x" * 2001}"/></testsuite>')


@pytest.mark.parametrize("payload", [
    '<testsuite tests="one"><testcase name="x"/></testsuite>',
    '<testsuite tests="1" failures="one"><testcase name="x"/></testsuite>',
])
def test_junit_rejects_non_integer_counts(payload: str) -> None:
    with pytest.raises(EvidenceParseError, match="integer"):
        parse_junit(payload)


def test_junit_rejects_over_case_limit() -> None:
    cases = "".join('<testcase name="x"/>' for _ in range(50_001))
    with pytest.raises(EvidenceParseError, match="exceeds 50000"):
        parse_junit(f"<testsuite>{cases}</testsuite>")


@pytest.mark.parametrize(("kwargs", "expected"), [
    ({"total_tests": 0}, EvidenceSufficiency.MALFORMED),
    ({"total_tests": -1}, EvidenceSufficiency.MALFORMED),
    ({"total_tests": 1, "report_well_formed": False}, EvidenceSufficiency.MALFORMED),
    ({"total_tests": 1, "outcomes_consistent": False}, EvidenceSufficiency.CONTRADICTORY),
    ({"total_tests": 1, "target_lines_exercised": False}, EvidenceSufficiency.COVERAGE_MISS),
    ({"total_tests": 1, "target_branches_exercised": False}, EvidenceSufficiency.COVERAGE_MISS),
    ({"total_tests": 1, "behavioral_assertion_verified": False}, EvidenceSufficiency.WEAK_EVIDENCE),
    ({"total_tests": 1}, EvidenceSufficiency.SUFFICIENT),
])
def test_sufficiency_negative_filters(kwargs: dict[str, object], expected: EvidenceSufficiency) -> None:
    values: dict[str, object] = {
        "total_tests": 1, "target_lines_exercised": True, "target_branches_exercised": True,
        "behavioral_assertion_verified": True, "report_well_formed": True, "outcomes_consistent": True,
    }
    values.update(kwargs)
    assert assess_evidence_sufficiency(**values) is expected  # type: ignore[arg-type]
