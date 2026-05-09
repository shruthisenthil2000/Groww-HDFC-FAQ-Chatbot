"""
Phase 2.3 — Embedding Generation

Batch-embeds all chunk texts produced by Phase 2.2.
Attaches an "embedding" key (list[float]) to each chunk dict.

The embedding model is selected from the EMBEDDING_MODEL env var (config.py):
  - Any "text-embedding-*" model  → OpenAI API  (requires valid OPENAI_API_KEY)
  - Any other string               → sentence-transformers local model
    e.g. "all-MiniLM-L6-v2"  (384-dim, default)
         "BAAI/bge-small-en-v1.5"  (384-dim, higher quality)

Public API
----------
embed_chunks(chunks) -> list[dict]
    Embed all chunk texts and add "embedding": list[float] to each dict.
    Fails loudly if embeddings cannot be produced (no silent/dummy vectors).

Input  : list of chunk dicts from Phase 2.2
Output : same list with "embedding": list[float] added to each chunk
"""

from __future__ import annotations

import logging
from typing import Any

from config import EMBEDDING_MODEL, EMBEDDING_DIM, require_openai_key

logger = logging.getLogger(__name__)

# ── Backend detection ─────────────────────────────────────────────────────────

def _is_openai_model(model: str) -> bool:
    return model.startswith("text-embedding-")


# ── OpenAI embedder ───────────────────────────────────────────────────────────

def _embed_openai(texts: list[str], model: str) -> list[list[float]]:
    """Batch-embed texts using the OpenAI Embeddings API."""
    try:
        import openai
    except ImportError as exc:
        raise RuntimeError(
            "openai package is not installed. Run: pip install openai"
        ) from exc

    api_key = require_openai_key()   # raises RuntimeError if key is missing/placeholder
    client = openai.OpenAI(api_key=api_key)

    # OpenAI recommends batching up to 2048 texts per call
    BATCH = 512
    all_vectors: list[list[float]] = []
    for i in range(0, len(texts), BATCH):
        batch = texts[i : i + BATCH]
        response = client.embeddings.create(model=model, input=batch)
        all_vectors.extend([item.embedding for item in response.data])
        logger.debug("  OpenAI embeddings: %d/%d", min(i + BATCH, len(texts)), len(texts))

    return all_vectors


# ── Sentence-transformers embedder ────────────────────────────────────────────

def _embed_local(texts: list[str], model_name: str) -> list[list[float]]:
    """Batch-embed texts using a local sentence-transformers model."""
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError(
            "sentence-transformers is not installed. Run: pip install sentence-transformers"
        ) from exc

    logger.info("  Loading sentence-transformers model: %s", model_name)
    model = SentenceTransformer(model_name)

    # For BGE models, queries need the instruction prefix at retrieval time.
    # Document chunks are embedded WITHOUT the prefix (as per BGE spec).
    embeddings = model.encode(
        texts,
        batch_size=64,
        normalize_embeddings=True,
        show_progress_bar=len(texts) > 20,
    )
    return [vec.tolist() for vec in embeddings]


# ── Validation ────────────────────────────────────────────────────────────────

def _validate_embeddings(
    chunks: list[dict],
    vectors: list[list[float]],
    expected_dim: int,
) -> None:
    """
    Validate that every chunk received a non-empty embedding of the correct dimension.

    Raises ValueError immediately — no silent skips.
    """
    if len(vectors) != len(chunks):
        raise ValueError(
            f"Embedding count mismatch: {len(vectors)} vectors for {len(chunks)} chunks."
        )

    for i, (chunk, vec) in enumerate(zip(chunks, vectors)):
        if not vec:
            raise ValueError(
                f"Chunk {chunk['chunk_id']} (index {i}) received an empty embedding vector."
            )
        if len(vec) != expected_dim:
            raise ValueError(
                f"Chunk {chunk['chunk_id']} embedding dim={len(vec)}, "
                f"expected {expected_dim} (EMBEDDING_DIM in .env). "
                "Update EMBEDDING_DIM if you changed EMBEDDING_MODEL."
            )


# ── Public API ────────────────────────────────────────────────────────────────

def embed_chunks(chunks: list[dict]) -> list[dict]:
    """
    Embed all chunk texts and attach "embedding": list[float] to each chunk.

    Args:
        chunks: list of chunk dicts from Phase 2.2 chunk_all().
                Each must have a non-empty "text" field.

    Returns:
        The same list, with "embedding" added to every dict.

    Raises:
        ValueError:  Any chunk has an empty or wrong-dimension embedding.
        RuntimeError: OPENAI_API_KEY is missing/placeholder (for OpenAI models),
                      or required packages are not installed.
    """
    if not chunks:
        logger.warning("embed_chunks called with empty chunk list — nothing to embed.")
        return chunks

    # Guard: every chunk must have non-empty text
    empty_text = [c["chunk_id"] for c in chunks if not c.get("text", "").strip()]
    if empty_text:
        raise ValueError(
            f"Cannot embed: {len(empty_text)} chunk(s) have empty text: {empty_text[:5]}"
        )

    texts = [c["text"] for c in chunks]
    model = EMBEDDING_MODEL

    logger.info(
        "Embedding %d chunks  model=%s  backend=%s",
        len(chunks),
        model,
        "openai" if _is_openai_model(model) else "sentence-transformers",
    )

    if _is_openai_model(model):
        vectors = _embed_openai(texts, model)
    else:
        vectors = _embed_local(texts, model)

    _validate_embeddings(chunks, vectors, EMBEDDING_DIM)

    for chunk, vec in zip(chunks, vectors):
        chunk["embedding"] = vec

    logger.info(
        "  ✔  %d embeddings generated  dim=%d  model=%s",
        len(chunks), len(vectors[0]), model,
    )
    return chunks
