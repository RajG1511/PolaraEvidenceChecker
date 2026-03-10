from __future__ import annotations
import json
from openai import OpenAI
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

_client: OpenAI | None = None

def _get_client() -> OpenAI:
    """
    Lazy-init the OpenAI client.
    It reads OPENAI_API_KEY from the environment automatically.
    We reuse one instance across calls (connection pooling).
    """
    global _client
    if _client is None:
        _client = OpenAI()
    return _client

def _build_prompt(control: dict,
    score: float,
    matched_snippets: dict[str, str],
    missing_subcriteria: list[str],
    mismatch_reasons: list[str],
) -> str:
    """
    Build the structured prompt the LLM will receive.

    Design principle: give the model exactly what it needs and nothing more.
    No full document — just the scored evidence excerpts and the gaps.
    The model's job is narrow: enforcement vs. intention.
    """
    control_id   = control.get("control_id",   "unknown")
    control_desc = control.get("description", control.get("control_id", "unknown"))
    snippetsText = ""
    for name, snippet in matched_snippets.items():
        snippetsText += f"\n  [{name}]\n  \"{snippet}\"\n"
    
    missingText = (
        "\n  - " + "\n  - ".join(missing_subcriteria)
        if missing_subcriteria
        else "\n  None"
    )

    mismatchText = (
        "\n  - " + "\n  - ".join(mismatch_reasons)
        if mismatch_reasons
        else "\n  None"
    )

    return f"""You are a SOC 2 audit evidence reviewer. Your job is to decide \
whether the evidence excerpts below demonstrate actual enforcement, \
configuration, or process — or merely express intention or mention.

CONTROL ID: {control_id}
CONTROL DESCRIPTION: {control_desc}
DETERMINISTIC SCORE: {score:.2f} (borderline — requires your judgment)

MATCHED EVIDENCE EXCERPTS:
{snippetsText}

MISSING SUBCRITERIA (not found in document):
{missingText}

MISMATCH SIGNALS DETECTED:
{mismatchText}
EXAMPLES OF THE DISTINCTION:
- Enforcement: "MFA is enforced for all users via Okta with SAML SSO"
- Intention: "Employees are encouraged to enable MFA on their accounts"
- Enforcement: "Branch protection requires 2 approving reviews before merge"
- Intention: "All changes should be reviewed before deployment"

Respond ONLY with this JSON object, no other text:
{{
  "verdict": "sufficient" | "insufficient" | "uncertain",
  "reasoning": "1-2 sentences explaining your decision"
}}

Rules:
- "sufficient": evidence shows enforcement, configuration, or active process
- "insufficient": evidence shows only intent, aspiration, or vague mention
- "uncertain": excerpts are genuinely too ambiguous to classify
- If mismatch signals fired, weigh them heavily toward "insufficient"
- Focus on WHAT the evidence proves, not what it discusses"""

def adjudicate(
    control: dict,
    score: float,
    matched_snippets: dict[str, str],
    missing_subcriteria: list[str],
    mismatch_reasons: list[str],
) -> dict:
    """
    Call OpenAI Chatgpt to resolve an ambiguous (uncertain) score.

    Returns a dict with:
      - verdict:    "sufficient" | "insufficient"
      - reasoning:  human-readable explanation
      - confidence: float 0–1
      - adjudicated: True (so callers know the LLM was invoked)
    """
    prompt = _build_prompt(
        control, score, matched_snippets, missing_subcriteria, mismatch_reasons
    )
    try:
        response = _get_client().chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=256,
            messages=[
                {"role": "user", "content": prompt}
            ],
        )
        raw_text = response.choices[0].message.content.strip()

        # Strip markdown fences if the model wraps the JSON despite instructions
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]

        result = json.loads(raw_text)

        verdict = result.get("verdict", "insufficient")
        if verdict == "uncertain":
            verdict = "insufficient"

        return {
            "verdict":     verdict,
            "reasoning":   result.get("reasoning", ""),
            "adjudicated": True,
        }

    except (json.JSONDecodeError, KeyError, IndexError) as e:
        # If the LLM returns malformed JSON, fail safe to "insufficient"
        # and flag that adjudication failed — don't crash the pipeline
        return {
            "verdict":     "insufficient",
            "reasoning":   f"LLM adjudication failed ({type(e).__name__}); defaulting to insufficient",
            "confidence":  0.0,
            "adjudicated": True,
        }