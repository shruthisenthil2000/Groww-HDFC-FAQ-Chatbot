"""
POST /api/query — main FAQ query endpoint.
"""

from __future__ import annotations

import logging
from fastapi import APIRouter, HTTPException

from api.models import QueryRequest, QueryResponse, SourceCitation

logger = logging.getLogger(__name__)
router = APIRouter()

# Pipeline is loaded once at startup (app lifespan), injected via app.state.
# Each request accesses it through the request object.
from fastapi import Request


@router.post(
    "/query",
    response_model=QueryResponse,
    summary="Ask a factual question about an HDFC Mutual Fund",
    description=(
        "Submits a natural-language query to the RAG pipeline. "
        "Returns a grounded answer with source citation, or a refusal "
        "if the query is advisory, out-of-scope, or contains personal data."
    ),
)
async def query_endpoint(body: QueryRequest, request: Request) -> QueryResponse:
    pipeline = request.app.state.pipeline

    try:
        result = pipeline.run(body.query)
    except Exception as exc:
        logger.exception("Pipeline error for query %r", body.query)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Coerce sources list to SourceCitation objects
    sources = [
        SourceCitation(
            fund_name=s.get("fund_name", ""),
            groww_url=s.get("groww_url", ""),
            ingestion_date=s.get("ingestion_date", ""),
        )
        for s in result.get("sources", [])
    ]

    return QueryResponse(
        response=result["response"],
        answered=result.get("answered", False),
        refused=result.get("refused", False),
        refused_reason=result.get("refused_reason"),
        intent=result.get("intent", "factual"),
        sources=sources,
        fund_id=result.get("fund_id"),
        section_type=result.get("section_type"),
        latency_s=result.get("latency_s", 0.0),
    )
