"""
Phase 2.3 — Embedding Generation

Batch-embeds all chunk texts produced by Phase 2.2.
Attaches an "embedding" key (list[float]) to each chunk dict.

Backend selection:
- OpenAI embeddings → if EMBEDDING_MODEL starts with "text-embedding-"
- Local sentence-transformers → otherwise

Examples:
    text-embedding-3-small
    all-MiniLM-L6-v2
    BAAI/bge-small-en-v1.5
"""

from __future__ import annotations

import logging

from config import (
    EMBEDDING_MODEL,
    EMBEDDING_DIM,
    OPENAI_API_KEY,
    require_openai_key,
)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Backend detection
# ──────────────────────────────────────────────────────────────────────────────

def _is_openai_model(model: str) -> bool:
    return model.startswith("text-embedding-")


# ──────────────────────────────────────────────────────────────────────────────
# OpenAI embeddings
# ──────────────────────────────────────────────────────────────────────────────

def _embed_openai(texts: list[str], model: str) -> list[list[float]]:
    """
    Embed texts using OpenAI embeddings API.
    """

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "openai package not installed. Run: pip install openai"
        ) from exc

    api_key = require_openai_key()

    client = OpenAI(api_key=api_key)

    BATCH_SIZE = 512
    vectors: list[list[float]] = []

    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i : i + BATCH_SIZE]

        response = client.embeddings.create(
            model=model,
            input=batch,
        )

        vectors.extend(item.embedding for item in response.data)

        logger.debug(
            "OpenAI embeddings progress: %d/%d",
            min(i + BATCH_SIZE, len(texts)),
            len(texts),
        )

    return vectors


# ──────────────────────────────────────────────────────────────────────────────
# Local embeddings
# ──────────────────────────────────────────────────────────────────────────────

def _embed_local(texts: list[str], model_name: str) -> list[list[float]]:
    """
    Embed texts using local sentence-transformers.
    """

    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError(
            "sentence-transformers not installed. "
            "Run: pip install sentence-transformers"
        ) from exc

    logger.info("Loading local embedding model: %s", model_name)

    model = SentenceTransformer(model_name)

    embeddings = model.encode(
        texts,
        batch_size=64,
        normalize_embeddings=True,
        show_progress_bar=len(texts) > 20,
    )

    return [vec.tolist() for vec in embeddings]


# ──────────────────────────────────────────────────────────────────────────────
# Validation
# ──────────────────────────────────────────────────────────────────────────────

def _validate_embeddings(
    chunks: list[dict],
    vectors: list[list[float]],
    expected_dim: int,
) -> None:

    if len(vectors) != len(chunks):
        raise ValueError(
            f"Embedding mismatch: "
            f"{len(vectors)} vectors for {len(chunks)} chunks."
        )

    for i, (chunk, vec) in enumerate(zip(chunks, vectors)):

        if not vec:
            raise ValueError(
                f"Empty embedding for chunk "
                f"{chunk['chunk_id']} (index={i})"
            )

        if len(vec) != expected_dim:
            raise ValueError(
                f"Wrong embedding dimension for chunk "
                f"{chunk['chunk_id']}: "
                f"{len(vec)} != {expected_dim}"
            )


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

def embed_chunks(chunks: list[dict]) -> list[dict]:
    """
    Generate embeddings for all chunks.
    """

    if not chunks:
        logger.warning("embed_chunks called with empty chunk list")
        return chunks

    empty_chunks = [
        c["chunk_id"]
        for c in chunks
        if not c.get("text", "").strip()
    ]

    if empty_chunks:
        raise ValueError(
            f"Cannot embed empty chunks: {empty_chunks[:5]}"
        )

    texts = [c["text"] for c in chunks]

    logger.info(
        "Embedding %d chunks using model=%s",
        len(chunks),
        EMBEDDING_MODEL,
    )

    if _is_openai_model(EMBEDDING_MODEL):
        vectors = _embed_openai(texts, EMBEDDING_MODEL)
    else:
        vectors = _embed_local(texts, EMBEDDING_MODEL)

    _validate_embeddings(
        chunks,
        vectors,
        EMBEDDING_DIM,
    )

    for chunk, vector in zip(chunks, vectors):
        chunk["embedding"] = vector

    logger.info(
        "Generated %d embeddings (dim=%d)",
        len(vectors),
        len(vectors[0]),
    )

    return chunks