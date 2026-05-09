"""
RAG Retriever — Phase 3.2.2

Embeds an incoming query string and retrieves the top-k most semantically
similar chunks from the persisted FAISS index (data/index/vector.faiss).

Implements the two-stage metadata-anchored retrieval strategy documented in
Phase 3.2 of architecture.md:

  Stage 1 (handled by router.py):
      route(query) → (fund_id, section_type)
      Extracts anchor signals before any embedding work is done.

  Stage 2 (this module):
      1. Embed the query with L2 normalisation.
      2. search_faiss(query_embedding, filter_section_type=section_type)
         → cuts the effective search space from ~90 to ~15 chunks.
      3. Hard corpus-grounding filter: discard any chunk whose fund_id does
         not belong to the 15 known HDFC funds. This prevents any future
         index contamination from leaking non-HDFC content to the LLM.
      4. Post-filter results by fund_id (if detected)
         → typically returns exactly 1 chunk for the correct fund.
      5. Fall back to section-filtered results if the fund post-filter
         produces an empty set (prevents silent empty responses).
      6. If after grounding filter the results are empty, return [] — the
         generator will return NO_ANSWER_SENTINEL rather than hallucinating.

Design decisions
----------------
- Single embedding model: read from config.EMBEDDING_MODEL (set in .env).
  The model is loaded once at import time to avoid per-request cold-start.
- Normalisation: query vector is L2-normalised before search.
  Mandatory — the FAISS index was built on L2-normalised document vectors.
- Backend: FAISS only (search_faiss). ChromaDB is not used in retrieval.
- Corpus grounding: ALL results are hard-filtered to HDFC fund IDs before
  being returned. If grounding filter removes all results, [] is returned
  so the generator issues a no-answer response instead of hallucinating.

Public API
----------
retrieve(query, top_k, fund_id, filter_section_type) -> list[dict]
    Returns ranked result dicts, each containing:
    chunk_id, fund_id, fund_name, groww_url, section_type, text, score.
"""

from __future__ import annotations

import logging

from config import EMBEDDING_MODEL, RETRIEVER_TOP_K
from ingestion.phase2.indexer import search_faiss

# Minimum cosine similarity for a retrieved chunk to be considered relevant.
# Chunks below this threshold are discarded — the generator will return the
# no-answer sentinel instead of hallucinating from unrelated content.
# Empirical calibration on this corpus: in-corpus queries score ≥ 0.40,
# fully out-of-scope queries (stock prices, weather, etc.) score < 0.45
# when no section filter is active.
_MIN_SCORE: float = 0.45

# ── Corpus grounding: the complete set of HDFC fund IDs in this project ────────
# This is the ground truth from corpus/sources.json.  Any chunk returned by
# FAISS whose fund_id is NOT in this set is silently discarded before the
# context is sent to the LLM — prevents hallucination from index drift.
_HDFC_FUND_IDS: frozenset[str] = frozenset({
    "hdfc_flexi_cap",
    "hdfc_focused",
    "hdfc_elss",
    "hdfc_large_cap",
    "hdfc_silver_etf_fof",
    "hdfc_small_cap",
    "hdfc_defence",
    "hdfc_gold_etf_fof",
    "hdfc_housing_opportunities",
    "hdfc_nifty50_index",
    "hdfc_balanced_advantage",
    "hdfc_pharma_healthcare",
    "hdfc_bse_sensex_index",
    "hdfc_short_term_debt",
    "hdfc_mid_cap",
})

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
    fund_id: str | None = None,
    filter_section_type: str | None = None,
) -> list[dict]:
    """
    Embed a query and retrieve the top-k most similar chunks (two-stage strategy).

    Args:
        query:               Natural-language question from the user.
        top_k:               Number of results to return (default: RETRIEVER_TOP_K).
        fund_id:             Optional fund ID detected by the router. When present,
                             results are post-filtered to chunks from this fund.
                             Falls back to unfiltered results if post-filter
                             produces an empty set.
        filter_section_type: Optional section filter, e.g. "fund_overview",
                             "exit_load_tax". Applied inside search_faiss() —
                             over-fetches internally to compensate.

    Returns:
        list of result dicts ordered by cosine similarity (highest first).
        Each dict contains: chunk_id, fund_id, fund_name, groww_url,
                            section_type, text, score.
    """
    logger.info(
        "Retrieving  top_k=%d  fund_id=%s  section_filter=%s  query=%r",
        top_k, fund_id, filter_section_type, query,
    )

    # L2-normalise: mandatory because the FAISS index uses IndexFlatIP on
    # unit vectors — without normalisation the scores are not cosine similarity.
    query_embedding: list[float] = _model.encode(
        query,
        normalize_embeddings=True,
    ).tolist()

    # Stage 2a: dense search with optional section_type pre-filter
    results = search_faiss(
        query_embedding,
        top_k=top_k,
        filter_section_type=filter_section_type,
    )

    # ── Hard corpus-grounding filter ─────────────────────────────────────────────
    # Keep ONLY chunks that belong to the known HDFC fund set.
    # This is a safety net against index drift or future multi-corpus expansion
    # where non-HDFC content might accidentally appear in the index.
    before_grounding = len(results)
    results = [r for r in results if r.get("fund_id", "") in _HDFC_FUND_IDS]
    if len(results) < before_grounding:
        logger.warning(
            "Corpus grounding: removed %d non-HDFC chunk(s) from results",
            before_grounding - len(results),
        )
    if not results:
        logger.warning("Corpus grounding: 0 HDFC chunks remain — returning empty (no-answer)")
        return []

    # ── Relevance threshold ─────────────────────────────────────────────────────
    # Apply the score threshold ONLY when the router found no anchors.
    # When section_type or fund_id is detected by the router, those signals are
    # keyword-based and precise — the corpus IS relevant even if cosine similarity
    # is low (embedding model limitation for short domain terms like "exit load").
    router_anchored = filter_section_type is not None or fund_id is not None
    if not router_anchored:
        results = [r for r in results if r.get("score", 0) >= _MIN_SCORE]
        if not results:
            logger.info("  → 0 chunks above relevance threshold (out-of-scope query)")
            return []

    # ── Stage 2b: fund_id post-filter ───────────────────────────────────────────
    # When the router detected a fund name, narrow to that fund's chunks.
    # To guarantee we find the correct fund+section pair (which may not be in
    # the top_k by similarity), re-fetch the full section-filtered set first.
    if fund_id is not None:
        if filter_section_type is not None:
            # Re-fetch the entire section to scan all fund chunks in that section
            all_section = search_faiss(
                query_embedding,
                top_k=85,          # fetch all; at 85 chunks this is negligible
                filter_section_type=filter_section_type,
            )
            filtered = [r for r in all_section if r.get("fund_id") == fund_id]
        else:
            filtered = [r for r in results if r.get("fund_id") == fund_id]

        if filtered:
            logger.info(
                "  → %d chunks after fund_id filter (%s)", len(filtered), fund_id
            )
            return filtered[:top_k]

        # Fallback: fund_id detected but fund not found — return section results
        logger.warning(
            "  fund_id=%r not found in results; falling back to section-filtered",
            fund_id,
        )

    logger.info("  → %d chunks retrieved", len(results))
    return results[:top_k]


# ── CLI smoke-test ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    from retrieval.router import route

    query = " ".join(sys.argv[1:]) or "What is the expense ratio of HDFC Mid Cap Fund?"
    detected_fund, detected_section = route(query)

    print(f"\nQuery:           {query}")
    print(f"Detected fund:   {detected_fund}")
    print(f"Detected section:{detected_section}\n")

    for r in retrieve(query, fund_id=detected_fund, filter_section_type=detected_section):
        print(
            f"  [{r['score']:.4f}]"
            f"  [{r['section_type']:20s}]"
            f"  [{r['fund_id']:25s}]"
            f"  {r['text'][:90]}..."
        )
