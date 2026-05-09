"""
RAG Retriever — Phase 3.1

Embeds an incoming query string and retrieves the top-k most semantically
similar chunks from the persisted FAISS index (data/index/vector.faiss).

Design decisions
----------------
- Single embedding model: read from config.EMBEDDING_MODEL (set in .env).
  The model is loaded once at import time to avoid per-request cold-start.
- Normalization: query vector is L2-normalised before search.
  This is mandatory — the FAISS index was built on L2-normalised document
  vectors, so skipping normalization produces incorrect cosine scores.
- Backend: FAISS only (search_faiss). ChromaDB is not used in the retrieval
  path; it remains available as an alternative index in indexer.py.
- Optional section_type filter: pass filter_section_type to restrict results
  to a specific chunk category (e.g. "fund_overview" for metric queries).

Public API
----------
retrieve(query, top_k, filter_section_type) -> list[dict]
    Returns ranked result dicts from search_faiss(), each containing:
    chunk_id, fund_id, fund_name, groww_url, section_type, text, score.
"""

from __future__ import annotations

import logging

from config import EMBEDDING_MODEL, RETRIEVER_TOP_K
from ingestion.phase2.indexer import search_faiss

logger = logging.getLogger(__name__)

# ── Embedding model — loaded once at import time ───────────────────────────────

def _load_model():
    """
    Load the configured embedding model.

    Supports local sentence-transformers models (default) and raises a clear
    error if an OpenAI model name is configured without a valid API key.
    """
    if EMBEDDING_MODEL.startswith("text-embedding-"):
        raise RuntimeError(
            f"EMBEDDING_MODEL={EMBEDDING_MODEL!r} is an OpenAI model. "
            "The retriever currently uses a local sentence-transformers model. "
            "Set EMBEDDING_MODEL=all-MiniLM-L6-v2 in .env to use the local backend, "
            "or implement an OpenAI encode path in retriever.py."
        )
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError(
            "sentence-transformers is not installed. Run: pip install sentence-transformers"
        ) from exc

    logger.debug("Loading embedding model: %s", EMBEDDING_MODEL)
    return SentenceTransformer(EMBEDDING_MODEL)


_model = _load_model()


# ── Public API ─────────────────────────────────────────────────────────────────

def retrieve(
    query: str,
    top_k: int = RETRIEVER_TOP_K,
    filter_section_type: str | None = None,
) -> list[dict]:
    """
    Embed a query and retrieve the top-k most similar chunks from the FAISS index.

    Args:
        query:               Natural-language question from the user.
        top_k:               Number of results to return (default: RETRIEVER_TOP_K).
        filter_section_type: Optional section filter, e.g. "fund_overview",
                             "exit_load_tax". Applied as a post-filter inside
                             search_faiss() — over-fetches internally to
                             compensate.

    Returns:
        list of result dicts ordered by cosine similarity (highest first).
        Each dict contains: chunk_id, fund_id, fund_name, groww_url,
                            section_type, text, score.
    """
    logger.info("Retrieving  top_k=%d  filter=%s  query=%r", top_k, filter_section_type, query)

    # L2-normalise: mandatory because the FAISS index uses IndexFlatIP on
    # unit vectors — without normalisation the scores are not cosine similarity.
    query_embedding: list[float] = _model.encode(
        query,
        normalize_embeddings=True,
    ).tolist()

    results = search_faiss(
        query_embedding,
        top_k=top_k,
        filter_section_type=filter_section_type,
    )

    logger.info("  → %d chunks retrieved", len(results))
    return results


# ── CLI smoke-test ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    query = " ".join(sys.argv[1:]) or "What is the expense ratio of HDFC Mid Cap Fund?"
    print(f"\nQuery: {query}\n")

    for r in retrieve(query):
        print(
            f"  [{r['score']:.4f}]"
            f"  [{r['section_type']:20s}]"
            f"  [{r['fund_id']:25s}]"
            f"  {r['text'][:90]}..."
        )
