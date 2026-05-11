from __future__ import annotations

from sentence_transformers import SentenceTransformer

from config import EMBEDDING_MODEL, RETRIEVER_TOP_K
from ingestion.phase2.indexer import search_faiss
from retrieval.scheme_matcher import (
    SCHEME_MATCH_MIN_SCORE,
    best_scheme_match,
    preferred_sections_for_query,
    retrieval_query_variants,
)

_model = None

def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model
_SECTION_BONUS = 0.08


def embed_query(text: str) -> list[float]:
    return _model.encode(text, normalize_embeddings=True).tolist()


def embed_texts(texts: list[str]) -> list[list[float]]:
    vecs = _model.encode(texts, normalize_embeddings=True)
    return [v.tolist() for v in vecs]


def _prioritize_fund_id(chunks: list[dict], fund_id: str) -> list[dict]:
    """Stable re-order: all chunks for fund_id first (by score), then the rest."""
    same = [c for c in chunks if c.get("fund_id") == fund_id]
    other = [c for c in chunks if c.get("fund_id") != fund_id]
    same.sort(key=lambda x: float(x.get("score", 0.0)), reverse=True)
    other.sort(key=lambda x: float(x.get("score", 0.0)), reverse=True)
    out: list[dict] = []
    seen: set[str] = set()
    for c in same + other:
        cid = c.get("chunk_id") or ""
        if cid and cid not in seen:
            seen.add(cid)
            out.append(c)
    return out


def retrieve_docs(query: str, top_k: int | None = None) -> list[dict]:
    """
    Semantic search over FAISS with query variants (synonyms, section intents,
    topic hints, fuzzy scheme name). Merges hits across variants (best score
    per chunk_id), then prioritizes the fuzzy-matched scheme before global rank.
    """
    k = top_k if top_k is not None else RETRIEVER_TOP_K
    fetch_k = max(k * 5, 96)
    merged: dict[str, dict] = {}
    preferred_sections = preferred_sections_for_query(query)

    for qtext in retrieval_query_variants(query):
        emb = embed_query(qtext)
        for c in search_faiss(emb, top_k=fetch_k):
            cid = c.get("chunk_id") or ""
            if not cid:
                continue
            prev = merged.get(cid)
            score = float(c.get("score", 0.0))
            if prev is None or score > float(prev.get("score", 0.0)):
                merged[cid] = c

    ranked = list(merged.values())
    for c in ranked:
        if c.get("section_type") in preferred_sections:
            c["score"] = float(c.get("score", 0.0)) + _SECTION_BONUS
    ranked.sort(key=lambda x: float(x.get("score", 0.0)), reverse=True)
    _, matched_fid, sc = best_scheme_match(query)
    if matched_fid and sc >= SCHEME_MATCH_MIN_SCORE:
        ranked = _prioritize_fund_id(ranked, matched_fid)
    return ranked[:k]
