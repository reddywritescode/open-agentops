from __future__ import annotations

import re
from typing import Any


EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
PHONE_RE = re.compile(r"\b(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}\b")
SECRET_VALUE_RE = re.compile(
    r"\b(?:"
    r"sk-(?:or-v1-)?[A-Za-z0-9_-]{12,}|"
    r"gh[pousr]_[A-Za-z0-9_]{20,}|"
    r"xox[baprs]-[A-Za-z0-9-]{10,}|"
    r"AKIA[0-9A-Z]{16}"
    r")\b"
)
SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(?:api[_-]?key|access[_-]?token|client[_-]?secret|password|secret|token)"
    r"\b\s*[:=]\s*[\"']?([A-Za-z0-9_\-./+=]{8,})"
)
CARD_CANDIDATE_RE = re.compile(r"\b(?:\d[ -]?){13,19}\b")


PII_KINDS = {"email", "phone", "ssn", "credit_card"}
SECRET_KINDS = {"api_key", "secret_assignment"}


def _redact(value: str) -> str:
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"


def _luhn_valid(value: str) -> bool:
    digits = [int(char) for char in value if char.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False
    total = 0
    parity = len(digits) % 2
    for index, digit in enumerate(digits):
        if index % 2 == parity:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def _add_finding(
    findings: list[dict[str, Any]],
    *,
    kind: str,
    category: str,
    match: str,
    source: str,
) -> None:
    redacted = _redact(match)
    key = (kind, redacted, source)
    if any((item["kind"], item["redacted"], item["source"]) == key for item in findings):
        return
    findings.append(
        {
            "kind": kind,
            "category": category,
            "redacted": redacted,
            "source": source,
        }
    )


def detect_sensitive_data(text: str, *, source: str = "text") -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if not text:
        return findings

    for match in EMAIL_RE.finditer(text):
        _add_finding(findings, kind="email", category="pii", match=match.group(0), source=source)
    for match in SSN_RE.finditer(text):
        _add_finding(findings, kind="ssn", category="pii", match=match.group(0), source=source)
    for match in PHONE_RE.finditer(text):
        _add_finding(findings, kind="phone", category="pii", match=match.group(0), source=source)
    for match in CARD_CANDIDATE_RE.finditer(text):
        candidate = re.sub(r"\D", "", match.group(0))
        if _luhn_valid(candidate):
            _add_finding(findings, kind="credit_card", category="pii", match=candidate, source=source)
    for match in SECRET_VALUE_RE.finditer(text):
        _add_finding(findings, kind="api_key", category="secret", match=match.group(0), source=source)
    for match in SECRET_ASSIGNMENT_RE.finditer(text):
        _add_finding(findings, kind="secret_assignment", category="secret", match=match.group(1), source=source)
    return findings
