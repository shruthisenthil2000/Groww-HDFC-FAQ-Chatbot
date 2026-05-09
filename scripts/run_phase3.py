"""
scripts/run_phase3.py — Phase 3 demo runner

Runs the full RAG pipeline against a set of test queries that cover:
  1. Answered queries (corpus has the information)
  2. No-answer queries (corpus does not have the information)
  3. PII queries (query contains personal data — refused, no URL)
  4. Out-of-scope queries (unrelated topic)

Prerequisites:
  - Phase 1 + 2 must have been run: corpus/raw/*.html, data/index/vector.faiss
  - .env must exist with EMBEDDING_MODEL set (OpenAI key optional)

Usage:
  python scripts/run_phase3.py
  python scripts/run_phase3.py "What is the expense ratio of HDFC Mid Cap Fund?"
"""

from __future__ import annotations

import sys
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.WARNING)  # suppress debug noise in demo

from orchestrator.pipeline import Pipeline

# ── Test queries ────────────────────────────────────────────────────────────────

TEST_QUERIES = [
    # (label, query)
    ("Answered — specific fund + section",
     "What is the exit load for HDFC Mid Cap Fund?"),

    ("Answered — expense ratio",
     "What is the expense ratio of HDFC ELSS Tax Saver Fund?"),

    ("Answered — fund manager",
     "Who manages the HDFC Small Cap Fund?"),

    ("Answered — investment objective",
     "What is the investment objective of HDFC Nifty 50 Index Fund?"),

    ("Answered — AMC info",
     "Tell me about HDFC Mutual Fund house"),

    ("No answer — out of corpus",
     "What is the current NAV of HDFC Mid Cap Fund today?"),

    ("No answer — completely unrelated",
     "What is the stock price of Reliance Industries?"),

    ("PII — Aadhaar number",
     "My Aadhaar is 1234 5678 9012, which HDFC fund has the lowest exit load?"),

    ("PII — phone number",
     "Call me at 9876543210 about the ELSS fund details"),

    ("PII — email address",
     "Send details to user@example.com about HDFC Large Cap Fund"),

    ("PII — PAN card",
     "My PAN is ABCDE1234F, can I invest in HDFC ELSS?"),
]


# ── Formatting ──────────────────────────────────────────────────────────────────

def _print_separator(char: str = "─", width: int = 70) -> None:
    print(char * width)


def _print_result(label: str, query: str, result: dict) -> None:
    _print_separator()
    print(f"  Category : {label}")
    print(f"  Query    : {query}")
    print()

    if result["refused"]:
        print(f"  [REFUSED — {result['refused_reason'].upper()}]")
        print(f"  Response : {result['response']}")
        print(f"  Sources  : (none — URL suppressed per policy)")
    elif not result["answered"]:
        print(f"  [NO ANSWER]")
        print(f"  Response : {result['response']}")
        print(f"  Sources  : (none — no URL when answer not found)")
    else:
        print(f"  [ANSWERED]")
        print(f"  Response : {result['response']}")
        if result["sources"]:
            print(f"  Sources  :")
            for s in result["sources"]:
                print(f"    - {s['fund_name']}")
                print(f"      {s['groww_url']}")
                print(f"      Data as of: {s.get('ingestion_date', 'unknown')}")
        else:
            print(f"  Sources  : (included in response text)")

    routing = []
    if result.get("fund_id"):
        routing.append(f"fund={result['fund_id']}")
    if result.get("section_type"):
        routing.append(f"section={result['section_type']}")
    if routing:
        print(f"  Router   : {', '.join(routing)}")

    print(f"  Latency  : {result['latency_s']}s")
    print()


# ── Main ─────────────────────────────────────────────────────────────────────────

def main() -> None:
    print()
    _print_separator("═")
    print("  HDFC Mutual Fund FAQ Assistant — Phase 3 Demo")
    _print_separator("═")
    print()

    pipeline = Pipeline()

    # Single query from CLI args
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        result = pipeline.run(query)
        _print_result("CLI query", query, result)
        return

    # Run all test queries
    counts = {"answered": 0, "no_answer": 0, "pii": 0, "other_refused": 0}

    for label, query in TEST_QUERIES:
        result = pipeline.run(query)
        _print_result(label, query, result)

        if result["refused"]:
            if result["refused_reason"] == "pii":
                counts["pii"] += 1
            else:
                counts["other_refused"] += 1
        elif result["answered"]:
            counts["answered"] += 1
        else:
            counts["no_answer"] += 1

    _print_separator("═")
    print(f"  Summary: {len(TEST_QUERIES)} queries")
    print(f"    Answered    : {counts['answered']}")
    print(f"    No answer   : {counts['no_answer']}  (no URL attached)")
    print(f"    PII refused : {counts['pii']}  (no URL attached)")
    print(f"    Other refused: {counts['other_refused']}")
    _print_separator("═")
    print()


if __name__ == "__main__":
    main()
