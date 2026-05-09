"""
Query Router — Phase 3.2.1

Extracts two anchor signals from the raw query string before the dense search:

  1. fund_id       — which of the 15 HDFC funds the user is asking about
  2. section_type  — which chunk category best matches the query intent

Both signals are optional (None = no match found). When both are present the
dense search is pre-filtered by section_type (cuts corpus to ~15 chunks) and
the results are post-filtered by fund_id (typically returns exactly 1 chunk),
producing near-perfect retrieval precision for the FAQ use case.

Why not BM25 or embeddings for routing?
----------------------------------------
Cross-fund cosine similarity is 0.93–0.99 for the high-confusion sections
(exit_load_tax, fund_house). Keyword matching is faster, interpretable, and
sufficient because:
  - Fund names are specific and rarely ambiguous in a mutual-fund corpus.
  - Section intent keywords ("expense ratio", "exit load", "fund manager")
    are well-defined domain terms that map cleanly to section types.

Public API
----------
route(query: str) -> tuple[str | None, str | None]
    Returns (fund_id, section_type). Either or both may be None.
"""

from __future__ import annotations

import re

# ── Fund alias table ────────────────────────────────────────────────────────────
# Each entry: (fund_id, [pattern, ...])
# Patterns are matched case-insensitively against the query.
# Longer / more specific patterns are placed first within each group so that
# "nifty 50" matches before a hypothetical shorter "nifty" wildcard.

_FUND_ALIASES: list[tuple[str, list[str]]] = [
    ("hdfc_nifty50_index",       ["nifty 50", "nifty50", "nifty-50"]),
    ("hdfc_bse_sensex_index",    ["bse sensex", "sensex index", "sensex"]),
    ("hdfc_elss",                ["elss", "tax saver", "tax-saver", "tax saving"]),
    ("hdfc_mid_cap",             ["mid cap", "mid-cap", "midcap"]),
    ("hdfc_small_cap",           ["small cap", "small-cap", "smallcap"]),
    ("hdfc_large_cap",           ["large cap", "large-cap", "largecap"]),
    ("hdfc_flexi_cap",           ["flexi cap", "flexi-cap", "flexicap", "equity fund"]),
    ("hdfc_focused",             ["focused fund", "focus fund", "hdfc focused"]),
    (
        "hdfc_housing_opportunities",
        [
            "hdfc housing opportunities fund direct growth",
            "hdfc housing opportunities fund",
            "housing opportunities fund direct growth",
            "housing opportunities fund",
            "housing opportunities",
            "hdfc housing opportunities",
            "hdfc housing",
            "housing fund",
            "housing",
        ],
    ),
    ("hdfc_defence",             ["defence fund", "defense fund", "hdfc defence"]),
    ("hdfc_pharma_healthcare",   ["pharma", "healthcare", "health care", "pharma and healthcare"]),
    ("hdfc_gold_etf_fof",        ["gold etf", "gold fund", "gold fof"]),
    ("hdfc_silver_etf_fof",      ["silver etf", "silver fund", "silver fof"]),
    ("hdfc_balanced_advantage",  ["balanced advantage", "balanced-advantage", "dynamic asset"]),
    ("hdfc_short_term_debt",     ["short term", "short-term", "debt fund", "short term debt"]),
]

# ── Section routing table ───────────────────────────────────────────────────────
# Each entry: ([pattern, ...], section_type)
# Ordered from most specific to least specific so the first match wins.

_SECTION_ROUTES: list[tuple[list[str], str]] = [
    (
        ["exit load", "exit-load", "redemption charge", "early withdrawal"],
        "exit_load_tax",
    ),
    (
        ["ltcg", "stcg", "capital gain", "capital-gain", "stamp duty", "tax implication",
         "tax on", "tax treatment", "indexation"],
        "exit_load_tax",
    ),
    (
        ["expense ratio", "ter", "total expense", "management fee", "annual fee",
         "minimum sip", "min sip", "min investment", "minimum investment",
         "minimum lump", "nav", "aum", "fund size", "asset under", "assets under",
         "riskometer", "risk level", "risk category"],
        "fund_overview",
    ),
    (
        ["investment objective", "what does it invest", "where does it invest",
         "investment goal", "objective of", "benchmark index", "benchmark",
         "index it tracks", "tracks index", "what index", "which index", "fund track"],
        "investment_objective",
    ),
    (
        ["fund manager", "who manages", "managed by", "portfolio manager",
         "fund management", "manager name", "manager experience"],
        "fund_manager",
    ),
    (
        ["fund house", "amc", "asset management company", "hdfc mutual fund details",
         "hdfc amc", "amc details", "fund company"],
        "fund_house",
    ),
    (
        ["tell me about", "describe", "background", "summary of",
         "what is hdfc", "overview of"],
        "about",
    ),
]


# ── Internal helpers ────────────────────────────────────────────────────────────

def _normalise(text: str) -> str:
    """Lowercase, collapse whitespace."""
    return re.sub(r"\s+", " ", text.lower().strip())


def _detect_fund(query_norm: str) -> str | None:
    """
    Return the fund_id of the first alias that matches the normalised query.
    Returns None if no alias matches.
    """
    for fund_id, patterns in _FUND_ALIASES:
        for pattern in patterns:
            if pattern in query_norm:
                return fund_id
    return None


def _detect_section(query_norm: str) -> str | None:
    """
    Return the section_type of the first routing rule that matches.
    Returns None if no rule matches.
    """
    for patterns, section_type in _SECTION_ROUTES:
        for pattern in patterns:
            if pattern in query_norm:
                return section_type
    return None


# ── Public API ──────────────────────────────────────────────────────────────────

def route(query: str) -> tuple[str | None, str | None]:
    """
    Extract (fund_id, section_type) anchor signals from a natural-language query.

    Args:
        query: Raw user query string.

    Returns:
        (fund_id, section_type) — either or both may be None.
        - fund_id:      Matches one of the 15 fund IDs in sources.json,
                        or None if no fund name was detected.
        - section_type: One of the 6 section types in the corpus,
                        or None if no intent signal was detected.

    Examples:
        >>> route("What is the exit load for HDFC Mid Cap?")
        ('hdfc_mid_cap', 'exit_load_tax')

        >>> route("Who manages the ELSS fund?")
        ('hdfc_elss', 'fund_manager')

        >>> route("What is the expense ratio?")
        (None, 'fund_overview')

        >>> route("What is a mutual fund?")
        (None, None)
    """
    q = _normalise(query)
    return _detect_fund(q), _detect_section(q)
