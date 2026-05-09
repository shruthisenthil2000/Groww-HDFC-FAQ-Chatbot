```python id="h3k9pw"
from __future__ import annotations

import logging

from openai import OpenAI

from config import (
    EMBEDDING_MODEL,
    OPENAI_API_KEY,
    RETRIEVER_TOP_K,
)

from ingestion.phase2.indexer import search_faiss

logger = logging.getLogger(__name__)

client = OpenAI(api_key=OPENAI_API_KEY)

_MIN_SCORE: float = 0.45

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


def get_openai_embedding(text: str) -> list[float]:
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text,
    )

    return response.data[0].embedding


def retrieve(
    query: str,
    top_k: int = RETRIEVER_TOP_K,
    fund_id: str | None = None,
    filter_section_type: str | None = None,
) -> list[dict]:

    logger.info(
        "Retrieving top_k=%d fund_id=%s section_filter=%s query=%r",
        top_k,
        fund_id,
        filter_section_type,
        query,
    )

    query_embedding = get_openai_embedding(query)

    results = search_faiss(
        query_embedding,
        top_k=top_k,
        filter_section_type=filter_section_type,
    )

    before_grounding = len(results)

    results = [
        r for r in results
        if r.get("fund_id", "") in _HDFC_FUND_IDS
    ]

    if len(results) < before_grounding:
        logger.warning(
            "Removed %d non-HDFC chunks",
            before_grounding - len(results),
        )

    if not results:
        logger.warning("No grounded HDFC chunks remain")
        return []

    router_anchored = (
        filter_section_type is not None
        or fund_id is not None
    )

    if not router_anchored:
        results = [
            r for r in results
            if r.get("score", 0) >= _MIN_SCORE
        ]

        if not results:
            logger.info("No chunks above relevance threshold")
            return []

    if fund_id is not None:

        if filter_section_type is not None:

            all_section = search_faiss(
                query_embedding,
                top_k=85,
                filter_section_type=filter_section_type,
            )

            filtered = [
                r for r in all_section
                if r.get("fund_id") == fund_id
            ]

        else:
            filtered = [
                r for r in results
                if r.get("fund_id") == fund_id
            ]

        if filtered:
            logger.info(
                "%d chunks after fund filter (%s)",
                len(filtered),
                fund_id,
            )

            return filtered[:top_k]

        logger.warning(
            "fund_id=%r not found; falling back",
            fund_id,
        )

    logger.info("%d chunks retrieved", len(results))

    return results[:top_k]


if __name__ == "__main__":

    import sys

    from retrieval.router import route

    query = (
        " ".join(sys.argv[1:])
        or "What is the expense ratio of HDFC Mid Cap Fund?"
    )

    detected_fund, detected_section = route(query)

    print(f"\nQuery: {query}")
    print(f"Detected fund: {detected_fund}")
    print(f"Detected section: {detected_section}\n")

    for r in retrieve(
        query,
        fund_id=detected_fund,
        filter_section_type=detected_section,
    ):

        print(
            f"[{r['score']:.4f}] "
            f"[{r['section_type']}] "
            f"[{r['fund_id']}] "
            f"{r['text'][:90]}..."
        )
```
