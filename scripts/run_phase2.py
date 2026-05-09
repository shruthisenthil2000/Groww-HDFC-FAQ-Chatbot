"""
Phase 2 Pipeline Runner — Chains subphases 2.1 → 2.4

Usage
-----
    python3 scripts/run_phase2.py

Prerequisites
-------------
    Phase 1 must be complete: corpus/raw/<fund_id>.html files must exist.
    Run scripts/run_phase1.py first if they are missing.

Runs each Phase 2 subphase in sequence:

  2.1  Extract clean text sections from 14 raw HTML files   (extractor.py)
  2.2  Chunk sections into metadata-rich chunk dicts         (chunker.py)
  2.3  Batch-embed all chunks with the configured model      (embedder.py)
  2.4a Save chunks + embeddings to Parquet                   (indexer.save_parquet)
  2.4b Build and persist ChromaDB vector index               (indexer.build_index)

Outputs
-------
  corpus/processed/chunks.jsonl       Raw chunk dicts (pre-embedding)
  corpus/processed/chunks.parquet     Full chunk table including embedding vectors
  corpus/index/chroma/                Persisted ChromaDB vector index
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config
from config import (
    RAW_HTML_DIR, PROCESSED_DIR, CHUNKS_PARQUET,
    CHROMA_DIR, CHROMA_COLLECTION, EMBEDDING_MODEL,
)
from ingestion.phase1.manifest import load_and_validate
from ingestion.phase2.extractor import extract_all
from ingestion.phase2.chunker  import chunk_all
from ingestion.phase2.embedder import embed_chunks
from ingestion.phase2.indexer  import save_parquet, build_index

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

RAW_DIR       = PROJECT_ROOT / RAW_HTML_DIR
PROCESSED     = PROJECT_ROOT / PROCESSED_DIR
PARQUET_PATH  = PROJECT_ROOT / CHUNKS_PARQUET
CHROMA_PATH   = PROJECT_ROOT / CHROMA_DIR


def _sep(title: str) -> None:
    logger.info("─" * 60)
    logger.info("  %s", title)
    logger.info("─" * 60)


def main() -> int:
    # ── Phase 1.1: load fund manifest ─────────────────────────────────────────
    _sep("Loading fund manifest (Phase 1.1)")
    funds = load_and_validate()
    logger.info("  ✔  %d funds loaded", len(funds))

    # Guard: HTML files must exist
    missing_html = [f["fund_id"] for f in funds
                    if not (RAW_DIR / f"{f['fund_id']}.html").exists()]
    if missing_html:
        logger.error(
            "Missing HTML for %d fund(s): %s\n"
            "Run scripts/run_phase1.py first.",
            len(missing_html), missing_html,
        )
        return 1

    # ── Phase 2.1: extract sections from HTML ─────────────────────────────────
    _sep("Phase 2.1 — Text Extraction")
    all_sections = extract_all(funds, RAW_DIR)
    logger.info("  ✔  %d funds extracted", len(all_sections))

    # ── Phase 2.2: chunk sections ─────────────────────────────────────────────
    _sep("Phase 2.2 — Chunking")
    chunks = chunk_all(funds, all_sections, PROCESSED)
    logger.info("  ✔  %d chunks produced", len(chunks))

    section_counts: dict[str, int] = {}
    for c in chunks:
        section_counts[c["section_type"]] = section_counts.get(c["section_type"], 0) + 1
    for stype, cnt in sorted(section_counts.items()):
        logger.info("    %s: %d", stype, cnt)

    # ── Phase 2.3: embed chunks ───────────────────────────────────────────────
    _sep(f"Phase 2.3 — Embedding  ({EMBEDDING_MODEL})")
    chunks = embed_chunks(chunks)
    dim = len(chunks[0]["embedding"])
    logger.info("  ✔  %d embeddings  dim=%d", len(chunks), dim)

    # ── Phase 2.4a: save parquet ──────────────────────────────────────────────
    _sep("Phase 2.4a — Save Parquet")
    parquet_path = save_parquet(chunks, PARQUET_PATH)
    logger.info("  ✔  Parquet saved → %s", parquet_path)

    # ── Phase 2.4b: build ChromaDB index ──────────────────────────────────────
    _sep("Phase 2.4b — Build ChromaDB Index")
    collection = build_index(chunks, CHROMA_PATH, CHROMA_COLLECTION)
    logger.info("  ✔  ChromaDB → %s  collection='%s'", CHROMA_PATH, CHROMA_COLLECTION)

    # ── Summary ───────────────────────────────────────────────────────────────
    _sep("Phase 2 COMPLETE")
    logger.info(
        "  Deliverables:\n"
        "    %s  (%d chunks)\n"
        "    %s  (ChromaDB, %d vectors)",
        parquet_path, len(chunks),
        CHROMA_PATH, collection.count(),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
