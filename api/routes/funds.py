"""
GET /api/funds  — list all 15 funds in the corpus.
GET /api/examples — return example questions for the frontend.
"""

from __future__ import annotations

import json
from pathlib import Path
from functools import lru_cache

from fastapi import APIRouter, HTTPException
from api.models import FundListResponse, FundInfo, ExamplesResponse

router = APIRouter()

_SOURCES_PATH = Path("corpus/sources.json")

# ── Example questions ────────────────────────────────────────────────────────────

_EXAMPLES: list[str] = [
    "What is the expense ratio of HDFC Mid Cap Fund?",
    "What is the exit load for HDFC ELSS Tax Saver Fund?",
    "Who manages the HDFC Small Cap Fund?",
    "What is the investment objective of HDFC Nifty 50 Index Fund?",
    "What is the minimum SIP amount for HDFC Balanced Advantage Fund?",
    "What is the LTCG tax treatment for HDFC Large Cap Fund?",
    "Tell me about HDFC Gold ETF Fund of Fund",
    "What is the benchmark index for HDFC Flexi Cap Fund?",
    "What is the AUM of HDFC Balanced Advantage Fund?",
    "What is the lock-in period for HDFC ELSS?",
]


@lru_cache(maxsize=1)
def _load_funds() -> list[FundInfo]:
    if not _SOURCES_PATH.exists():
        return []
    data = json.loads(_SOURCES_PATH.read_text(encoding="utf-8"))
    return [
        FundInfo(
            fund_id=f.get("fund_id", ""),
            fund_name=f.get("fund_name", ""),
            category=f.get("category", ""),
            groww_url=f.get("groww_url", ""),
        )
        for f in data.get("funds", [])
    ]


@router.get(
    "/funds",
    response_model=FundListResponse,
    summary="List all 15 HDFC fund schemes in the corpus",
)
async def list_funds() -> FundListResponse:
    funds = _load_funds()
    if not funds:
        raise HTTPException(
            status_code=503,
            detail="corpus/sources.json not found — run Phase 0 setup first.",
        )
    return FundListResponse(total=len(funds), funds=funds)


@router.get(
    "/examples",
    response_model=ExamplesResponse,
    summary="Get example factual questions for the UI",
)
async def get_examples() -> ExamplesResponse:
    return ExamplesResponse(examples=_EXAMPLES)
