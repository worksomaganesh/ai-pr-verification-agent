"""Secret-scrubbing regression tests."""

from __future__ import annotations

import pytest

from verification_core.security import scrub_secrets


@pytest.mark.parametrize("secret", [
    "ghp_abcdefghijklmnopqrstuvwxyz0123456789",
    "github_pat_abcdefghijklmnopqrstuvwxyz0123456789",
    "AKIA1234567890ABCDEF",
    "AIza1234567890abcdefghijklmnopqrstuvwxyz",
    "sk-abcdefghijklmnopqrstuvwxyz0123456789",
    "Bearer abcdefghijklmnopqrstuvwxyz123456",
    "api_key=supersecretvalue",
    "password: 'correcthorsebatterystaple'",
    "-----BEGIN PRIVATE KEY-----\nprivate-material\n-----END PRIVATE KEY-----",
])
def test_common_secret_formats_are_redacted(secret: str) -> None:
    result = scrub_secrets(secret)
    assert "[REDACTED]" in result
    assert secret not in result


def test_scrubbing_is_deterministic_and_preserves_safe_text() -> None:
    text = "ordinary failure in test_checkout"
    assert scrub_secrets(text) == text
    assert scrub_secrets("token=abcdef1234567890") == scrub_secrets("token=abcdef1234567890")


def test_scrubber_rejects_non_string_and_bounds_input() -> None:
    with pytest.raises(TypeError, match="strings only"):
        scrub_secrets(None)  # type: ignore[arg-type]
    output = scrub_secrets("x" * (2 * 1024 * 1024 + 100))
    assert len(output) < 2 * 1024 * 1024 + 100
    assert output.endswith("…[TRUNCATED]")
