"""
Unit tests for orchestrator/classifier.py — Phase 4.1

Tests cover:
  - Advisory intent detection (investment advice queries)
  - Out-of-scope detection (non-mutual-fund topics)
  - Factual intent (fund-specific fact queries)
  - Ambiguous fallback (no rule matches, no LLM available)
  - Case insensitivity
  - Method field correctness
"""

import pytest
from unittest.mock import patch
from orchestrator.classifier import (
    classify,
    _rule_classify,
    INTENT_FACTUAL,
    INTENT_ADVISORY,
    INTENT_OUT_OF_SCOPE,
    INTENT_AMBIGUOUS,
)


# ── Advisory queries ────────────────────────────────────────────────────────────

ADVISORY_QUERIES = [
    "Should I invest in HDFC Mid Cap Fund?",
    "Which fund should I invest in?",
    "Recommend a good HDFC fund for me",
    "Which is the best HDFC fund?",
    "Is HDFC ELSS a good investment?",
    "Is it worth investing in HDFC Mid Cap?",
    "Which one should I choose, HDFC Mid Cap or HDFC Large Cap?",
    "Will HDFC Nifty 50 give good returns?",
    "What is the expected return from HDFC ELSS?",
    "Can I get guaranteed returns from this fund?",
    "Suggest a fund for tax saving",
    "HDFC mid cap vs HDFC large cap which is better?",
    "What are the future returns of HDFC Small Cap?",
]

@pytest.mark.parametrize("query", ADVISORY_QUERIES)
def test_advisory_queries(query):
    result = classify(query)
    assert result["intent"] == INTENT_ADVISORY, (
        f"Expected advisory for: {query!r}, got {result['intent']!r}"
    )
    assert result["method"] == "rule_based"
    assert result["confidence"] == 1.0


# ── Out-of-scope queries ────────────────────────────────────────────────────────

OUT_OF_SCOPE_QUERIES = [
    "What is the stock price of Infosys?",
    "Tell me the share price of Reliance",
    "What is Bitcoin trading at?",
    "I want to buy crypto",
    "How do I open a demat account?",
    "What is the Sensex level today?",
    "What is the weather in Mumbai?",
    "Who won the cricket match yesterday?",
    "What is the NSE Nifty level right now?",
    "Tell me about Infosys IPO",
]

@pytest.mark.parametrize("query", OUT_OF_SCOPE_QUERIES)
def test_out_of_scope_queries(query):
    result = classify(query)
    assert result["intent"] == INTENT_OUT_OF_SCOPE, (
        f"Expected out_of_scope for: {query!r}, got {result['intent']!r}"
    )
    assert result["method"] == "rule_based"


# ── Factual queries ─────────────────────────────────────────────────────────────

FACTUAL_QUERIES = [
    "What is the expense ratio of HDFC Mid Cap Fund?",
    "What is the exit load for HDFC ELSS?",
    "Who manages HDFC Small Cap Fund?",
    "What is the minimum SIP for HDFC Nifty 50?",
    "What is the AUM of HDFC Balanced Advantage Fund?",
    "What is the investment objective of HDFC Large Cap?",
    "What is the benchmark index for HDFC Flexi Cap?",
    "What is the LTCG tax on HDFC Mid Cap Fund?",
    "What is the lock-in period for HDFC ELSS?",
    "Tell me about HDFC Mutual Fund AMC",
    "What is the NAV of HDFC Mid Cap?",
    "What is the riskometer rating of HDFC Small Cap?",
    "What is the stamp duty on HDFC funds?",
    # HDFC Housing Opportunities Fund — must classify as factual (not out_of_scope)
    "housing",
    "HDFC Housing Opportunities Fund",
    "expense ratio of housing opportunities fund",
]

@pytest.mark.parametrize("query", FACTUAL_QUERIES)
def test_factual_queries(query):
    result = classify(query)
    assert result["intent"] == INTENT_FACTUAL, (
        f"Expected factual for: {query!r}, got {result['intent']!r}"
    )
    assert result["method"] == "rule_based"


# ── Ambiguous (fallback, no LLM) ────────────────────────────────────────────────

def test_ambiguous_no_llm():
    """Queries that match no rule should return ambiguous when LLM is unavailable."""
    with patch("orchestrator.classifier._llm_classify") as mock_llm:
        mock_llm.return_value = {
            "intent": INTENT_AMBIGUOUS,
            "confidence": 0.5,
            "reason": "no rule matched; LLM unavailable",
            "method": "fallback",
        }
        # This query deliberately has no advisory, out-of-scope, or factual keywords
        result = classify("Can you help me?")
        assert result["intent"] == INTENT_AMBIGUOUS


# ── Case insensitivity ──────────────────────────────────────────────────────────

def test_advisory_uppercase():
    result = classify("SHOULD I INVEST IN HDFC MID CAP?")
    assert result["intent"] == INTENT_ADVISORY

def test_factual_uppercase():
    result = classify("WHAT IS THE EXPENSE RATIO OF HDFC MID CAP?")
    assert result["intent"] == INTENT_FACTUAL

def test_out_of_scope_mixed_case():
    result = classify("What is the Stock Price of Reliance?")
    assert result["intent"] == INTENT_OUT_OF_SCOPE


# ── Priority: advisory beats factual ────────────────────────────────────────────

def test_advisory_beats_factual_signals():
    """'should I' + 'expense ratio' in same query → advisory wins."""
    result = classify("Should I invest based on the expense ratio?")
    assert result["intent"] == INTENT_ADVISORY


# ── Result structure ────────────────────────────────────────────────────────────

def test_result_has_required_fields():
    result = classify("What is the exit load for HDFC Mid Cap?")
    assert "intent" in result
    assert "confidence" in result
    assert "reason" in result
    assert "method" in result

def test_confidence_is_float():
    result = classify("What is the expense ratio?")
    assert isinstance(result["confidence"], float)

def test_rule_based_confidence_is_1():
    result = classify("Should I invest in this fund?")
    assert result["confidence"] == 1.0
    assert result["method"] == "rule_based"
