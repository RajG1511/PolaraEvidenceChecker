from __future__ import annotations
import re

def normalize(text: str) -> str:
    """
    Lowercase and strip punctuation so 'MFA', 'mfa', and 'MFA.' all match.
    """
    return re.sub(r"[^\w\s]", " ", text.lower())

def computeKeywordScore(document_text: str, concept_clusters: list[str | list[str]],) -> tuple[float, list[str]]:
    """
    Score concept coverage using the concept_clusters structure from the JSON.

    Each cluster looks like:
      {
        "concept_name": "tls_ssl",
        "keywords": ["TLS", "SSL", "TLS 1.3", ...],
        "required": true
      }

    A cluster is "covered" if ANY of its keywords appear in the document.
    Required clusters are weighted 2x vs optional ones.

    Returns:
      - score: float 0–1
      - matched: list of concept names that were found
      - missing: list of concept names that were NOT found
    """
    if not concept_clusters:
        return 0.0, []
    
    docNormalized = normalize(document_text)
    matched = []
    missing = []
    weighted_hits  = 0.0
    weighted_total = 0.0

    for cluster in concept_clusters:
        name     = cluster.get("concept_name", "unknown")
        keywords = cluster.get("keywords", [])
        required = cluster.get("required", True)
        weight   = 2.0 if required else 1.0

        weighted_total += weight

        # Check if ANY keyword in this cluster appears in the document
        cluster_hit = any(normalize(kw) in docNormalized for kw in keywords)

        if cluster_hit:
            matched.append(name)
            weighted_hits += weight
        else:
            missing.append(name)

    score = weighted_hits / weighted_total if weighted_total > 0 else 0.0
    return score, matched, missing