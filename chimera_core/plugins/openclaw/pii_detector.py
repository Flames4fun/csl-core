"""
PII Detector — Lightweight Regex Scanner

Scans tool parameters for personally identifiable information.
Zero ML dependencies — pure regex for speed.

Detects: SSN, credit cards, email addresses, phone numbers,
         passport numbers, IP addresses, AWS keys.
"""

import re
from typing import Any, Dict, List


# Compiled patterns for performance
_PATTERNS: Dict[str, re.Pattern] = {
    # US Social Security Number: 123-45-6789 or 123456789
    "ssn": re.compile(r"\b\d{3}-?\d{2}-?\d{4}\b"),
    # Credit card: 13-19 digits, optional separators
    "credit_card": re.compile(
        r"\b(?:\d[ -]*?){13,19}\b"
    ),
    # Email address
    "email": re.compile(
        r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b"
    ),
    # Phone numbers: international and US formats
    "phone": re.compile(
        r"(?:\+\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"
    ),
    # AWS access key (starts with AKIA)
    "aws_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    # Generic API key pattern (long hex/base64 strings)
    "api_key": re.compile(
        r"\b(?:sk|pk|api|key|token|secret)[_-][a-zA-Z0-9]{20,}\b",
        re.IGNORECASE,
    ),
}

# Credit card Luhn validation for reducing false positives
def _luhn_check(number: str) -> bool:
    """Validate credit card number with Luhn algorithm."""
    digits = [int(d) for d in number if d.isdigit()]
    if len(digits) < 13:
        return False
    checksum = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


def scan(data: Any) -> bool:
    """Scan data for PII. Returns True if any PII found.

    Args:
        data: Any JSON-serializable value (dict, list, str, etc.)
              Will be flattened to a single string for scanning.

    Returns:
        True if PII patterns detected, False otherwise.
    """
    text = _flatten_to_text(data)
    if not text:
        return False

    for name, pattern in _PATTERNS.items():
        matches = pattern.findall(text)
        if not matches:
            continue

        # Extra validation for credit cards (reduce false positives)
        if name == "credit_card":
            for match in matches:
                clean = re.sub(r"[- ]", "", match)
                if _luhn_check(clean):
                    return True
            continue

        # Any other pattern match = PII found
        return True

    return False


def scan_detailed(data: Any) -> List[str]:
    """Scan data and return list of PII types found.

    Returns:
        List of matched PII type names, e.g. ["email", "phone"]
    """
    text = _flatten_to_text(data)
    if not text:
        return []

    found = []
    for name, pattern in _PATTERNS.items():
        matches = pattern.findall(text)
        if not matches:
            continue

        if name == "credit_card":
            for match in matches:
                clean = re.sub(r"[- ]", "", match)
                if _luhn_check(clean):
                    found.append(name)
                    break
            continue

        found.append(name)

    return found


def _flatten_to_text(data: Any) -> str:
    """Recursively flatten any data structure to a single searchable string."""
    if data is None:
        return ""
    if isinstance(data, str):
        return data
    if isinstance(data, (int, float, bool)):
        return str(data)
    if isinstance(data, dict):
        parts = []
        for v in data.values():
            parts.append(_flatten_to_text(v))
        return " ".join(parts)
    if isinstance(data, (list, tuple)):
        return " ".join(_flatten_to_text(item) for item in data)
    return str(data)
