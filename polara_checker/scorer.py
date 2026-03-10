#scorer.py
from __future__ import annotations

import numpy as np

from polara_checker.embeddings import embedDocument, best_chunk_similarity
from polara_checker.chunking import chunkText
from polara_checker.keywords import computeKeywordScore
from polara_checker.mismatch import computeMismatchPenalty
from polara_checker.specificity import computeSpecificityScore
from polara_checker.verdicts import getVerdict
from polara_checker.llm_adjudicator import adjudicate

def scoreDocument(document_text: str, control: dict,) -> dict:
    """
    Run the full deterministic scoring pipeline for one document + control.

    control: the loaded JSON dict for a control (CC6.1, CC7.3, etc.)

    Returns a dict with:
      - score: float 0–1
      - semantic_score: float
      - keyword_score: float
      - specificity_score: float
      - mismatch_penalty: float
      - matched_keywords: list[str]
      - mismatch_reasons: list[str]
      - missing_subcriteria: list[str]   ← feeds the "what's missing" explanation
      - subcriterion_scores: dict        ← per-subcriterion breakdown for debugging
    """

    # 1. Chunk the document and embed all the chunks in one batch
    chunks = chunkText(document_text)

    if not chunks:
        return _empty_result()
    
    chunkEmbeddings = embedDocument(chunks)

    # 2. Semantic similarirty per subcriteria
    subcriteria = control.get("subcriteria", [])
    subcriterionScores = {}
    missingSubcriteria = []
    weightedSum = 0.0
    totalWeight = 0.0

    matchedSnippets: dict[str, str] = {} # store the best-matching snippet for LLM layer

    SUFFICIENT_SUBCRITERION_THRESHOLD = 0.45  # tuned for EmbeddingGemma

    for sub in subcriteria:
        refVector = np.array(sub["embedding"], dtype=np.float32)
        similarities = chunkEmbeddings @ refVector      # shape: (N,)  one sim per chunk
        best_idx     = int(np.argmax(similarities))     # index of the highest-scoring chunk
        bestSim      = float(similarities[best_idx])    # the actual similarity score
        bestSnippet  = chunks[best_idx][:400]           # cap at 400 chars to keep prompt small
        
        #bestSim = best_chunk_similarity(chunkEmbeddings, refVector)

        name = sub["name"]
        required = sub.get("required", True)
        weight = 2.0 if required else 1.0 # required subcriteria count double

        subcriterionScores[name] = round(bestSim, 4)
        weightedSum += bestSim * weight
        totalWeight += weight

        if bestSim < SUFFICIENT_SUBCRITERION_THRESHOLD:
            missingSubcriteria.append(name)
        else:
            matchedSnippets[name] = bestSnippet
        
    semanticScore = weightedSum / totalWeight if totalWeight > 0 else 0.0

    # 3. Keyword/concept coverage
    concept_clusters = control.get("concept_clusters", [])
    keywordScore, matchedKeywords, missingKeywords = computeKeywordScore(document_text, concept_clusters)

    # 3. Specificity 
    specificityScore = computeSpecificityScore(document_text)

    # 5. Mismatch Penalization
    mismatchSignals = control.get("mismatch_signals", [])
    mismatchPenalty, mismatchReasons = computeMismatchPenalty(document_text, mismatchSignals)

    # 6. Weighted formula
    # finalScore = (0.40 × semantic) + (0.25 × conceptCoverage) + (0.20 × specificity) - (0.15 × mismatchPenalty)
    raw_score = (
          0.40 * semanticScore
        + 0.25 * keywordScore
        + 0.20 * specificityScore
        - 0.15 * mismatchPenalty
    )
    final_score = float(np.clip(raw_score, 0.0, 1.0))

    # Verdict Layer
    verdict = getVerdict(final_score, control)

    llm_reasoning  = None
    llm_confidence = None
    adjudicated    = False

    if verdict == "uncertain":
        # The score landed in the ambiguous band — hand off to Claude Haiku.
        # We pass the snippets (not the full doc) + the gaps + any mismatch
        # reasons so the LLM can make a focused enforcement-vs-intention call.
        llm_result = adjudicate(
            control             = control,
            score               = final_score,
            matched_snippets    = matchedSnippets,
            missing_subcriteria = missingSubcriteria,
            mismatch_reasons    = mismatchReasons,
        )
        # Replace "uncertain" with the LLM's actual verdict.
        # After this point "uncertain" never appears in the output.
        verdict        = llm_result["verdict"]
        llm_reasoning  = llm_result["reasoning"]
        llm_confidence = llm_result["confidence"]
        adjudicated    = True

    return {
        "score":               round(final_score, 4),
        "verdict":             verdict,        # the final human-readable decision
        "adjudicated":         adjudicated,    # True if the LLM was called
        "llm_reasoning":       llm_reasoning,  # None on clear-cut cases
        "llm_confidence":      llm_confidence, # None on clear-cut cases
        "semantic_score":      round(semanticScore, 4),
        "keyword_score":       round(keywordScore, 4),
        "specificity_score":   round(specificityScore, 4),
        "mismatch_penalty":    round(mismatchPenalty, 4),
        "matched_keywords":    matchedKeywords,
        "missing_keywords":    missingKeywords,
        "mismatch_reasons":    mismatchReasons,
        "missing_subcriteria": missingSubcriteria,
        "subcriterion_scores": subcriterionScores,
        "matched_snippets":    matchedSnippets,
    }

def _empty_result() -> dict:
    """Fallback when document text is empty or couldn't be extracted."""
    return {
        "score": 0.0,
        "verdict":             "insufficient",
        "adjudicated":         False,
        "llm_reasoning":       None,
        "llm_confidence":      None,
        "semantic_score": 0.0,
        "keyword_score": 0.0,
        "specificity_score": 0.0,
        "mismatch_penalty": 0.0,
        "matched_keywords": [],
        "missing_keywords": [],
        "mismatch_reasons": ["Document appears to be empty or unreadable"],
        "missing_subcriteria": [],
        "subcriterion_scores": {},
        "matched_snippets": {},
    }