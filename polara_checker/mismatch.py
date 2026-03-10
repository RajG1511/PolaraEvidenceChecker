#mismatch.py
from __future__ import annotations
import re

def computeMismatchPenalty(document_text: str, mismatch_signals: list[dict],) -> tuple[float, list[str]]:
    """
    Detect wrong-control signals using regex patterns.

    Each signal in mismatch_signals looks like:
      {
        "pattern": "\\bat.?rest\\b|\\bdatabase encryption\\b",
        "reason": "Describes at-rest encryption, not in-transit",
        "strength": 0.6
      }

    Penalty logic:
      - Each fired signal contributes its strength value
      - We take the MAX strength of all fired signals as the base
      - Then add 0.2 for each additional signal beyond the first (capped at 1.0)
      - This means one strong mismatch signal (0.6) is already significant,
        but multiple signals compound the penalty

    Returns:
      - penalty: float 0–1
      - reasons: list of human-readable reasons for fired signals
    """
    if not mismatch_signals:
        return 0.0, []
    
    firedStrengths = []
    firedReasons   = []

    for signal in mismatch_signals:
        pattern  = signal.get("pattern", "")
        reason   = signal.get("reason", pattern)
        strength = float(signal.get("strength", 0.3))

        if not pattern:
            continue

        try:
            # re.IGNORECASE so "At Rest" and "at rest" both match
            if re.search(pattern, document_text, re.IGNORECASE):
                firedStrengths.append(strength)
                firedReasons.append(reason)
        except re.error:
            # Malformed regex in the JSON — skip rather than crash
            continue

    if not firedStrengths:
        return 0.0, []

    # Base penalty = strongest single signal
    # Each additional signal adds 0.2, capped at 1.0
    base_penalty = max(firedStrengths)
    extra        = (len(firedStrengths) - 1) * 0.2
    penalty      = min(1.0, base_penalty + extra)

    return penalty, firedReasons