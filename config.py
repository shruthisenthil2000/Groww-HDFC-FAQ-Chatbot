"""
config.py — Centralized environment configuration

Single source of truth for all environment-variable-backed settings.
Called once at import time: reads .env from the project root, then
exposes typed constants with safe defaults for every setting.

Usage (any module in the project):
    from config import EMBEDDING_MODEL, OPENAI_API_KEY

.env file:
    Expected at: <project_root>/.env
    Template at: <project_root>/.env.example
    If missing:  defaults are used and a WARNING is printed.

All values are read with os.getenv() so real environment variables
(e.g. set in CI/CD) always take precedence over .env contents.
"""

from __future__ import annotations

import os
import sys
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Locate project root and .env ──────────────────────────────────────────────

_PROJECT_ROOT: Path = Path(__file__).resolve().parent
_ENV_FILE: Path = _PROJECT_ROOT / ".env"
_ENV_EXAMPLE: Path = _PROJECT_ROOT / ".env.example"


def _load_env() -> bool:
    """
    Load .env into the process environment.

    Returns True if the file was found and loaded, False otherwise.
    Uses override=False so variables already set in the shell or CI
    environment are never overwritten by .env values.
    """
    try:
        from dotenv import load_dotenv
    except ImportError:
        print(
            "WARNING: python-dotenv is not installed. "
            "Run: pip install python-dotenv",
            file=sys.stderr,
        )
        return False

    if _ENV_FILE.exists():
        load_dotenv(_ENV_FILE, override=False)
        logger.debug("Loaded environment from %s", _ENV_FILE)
        return True

    # .env is missing — warn clearly and fall through to defaults
    print(
        f"\nWARNING: .env not found at {_ENV_FILE}. Using default config.\n"
        f"  → Copy .env.example to .env and fill in your values:\n"
        f"       cp {_ENV_EXAMPLE.name} .env\n",
        file=sys.stderr,
    )
    return False


# Load once at import time.
ENV_LOADED: bool = _load_env()


# ── Embedding ─────────────────────────────────────────────────────────────────

EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
EMBEDDING_DIM: int = int(os.getenv("EMBEDDING_DIM", "1536"))

# Not validated here — modules calling OpenAI must check this themselves.
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")


def require_openai_key() -> str:
    """
    Return OPENAI_API_KEY, raising RuntimeError if it is not set or is a placeholder.

    Call this inside functions that make actual OpenAI API calls, not at module
    import time, so that imports succeed even when the key is absent.
    """
    key = OPENAI_API_KEY.strip()
    if not key or key in ("your_key_here", "sk-..."):
        raise RuntimeError(
            "OPENAI_API_KEY is not configured. "
            "Set it in your .env file or as an environment variable."
        )
    return key


# ── LLM ───────────────────────────────────────────────────────────────────────

LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "groq")
LLM_MODEL: str = os.getenv("LLM_MODEL", "llama-3.1-8b-instant")
LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.1"))

# Groq — fast inference, OpenAI-compatible API
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")


def require_groq_key() -> str:
    """
    Return GROQ_API_KEY, raising RuntimeError if it is not set or is a placeholder.

    Call this inside functions that make actual Groq API calls, not at module
    import time, so that imports succeed even when the key is absent.
    """
    key = GROQ_API_KEY.strip()
    if not key or key in ("your_groq_key_here", "gsk_..."):
        raise RuntimeError(
            "GROQ_API_KEY is not configured. "
            "Get a free key at https://console.groq.com and set it in your .env file."
        )
    return key

# ── Vector Store ──────────────────────────────────────────────────────────────

VECTOR_STORE: str = os.getenv("VECTOR_STORE", "faiss")

# FAISS paths — index binary + metadata sidecar (FAISS stores no metadata natively)
FAISS_INDEX_PATH: str = os.getenv("FAISS_INDEX_PATH", "data/index/vector.faiss")
FAISS_META_PATH: str  = os.getenv("FAISS_META_PATH",  "data/index/vector.meta.json")

PINECONE_API_KEY: str = os.getenv("PINECONE_API_KEY", "")
PINECONE_ENVIRONMENT: str = os.getenv("PINECONE_ENVIRONMENT", "")
PINECONE_INDEX_NAME: str = os.getenv("PINECONE_INDEX_NAME", "hdfc-mf-faq")

# ── Retriever ─────────────────────────────────────────────────────────────────

RETRIEVER_TOP_K: int = int(os.getenv("RETRIEVER_TOP_K", "5"))

# ── Reranker ──────────────────────────────────────────────────────────────────

USE_RERANKER: bool = os.getenv("USE_RERANKER", "false").lower() == "true"
RERANKER_MODEL: str = os.getenv("RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
RERANKER_TOP_N: int = int(os.getenv("RERANKER_TOP_N", "3"))

# ── Corpus paths ──────────────────────────────────────────────────────────────

SOURCES_FILE: str = os.getenv("SOURCES_FILE", "corpus/sources.json")
RAW_HTML_DIR: str = os.getenv("RAW_HTML_DIR", "corpus/raw")
PROCESSED_DIR: str = os.getenv("PROCESSED_DIR", "corpus/processed")

# Phase 2 output paths
CHUNKS_PARQUET: str = os.getenv("CHUNKS_PARQUET", "corpus/processed/chunks.parquet")
CHROMA_DIR: str = os.getenv("CHROMA_DIR", "corpus/index/chroma")
CHROMA_COLLECTION: str = os.getenv("CHROMA_COLLECTION", "hdfc_mf_faq")

# ── Scraper ───────────────────────────────────────────────────────────────────

SCRAPER_DELAY_SECONDS: float = float(os.getenv("SCRAPER_DELAY_SECONDS", "2"))
SCRAPER_TIMEOUT_SECONDS: int = int(os.getenv("SCRAPER_TIMEOUT_SECONDS", "30"))
SCRAPER_USER_AGENT: str = os.getenv(
    "SCRAPER_USER_AGENT",
    "Mozilla/5.0 (compatible; HDFCFAQBot/1.0)",
)

# ── Logging ───────────────────────────────────────────────────────────────────

LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
