"""
Phase 4.1 — Intent Classifier (Hybrid)

Classifies an incoming user query into one of four intents:
    factual      — answerable from the 15-fund corpus (proceeds to RAG)
    advisory     — investment advice or recommendation request (refused)
    out_of_scope — topic not covered by the corpus (refused)
    ambiguous    — insufficient signal; Groq LLM used as tiebreaker

Two-stage hybrid approach
--------------------------
Stage A: Rule-based (always runs, zero latency)
  - Advisory and out-of-scope patterns are checked first (fast exit).
  - Known factual signals short-circuit to "factual" immediately.
  - If no rule fires → result is "ambiguous".

Stage B: Groq LLM tiebreaker (only for "ambiguous" queries)
  - A zero-shot classification prompt asks Groq to pick one of:
    factual | advisory | out_of_scope
  - Falls back to "ambiguous" if Groq is unavailable or returns noise.

Design notes
------------
- Rule-based stage catches >95% of real queries without any LLM call.
- LLM stage only activates for genuinely ambiguous edge cases.
- All rules are case-insensitive substring matches (simple and auditable).

Public API
----------
classify(query: str) -> ClassificationResult
    Returns a TypedDict with intent, confidence, reason, method.
"""

from __future__ import annotations

import logging
from typing import TypedDict

logger = logging.getLogger(__name__)

# ── Intent labels ───────────────────────────────────────────────────────────────
INTENT_FACTUAL      = "factual"
INTENT_ADVISORY     = "advisory"
INTENT_OUT_OF_SCOPE = "out_of_scope"
INTENT_AMBIGUOUS    = "ambiguous"


# ── Rule tables ─────────────────────────────────────────────────────────────────

# Advisory: user is asking for a recommendation or prediction.
# Any match → intent = advisory.  Checked BEFORE factual signals.
_ADVISORY_PATTERNS: list[str] = [
    "should i", "should i invest", "should i buy",
    "recommend", "recommendation", "suggest", "suggestion",
    "which is best", "which is the best", "which is better", "best fund", "better fund",
    "worth investing", "worth it", "is it good", "good investment",
    "which fund should", "which one should", "which fund to",
    "will it give", "will i get", "expected return", "future return",
    "how much will i get", "guaranteed return", "safe investment",
    "high return", "good return", "better returns", "compare funds",
    "vs ", " vs ", " versus ",
    "invest in which", "invest in what",
    "outperform", "beat the market", "alpha",
]

# Out-of-scope: clearly outside the mutual fund domain.
_OUT_OF_SCOPE_PATTERNS: list[str] = [
    "stock price", "share price", "share market",
    "crypto", "bitcoin", "ethereum", "nft",
    " ipo", "ipo ", "ipo.", "initial public offering",
    "demat account", "trading account", "brokerage",
    "sensex level", "nifty level", "market crash", "market rally",
    "company revenue", "company profit", "quarterly results",
    "fixed deposit", "fd rate", "ppf", "nps account",
    "weather", "cricket", "football", "election", "politics",
    "movie", "recipe", "travel", "hotel",
    "gold price today", "silver price today",
    "real estate", "property price",
    "insurance premium",
]

# Factual: strong signal that the query is about fund facts.
# Any match here → intent = factual (skip ambiguous/LLM stage).
_FACTUAL_PATTERNS: list[str] = [
    "expense ratio", " ter ", "ter ",  # TER (total expense ratio) — avoid matching "interesting"
    "exit load", "exit charge", "redemption charge",
    "minimum sip", "min sip", "minimum investment", "minimum lump",
    "fund manager", "who manages", "managed by", "portfolio manager",
    "investment objective", "benchmark index", "benchmark",
    "lock-in", "lock in", "elss lock",
    "nav", "net asset value",
    "aum", "fund size", "assets under",
    "riskometer", "risk level", "risk category",
    "stamp duty", "ltcg", "stcg", "capital gain",
    "tax implication", "tax on",
    "fund house", "amc", "hdfc mutual fund",
    "about hdfc", "tell me about hdfc",
    "sip amount", "sip date", "start sip",
    "direct plan", "growth plan",
    "hdfc mid cap", "hdfc small cap", "hdfc large cap",
    "hdfc elss", "hdfc nifty", "hdfc sensex",
    "hdfc focused", "hdfc defence", "hdfc pharma",
    "hdfc gold", "hdfc silver", "hdfc balanced",
    "hdfc short term", "hdfc flexi",
    # HDFC Housing Opportunities Fund (sectoral/thematic)
    "housing opportunities",
    "hdfc housing",
    "housing fund",
    "housing",
]


# ── TypedDict return type ───────────────────────────────────────────────────────

class ClassificationResult(TypedDict):
    intent:     str          # factual | advisory | out_of_scope | ambiguous
    confidence: float        # 1.0 for rule-based; 0.8 for LLM; 0.5 for fallback
    reason:     str          # human-readable explanation
    method:     str          # rule_based | groq_llm | fallback


# ── Stage A: Rule-based classifier ─────────────────────────────────────────────

def _rule_classify(query_lower: str) -> ClassificationResult | None:
    """
    Apply rule tables in priority order.

    Returns a ClassificationResult if a rule fires, else None.
    Priority: advisory > out_of_scope > factual
    """
    # Advisory check first (highest priority — we must not answer these)
    for pattern in _ADVISORY_PATTERNS:
        if pattern in query_lower:
            return ClassificationResult(
                intent=INTENT_ADVISORY,
                confidence=1.0,
                reason=f"matched advisory pattern: '{pattern}'",
                method="rule_based",
            )

    # Out-of-scope check
    for pattern in _OUT_OF_SCOPE_PATTERNS:
        if pattern in query_lower:
            return ClassificationResult(
                intent=INTENT_OUT_OF_SCOPE,
                confidence=1.0,
                reason=f"matched out-of-scope pattern: '{pattern}'",
                method="rule_based",
            )

    # Factual signal check
    for pattern in _FACTUAL_PATTERNS:
        if pattern in query_lower:
            return ClassificationResult(
                intent=INTENT_FACTUAL,
                confidence=1.0,
                reason=f"matched factual pattern: '{pattern}'",
                method="rule_based",
            )

    return None  # no rule fired → ambiguous


# ── Stage B: Groq LLM tiebreaker ───────────────────────────────────────────────

_LLM_SYSTEM = (
    "You are a query classifier for a mutual fund FAQ assistant. "
    "Classify the user query into exactly ONE of these categories:\n"
    "  factual      — asking for a factual detail about a mutual fund "
    "(expense ratio, exit load, fund manager, NAV, etc.)\n"
    "  advisory     — asking for investment advice, recommendation, or "
    "expected returns\n"
    "  out_of_scope — completely unrelated to mutual funds\n\n"
    "Reply with a single lowercase word: factual, advisory, or out_of_scope. "
    "No explanation. No punctuation."
)


def _llm_classify(query: str) -> ClassificationResult:
    """
    Use Groq to classify an ambiguous query.
    Falls back to 'ambiguous' if Groq is unavailable.
    """
    try:
        from config import GROQ_API_KEY, LLM_MODEL, require_groq_key
        from groq import Groq

        key = GROQ_API_KEY.strip()
        if not key or key in ("your_groq_key_here", "gsk_..."):
            raise RuntimeError("no key")

        client = Groq(api_key=require_groq_key())
        resp = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": _LLM_SYSTEM},
                {"role": "user",   "content": query},
            ],
            temperature=0.0,
            max_tokens=5,
        )
        label = resp.choices[0].message.content.strip().lower()

        intent_map = {
            "factual":      INTENT_FACTUAL,
            "advisory":     INTENT_ADVISORY,
            "out_of_scope": INTENT_OUT_OF_SCOPE,
        }
        intent = intent_map.get(label, INTENT_AMBIGUOUS)

        logger.info("LLM classifier: raw=%r → intent=%s", label, intent)
        return ClassificationResult(
            intent=intent,
            confidence=0.8,
            reason=f"Groq LLM returned: '{label}'",
            method="groq_llm",
        )

    except Exception as exc:
        logger.info("LLM classifier unavailable (%s) — keeping ambiguous", exc)
        return ClassificationResult(
            intent=INTENT_AMBIGUOUS,
            confidence=0.5,
            reason="no rule matched; LLM unavailable",
            method="fallback",
        )


# ── Public API ──────────────────────────────────────────────────────────────────

def classify(query: str) -> ClassificationResult:
    """
    Classify a user query into: factual | advisory | out_of_scope | ambiguous.

    Uses a two-stage hybrid approach:
      Stage A: Rule-based (instant, catches >95% of queries)
      Stage B: Groq LLM (only for queries that remain ambiguous after Stage A)

    Args:
        query: Raw user query string.

    Returns:
        ClassificationResult with intent, confidence, reason, method.
    """
    q = query.lower().strip()

    # Stage A
    result = _rule_classify(q)
    if result is not None:
        logger.debug(
            "Classified [rule_based]: intent=%s  reason=%s",
            result["intent"], result["reason"],
        )
        return result

    # Stage B — only reached for genuinely ambiguous queries
    logger.info("Query ambiguous after rule pass — trying Groq LLM classifier")
    result = _llm_classify(query)
    logger.debug(
        "Classified [%s]: intent=%s  reason=%s",
        result["method"], result["intent"], result["reason"],
    )
    return result
