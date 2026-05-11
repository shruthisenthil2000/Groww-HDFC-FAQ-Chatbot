"""Detect opinion / advisory / comparative queries and return a facts-only refusal."""

from __future__ import annotations

import re

# AMFI investor education hub (official).
AMFI_INVESTOR_EDUCATION_URL = (
    "https://www.amfiindia.com/investor-information/investor-education"
)

REFUSAL_MESSAGE = (
    "Facts-only assistant. I cannot provide investment advice or recommendations."
)


_ADVISORY_RE = re.compile(
    r"(?ix)"
    r"\b("
    r"should\s+i|shall\s+i|must\s+i|"
    r"can\s+i\s+invest|worth\s+investing|good\s+time\s+to\s+buy|"
    r"which\s+(fund|scheme)s?\s+(is\s+)?best|which\s+one\s+(is\s+)?better|"
    r"which\s+(fund|scheme)\s+(should|to)\s+(i\s+)?(pick|choose|buy)|"
    r"recommend(?:ation)?s?|investment\s+advice|financial\s+advice|"
    r"advise\s+me|give\s+me\s+advice|your\s+opinion|"
    r"beat\s+the\s+market|outperform|predict|prediction|forecast|"
    r"vs\.?\s|versus|compared?\s+to|better\s+than|"
    r"which\s+(is\s+)?better|sell\s+or\s+hold|buy\s+or\s+sell|"
    r"top\s+\d+\s+funds?|best\s+hdfc\s+fund"
    r")\b"
)


def is_advisory_or_opinion_query(query: str) -> bool:
    q = (query or "").strip()
    if len(q) < 6:
        return False
    return bool(_ADVISORY_RE.search(q))


def refusal_response() -> dict:
    """Structured response for ChatResponse (answer + sources)."""
    answer = f"{REFUSAL_MESSAGE}\n\nInvestor education: {AMFI_INVESTOR_EDUCATION_URL}"
    return {
        "answer": answer,
        "sources": [
            {
                "fund_name": "AMFI — investor education",
                "groww_url": AMFI_INVESTOR_EDUCATION_URL,
                "ingestion_date": "",
            }
        ],
    }
