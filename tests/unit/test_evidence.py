"""Adversarial tests for JUnit parsing and evidence sufficiency."""

from __future__ import annotations

import pytest

from verification_core.domain.enums import EvidenceSufficiency, ExecutionOutcome
from verification_core.evidence import EvidenceParseError, assess_evidence_sufficiency, parse_junit

VALID = (
    '<testsuite tests="3" failures="1" errors="0" skipped="1">\n'
    '<testcase classname="tests.test_auth" name="test_good" time="0.1" />\n'
    '<testcase classname="tests.test_auth" name="test_bad" time="0.2">'
    '<failure message="token=ghp_abcdefghijklmnopqrstuvwxyz0123456789">failed</failure>'
    "</testcase>\n"
    '<testcase classname="tests.test_auth" name="test_skip">'
    '<skipped message="not ready" /></testcase>\n'
    "</testsuite>"
)
