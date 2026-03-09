from __future__ import annotations

import numpy as np
from sentence_transformers import SentenceTransformer

_MODEL_NAME = "google/embeddinggemma-300m"
_model: SentenceTransformer | None = None

EMBEDDING_DIM = 768

def getModel() -> SentenceTransformer:
    """
    Return the shared model instance, loading it on first call.

    EmbeddingGemma is a gated model — you must run `huggingface-cli login`
    before this will work. After that, the weights are cached locally.

    Note: this model does not support float16. It uses float32 by default,
    which is what SentenceTransformer uses unless you override it.
    """
    global _model
    if _model is None:
        _model = SentenceTransformer(_MODEL_NAME)
    return _model

def embedQuery(text: str | list[str]) -> np.ndarray:
    """
    Embed text that represents what we're LOOKING FOR.

    Use this for: subcriteria reference descriptions in build_references.py

    EmbeddingGemma is an asymmetric model — queries and documents are
    encoded differently under the hood. Using the wrong method produces
    vectors that land in the wrong region of the embedding space,
    which quietly tanks your similarity scores.
    """
    model = getModel()
    return model.encode_query(text, normalize_embeddings=True)

def embedDocument(text: str | list[str]) -> np.ndarray:
    """
    Embed text that represents the CONTENT BEING SEARCHED.

    Use this for: uploaded document chunks in the scoring pipeline.
    """
    model = getModel()
    return model.encode_document(text, normalize_embeddings=True)

def cosineSimilarity(a: np.ndarray, b: np.ndarray) -> float:
    """
    Measure semantic similarity between two normalized vectors.

    Returns a float roughly between 0.1 (unrelated) and 0.9 (near-identical).
    Because both vectors are normalized, this is just a dot product.
    """
    return float(np.clip(np.dot(a, b), -1.0, 1.0))

def best_chunk_similarity(chunk_embeddings: np.ndarray, reference_embedding: np.ndarray,) -> float:
    """
    Find the best-matching chunk for a given subcriterion reference.

    chunk_embeddings: shape (N, 768) — one row per document chunk
    reference_embedding: shape (768,) — the subcriterion we're looking for

    The math here is identical to before — only the dimension changed.
    """
    similarities = chunk_embeddings @ reference_embedding
    return float(np.max(similarities))