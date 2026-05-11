"""Tests for retrieval/query_guard.py (facts-only refusal)."""

from retrieval.query_guard import (
    AMFI_INVESTOR_EDUCATION_URL,
    REFUSAL_MESSAGE,
    is_advisory_or_opinion_query,
    refusal_response,
)


def test_advisory_should_i():
    assert is_advisory_or_opinion_query("Should I invest in HDFC Mid Cap Fund?")


def test_advisory_which_best():
    assert is_advisory_or_opinion_query("Which fund is best for 2026?")


def test_advisory_compare():
    assert is_advisory_or_opinion_query("HDFC Flexi Cap vs HDFC Mid Cap — which is better?")


def test_factual_not_advisory():
    assert not is_advisory_or_opinion_query("What is the expense ratio of HDFC Mid Cap Fund?")


def test_refusal_payload():
    r = refusal_response()
    assert REFUSAL_MESSAGE in r["answer"]
    assert AMFI_INVESTOR_EDUCATION_URL in r["answer"]
    assert len(r["sources"]) == 1
    assert r["sources"][0]["groww_url"] == AMFI_INVESTOR_EDUCATION_URL
    assert "amfiindia.com" in r["sources"][0]["groww_url"]
