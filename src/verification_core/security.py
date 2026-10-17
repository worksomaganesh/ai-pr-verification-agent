"""Deterministic secret scrubbing for verifier-generated evidence and reports."""

from __future__ import annotations

import re

_MAX_SCRUB_INPUT = 2 * 1024 * 1024
_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----[\s\S]*?"
        r"-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
    ),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{12,}"),
    re.compile(
        r"(?i)\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|secret)\s*[:=]\s*['\"]?[^\s,;'\"}]+"
    ),
)
_REDACTED = "[REDACTED]"


def scrub_secrets(value: str) -> str:
    """Replace common credential formats deterministically and bound output size."""
    if not isinstance(value, str):
        raise TypeError("secret scrubbing accepts strings only")
    if len(value) > _MAX_SCRUB_INPUT:
        value = value[:_MAX_SCRUB_INPUT] + "…[TRUNCATED]"
    result = value
    for pattern in _PATTERNS:
        result = pattern.sub(_REDACTED, result)
    return result
