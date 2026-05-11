from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter

from api.models import HealthResponse
from config import EMBEDDING_MODEL, FAISS_META_PATH, GROQ_API_KEY, LLM_MODEL

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    try:
        path = Path(FAISS_META_PATH)
        corpus_chunks = len(json.loads(path.read_text(encoding="utf-8"))) if path.exists() else 0
    except Exception:
        corpus_chunks = 0
    return HealthResponse(
        status="ok",
        llm_model=LLM_MODEL,
        embedding_model=EMBEDDING_MODEL,
        corpus_chunks=corpus_chunks,
        groq_key_set=bool(GROQ_API_KEY.strip()),
    )
