#sprcificity.py
from __future__ import annotations
import re

# Named tools/platforms commonly cited in SOC 2 evidence
TOOL_PATTERNS = [
    # Identity & Access
    r"\bokta\b", r"\bonelogin\b", r"\bping identity\b", r"\bazure ad\b", r"\bactive directory\b",
    r"\bldap\b", r"\bsaml\b", r"\bsso\b",

    # Security monitoring & SIEM
    r"\bsplunk\b", r"\bdatadog\b", r"\bsentinel\b", r"\bcrowdstrike\b",
    r"\bcloudtrail\b", r"\bguardduty\b", r"\bsecurity hub\b", r"\bwazuh\b",
    r"\bpagerduty\b", r"\bopsgenie\b",

    # Vulnerability & code scanning
    r"\bsnyk\b", r"\bdependabot\b", r"\bsonarqube\b", r"\bveracode\b",
    r"\bsemgrep\b", r"\btrivy\b", r"\bnessus\b", r"\bqualys\b",

    # Cloud & infrastructure
    r"\baws\b", r"\bgcp\b", r"\bazure\b", r"\bkms\b", r"\biam\b",
    r"\bcloudwatch\b", r"\bterraform\b", r"\bkubernetes\b", r"\bdocker\b",

    # Compliance platforms
    r"\bvanta\b", r"\bdrata\b", r"\bsecureframe\b", r"\btoretto\b",

    # Change management & CI/CD
    r"\bgithub\b", r"\bgitlab\b", r"\bbitbucket\b", r"\bjira\b",
    r"\bjenkins\b", r"\bcircle ?ci\b", r"\bgithub actions\b",
    r"\bci/cd\b", r"\bpipeline\b", r"\bstaging\b",

    # Change management concepts (count as named process evidence)
    r"\bbranch protection\b", r"\bpull request\b",
    r"\brunbook\b", r"\brollback\b", r"\brelease runbook\b",
]

# Dates, version numbers, and configuration specifics
DATE_VERSION_PATTERN = re.compile(
    r"\b("
    r"\d{4}[-/]\d{2}[-/]\d{2}"          # 2024-01-01
    r"|\bv\d+\.\d+"                      # v1.2
    r"|\btls\s+1\.[23]"                  # TLS 1.2 / 1.3
    r"|\baes[-\s]?\d{3}"                 # AES-256
    r"|\bsha[-\s]?\d+"                   # SHA-256
    r"|\brsa[-\s]?\d{4}"                 # RSA-2048
    r"|\bport\s+\d+"                     # port 443
    r"|\bpython\s+\d+\.\d+"             # Python 3.11
    r"|\bnode\s+\d+\.\d+"               # Node 18.0
    r")\b",
    re.IGNORECASE,
)

# Quantitative claims — expanded to cover reviewer counts, retention, SLAs
QUANTITATIVE_PATTERN = re.compile(
    r"\b\d+\s*("
    r"days?|hours?|minutes?|seconds?"   # time periods
    r"|%|percent"                        # percentages
    r"|mb|gb|tb"                         # storage
    r"|approving reviews?"               # ← CC8.1 fix: "2 approving reviews"
    r"|reviewers?"                       # "2 reviewers required"
    r"|approvals?"                       # "2 approvals before merge"
    r"|attempts?"                        # "3 failed attempts"
    r"|retries"                          # "3 retries"
    r"|months?"                          # "6 months retention"
    r"|weeks?"                           # "2 weeks"
    r"|years?"                           # "1 year"
    r")\b",
    re.IGNORECASE,
)

# Named roles and people — expanded to cover engineering org roles
ROLE_PATTERN = re.compile(
    r"\b("
    r"ciso|cto|ceo|coo"
    r"|vp of engineering|vp of security|vp of infrastructure"
    r"|security engineer|security analyst|security architect"
    r"|devops|devsecops|platform engineer"
    r"|sre|site reliability"
    r"|on[-\s]?call|incident commander|incident manager"
    r"|security team|engineering team|platform team|ops team"
    r"|change advisory board|cab"        # formal change management role
    r"|release manager|release engineer" # ← CC8.1: release management
    r"|system owner|asset owner"
    r")\b",
    re.IGNORECASE,
)

# Configuration table entries — catches structured evidence like:
# "Required pull request reviews: 2 — Enabled"
# "Restrict direct pushes to main: Enabled"
# This is the pattern that was missing for CC8.1 tabular evidence
CONFIG_TABLE_PATTERN = re.compile(
    r"\b(enabled|disabled|enforced|required|configured|active|on|off)\b"
    r".{0,30}"                           # short gap
    r"\b(enabled|disabled|enforced|required|configured|active)\b"
    r"|\b(enabled|enforced|required|configured)\b",
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
    
    # Signal 5: Configuration table entries
    if CONFIG_TABLE_PATTERN.search(document_text):
        signals_found += 1

    return signals_found / 5.0