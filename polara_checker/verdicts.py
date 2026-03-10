from __future__ import annotations

def getVerdict(score: float, control: dict) -> str:
    """
    Map a numeric score to a verdict string using the control's threshold band.

    The control JSON contains a 'thresholds' block like:
        { "sufficient": 0.60, "insufficient": 0.40 }

    Scores above the sufficient floor → "sufficient"
    Scores below the insufficient ceiling → "insufficient"
    Everything in between → "uncertain" (will go to LLM)

    We use .get() with sensible defaults so the function doesn't crash
    if someone forgot to add thresholds to a control JSON.
    """
    thresholds = control.get("thresholds", {})
    sufficient_floor     = thresholds.get("sufficient_floor",    0.5)
    insufficient_ceiling = thresholds.get("insufficient_ceiling",  0.3)

    if score >= sufficient_floor:
        return "sufficient"
    elif score <= insufficient_ceiling:
        return "insufficient"
    else:
        return "uncertain"
    