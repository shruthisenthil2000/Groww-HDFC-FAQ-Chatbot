"""
Phase 4.2 — Refusal Handler

Returns a polite, SEBI-compliant refusal message for queries classified
as advisory, out_of_scope, or ambiguous.

URL attachment policy
---------------------
No source URL is ever attached to a refusal response.
Attaching a fund URL to a refusal could be misread as endorsement.

Public API
----------
get_refusal(classification_result) -> RefusalResult
    Returns a TypedDict with response, intent, refused=True, sources=[].
"""

from __future__ import annotations

from typing import TypedDict


# ── Refusal templates ───────────────────────────────────────────────────────────

_ADVISORY_REFUSAL = (
    "I'm sorry, but I can only answer factual questions about mutual fund schemes. "
    "Questions about whether to invest, which fund is better, or expected returns "
    "fall outside the scope of this assistant.\n\n"
    "For investment guidance, please consult a SEBI-registered investment advisor. "
    "You can learn more about mutual funds at: https://www.amfiindia.com/investor-corner"
)

_OUT_OF_SCOPE_REFUSAL = (
    "This assistant only covers factual questions about the 15 HDFC Mutual Fund "
    "schemes in its corpus — such as expense ratios, exit loads, fund managers, "
    "and investment objectives. "
    "For other topics, please refer to official sources at https://www.hdfcfund.com"
)

_AMBIGUOUS_REFUSAL = (
    "I can answer factual questions about HDFC Mutual Fund schemes. "
    "Here are some examples:\n"
    "  \u2022 \"What is the expense ratio of HDFC Mid Cap Fund?\"\n"
    "  \u2022 \"What is the exit load for HDFC ELSS?\"\n"
    "  \u2022 \"Who manages the HDFC Balanced Advantage Fund?\"\n"
    "  \u2022 \"What is the minimum SIP for HDFC Nifty 50 Index Fund?\"\n\n"
    "Could you rephrase your question along those lines?"
)

# Mapping from intent to template
_TEMPLATES: dict[str, str] = {
    "advisory":     _ADVISORY_REFUSAL,
    "out_of_scope": _OUT_OF_SCOPE_REFUSAL,
    "ambiguous":    _AMBIGUOUS_REFUSAL,
}


# ── TypedDict return type ───────────────────────────────────────────────────────

class RefusalResult(TypedDict):
    response:       str
    intent:         str
    refused:        bool   # always True
    refused_reason: str    # mirrors intent
    sources:        list   # always empty — no URL on refusals


# ── Public API ──────────────────────────────────────────────────────────────────

def get_refusal(classification_result: dict) -> RefusalResult:
    """
    Build a refusal response for a non-factual query.

    Args:
        classification_result: Output from classifier.classify() —
                               a ClassificationResult dict.

    Returns:
        RefusalResult with the appropriate template text.
        sources is always [] — no URL attached to any refusal.
    """
    intent = classification_result.get("intent", "ambiguous")
    template = _TEMPLATES.get(intent, _AMBIGUOUS_REFUSAL)

    return RefusalResult(
        response=template,
        intent=intent,
        refused=True,
        refused_reason=intent,
        sources=[],
    )
