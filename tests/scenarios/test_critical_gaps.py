"""Release-gate test for the critical-missing-evidence scenario."""

from verification_core.domain.enums import GitHubCheckConclusion
from verification_core.scenarios.critical_gaps import run_missing_critical_obligations_scenario


def test_140_unrelated_passes_cannot_mask_missing_critical_obligations() -> None:
    result = run_missing_critical_obligations_scenario()
    assert result.unrelated_passing_tests == 140
    assert result.missing_critical_obligations == ("OBL-AUTH-01", "OBL-WHK-01")
    assert result.conclusion is GitHubCheckConclusion.ACTION_REQUIRED
    assert "unverified" in result.summary_rationale.lower()
