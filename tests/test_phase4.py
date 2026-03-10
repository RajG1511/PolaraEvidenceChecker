# tests/test_phase4.py
from __future__ import annotations
import pytest
from unittest.mock import patch, MagicMock

from polara_checker.verdicts import getVerdict
from polara_checker.llm_adjudicator import _build_prompt, adjudicate


# ─────────────────────────────────────────────────────────────────────────────
# FIXTURES
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_control():
    """A minimal control dict that mirrors what a real JSON file contains."""
    return {
        "control_id":  "CC6.1",
        "description": "Logical access controls are implemented to restrict access to systems.",
        "thresholds": {
            "sufficient_floor":     0.50,
            "insufficient_ceiling": 0.30,
        }
    }


@pytest.fixture
def control_no_thresholds():
    """A control with no thresholds block — tests that defaults kick in."""
    return {
        "control_id":  "CC6.1",
        "description": "Logical access controls.",
    }


@pytest.fixture
def sample_snippets():
    """Realistic matched snippets dict as scoreDocument would produce."""
    return {
        "rbac_definition": "Users are assigned roles in Okta based on their department. "
                           "Role assignments are reviewed quarterly by the security team.",
        "access_review":   "Access reviews are conducted every 90 days using Vanta. "
                           "Stale accounts are revoked within 24 hours of detection.",
    }


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: verdicts.py
# ─────────────────────────────────────────────────────────────────────────────

class TestGetVerdict:

    def test_above_sufficient_floor(self, sample_control):
        # Scores at or above 0.50 should be sufficient
        assert getVerdict(0.50, sample_control) == "sufficient"
        assert getVerdict(0.75, sample_control) == "sufficient"
        assert getVerdict(1.00, sample_control) == "sufficient"

    def test_below_insufficient_ceiling(self, sample_control):
        # Scores at or below 0.30 should be insufficient
        assert getVerdict(0.30, sample_control) == "insufficient"
        assert getVerdict(0.15, sample_control) == "insufficient"
        assert getVerdict(0.00, sample_control) == "insufficient"

    def test_inside_uncertain_band(self, sample_control):
        # Scores strictly between 0.30 and 0.50 should be uncertain
        assert getVerdict(0.31, sample_control) == "uncertain"
        assert getVerdict(0.40, sample_control) == "uncertain"
        assert getVerdict(0.49, sample_control) == "uncertain"

    def test_boundary_values_are_decisive(self, sample_control):
        # Exact boundary values should NOT be uncertain — they should resolve
        assert getVerdict(0.50, sample_control) != "uncertain"
        assert getVerdict(0.30, sample_control) != "uncertain"

    def test_missing_thresholds_uses_defaults(self, control_no_thresholds):
        # If thresholds block is missing, defaults (0.5 / 0.3) should apply
        # and the function should not crash
        assert getVerdict(0.60, control_no_thresholds) == "sufficient"   # above 0.5
        assert getVerdict(0.20, control_no_thresholds) == "insufficient" # below 0.3
        assert getVerdict(0.40, control_no_thresholds) == "uncertain"    # between 0.3–0.5

    def test_custom_narrow_band(self):
        # A tight-band control — uncertain zone is small
        control = {"thresholds": {"sufficient_floor": 0.65, "insufficient_ceiling": 0.45}}
        assert getVerdict(0.70, control) == "sufficient"
        assert getVerdict(0.40, control) == "insufficient"
        assert getVerdict(0.55, control) == "uncertain"

    def test_custom_wide_band(self):
        # A loose-band control — wide uncertain zone
        control = {"thresholds": {"sufficient_floor": 0.70, "insufficient_ceiling": 0.20}}
        assert getVerdict(0.80, control) == "sufficient"
        assert getVerdict(0.15, control) == "insufficient"
        assert getVerdict(0.50, control) == "uncertain"


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: _build_prompt()
# ─────────────────────────────────────────────────────────────────────────────

class TestBuildPrompt:

    def test_control_id_appears(self, sample_control, sample_snippets):
        prompt = _build_prompt(sample_control, 0.50, sample_snippets, [], [])
        assert "CC6.1" in prompt

    def test_control_description_appears(self, sample_control, sample_snippets):
        prompt = _build_prompt(sample_control, 0.50, sample_snippets, [], [])
        assert "Logical access controls are implemented" in prompt

    def test_score_appears(self, sample_control, sample_snippets):
        prompt = _build_prompt(sample_control, 0.42, sample_snippets, [], [])
        assert "0.42" in prompt

    def test_snippets_appear(self, sample_control, sample_snippets):
        prompt = _build_prompt(sample_control, 0.40, sample_snippets, [], [])
        assert "rbac_definition" in prompt
        assert "access_review"   in prompt
        assert "Okta"            in prompt

    def test_missing_subcriteria_appear(self, sample_control, sample_snippets):
        missing = ["provisioning_process", "least_privilege"]
        prompt  = _build_prompt(sample_control, 0.40, sample_snippets, missing, [])
        assert "provisioning_process" in prompt
        assert "least_privilege"      in prompt

    def test_mismatch_reasons_appear(self, sample_control, sample_snippets):
        reasons = ["Document describes at-rest encryption, not in-transit"]
        prompt  = _build_prompt(sample_control, 0.40, sample_snippets, [], reasons)
        assert "at-rest encryption" in prompt

    def test_no_missing_subcriteria_shows_none(self, sample_control, sample_snippets):
        prompt = _build_prompt(sample_control, 0.40, sample_snippets, [], [])
        assert "None" in prompt

    def test_no_mismatch_shows_none(self, sample_control, sample_snippets):
        prompt          = _build_prompt(sample_control, 0.40, sample_snippets, [], [])
        mismatch_section = prompt.split("MISMATCH SIGNALS DETECTED:")[1]
        assert "None" in mismatch_section

    def test_enforcement_examples_present(self, sample_control, sample_snippets):
        prompt = _build_prompt(sample_control, 0.40, sample_snippets, [], [])
        assert "Enforcement:" in prompt
        assert "Intention:"   in prompt

    def test_mfa_example_present(self, sample_control, sample_snippets):
        prompt = _build_prompt(sample_control, 0.40, sample_snippets, [], [])
        assert "MFA" in prompt

    def test_prompt_instructs_json_only(self, sample_control, sample_snippets):
        prompt = _build_prompt(sample_control, 0.40, sample_snippets, [], [])
        assert "Respond ONLY with this JSON object" in prompt

    def test_new_schema_has_no_confidence_field(self, sample_control, sample_snippets):
        # The schema dropped confidence — prompt must not ask for it
        prompt = _build_prompt(sample_control, 0.40, sample_snippets, [], [])
        assert "confidence" not in prompt

    def test_uncertain_verdict_option_in_prompt(self, sample_control, sample_snippets):
        # The schema allows the LLM to return "uncertain" — prompt should say so
        prompt = _build_prompt(sample_control, 0.40, sample_snippets, [], [])
        assert '"uncertain"' in prompt

    def test_mismatch_weighting_instruction_present(self, sample_control, sample_snippets):
        # Prompt must explicitly tell the model to weigh mismatch signals heavily
        prompt = _build_prompt(sample_control, 0.40, sample_snippets, [], [])
        assert "mismatch" in prompt.lower()

    def test_empty_snippets_doesnt_crash(self, sample_control):
        # Edge case: all subcriteria were missing, so no snippets collected
        prompt = _build_prompt(sample_control, 0.40, {}, ["all_subcriteria"], [])
        assert "MATCHED EVIDENCE EXCERPTS" in prompt

    def test_fallback_uses_control_id_when_no_description(self, sample_snippets):
        # If description key is missing, control_id should appear as fallback
        control = {"control_id": "CC7.3"}
        prompt  = _build_prompt(control, 0.40, sample_snippets, [], [])
        assert "CC7.3" in prompt


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: adjudicate()
# ─────────────────────────────────────────────────────────────────────────────

def _make_mock_response(content: str) -> MagicMock:
    """
    Build a fake OpenAI response object that mirrors:
    response.choices[0].message.content
    """
    mock_message          = MagicMock()
    mock_message.content  = content
    mock_choice           = MagicMock()
    mock_choice.message   = mock_message
    mock_response         = MagicMock()
    mock_response.choices = [mock_choice]
    return mock_response


class TestAdjudicate:

    @patch("polara_checker.llm_adjudicator._get_client")
    def test_sufficient_verdict(self, mock_get_client, sample_control, sample_snippets):
        # Happy path: clean JSON, sufficient verdict
        mock_get_client.return_value.chat.completions.create.return_value = (
            _make_mock_response('{"verdict": "sufficient", "reasoning": "Document shows enforcement via Okta."}')
        )
        result = adjudicate(sample_control, 0.42, sample_snippets, [], [])

        assert result["verdict"]     == "sufficient"
        assert result["adjudicated"] == True
        assert "Okta" in result["reasoning"]

    @patch("polara_checker.llm_adjudicator._get_client")
    def test_insufficient_verdict(self, mock_get_client, sample_control, sample_snippets):
        mock_get_client.return_value.chat.completions.create.return_value = (
            _make_mock_response('{"verdict": "insufficient", "reasoning": "Only policy intent, no enforcement."}')
        )
        result = adjudicate(sample_control, 0.38, sample_snippets, ["access_review"], [])

        assert result["verdict"]     == "insufficient"
        assert result["adjudicated"] == True

    @patch("polara_checker.llm_adjudicator._get_client")
    def test_llm_uncertain_fails_safe(self, mock_get_client, sample_control, sample_snippets):
        # LLM is allowed to return "uncertain" — we must fail safe to insufficient
        mock_get_client.return_value.chat.completions.create.return_value = (
            _make_mock_response('{"verdict": "uncertain", "reasoning": "Excerpts are too ambiguous."}')
        )
        result = adjudicate(sample_control, 0.40, sample_snippets, [], [])

        # "uncertain" must never leave the pipeline — resolve it to insufficient
        assert result["verdict"]     == "insufficient"
        assert result["adjudicated"] == True
        assert "ambiguous" in result["reasoning"].lower()

    @patch("polara_checker.llm_adjudicator._get_client")
    def test_malformed_json_fails_safe(self, mock_get_client, sample_control, sample_snippets):
        # If the model returns garbage, we should get "insufficient" not a crash
        mock_get_client.return_value.chat.completions.create.return_value = (
            _make_mock_response("Sorry, I cannot help with that.")
        )
        result = adjudicate(sample_control, 0.40, sample_snippets, [], [])

        assert result["verdict"]     == "insufficient"
        assert result["adjudicated"] == True
        assert result["confidence"]  == 0.0
        assert "failed" in result["reasoning"].lower()

    @patch("polara_checker.llm_adjudicator._get_client")
    def test_markdown_fences_are_stripped(self, mock_get_client, sample_control, sample_snippets):
        # Some models wrap JSON in ```json ... ``` despite instructions
        fenced = '```json\n{"verdict": "sufficient", "reasoning": "Good evidence."}\n```'
        mock_get_client.return_value.chat.completions.create.return_value = (
            _make_mock_response(fenced)
        )
        result = adjudicate(sample_control, 0.42, sample_snippets, [], [])
        assert result["verdict"] == "sufficient"

    @patch("polara_checker.llm_adjudicator._get_client")
    def test_missing_reasoning_uses_default(self, mock_get_client, sample_control, sample_snippets):
        # Model returns verdict only — reasoning should default to empty string
        mock_get_client.return_value.chat.completions.create.return_value = (
            _make_mock_response('{"verdict": "sufficient"}')
        )
        result = adjudicate(sample_control, 0.42, sample_snippets, [], [])

        assert result["verdict"]   == "sufficient"
        assert result["reasoning"] == ""

    @patch("polara_checker.llm_adjudicator._get_client")
    def test_no_confidence_in_result(self, mock_get_client, sample_control, sample_snippets):
        # Schema dropped confidence — result dict should not contain it on success
        mock_get_client.return_value.chat.completions.create.return_value = (
            _make_mock_response('{"verdict": "sufficient", "reasoning": "Looks good."}')
        )
        result = adjudicate(sample_control, 0.42, sample_snippets, [], [])
        assert "confidence" not in result

    @patch("polara_checker.llm_adjudicator._get_client")
    def test_adjudicated_always_true(self, mock_get_client, sample_control, sample_snippets):
        # adjudicated must be True even when adjudication fails
        mock_get_client.return_value.chat.completions.create.return_value = (
            _make_mock_response("not json at all")
        )
        result = adjudicate(sample_control, 0.40, sample_snippets, [], [])
        assert result["adjudicated"] == True

    @patch("polara_checker.llm_adjudicator._get_client")
    def test_mismatch_signals_passed_to_prompt(self, mock_get_client, sample_control, sample_snippets):
        # Verify mismatch reasons make it into the actual API call
        mock_get_client.return_value.chat.completions.create.return_value = (
            _make_mock_response('{"verdict": "insufficient", "reasoning": "Wrong control type."}')
        )
        reasons = ["Describes at-rest encryption, not in-transit"]
        adjudicate(sample_control, 0.40, sample_snippets, [], reasons)

        # Grab the prompt that was actually sent to the model
        call_args   = mock_get_client.return_value.chat.completions.create.call_args
        sent_prompt = call_args.kwargs["messages"][0]["content"]
        assert "at-rest encryption" in sent_prompt


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Integration sanity checks
# ─────────────────────────────────────────────────────────────────────────────

class TestVerdictAndAdjudicateIntegration:

    def test_high_score_never_calls_llm(self, sample_control):
        # Score above sufficient_floor — resolves immediately, no LLM needed
        verdict = getVerdict(0.80, sample_control)
        assert verdict == "sufficient"

    def test_low_score_never_calls_llm(self, sample_control):
        # Score below insufficient_ceiling — resolves immediately, no LLM needed
        verdict = getVerdict(0.10, sample_control)
        assert verdict == "insufficient"

    def test_uncertain_score_requires_llm(self, sample_control):
        # Score inside the band — must come back as uncertain before LLM call
        verdict = getVerdict(0.40, sample_control)
        assert verdict == "uncertain"

    @patch("polara_checker.llm_adjudicator._get_client")
    def test_uncertain_never_in_final_output(self, mock_get_client, sample_control, sample_snippets):
        # Even if the LLM returns "uncertain", the pipeline must resolve it
        mock_get_client.return_value.chat.completions.create.return_value = (
            _make_mock_response('{"verdict": "uncertain", "reasoning": "Too ambiguous."}')
        )
        score   = 0.40
        verdict = getVerdict(score, sample_control)
        assert verdict == "uncertain"

        result = adjudicate(sample_control, score, sample_snippets, [], [])

        # Final output must never be "uncertain"
        assert result["verdict"] in ("sufficient", "insufficient")
        assert result["verdict"] != "uncertain"

    @patch("polara_checker.llm_adjudicator._get_client")
    def test_full_sufficient_flow(self, mock_get_client, sample_control, sample_snippets):
        mock_get_client.return_value.chat.completions.create.return_value = (
            _make_mock_response('{"verdict": "sufficient", "reasoning": "Strong enforcement evidence."}')
        )
        score   = 0.40
        verdict = getVerdict(score, sample_control)
        assert verdict == "uncertain"   # starts uncertain

        result = adjudicate(sample_control, score, sample_snippets, [], [])
        assert result["verdict"]     == "sufficient"   # LLM resolved it
        assert result["adjudicated"] == True
        assert result["reasoning"]   != ""