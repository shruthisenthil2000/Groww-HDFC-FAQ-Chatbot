"""
Phase 3 — RAG Core: Reranker (optional)

Cross-encoder reranker to improve retrieval relevance beyond
dense vector similarity. Applied after retriever returns top-k results.

Environment variables (loaded via config.py):
    USE_RERANKER     Enable reranking: true | false (default: false)
    RERANKER_MODEL   Cross-encoder model (default: cross-encoder/ms-marco-MiniLM-L-6-v2)
    RERANKER_TOP_N   Number of top chunks to return after reranking (default: 3)
"""

from __future__ import annotations

import logging

# Environment is loaded once via config.py — no per-module load_dotenv() needed.
from config import USE_RERANKER, RERANKER_MODEL, RERANKER_TOP_N

logger = logging.getLogger(__name__)

# ── TODO (Phase 3): Implement reranker ────────────────────────────────────────
#   - Guard with: if not USE_RERANKER: return chunks unchanged
#   - Accept (query, list_of_chunks) from retriever
#   - Score each chunk using the cross-encoder model
#       from sentence_transformers import CrossEncoder
#       model = CrossEncoder(RERANKER_MODEL)
#       pairs = [(query, c["text"]) for c in chunks]
#       scores = model.predict(pairs)
#   - Return reranked list of chunks (top RERANKER_TOP_N)
