"""
tests/test_phase3.py

Comprehensive tests for Phase 3: the deterministic scoring engine.
Covers all four sub-components individually, then integration tests
through scoreDocument().

Run from project root:
    pytest tests/test_phase3.py -v
"""

import json
import numpy as np
import pytest
from pathlib import Path

from polara_checker.keywords import computeKeywordScore
from polara_checker.mismatch import computeMismatchPenalty
from polara_checker.specificity import computeSpecificityScore
from polara_checker.scorer import scoreDocument


# ════════════════════════════════════════════════════════════════════════════
# FIXTURES — reusable test data
# ════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="session")
def cc67_control():
    """Load the real CC6.7 control JSON (with embeddings)."""
    path = Path("controls/CC6.7.json")
    with path.open() as f:
        return json.load(f)

@pytest.fixture(scope="session")
def cc73_control():
    """Load the real CC7.3 control JSON (with embeddings)."""
    path = Path("controls/CC7.3.json")
    with path.open() as f:
        return json.load(f)

@pytest.fixture(scope="session")
def cc61_control():
    """Load the real CC6.1 control JSON (with embeddings)."""
    path = Path("controls/CC6.1.json")
    with path.open() as f:
        return json.load(f)

@pytest.fixture
def sample_clusters():
    """
    A minimal concept_clusters list for unit testing keywords.py
    in isolation — no real JSON file needed.
    """
    return [
        {
            "concept_name": "tls_ssl",
            "keywords": ["TLS", "SSL", "TLS 1.3", "transport layer security"],
            "required": True,
        },
        {
            "concept_name": "https",
            "keywords": ["HTTPS", "HSTS", "HTTP redirect"],
            "required": True,
        },
        {
            "concept_name": "certificates",
            "keywords": ["certificate", "Let's Encrypt", "cert renewal", "CA"],
            "required": True,
        },
        {
            "concept_name": "transit_protection",
            "keywords": ["encryption in transit", "data in transit"],
            "required": False,
        },
    ]

@pytest.fixture
def sample_mismatch_signals():
    """
    Minimal mismatch_signals for unit testing mismatch.py in isolation.
    Uses the same regex style as the real control JSONs.
    """
    return [
        {
            "pattern": r"\bat.?rest\b|\bdatabase encryption\b|\bstorage encryption\b",
            "reason": "Describes at-rest encryption, not in-transit",
            "strength": 0.6,
        },
        {
            "pattern": r"\bfull.?disk encryption\b|\bbitlocker\b|\bfilevault\b",
            "reason": "Device/disk encryption is not in-transit",
            "strength": 0.5,
        },
        {
            "pattern": r"\bpadlock\b|\bgreen.{0,20}padlock\b",
            "reason": "Browser padlock screenshot proves nothing about TLS config",
            "strength": 0.4,
        },
    ]


# ════════════════════════════════════════════════════════════════════════════
# SECTION 1 — keywords.py
# ════════════════════════════════════════════════════════════════════════════

class TestComputeKeywordScore:

    def test_all_clusters_matched(self, sample_clusters):
        """A document that hits every concept cluster should score 1.0."""
        doc = (
            "TLS 1.3 enforced. HTTPS with HSTS headers. "
            "Certificate renewed via Let's Encrypt. "
            "All data in transit is encrypted."
        )
        score, matched, missing = computeKeywordScore(doc, sample_clusters)
        assert score == 1.0
        assert len(missing) == 0
        assert len(matched) == 4

    def test_no_clusters_matched(self, sample_clusters):
        """A completely irrelevant document should score 0.0."""
        doc = "Employees accrue 20 days of PTO per year. Vacation must be pre-approved."
        score, matched, missing = computeKeywordScore(doc, sample_clusters)
        assert score == 0.0
        assert len(matched) == 0
        assert len(missing) == 4

    def test_partial_match_required_only(self, sample_clusters):
        """
        Hitting only required clusters should score higher than
        hitting only the optional one, because required weight = 2.0.
        """
        # Hit 3 required clusters, miss the 1 optional
        doc_required = "TLS 1.3 enforced on all endpoints. HTTPS with certificate renewal."
        score_req, _, _ = computeKeywordScore(doc_required, sample_clusters)

        # Hit only the optional cluster, miss all required
        doc_optional = "All data in transit is protected."
        score_opt, _, _ = computeKeywordScore(doc_optional, sample_clusters)

        assert score_req > score_opt

    def test_synonym_hit_covers_cluster(self, sample_clusters):
        """
        'transport layer security' is a synonym for TLS.
        Hitting any keyword in a cluster should cover it.
        """
        doc = "All connections use transport layer security protocols."
        score, matched, _ = computeKeywordScore(doc, sample_clusters)
        assert "tls_ssl" in matched

    def test_case_insensitive_matching(self, sample_clusters):
        """Keywords should match regardless of case."""
        doc = "tls 1.3 is enforced. https is required. certificate management in place."
        score, matched, _ = computeKeywordScore(doc, sample_clusters)
        assert "tls_ssl" in matched
        assert "https" in matched
        assert "certificates" in matched

    def test_empty_document(self, sample_clusters):
        """Empty document should return 0.0 gracefully."""
        score, matched, missing = computeKeywordScore("", sample_clusters)
        assert score == 0.0
        assert matched == []

    def test_empty_clusters(self):
        """Empty cluster list should return 0.0 gracefully."""
        score, matched, missing = computeKeywordScore("Some document text.", [])
        assert score == 0.0
        assert matched == []
        assert missing == []

    def test_missing_list_is_complement_of_matched(self, sample_clusters):
        """matched + missing should always equal all cluster names."""
        doc = "TLS 1.3 enforced. No other relevant content."
        score, matched, missing = computeKeywordScore(doc, sample_clusters)
        all_names = {c["concept_name"] for c in sample_clusters}
        assert set(matched) | set(missing) == all_names
        assert set(matched) & set(missing) == set()  # no overlap

    def test_returns_three_values(self, sample_clusters):
        """Ensure the function always returns exactly (float, list, list)."""
        result = computeKeywordScore("some text", sample_clusters)
        assert len(result) == 3
        assert isinstance(result[0], float)
        assert isinstance(result[1], list)
        assert isinstance(result[2], list)


# ════════════════════════════════════════════════════════════════════════════
# SECTION 2 — mismatch.py
# ════════════════════════════════════════════════════════════════════════════

class TestComputeMismatchPenalty:

    def test_no_signals_fire(self, sample_mismatch_signals):
        """A clean in-transit doc should produce zero penalty."""
        doc = "TLS 1.3 enforced on all endpoints. Certificates auto-renewed via Let's Encrypt."
        penalty, reasons = computeMismatchPenalty(doc, sample_mismatch_signals)
        assert penalty == 0.0
        assert reasons == []

    def test_single_signal_fires(self, sample_mismatch_signals):
        """One fired signal should produce a penalty equal to that signal's strength."""
        doc = "All data at rest is encrypted using AES-256 in our database."
        penalty, reasons = computeMismatchPenalty(doc, sample_mismatch_signals)
        # "at rest" matches first signal with strength 0.6
        assert penalty == pytest.approx(0.6, abs=0.01)
        assert len(reasons) == 1

    def test_multiple_signals_compound(self, sample_mismatch_signals):
        """Multiple fired signals should compound: base + 0.2 per extra signal."""
        doc = (
            "BitLocker full disk encryption for all laptops. "
            "Database encryption at rest using AES-256."
        )
        penalty, reasons = computeMismatchPenalty(doc, sample_mismatch_signals)
        # Two signals fire: strength 0.6 and 0.5
        # base = max(0.6, 0.5) = 0.6, extra = 1 * 0.2 = 0.2, total = 0.8
        assert penalty == pytest.approx(0.8, abs=0.01)
        assert len(reasons) == 2

    def test_penalty_capped_at_1(self, sample_mismatch_signals):
        """Penalty should never exceed 1.0 regardless of how many signals fire."""
        doc = (
            "Database encryption at rest. BitLocker full disk encryption. "
            "Green padlock visible in browser for homepage."
        )
        penalty, reasons = computeMismatchPenalty(doc, sample_mismatch_signals)
        assert penalty <= 1.0
        assert len(reasons) == 3

    def test_empty_signals_list(self):
        """Empty mismatch_signals should return 0.0 gracefully."""
        penalty, reasons = computeMismatchPenalty("Some document about encryption.", [])
        assert penalty == 0.0
        assert reasons == []

    def test_empty_document(self, sample_mismatch_signals):
        """Empty document should return 0.0 gracefully."""
        penalty, reasons = computeMismatchPenalty("", sample_mismatch_signals)
        assert penalty == 0.0
        assert reasons == []

    def test_case_insensitive_regex(self, sample_mismatch_signals):
        """Regex patterns should match regardless of capitalisation."""
        doc = "All Data AT REST is protected with AES encryption."
        penalty, reasons = computeMismatchPenalty(doc, sample_mismatch_signals)
        assert penalty > 0.0

    def test_malformed_regex_doesnt_crash(self):
        """A malformed regex pattern in the JSON should be skipped, not crash."""
        bad_signals = [
            {"pattern": "[invalid(regex", "reason": "Bad pattern", "strength": 0.5}
        ]
        penalty, reasons = computeMismatchPenalty("some document text", bad_signals)
        assert penalty == 0.0  # bad signal skipped silently

    def test_regex_word_boundary_precision(self, sample_mismatch_signals):
        """
        'at rest' should NOT match inside 'interest' or 'latest'.
        The \b word boundary in the pattern enforces this.
        """
        doc = "Our latest feature is of great interest to security teams."
        penalty, reasons = computeMismatchPenalty(doc, sample_mismatch_signals)
        assert penalty == 0.0


# ════════════════════════════════════════════════════════════════════════════
# SECTION 3 — specificity.py
# ════════════════════════════════════════════════════════════════════════════

class TestComputeSpecificityScore:

    def test_all_signals_present(self):
        """A document with tool names, versions, quantities, and roles scores 1.0."""
        doc = (
            "Datadog SIEM configured by the CISO with 90-day log retention. "
            "TLS 1.3 enforced. Incident commander notified within 4 hours. "
            "PagerDuty on-call rotation active."
        )
        score = computeSpecificityScore(doc)
        assert score == 1.0

    def test_no_signals_present(self):
        """Vague policy language with no specifics should score 0.0."""
        doc = (
            "The company takes security seriously. We monitor our systems "
            "and respond to incidents promptly. Access is controlled appropriately."
        )
        score = computeSpecificityScore(doc)
        assert score == 0.0

    def test_tool_name_only(self):
        """A document with only a tool name scores 0.25 (1 of 4 signals)."""
        doc = "We use Okta for identity management."
        score = computeSpecificityScore(doc)
        assert score == pytest.approx(0.25, abs=0.01)

    def test_quantitative_claim_only(self):
        """A document with only a quantitative claim scores 0.25."""
        doc = "Logs are retained for 90 days in our system."
        score = computeSpecificityScore(doc)
        assert score == pytest.approx(0.25, abs=0.01)

    def test_version_number_detected(self):
        """Version numbers like TLS 1.3 or v2.1 should trigger the signal."""
        doc = "All connections use TLS 1.3. Agent version v2.4 deployed."
        score = computeSpecificityScore(doc)
        assert score >= 0.25  # at least the version signal

    def test_named_role_detected(self):
        """Named roles like CISO or on-call should trigger the role signal."""
        doc = "The CISO reviews all access requests quarterly."
        score = computeSpecificityScore(doc)
        assert score >= 0.25

    def test_score_range(self):
        """Score should always be between 0.0 and 1.0 inclusive."""
        docs = [
            "",
            "vague policy document with no specifics whatsoever",
            "Okta + Datadog + PagerDuty + Splunk + AWS + GitHub configured by CISO "
            "with 99.9% uptime SLA, TLS 1.3, v3.1, 30-day retention",
        ]
        for doc in docs:
            score = computeSpecificityScore(doc)
            assert 0.0 <= score <= 1.0, f"Score {score} out of range for: {doc[:50]}"

    def test_empty_document(self):
        """Empty string should return 0.0 without error."""
        score = computeSpecificityScore("")
        assert score == 0.0

    def test_multiple_tools_still_one_signal(self):
        """
        Mentioning 5 different tools should still only count as 1 signal (0.25),
        not boost the score above 0.25 from tools alone.
        """
        doc = "We use Okta, Datadog, Splunk, PagerDuty, and Snyk."
        score = computeSpecificityScore(doc)
        # Only tool signal fires — still 0.25 unless other signals also present
        assert score == pytest.approx(0.25, abs=0.01)


# ════════════════════════════════════════════════════════════════════════════
# SECTION 4 — scorer.py integration tests (uses real control JSON + embeddings)
# ════════════════════════════════════════════════════════════════════════════

class TestScoreDocument:

    # ── Output structure ────────────────────────────────────────────────────

    def test_returns_expected_keys(self, cc67_control):
        """scoreDocument should always return all expected keys."""
        result = scoreDocument("TLS 1.3 enforced on all endpoints.", cc67_control)
        expected_keys = {
            "score", "semantic_score", "keyword_score", "specificity_score",
            "mismatch_penalty", "matched_keywords", "missing_keywords",
            "mismatch_reasons", "missing_subcriteria", "subcriterion_scores",
        }
        assert expected_keys.issubset(result.keys())

    def test_score_always_in_range(self, cc67_control, cc73_control):
        """Final score should always be clamped to 0–1."""
        docs = [
            "TLS 1.3 enforced, HTTPS, certificates auto-renewed.",
            "AES-256 database encryption at rest using AWS KMS.",
            "",
            "PTO policy: employees get 20 days per year.",
        ]
        for doc in docs:
            for ctrl in [cc67_control, cc73_control]:
                result = scoreDocument(doc, ctrl)
                assert 0.0 <= result["score"] <= 1.0, (
                    f"Score {result['score']} out of range for doc: {doc[:40]}"
                )

    def test_subcriterion_scores_keys_match_control(self, cc67_control):
        """subcriterion_scores dict should have one key per subcriterion."""
        result = scoreDocument("TLS enforced with certificates.", cc67_control)
        expected_names = {s["name"] for s in cc67_control["subcriteria"]}
        assert set(result["subcriterion_scores"].keys()) == expected_names

    def test_empty_document_returns_zero(self, cc67_control):
        """An empty document should score 0.0 across all sub-scores."""
        result = scoreDocument("", cc67_control)
        assert result["score"] == 0.0

    def test_missing_subcriteria_is_list(self, cc67_control):
        """missing_subcriteria should always be a list, never None."""
        result = scoreDocument("Some document text here.", cc67_control)
        assert isinstance(result["missing_subcriteria"], list)

    # ── Discrimination tests ────────────────────────────────────────────────

    def test_good_doc_scores_higher_than_irrelevant(self, cc67_control):
        """
        A relevant CC6.7 document should score higher than a completely
        irrelevant document (PTO policy).
        """
        good_doc = (
            "SSL Labs scan shows A+ rating. TLS 1.3 enforced on all endpoints. "
            "Certificates auto-renewed via Let's Encrypt every 90 days. "
            "HSTS enabled. Load balancer rejects TLS 1.0 and 1.1."
        )
        bad_doc = (
            "Employees accrue 20 days of PTO per year. "
            "Vacation requests must be submitted two weeks in advance."
        )
        good_result = scoreDocument(good_doc, cc67_control)
        bad_result  = scoreDocument(bad_doc, cc67_control)
        assert good_result["score"] > bad_result["score"]

    def test_wrong_encryption_type_penalized(self, cc67_control):
        """
        An at-rest encryption doc scored against CC6.7 (in-transit) should
        score lower than a good in-transit doc, with a non-zero mismatch penalty.
        """
        transit_doc = (
            "TLS 1.3 enforced. HTTPS required. Certificates auto-renewed. "
            "HSTS header configured. Cipher suites audited quarterly."
        )
        at_rest_doc = (
            "AES-256 encryption applied to all database tables and S3 buckets. "
            "Encryption keys managed via AWS KMS. All data at rest is encrypted."
        )
        transit_result  = scoreDocument(transit_doc, cc67_control)
        at_rest_result  = scoreDocument(at_rest_doc, cc67_control)

        assert at_rest_result["mismatch_penalty"] > 0.0
        assert transit_result["score"] > at_rest_result["score"]

    def test_specific_doc_scores_higher_than_vague(self, cc73_control):
        """
        A specific, operational incident response doc should outscore a vague one.
        """
        specific_doc = (
            "PagerDuty on-call rotation for P1-P4 incidents. Escalation matrix "
            "defines CISO notification within 15 minutes for P1. "
            "Post-mortem required within 48 hours. SLA: P1 resolved in 4 hours."
        )
        vague_doc = (
            "The company has an incident response policy. Incidents are escalated "
            "to the appropriate team. Post-mortems are conducted after major events."
        )
        specific_result = scoreDocument(specific_doc, cc73_control)
        vague_result    = scoreDocument(vague_doc, cc73_control)

        assert specific_result["specificity_score"] > vague_result["specificity_score"]
        assert specific_result["score"] > vague_result["score"]

    def test_more_keywords_means_higher_keyword_score(self, cc67_control):
        """
        A document hitting more concept clusters should have a higher keyword_score.
        """
        doc_few_keywords = "TLS is used for connections."
        doc_many_keywords = (
            "TLS 1.3 enforced. HTTPS required with HSTS. "
            "Certificates managed via Let's Encrypt. Encryption in transit verified."
        )
        result_few  = scoreDocument(doc_few_keywords, cc67_control)
        result_many = scoreDocument(doc_many_keywords, cc67_control)
        assert result_many["keyword_score"] > result_few["keyword_score"]

    # ── Mismatch compound penalty ───────────────────────────────────────────

    def test_mismatch_reasons_populated_when_penalty_fires(self, cc67_control):
        """When mismatch penalty > 0, mismatch_reasons should be non-empty."""
        doc = (
            "AES-256 encryption at rest. Database encryption using AWS KMS. "
            "BitLocker full disk encryption on all laptops."
        )
        result = scoreDocument(doc, cc67_control)
        if result["mismatch_penalty"] > 0.0:
            assert len(result["mismatch_reasons"]) > 0

    # ── Cross-control sanity ────────────────────────────────────────────────

    def test_access_control_doc_scores_higher_on_cc61_than_cc73(
        self, cc61_control, cc73_control
    ):
        """
        An RBAC/access control document should score higher against CC6.1
        than against CC7.3 (incident response).
        """
        access_doc = (
            "RBAC policy defines least privilege roles with quarterly access reviews. "
            "Provisioning workflow requires manager approval. "
            "Role assignments reviewed by IAM team. Okta used for SSO."
        )
        score_cc61 = scoreDocument(access_doc, cc61_control)["score"]
        score_cc73 = scoreDocument(access_doc, cc73_control)["score"]
        assert score_cc61 > score_cc73

    def test_incident_response_doc_scores_higher_on_cc73_than_cc61(
        self, cc61_control, cc73_control
    ):
        """
        An incident response document should score higher against CC7.3
        than against CC6.1 (access controls).
        """
        ir_doc = (
            "Incident response plan defines P1-P4 severity tiers. "
            "PagerDuty on-call rotation. Escalation matrix with CISO notification. "
            "Post-mortem required within 48 hours of P1 resolution."
        )
        score_cc61 = scoreDocument(ir_doc, cc61_control)["score"]
        score_cc73 = scoreDocument(ir_doc, cc73_control)["score"]
        assert score_cc73 > score_cc61