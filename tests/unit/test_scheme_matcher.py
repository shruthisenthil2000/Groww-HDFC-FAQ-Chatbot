"""Tests for retrieval/scheme_matcher.py (fuzzy scheme resolution)."""

import importlib.util

import pytest

from retrieval.scheme_matcher import best_scheme_match, retrieval_query_variants

_HAS_RAPIDFUZZ = importlib.util.find_spec("rapidfuzz") is not None


@pytest.mark.skipif(not _HAS_RAPIDFUZZ, reason="rapidfuzz not installed")
def test_fuzzy_hdfc_silver():
    name, fund_id, score = best_scheme_match("hdfc silver expense ratio")
    assert name is not None
    assert "Silver" in name
    assert fund_id
    assert score >= 72


@pytest.mark.skipif(not _HAS_RAPIDFUZZ, reason="rapidfuzz not installed")
def test_fuzzy_elss_tax_saver():
    name, fund_id, score = best_scheme_match("ELSS tax saver minimum SIP")
    assert name is not None
    assert "ELSS" in name or "Tax Saver" in name
    assert score >= 72


def test_retrieval_variants_non_empty():
    v = retrieval_query_variants("exit load for HDFC Mid Cap Fund")
    assert len(v) >= 1
    assert any("exit" in x.lower() for x in v)
