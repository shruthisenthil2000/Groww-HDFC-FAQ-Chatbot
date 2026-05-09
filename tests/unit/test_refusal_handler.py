"""
Unit tests for orchestrator/refusal_handler.py — Phase 4.2
"""

import pytest
from orchestrator.refusal_handler import get_refusal, RefusalResult


def _make_clf(intent: str) -> dict:
    return {"intent": intent, "confidence": 1.0, "reason": "test", "method": "rule_based"}


class TestGetRefusal:

    def test_advisory_response_not_empty(self):
        result = get_refusal(_make_clf("advisory"))
        assert len(result["response"]) > 20

    def test_advisory_mentions_sebi(self):
        result = get_refusal(_make_clf("advisory"))
        assert "SEBI" in result["response"] or "sebi" in result["response"].lower()

    def test_advisory_contains_amfi_link(self):
        result = get_refusal(_make_clf("advisory"))
        assert "amfiindia.com" in result["response"]

    def test_out_of_scope_response_not_empty(self):
        result = get_refusal(_make_clf("out_of_scope"))
        assert len(result["response"]) > 20

    def test_out_of_scope_mentions_hdfc(self):
        result = get_refusal(_make_clf("out_of_scope"))
        assert "HDFC" in result["response"]

    def test_ambiguous_contains_examples(self):
        result = get_refusal(_make_clf("ambiguous"))
        assert "expense ratio" in result["response"].lower() or "exit load" in result["response"].lower()

    def test_sources_always_empty(self):
        for intent in ("advisory", "out_of_scope", "ambiguous"):
            result = get_refusal(_make_clf(intent))
            assert result["sources"] == [], f"sources must be empty for {intent}"

    def test_refused_always_true(self):
        for intent in ("advisory", "out_of_scope", "ambiguous"):
            result = get_refusal(_make_clf(intent))
            assert result["refused"] is True

    def test_refused_reason_matches_intent(self):
        for intent in ("advisory", "out_of_scope", "ambiguous"):
            result = get_refusal(_make_clf(intent))
            assert result["refused_reason"] == intent

    def test_intent_field_preserved(self):
        result = get_refusal(_make_clf("advisory"))
        assert result["intent"] == "advisory"

    def test_unknown_intent_falls_back_to_ambiguous(self):
        result = get_refusal(_make_clf("unknown_intent"))
        assert len(result["response"]) > 0
        assert result["refused"] is True

    def test_result_is_typed_dict(self):
        result = get_refusal(_make_clf("advisory"))
        assert isinstance(result, dict)
        assert "response" in result
        assert "sources" in result
        assert "refused" in result
