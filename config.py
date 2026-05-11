from __future__ import annotations

import os
import sys
from pathlib import Path


_PROJECT_ROOT = Path(__file__).resolve().parent
_ENV_FILE = _PROJECT_ROOT / ".env"


def _load_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    if _ENV_FILE.exists():
        load_dotenv(_ENV_FILE, override=False)


_load_env()

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "384"))

LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.1-8b-instant")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

FAISS_INDEX_PATH = os.getenv("FAISS_INDEX_PATH", "data/index/vector.faiss")
FAISS_META_PATH = os.getenv("FAISS_META_PATH", "data/index/vector.meta.json")
RETRIEVER_TOP_K = int(os.getenv("RETRIEVER_TOP_K", "20"))
CHUNKS_PARQUET = os.getenv("CHUNKS_PARQUET", "corpus/processed/chunks.parquet")
CHROMA_DIR = os.getenv("CHROMA_DIR", "corpus/index/chroma")
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "hdfc_mf_faq")


def require_groq_key() -> str:
    key = GROQ_API_KEY.strip()
    if not key:
        raise RuntimeError("GROQ_API_KEY is missing")
    return key
