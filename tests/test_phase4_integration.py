# tests/test_phase4_integration.py
#
# INTEGRATION TESTS — these make real OpenAI API calls and cost money.
# Run manually only when you want to verify the live LLM integration:
#
#   pytest tests/test_phase4_integration.py -v -s
#
# They are intentionally excluded from the normal test run.
# Never run these in CI.

from __future__ import annotations
import pytest
from polara_checker.llm_adjudicator import adjudicate

# ─────────────────────────────────────────────────────────────────────────────
# FIXTURES
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def cc6_1_control():
    return {
        "control_id":  "CC6.1",
        "description": "Logical access controls restrict access to systems and data based on least privilege.",
        "thresholds": {
            "sufficient_floor":     0.50,
            "insufficient_ceiling": 0.30,
        }
    }


# ─────────────────────────────────────────────────────────────────────────────
# CASE 1: Strong enforcement evidence — expect "sufficient"
# Real, specific, concrete language. Should not need much deliberation.
# ─────────────────────────────────────────────────────────────────────────────

def test_real_llm_strong_enforcement(cc6_1_control):
    snippets = {
        "rbac_definition": (
            "All user access is provisioned through Okta with role-based access control. "
            "Engineers are assigned the least-privilege role required for their team. "
            "Privileged access requires manager approval via a Jira ticket before provisioning."
        ),
        "access_review": (
            "Access reviews are conducted quarterly using Vanta. "
            "Any account inactive for 30 days is automatically suspended. "
            "Terminated employee accounts are revoked within 2 hours via automated Okta deprovisioning."
        ),
    }

    result = adjudicate(
        control             = cc6_1_control,
        score               = 0.42,             # borderline — inside uncertain band
        matched_snippets    = snippets,
        missing_subcriteria = [],
        mismatch_reasons    = [],
    )

    print(f"\n[CASE 1] verdict={result['verdict']}  reasoning={result['reasoning']}")

    assert result["adjudicated"] == True
    assert result["verdict"] in ("sufficient", "insufficient")  # never uncertain
    assert result["verdict"] == "sufficient"                    # we expect this
    assert len(result["reasoning"]) > 0


# ─────────────────────────────────────────────────────────────────────────────
# CASE 2: Vague intention language — expect "insufficient"
# Policy aspiration with no enforcement details.
# ─────────────────────────────────────────────────────────────────────────────

def test_real_llm_intention_only(cc6_1_control):
    snippets = {
        "rbac_definition": (
            "The company believes in the importance of access controls. "
            "Employees should only access systems relevant to their role. "
            "We aim to implement least privilege across all systems in the future."
        ),
    }

    result = adjudicate(
        control             = cc6_1_control,
        score               = 0.38,
        matched_snippets    = snippets,
        missing_subcriteria = ["access_review", "provisioning_process"],
        mismatch_reasons    = [],
    )

    print(f"\n[CASE 2] verdict={result['verdict']}  reasoning={result['reasoning']}")

    assert result["adjudicated"] == True
    assert result["verdict"] in ("sufficient", "insufficient")
    assert result["verdict"] == "insufficient"
    assert len(result["reasoning"]) > 0


# ─────────────────────────────────────────────────────────────────────────────
# CASE 3: Mismatch signal fired — expect "insufficient"
# Document talks about encryption at rest, not access controls.
# ─────────────────────────────────────────────────────────────────────────────

def test_real_llm_mismatch_signal(cc6_1_control):
    snippets = {
        "rbac_definition": (
            "All data at rest is encrypted using AES-256. "
            "Database backups are encrypted and stored in S3 with KMS key management. "
            "Encryption keys are rotated every 90 days."
        ),
    }

    result = adjudicate(
        control             = cc6_1_control,
        score               = 0.40,
        matched_snippets    = snippets,
        missing_subcriteria = ["access_review", "least_privilege"],
        mismatch_reasons    = ["Document describes encryption at rest, not access control"],
    )

    print(f"\n[CASE 3] verdict={result['verdict']}  reasoning={result['reasoning']}")

    assert result["adjudicated"] == True
    assert result["verdict"] in ("sufficient", "insufficient")
    assert result["verdict"] == "insufficient"
    assert len(result["reasoning"]) > 0


# ─────────────────────────────────────────────────────────────────────────────
# CASE 4: Genuinely ambiguous — no strict assertion on verdict
# We just verify the pipeline completes and returns a valid structure.
# ─────────────────────────────────────────────────────────────────────────────

def test_real_llm_ambiguous_case(cc6_1_control):
    snippets = {
        "rbac_definition": (
            "Access to production systems requires approval. "
            "The security team reviews access requests on a case by case basis."
        ),
    }

    result = adjudicate(
        control             = cc6_1_control,
        score               = 0.41,
        matched_snippets    = snippets,
        missing_subcriteria = ["access_review"],
        mismatch_reasons    = [],
    )

    print(f"\n[CASE 4] verdict={result['verdict']}  reasoning={result['reasoning']}")

    # For ambiguous cases we don't assert a specific verdict —
    # we just verify the pipeline returns a valid, well-formed result
    assert result["adjudicated"] == True
    assert result["verdict"] in ("sufficient", "insufficient")  # never uncertain
    assert isinstance(result["reasoning"], str)
    assert len(result["reasoning"]) > 0