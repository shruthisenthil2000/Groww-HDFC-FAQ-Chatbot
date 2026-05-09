"""
HDFC Mutual Fund FAQ Assistant — FastAPI Backend

Endpoints
---------
POST  /api/query    — Submit a question, get a grounded answer
GET   /api/health   — Liveness + configuration check
GET   /api/funds    — List all 15 fund schemes in the corpus
GET   /api/examples — Fetch example questions for the frontend UI

Usage
-----
  uvicorn api.main:app --reload --port 8000

Then open:
  http://localhost:8000/docs   (Swagger UI)
  http://localhost:8000/redoc  (ReDoc)

Environment
-----------
  All config comes from .env via config.py.
  Set GROQ_API_KEY in .env to enable LLM-backed answers.
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Add project root to path so imports work when run from any directory
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.routes import query as query_route
from api.routes import health as health_route
from api.routes import funds as funds_route

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)


# ── Lifespan: load the pipeline once at startup ─────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Load the pipeline (embedding model + FAISS index) once at startup.
    Storing on app.state makes it available to all request handlers
    without re-loading on every request.
    """
    logger.info("Loading RAG pipeline...")
    from orchestrator.pipeline import Pipeline
    app.state.pipeline = Pipeline()
    logger.info("Pipeline ready.")
    yield
    logger.info("Shutting down.")


# ── App ─────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="HDFC Mutual Fund FAQ Assistant",
    description=(
        "A facts-only RAG-based assistant that answers questions about "
        "15 HDFC Mutual Fund schemes using source-derived, snapshot-based data. "
        "No investment advice. All values are ingestion-time snapshots."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS — allow all origins for local dev; restrict in production ───────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # tighten to ["http://localhost:3000"] in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──────────────────────────────────────────────────────────────────────
app.include_router(query_route.router,  prefix="/api", tags=["Query"])
app.include_router(health_route.router, prefix="/api", tags=["Health"])
app.include_router(funds_route.router,  prefix="/api", tags=["Corpus"])


# ── Root redirect ─────────────────────────────────────────────────────────────────
@app.get("/", include_in_schema=False)
async def root():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/docs")
