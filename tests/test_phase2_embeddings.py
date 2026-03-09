"""
tests/test_phase2_embeddings.py

Phase 2 tests covering:
- chunking.py  : text splitting behaviour
- embeddings.py: model loading, embed shape, similarity math
- controls/    : JSON structure validation + embedding presence

Run with:
    pytest tests/test_phase2_embeddings.py -v

The embedding model tests are marked @pytest.mark.slow because they
load the model from disk (~1 second). Run without slow tests with:
    pytest tests/test_phase2_embeddings.py -v -m "not slow"
"""

import json
import math
from pathlib import Path

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

CONTROLS_DIR = Path(__file__).parent.parent / "controls"


# ===========================================================================
# chunking.py tests  (no model needed — fast)
# ===========================================================================

class TestChunking:
    """Tests for polara_checker.chunking.chunkText"""

    def test_short_text_returns_single_chunk(self):
        from polara_checker.chunking import chunkText

        text = "This is a short document."
        chunks = chunkText(text, chunk_size=250, overlap=50)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_long_text_produces_multiple_chunks(self):
        from polara_checker.chunking import chunkText

        # 600 words — should produce more than 1 chunk at chunk_size=250
        text = " ".join([f"word{i}" for i in range(600)])
        chunks = chunkText(text, chunk_size=250, overlap=50)
        assert len(chunks) > 1

    def test_overlap_means_words_repeat_between_chunks(self):
        from polara_checker.chunking import chunkText

        # 10 words, chunk_size=6, overlap=2 → step=4
        # chunk 1: words 0-5, chunk 2: words 4-9
        # words 4 and 5 should appear in both
        words = [f"w{i}" for i in range(10)]
        text = " ".join(words)
        chunks = chunkText(text, chunk_size=6, overlap=2)

        assert len(chunks) == 2
        chunk1_words = set(chunks[0].split())
        chunk2_words = set(chunks[1].split())
        overlap_words = chunk1_words & chunk2_words
        assert len(overlap_words) == 2  # exactly the 2 overlapping words

    def test_empty_string_returns_empty_list(self):
        from polara_checker.chunking import chunkText

        assert chunkText("") == []
        assert chunkText("   ") == []

    def test_exact_chunk_size_returns_single_chunk(self):
        from polara_checker.chunking import chunkText

        text = " ".join([f"w{i}" for i in range(250)])
        chunks = chunkText(text, chunk_size=250, overlap=50)
        assert len(chunks) == 1

    def test_chunks_cover_all_words(self):
        """Every word in the original text should appear in at least one chunk."""
        from polara_checker.chunking import chunkText

        words = [f"unique_{i}" for i in range(500)]
        text = " ".join(words)
        chunks = chunkText(text, chunk_size=250, overlap=50)

        all_chunk_words = set()
        for chunk in chunks:
            all_chunk_words.update(chunk.split())

        for word in words:
            assert word in all_chunk_words, f"'{word}' missing from all chunks"


# ===========================================================================
# embeddings.py tests  (loads the model — marked slow)
# ===========================================================================

class TestEmbeddings:
    """Tests for polara_checker.embeddings"""

    @pytest.mark.slow
    def test_embedQuery_returns_correct_shape(self):
        from polara_checker.embeddings import embedQuery, EMBEDDING_DIM

        vec = embedQuery("Access control policy with role-based permissions")
        assert vec.shape == (EMBEDDING_DIM,), (
            f"Expected shape ({EMBEDDING_DIM},) but got {vec.shape}. "
            "Did you change EMBEDDING_DIM to 768 for EmbeddingGemma?"
        )

    @pytest.mark.slow
    def test_embedDocument_returns_correct_shape(self):
        from polara_checker.embeddings import embedDocument, EMBEDDING_DIM

        vec = embedDocument("This is an example uploaded policy document.")
        assert vec.shape == (EMBEDDING_DIM,)

    @pytest.mark.slow
    def test_batch_embed_returns_matrix(self):
        from polara_checker.embeddings import embedDocument, EMBEDDING_DIM

        texts = ["First document.", "Second document.", "Third document."]
        matrix = embedDocument(texts)
        assert matrix.shape == (3, EMBEDDING_DIM)

    @pytest.mark.slow
    def test_vectors_are_normalized(self):
        """Normalized vectors should have magnitude (L2 norm) of 1.0."""
        from polara_checker.embeddings import embedQuery

        vec = embedQuery("Some reference text about access control")
        magnitude = float(np.linalg.norm(vec))
        assert math.isclose(magnitude, 1.0, abs_tol=1e-5), (
            f"Expected magnitude 1.0 but got {magnitude}. "
            "normalize_embeddings=True may not be working."
        )

    @pytest.mark.slow
    def test_cosineSimilarity_identical_text_is_near_one(self):
        from polara_checker.embeddings import embedQuery, embedDocument, cosineSimilarity

        text = "Role-based access control with quarterly access reviews"
        # Query and document embeddings of the same text should be very similar
        q = embedQuery(text)
        d = embedDocument(text)
        sim = cosineSimilarity(q, d)
        assert sim > 0.75, f"Same text similarity was only {sim:.3f}"

    @pytest.mark.slow
    def test_cosineSimilarity_unrelated_text_is_low(self):
        from polara_checker.embeddings import embedQuery, embedDocument, cosineSimilarity

        ref = embedQuery("Role-based access control policy with permission tiers")
        unrelated = embedDocument("Annual employee PTO and vacation accrual schedule")
        sim = cosineSimilarity(ref, unrelated)
        assert sim < 0.5, (
            f"Unrelated text similarity was {sim:.3f} — higher than expected. "
            "Mismatch detection may be unreliable."
        )

    @pytest.mark.slow
    def test_relevant_document_scores_higher_than_irrelevant(self):
        """
        The core sanity check: a relevant document chunk should score
        higher against a control reference than an irrelevant one.
        """
        from polara_checker.embeddings import embedQuery, embedDocument, cosineSimilarity

        reference = embedQuery(
            "Role-based access control policy defining permission tiers and user roles"
        )
        relevant_chunk = embedDocument(
            "RBAC policy defining least privilege roles with quarterly access reviews "
            "and formal provisioning workflow requiring manager approval"
        )
        irrelevant_chunk = embedDocument(
            "Badge reader installed at office entrance for physical building access. "
            "Employees must swipe keycard to enter the facility."
        )

        relevant_sim = cosineSimilarity(relevant_chunk, reference)
        irrelevant_sim = cosineSimilarity(irrelevant_chunk, reference)

        assert relevant_sim > irrelevant_sim, (
            f"Relevant ({relevant_sim:.3f}) should outscore irrelevant ({irrelevant_sim:.3f})"
        )

    @pytest.mark.slow
    def test_best_chunk_similarity_finds_needle_in_haystack(self):
        """
        A relevant paragraph buried in a sea of unrelated chunks
        should still produce a high best_chunk_similarity score.
        """
        from polara_checker.embeddings import (
            embedQuery, embedDocument, best_chunk_similarity, EMBEDDING_DIM
        )

        reference = embedQuery("TLS 1.2 encryption in transit certificate management")

        # One relevant chunk surrounded by irrelevant ones
        chunks = [
            "The company has a generous PTO policy with 20 days per year.",
            "All API traffic is encrypted using TLS 1.3 with auto-renewed certificates.",  # ← the needle
            "Employees must complete annual security awareness training.",
            "Change requests require two approvals before merging to main branch.",
        ]
        chunk_embeddings = embedDocument(chunks)  # shape: (4, 768)

        best_sim = best_chunk_similarity(chunk_embeddings, reference)

        # The best chunk (TLS one) should score well even though 3/4 chunks are off-topic
        assert best_sim > 0.35, (
            f"best_chunk_similarity was {best_sim:.3f}. "
            "The relevant chunk should have been found."
        )

    @pytest.mark.slow
    def test_singleton_model_is_reused(self):
        """Calling getModel() twice should return the exact same object."""
        from polara_checker.embeddings import getModel

        model_a = getModel()
        model_b = getModel()
        assert model_a is model_b


# ===========================================================================
# Control JSON file tests  (no model needed — validates structure only)
# ===========================================================================

class TestControlFiles:
    """
    Validates that every control JSON file:
    - Exists and is valid JSON
    - Has all required top-level fields
    - Has at least one required subcriterion
    - Has embeddings populated (non-null, correct length)
    - Has at least one mismatch signal
    - Has sensible threshold values
    """

    REQUIRED_TOP_LEVEL_FIELDS = {
        "control_id", "description", "subcriteria",
        "mismatch_signals", "thresholds"
    }
    REQUIRED_SUBCRITERION_FIELDS = {"name", "reference_text", "embedding", "required"}
    EXPECTED_CONTROL_IDS = {
        "CC6.1", "CC6.2", "CC6.3", "CC6.6", "CC6.7",
        "CC6.8", "CC7.2", "CC7.3", "CC8.1", "CC1.4"
    }
    EMBEDDING_DIM = 768

    def _load_all_controls(self) -> list[dict]:
        files = list(CONTROLS_DIR.glob("*.json"))
        controls = []
        for f in files:
            with f.open(encoding="utf-8") as fh:
                controls.append((f.name, json.load(fh)))
        return controls

    def test_all_ten_control_files_exist(self):
        found_ids = set()
        for f in CONTROLS_DIR.glob("*.json"):
            with f.open(encoding="utf-8") as fh:
                data = json.load(fh)
            found_ids.add(data.get("control_id", ""))

        missing = self.EXPECTED_CONTROL_IDS - found_ids
        assert not missing, f"Missing control files for: {missing}"

    def test_all_files_are_valid_json(self):
        for filename, _ in self._load_all_controls():
            pass  # If we get here without exception, JSON is valid

    @pytest.mark.parametrize("filename,control", [
        (f.name, json.load(f.open(encoding="utf-8")))
        for f in sorted(CONTROLS_DIR.glob("*.json"))
    ])
    def test_required_top_level_fields_present(self, filename, control):
        missing = self.REQUIRED_TOP_LEVEL_FIELDS - control.keys()
        assert not missing, f"{filename} is missing fields: {missing}"

    @pytest.mark.parametrize("filename,control", [
        (f.name, json.load(f.open(encoding="utf-8")))
        for f in sorted(CONTROLS_DIR.glob("*.json"))
    ])
    def test_has_at_least_one_required_subcriterion(self, filename, control):
        required = [s for s in control.get("subcriteria", []) if s.get("required")]
        assert len(required) >= 1, (
            f"{filename} has no required subcriteria — "
            "Phase 3 needs at least one to compute a meaningful score"
        )

    @pytest.mark.parametrize("filename,control", [
        (f.name, json.load(f.open(encoding="utf-8")))
        for f in sorted(CONTROLS_DIR.glob("*.json"))
    ])
    def test_embeddings_are_populated(self, filename, control):
        """Fails if build_references.py hasn't been run yet."""
        for sub in control.get("subcriteria", []):
            embedding = sub.get("embedding")
            assert embedding is not None and len(embedding) > 0, (
                f"{filename} → subcriterion '{sub.get('name')}' has no embedding. "
                "Run: python scripts/build_references.py"
            )

    @pytest.mark.parametrize("filename,control", [
        (f.name, json.load(f.open(encoding="utf-8")))
        for f in sorted(CONTROLS_DIR.glob("*.json"))
    ])
    def test_embedding_dimensions_are_correct(self, filename, control):
        for sub in control.get("subcriteria", []):
            embedding = sub.get("embedding")
            if embedding:  # Skip if not yet populated
                assert len(embedding) == self.EMBEDDING_DIM, (
                    f"{filename} → '{sub.get('name')}' embedding has {len(embedding)} dims, "
                    f"expected {self.EMBEDDING_DIM}. Did you use the wrong model?"
                )

    @pytest.mark.parametrize("filename,control", [
        (f.name, json.load(f.open(encoding="utf-8")))
        for f in sorted(CONTROLS_DIR.glob("*.json"))
    ])
    def test_thresholds_are_valid(self, filename, control):
        thresholds = control.get("thresholds", {})
        floor = thresholds.get("sufficient_floor")
        ceiling = thresholds.get("insufficient_ceiling")

        assert floor is not None, f"{filename} missing sufficient_floor"
        assert ceiling is not None, f"{filename} missing insufficient_ceiling"
        assert 0 < ceiling < floor < 1, (
            f"{filename} thresholds are invalid: ceiling={ceiling}, floor={floor}. "
            "Must satisfy: 0 < insufficient_ceiling < sufficient_floor < 1"
        )

    @pytest.mark.parametrize("filename,control", [
        (f.name, json.load(f.open(encoding="utf-8")))
        for f in sorted(CONTROLS_DIR.glob("*.json"))
    ])
    def test_has_at_least_one_mismatch_signal(self, filename, control):
        signals = control.get("mismatch_signals", [])
        assert len(signals) >= 1, (
            f"{filename} has no mismatch signals — "
            "Phase 3 won't be able to penalise wrong-type documents"
        )
