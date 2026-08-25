from __future__ import annotations

import re

from .core import FaultPackError


class RedactionPolicyError(FaultPackError):
    """Raised when an additional redaction pattern is invalid."""

_SECRET_NAME = re.compile(
    r"(TOKEN|SECRET|PASSWORD|PASS|API[_-]?KEY|PRIVATE[_-]?KEY|COOKIE|AUTH)", re.I
)
_SECRET_VALUE = re.compile(
    r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+|"
    r"(?:sk|ghp|glpat|xoxb)-[A-Za-z0-9_-]{12,}|"
    r"-----BEGIN [A-Z ]+-----[\s\S]+?-----END [A-Z ]+-----"
)
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


def redact_value(value: str, extra_patterns: list[str] | None = None) -> str:
    result = _SECRET_VALUE.sub("[REDACTED]", value)
    result = _EMAIL.sub("[REDACTED_EMAIL]", result)
    result = _IPV4.sub("[REDACTED_IP]", result)
    for pattern in extra_patterns or []:
        try:
            result = re.sub(pattern, "[REDACTED]", result)
        except re.error as exc:
            raise RedactionPolicyError(f"invalid redaction pattern: {exc}") from exc
    return result


def redact_environment(
    values: dict[str, str], extra_patterns: list[str] | None = None
) -> dict[str, str]:
    return {
        key: "[REDACTED]" if _SECRET_NAME.search(key) else redact_value(value, extra_patterns)
        for key, value in values.items()
    }
