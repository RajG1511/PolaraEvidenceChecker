from __future__ import annotations
import re

# Named tools/platforms commonly cited in SOC 2 evidence
TOOL_PATTERNS = [
    r"\bokta\b", r"\bpagerduty\b", r"\bsplunk\b", r"\bdatadog\b",
    r"\bsnyk\b", r"\bdependabot\b", r"\bgithub\b", r"\bjira\b",
    r"\baws\b", r"\bkms\b", r"\biam\b", r"\bvanta\b", r"\bdrata\b",
    r"\bcloudtrail\b", r"\bguardduty\b", r"\bsentinel\b", r"\bcrowdstrike\b",
]

# Dates, version numbers (v1.2, TLS 1.3, etc.)
DATE_VERSION_PATTERN = re.compile(
    r"\b(\d{4}[-/]\d{2}[-/]\d{2}|\bv\d+\.\d+|\btls\s+1\.[23]|"
    r"aes[-\s]?\d{3}|\bsha[-\s]?\d+)\b",
    re.IGNORECASE,
)

# Quantitative claims: "90 days", "99.9%", "< 4 hours"
QUANTITATIVE_PATTERN = re.compile(
    r"\b\d+\s*(days?|hours?|minutes?|seconds?|%|percent|mb|gb|tb)\b",
    re.IGNORECASE,
)

# Named roles
ROLE_PATTERN = re.compile(
    r"\b(ciso|cto|ceo|vp of engineering|security engineer|devops|"
    r"sre|on[-\s]?call|incident commander|security team)\b",
    re.IGNORECASE,
)

def computeSpecificityScore(document_text: str) -> float:
    """
    Score how concrete and operational the document evidence is.

    Checks four signals:
      1. Named tools / platforms (Okta, PagerDuty, Snyk...)
      2. Dates and version numbers (TLS 1.3, v2.1, 2024-01-01)
      3. Quantitative claims (90 days, 99.9%, < 4 hours)
      4. Named roles (CISO, on-call, incident commander)

    Each signal found contributes 0.25 to the score (max 1.0).
    The idea: real evidence is specific. Vague policy is not.
    """
    text_lower = document_text.lower()
    signals_found = 0

    # Signal 1: Named tools
    for pattern in TOOL_PATTERNS:
        if re.search(pattern, text_lower):
            signals_found += 1
            break  # One tool hit is enough for this signal

    # Signal 2: Dates/versions
    if DATE_VERSION_PATTERN.search(document_text):
        signals_found += 1

    # Signal 3: Quantitative claims
    if QUANTITATIVE_PATTERN.search(document_text):
        signals_found += 1

    # Signal 4: Named roles
    if ROLE_PATTERN.search(document_text):
        signals_found += 1

    return signals_found / 4.0