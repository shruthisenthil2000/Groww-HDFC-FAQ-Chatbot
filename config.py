from __future__ import annotations

import os
import sys
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# Project paths
# ─────────────────────────────────────────────────────────────

_PROJECT_ROOT: Path = Path(__file__).resolve().parent
_ENV_FILE: Path = _PROJECT_ROOT / ".env"


def _load_env() -> bool:
    try:
        from dotenv import load_dotenv
    except ImportError:
        print(
            "WARNING: python-dotenv not installed",
            file=sys.stderr,
        )
        return False

    if _ENV_FILE.exists():
        load_dotenv(_ENV_FILE, override=False)
        return True

    print(
        f"WARNING: .env not found at {_ENV_FILE}",
        file=sys.stderr,
    )
    return False


ENV_LOADED: bool = _load_env()

# ─────────────────────────────────────────────────────────────
# EMBEDDINGS
# ─────────────────────────────────────────────────────────────

EMBEDDING_MODEL: str = os.getenv(
    "EMBEDDING_MODEL",
    "all-MiniLM-L6-v2"
)

EMBEDDING_DIM: int = int(
    os.getenv("EMBEDDING_DIM", "384")
)

# ─────────────────────────────────────────────────────────────
# LLM CONFIG
# ─────────────────────────────────────────────────────────────

LLM_PROVIDER: str = os.getenv(
    "LLM_PROVIDER",
    "groq"
).lower()

LLM_MODEL: str = os.getenv(
    "LLM_MODEL",
    "llama-3.1-8b-instant"
)

LLM_TEMPERATURE: float = float(
    os.getenv("LLM_TEMPERATURE", "0.1")
)

# ─────────────────────────────────────────────────────────────
# GROQ
# ─────────────────────────────────────────────────────────────

GROQ_API_KEY: str = os.getenv(
    "GROQ_API_KEY",
    ""
)


def require_groq_key() -> str:
    key = GROQ_API_KEY.strip()

    if not key or key.startswith("gsk_..."):
        raise RuntimeError(
            "GROQ_API_KEY is missing"
        )

    return key


# ─────────────────────────────────────────────────────────────
# OPENAI (OPTIONAL)
# ─────────────────────────────────────────────────────────────

OPENAI_API_KEY: str = os.getenv(
    "OPENAI_API_KEY",
    ""
)


def require_openai_key() -> str:
    key = OPENAI_API_KEY.strip()

    if not key or key.startswith("sk-..."):
        raise RuntimeError(
            "OPENAI_API_KEY is missing"
        )

    return key


# ─────────────────────────────────────────────────────────────
# VECTOR STORE
# ─────────────────────────────────────────────────────────────

VECTOR_STORE: str = os.getenv(
    "VECTOR_STORE",
    "faiss"
)

FAISS_INDEX_PATH: str = os.getenv(
    "FAISS_INDEX_PATH",
    "data/index/vector.faiss"
)

FAISS_META_PATH: str = os.getenv(
    "FAISS_META_PATH",
    "data/index/vector.meta.json"
)

# ─────────────────────────────────────────────────────────────
# RETRIEVER
# ─────────────────────────────────────────────────────────────

RETRIEVER_TOP_K: int = int(
    os.getenv("RETRIEVER_TOP_K", "5")
)

# ─────────────────────────────────────────────────────────────
# RERANKER
# ─────────────────────────────────────────────────────────────

USE_RERANKER: bool = (
    os.getenv("USE_RERANKER", "false").lower() == "true"
)

RERANKER_MODEL: str = os.getenv(
    "RERANKER_MODEL",
    "cross-encoder/ms-marco-MiniLM-L-6-v2"
)

RERANKER_TOP_N: int = int(
    os.getenv("RERANKER_TOP_N", "3")
)

# ─────────────────────────────────────────────────────────────
# CORPUS
# ─────────────────────────────────────────────────────────────

SOURCES_FILE: str = os.getenv(
    "SOURCES_FILE",
    "corpus/sources.json"
)

RAW_HTML_DIR: str = os.getenv(
    "RAW_HTML_DIR",
    "corpus/raw"
)

PROCESSED_DIR: str = os.getenv(
    "PROCESSED_DIR",
    "corpus/processed"
)

CHUNKS_PARQUET: str = os.getenv(
    "CHUNKS_PARQUET",
    "corpus/processed/chunks.parquet"
)

CHROMA_DIR: str = os.getenv(
    "CHROMA_DIR",
    "corpus/index/chroma"
)

CHROMA_COLLECTION: str = os.getenv(
    "CHROMA_COLLECTION",
    "hdfc_mf_faq"
)

# ─────────────────────────────────────────────────────────────
# SCRAPER
# ─────────────────────────────────────────────────────────────

SCRAPER_DELAY_SECONDS: float = float(
    os.getenv("SCRAPER_DELAY_SECONDS", "2")
)

SCRAPER_TIMEOUT_SECONDS: int = int(
    os.getenv("SCRAPER_TIMEOUT_SECONDS", "30")
)

SCRAPER_USER_AGENT: str = os.getenv(
    "SCRAPER_USER_AGENT",
    "Mozilla/5.0 (compatible; HDFCFAQBot/1.0)"
)

# ─────────────────────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────────────────────

LOG_LEVEL: str = os.getenv(
    "LOG_LEVEL",
    "INFO"
)