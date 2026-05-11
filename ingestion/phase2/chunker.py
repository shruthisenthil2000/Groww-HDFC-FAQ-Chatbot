"""
Phase 2.2 — Section-Aware Chunking

Converts the extracted section text from Phase 2.1 into chunk dicts
that carry both the text and the full metadata schema defined in
architecture.md Phase 2.2.4.

Strategy
--------
Each section type maps to 1+ chunks. Sections < MAX_SECTION_TOKENS are
kept whole. Sections that exceed the threshold are split by the recursive
character splitter (FALLBACK_CHUNK_SIZE / FALLBACK_OVERLAP).

See architecture.md Phase 2.2 for the full rationale and exclusion table.

Public API
----------
chunk_fund(fund, sections) -> list[dict]
    Convert one fund's section dict into chunk dicts.

chunk_all(funds, all_sections, processed_dir) -> list[dict]
    Chunk all 14 funds and write corpus/processed/chunks.jsonl.

Chunk schema (per architecture.md Phase 2.2.4)
----------------------------------------------
{
  "chunk_id":      "<fund_id>_<section_type>_<seq>",
  "fund_id":       str,
  "fund_name":     str,
  "groww_url":     str,
  "doc_type":      "groww_fund_page",
  "section_type":  "fund_overview" | "holdings" | "asset_allocation" | "sector_allocation"
                   | "exit_load_tax" | "investment_objective" | "about" | "fund_manager" | "fund_house",
  "ingestion_date": "YYYY-MM-DD",
  "text":          str,
  "tokens":        int
}
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

MAX_SECTION_TOKENS: int = 250    # sections within this limit are kept whole
FALLBACK_CHUNK_SIZE: int = 200   # token limit for the recursive splitter
FALLBACK_OVERLAP: int = 20       # token overlap between fallback sub-chunks

SECTION_TYPES: tuple[str, ...] = (
    "fund_overview",
    "riskometer",
    "benchmark",
    "holdings",
    "asset_allocation",
    "sector_allocation",
    "exit_load_rules",
    "taxation",
    "exit_load_tax",
    "investment_objective",
    "about",
    "fund_manager",
    "fund_house",
)

# Embeds `section: …` labels into chunk text for vector retrieval (re-run Phase 2 after extractor changes).
_SECTION_EMBED_PREFIX: dict[str, str] = {
    "fund_overview": (
        "section: fund_overview AUM NAV expense ratio minimum SIP lumpsum "
        "risk rating category lock-in SID KIM factsheet"
    ),
    "riskometer": "section: riskometer risk level risk category rating value research",
    "benchmark": "section: benchmark index underlying tracked total return NIFTY SENSEX",
    "holdings": "section: holdings top holdings portfolio stocks weights constituents",
    "asset_allocation": (
        "section: asset_allocation section: allocation asset allocation equity debt cash "
        "hybrid split portfolio allocation asset classes"
    ),
    "sector_allocation": (
        "section: sector_allocation section: allocation sector allocation sector industry "
        "exposure weights portfolio"
    ),
    "exit_load_rules": "section: exit_load exit load redemption fee window stamp duty header",
    "taxation": "section: taxation LTCG STCG tax implication redeem capital gains withholding",
    "exit_load_tax": (
        "section: exit_load section: taxation stamp duty LTCG STCG exit load combined block"
    ),
    "investment_objective": "section: objective section: benchmark investment objective index",
    "about": "section: about scheme summary launch AMC description",
    "fund_manager": "section: fund_manager manager CIO experience education tenure",
    "fund_house": "section: fund_house AMC registrar custodian contact website AUM",
}

CHUNKS_JSONL_FILENAME: str = "chunks.jsonl"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _approx_tokens(text: str) -> int:
    """
    Approximate token count using whitespace split (no tokenizer dependency).
    Accurate enough for the 80–250 token range we target; avoids importing
    tiktoken at chunk time.
    """
    return len(re.findall(r"\S+", text))


def _split_if_long(text: str) -> list[str]:
    """
    Split text into sub-chunks if it exceeds MAX_SECTION_TOKENS.

    Uses word-boundary splitting to approximate the recursive character splitter
    without requiring langchain/tiktoken at this stage.  Returns [text] unchanged
    if within the token threshold.
    """
    if _approx_tokens(text) <= MAX_SECTION_TOKENS:
        return [text]

    words = text.split()
    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = min(start + FALLBACK_CHUNK_SIZE, len(words))
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        start += FALLBACK_CHUNK_SIZE - FALLBACK_OVERLAP

    return chunks


# ── Public API ────────────────────────────────────────────────────────────────

def chunk_fund(fund: dict, sections: dict[str, str]) -> list[dict]:
    """
    Convert one fund's extracted sections into a list of chunk dicts.

    Args:
        fund:     Validated fund dict (must have fund_id, fund_name, groww_url).
        sections: dict[section_type → text] from Phase 2.1 extract().

    Returns:
        list of chunk dicts with full metadata. Empty sections produce no chunks.
    """
    fund_id   = fund["fund_id"]
    fund_name = fund["fund_name"]
    groww_url = fund["groww_url"]
    today     = str(date.today())

    chunks: list[dict] = []

    for section_type in SECTION_TYPES:
        text = sections.get(section_type, "").strip()
        if not text:
            logger.debug("  [%s] section '%s' is empty — skipped", fund_id, section_type)
            continue

        sub_texts = _split_if_long(text)
        for seq, sub_text in enumerate(sub_texts):
            sub_text = sub_text.strip()
            if not sub_text:
                continue
            chunk_id = f"{fund_id}_{section_type}_{seq}"
            label = _SECTION_EMBED_PREFIX.get(
                section_type,
                f"section: {section_type.replace('_', ' ')}",
            )
            embed_text = f"{label}\nfund={fund_name}\n\n{sub_text}"
            chunks.append({
                "chunk_id":       chunk_id,
                "fund_id":        fund_id,
                "fund_name":      fund_name,
                "groww_url":      groww_url,
                "doc_type":       "groww_fund_page",
                "section_type":   section_type,
                "ingestion_date": today,
                "text":           embed_text,
                "tokens":         _approx_tokens(embed_text),
            })

    logger.debug("  [%s] %d chunks produced", fund_id, len(chunks))
    return chunks


def chunk_all(
    funds: list[dict],
    all_sections: list[dict[str, str]],
    processed_dir: Path,
) -> list[dict]:
    """
    Chunk all funds and write corpus/processed/chunks.jsonl.

    Args:
        funds:         Validated fund list from Phase 1.1.
        all_sections:  list of section dicts from Phase 2.1 extract_all()
                       (same order as funds).
        processed_dir: Directory to write chunks.jsonl into.

    Returns:
        Complete list of chunk dicts (all funds combined).
    """
    if len(funds) != len(all_sections):
        raise ValueError(
            f"funds ({len(funds)}) and all_sections ({len(all_sections)}) "
            "must have the same length."
        )

    all_chunks: list[dict] = []
    for fund, sections in zip(funds, all_sections):
        fund_chunks = chunk_fund(fund, sections)
        all_chunks.extend(fund_chunks)

    processed_dir.mkdir(parents=True, exist_ok=True)
    out_path = processed_dir / CHUNKS_JSONL_FILENAME
    with out_path.open("w", encoding="utf-8") as fh:
        for chunk in all_chunks:
            fh.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    logger.info(
        "chunk_all complete — %d chunks from %d funds → %s",
        len(all_chunks), len(funds), out_path,
    )
    return all_chunks
