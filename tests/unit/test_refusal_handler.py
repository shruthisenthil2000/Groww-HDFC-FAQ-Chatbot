"""
Legacy module `orchestrator/refusal_handler` was removed.
Facts-only refusal is implemented in `retrieval/query_guard.py`.
See `test_query_guard.py` for current tests.
"""

from retrieval.query_guard import is_advisory_or_opinion_query, refusal_response


def test_advisory_response_not_empty():
    result = refusal_response()
    assert len(result["answer"]) > 20


def test_advisory_contains_required_copy():
    result = refusal_response()
    assert "Facts-only assistant" in result["answer"]


def test_advisory_contains_amfi_link():
    result = refusal_response()
    assert "amfiindia.com" in result["answer"]


def test_sources_include_education_url():
    result = refusal_response()
    assert len(result["sources"]) == 1
    assert "amfiindia.com" in result["sources"][0]["groww_url"]


def test_factual_query_not_flagged():
    assert not is_advisory_or_opinion_query("What is the exit load for HDFC ELSS Tax Saver?")
