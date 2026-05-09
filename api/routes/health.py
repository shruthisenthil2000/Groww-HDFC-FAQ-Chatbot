"""
GET /api/health — liveness + configuration check.
"""

from __future__ import annotations

from fastapi import APIRouter
from api.models import HealthResponse

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
)
async def health() -> HealthResponse:
    import json
    from pathlib import Path
    from config import LLM_PROVIDER, LLM_MODEL, EMBEDDING_MODEL, GROQ_API_KEY

    # Count indexed chunks from sidecar (quick, no model load)
    try:
        meta_path = Path("data/index/vector.meta.json")
        corpus_chunks = len(json.loads(meta_path.read_text())) if meta_path.exists() else 0
    except Exception:
        corpus_chunks = 0

    groq_key = GROQ_API_KEY.strip()
    groq_key_set = bool(groq_key) and groq_key not in ("your_groq_key_here", "gsk_...")

    return HealthResponse(
        status="ok",
        llm_provider=LLM_PROVIDER,
        llm_model=LLM_MODEL,
        embedding_model=EMBEDDING_MODEL,
        corpus_chunks=corpus_chunks,
        groq_key_set=groq_key_set,
    )
