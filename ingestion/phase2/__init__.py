"""
ingestion.phase2 — Phase 2: Data Processing & Indexing

Subphase modules
----------------
extractor   (2.1)  Section-aware text extraction from raw HTML   [implemented]
chunker     (2.2)  Metadata-rich chunk dicts from section text   [implemented]
embedder    (2.3)  Batch embedding (local sentence-transformers)  [implemented]
indexer     (2.4)  Parquet persistence + ChromaDB vector index   [implemented]

Phase 2 begins only after Phase 1.4 (integrity check) passes.

  Input:  corpus/raw/<fund_id>.html         (14 files from Phase 1.3)
  Output: corpus/processed/chunks.parquet   (embedded chunks table)
          corpus/index/chroma/              (ChromaDB vector store)

Quick imports
-------------
    from ingestion.phase2.extractor import extract, extract_all
    from ingestion.phase2.chunker   import chunk_fund, chunk_all
    from ingestion.phase2.embedder  import embed_chunks
    from ingestion.phase2.indexer   import save_parquet, build_index, search
"""

from ingestion.phase2.extractor import extract, extract_all, ExtractionError
from ingestion.phase2.chunker   import chunk_fund, chunk_all
from ingestion.phase2.embedder  import embed_chunks
from ingestion.phase2.indexer   import (
    save_parquet,
    build_index,
    search,
    build_faiss_index,
    search_faiss,
)

__all__ = [
    # 2.1
    "extract",
    "extract_all",
    "ExtractionError",
    # 2.2
    "chunk_fund",
    "chunk_all",
    # 2.3
    "embed_chunks",
    # 2.4 — ChromaDB
    "save_parquet",
    "build_index",
    "search",
    # 2.4 — FAISS
    "build_faiss_index",
    "search_faiss",
]
