from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from config import FAISS_META_PATH, RETRIEVER_TOP_K
from retrieval.scheme_matcher import (
    SCHEME_MATCH_MIN_SCORE,
    best_scheme_match,
    preferred_sections_for_query,
    retrieval_query_variants,
)

_SECTION_BONUS = 0.20

_STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "do",
    "does",
    "for",
    "from",
    "fund",
    "hdfc",
    "how",
    "i",
    "in",
    "is",
    "it",
    "me",
    "mutual",
    "of",
    "on",
    "or",
    "please",
    "scheme",
    "tell",
    "that",
    "the",
    "this",
    "to",
    "what",
    "when",
    "where",
    "which",
    "who",
    "with",
}

_PROMOTIONAL_PHRASES = (
    "invest in stocks",
    "invest in etfs",
    "invest in ipos",
    "fast orders",
    "real-time p&l",
    "track returns on your stock holdings",
    "download the app",
    "open demat account",
    "start investing",
    "zero brokerage",
    "sign up on groww",
    "groww stocks",
)


@lru_cache(maxsize=1)
def _load_chunks() -> list[dict]:
    """
    Load chunk text and metadata from the existing metadata JSON.

    This avoids loading FAISS, NumPy, PyTorch, Transformers, or an
    embedding model and is suitable for Render's free instance.
    """
    path = Path(FAISS_META_PATH)

    if not path.exists():
        raise FileNotFoundError(
            f"Chunk metadata file not found: {path}"
        )

    data = json.loads(
        path.read_text(encoding="utf-8")
    )

    if not isinstance(data, list):
        raise ValueError(
            f"Expected a list of chunks in {path}"
        )

    return data


def _tokens(text: str) -> set[str]:
    words = re.findall(
        r"[a-z0-9]+",
        (text or "").lower(),
    )

    return {
        word
        for word in words
        if len(word) > 1 and word not in _STOP_WORDS
    }


def _normalise(text: str) -> str:
    return re.sub(
        r"\s+",
        " ",
        (text or "").lower(),
    ).strip()


def _is_promotional_chunk(chunk: dict) -> bool:
    text = _normalise(
        chunk.get("text") or ""
    )

    return any(
        phrase in text
        for phrase in _PROMOTIONAL_PHRASES
    )


def _score_chunk(
    query_variants: list[str],
    chunk: dict,
    preferred_sections: set[str],
    matched_fund_id: str | None,
) -> float:
    text = chunk.get("text") or ""
    fund_name = chunk.get("fund_name") or ""
    section_type = chunk.get("section_type") or ""
    fund_id = chunk.get("fund_id") or ""

    searchable = _normalise(
        f"{fund_name} {section_type} {text}"
    )
    searchable_tokens = _tokens(searchable)

    best_score = 0.0

    for query in query_variants:
        query_normalised = _normalise(query)
        query_tokens = _tokens(query_normalised)

        if not query_tokens:
            continue

        overlap = query_tokens & searchable_tokens
        coverage = len(overlap) / len(query_tokens)
        overlap_bonus = min(
            len(overlap) * 0.03,
            0.24,
        )

        score = coverage + overlap_bonus

        if (
            query_normalised
            and query_normalised in searchable
        ):
            score += 0.35

        best_score = max(
            best_score,
            score,
        )

    if section_type in preferred_sections:
        best_score += _SECTION_BONUS

    if (
        matched_fund_id
        and fund_id == matched_fund_id
    ):
        best_score += 0.75

    return best_score


def _deduplicate(
    chunks: list[dict],
) -> list[dict]:
    output: list[dict] = []
    seen: set[str] = set()

    for chunk in chunks:
        chunk_id = chunk.get("chunk_id") or ""

        if not chunk_id:
            chunk_id = (
                f"{chunk.get('fund_id', '')}:"
                f"{chunk.get('section_type', '')}:"
                f"{chunk.get('text', '')[:100]}"
            )

        if chunk_id in seen:
            continue

        seen.add(chunk_id)
        output.append(chunk)

    return output


def retrieve_docs(
    query: str,
    top_k: int | None = None,
) -> list[dict]:
    k = (
        top_k
        if top_k is not None
        else RETRIEVER_TOP_K
    )

    chunks = _load_chunks()

    preferred_sections = set(
        preferred_sections_for_query(query)
    )

    query_variants = retrieval_query_variants(
        query
    )

    _, matched_fund_id, match_score = (
        best_scheme_match(query)
    )

    if match_score < SCHEME_MATCH_MIN_SCORE:
        matched_fund_id = None

    ranked: list[dict] = []

    for original_chunk in chunks:
        chunk = dict(original_chunk)

        if _is_promotional_chunk(chunk):
            continue

        score = _score_chunk(
            query_variants=query_variants,
            chunk=chunk,
            preferred_sections=preferred_sections,
            matched_fund_id=matched_fund_id,
        )

        if score <= 0:
            continue

        chunk["score"] = float(score)
        ranked.append(chunk)

    if matched_fund_id:
        same_fund = [
            chunk
            for chunk in ranked
            if chunk.get("fund_id")
            == matched_fund_id
        ]

        if same_fund:
            ranked = same_fund

    if preferred_sections:
        matching_sections = [
            chunk
            for chunk in ranked
            if chunk.get("section_type")
            in preferred_sections
        ]

        if matching_sections:
            ranked = matching_sections

    ranked.sort(
        key=lambda item: float(
            item.get("score", 0.0)
        ),
        reverse=True,
    )

    return _deduplicate(ranked)[:k]