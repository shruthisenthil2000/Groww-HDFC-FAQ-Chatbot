from __future__ import annotations

from typing import TYPE_CHECKING

from config import RETRIEVER_TOP_K
from ingestion.phase2.indexer import search_faiss
from retrieval.scheme_matcher import (
    SCHEME_MATCH_MIN_SCORE,
    best_scheme_match,
    preferred_sections_for_query,
    retrieval_query_variants,
)

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

_SECTION_BONUS = 0.08

# Lazy-loaded embedding model so Render can open the web-service port first.
model = None


def get_model() -> SentenceTransformer:
    global model

    if model is None:
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer(
            "all-MiniLM-L6-v2",
            device="cpu",
        )
        model.max_seq_length = 128

    return model


def embed_query(text: str) -> list[float]:
    return get_model().encode(text).tolist()


def embed_texts(texts: list[str]) -> list[list[float]]:
    return get_model().encode(texts).tolist()


def _prioritize_fund_id(chunks: list[dict], fund_id: str) -> list[dict]:
    same = [c for c in chunks if c.get("fund_id") == fund_id]
    other = [c for c in chunks if c.get("fund_id") != fund_id]

    same.sort(
        key=lambda x: float(x.get("score", 0.0)),
        reverse=True,
    )
    other.sort(
        key=lambda x: float(x.get("score", 0.0)),
        reverse=True,
    )

    out = []
    seen = set()

    for chunk in same + other:
        chunk_id = chunk.get("chunk_id") or ""

        if chunk_id and chunk_id not in seen:
            seen.add(chunk_id)
            out.append(chunk)

    return out


def retrieve_docs(query: str, top_k: int | None = None) -> list[dict]:
    k = top_k if top_k is not None else RETRIEVER_TOP_K
    fetch_k = max(k * 5, 96)

    merged = {}
    preferred_sections = preferred_sections_for_query(query)

    for query_text in retrieval_query_variants(query):
        embedding = embed_query(query_text)

        for chunk in search_faiss(embedding, top_k=fetch_k):
            chunk_id = chunk.get("chunk_id") or ""

            if not chunk_id:
                continue

            previous = merged.get(chunk_id)
            score = float(chunk.get("score", 0.0))

            if previous is None or score > float(
                previous.get("score", 0.0)
            ):
                merged[chunk_id] = chunk

    ranked = list(merged.values())

    for chunk in ranked:
        if chunk.get("section_type") in preferred_sections:
            chunk["score"] = (
                float(chunk.get("score", 0.0)) + _SECTION_BONUS
            )

    ranked.sort(
        key=lambda x: float(x.get("score", 0.0)),
        reverse=True,
    )

    _, matched_fund_id, match_score = best_scheme_match(query)

    if (
        matched_fund_id
        and match_score >= SCHEME_MATCH_MIN_SCORE
    ):
        ranked = _prioritize_fund_id(
            ranked,
            matched_fund_id,
        )

    return ranked[:k]