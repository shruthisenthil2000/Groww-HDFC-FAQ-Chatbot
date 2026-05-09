"""
RAG Post-Processor — Phase 3.6

Applies the URL-attachment policy and privacy rules defined in Phase 3.6
of architecture.md before the response is surfaced to the user.

Rules (in order of precedence):
1. PII check on the QUERY — if personal information is detected, refuse
   immediately and attach NO source URL.
2. No-answer check — if GeneratorResult.answered is False, return the
   sentinel phrase and attach NO source URL.
3. Format answered response — enforce 3-sentence limit, ensure source
   citation is present, sanitize any PII that leaked into the LLM output.

URL attachment policy
---------------------
| Condition                 | URL attached? |
|---------------------------|---------------|
| Answer found in corpus    | Yes           |
| Answer NOT found          | No            |
| PII in query              | No            |
| Advisory / other refusal  | No            |

Public API
----------
postprocess(query, generator_result) -> PostProcessResult
    PostProcessResult is a TypedDict:
        response:       str   — final text to display to the user
        refused:        bool
        refused_reason: str | None  — "pii" | "no_answer" | None
        sources:        list  — [{fund_name, groww_url, ingestion_date}]
                                (empty whenever refused=True)
        answered:       bool  — mirrors GeneratorResult.answered

check_pii(text) -> bool
    Returns True if the text contains patterns matching personal information.
"""

from __future__ import annotations

import re
import logging
from typing import TypedDict

logger = logging.getLogger(__name__)

# ── Static response strings ─────────────────────────────────────────────────────

_PII_REFUSAL = (
    "I'm sorry, but I cannot process queries containing personal information. "
    "Please remove any personal details (such as phone numbers, email addresses, "
    "Aadhaar, or PAN numbers) and try again."
)

_NO_ANSWER_RESPONSE = "I don't have this information in my current sources."

# ── PII patterns ────────────────────────────────────────────────────────────────
# Ordered from most specific to least specific.
# All patterns are case-insensitive; applied to the normalised query.

_PII_PATTERNS: list[tuple[str, re.Pattern]] = [
    # Aadhaar: 12 digits, optionally grouped as XXXX XXXX XXXX or XXXX-XXXX-XXXX
    ("aadhaar",  re.compile(r"\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b")),
    # PAN card: 5 uppercase letters, 4 digits, 1 uppercase letter (e.g. ABCDE1234F)
    ("pan",      re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")),
    # Indian mobile: 10 digits starting with 6–9, optionally preceded by +91 or 0
    ("phone",    re.compile(r"(?:(?:\+91|0)?[\s\-]?)?[6-9]\d{9}\b")),
    # Email addresses
    ("email",    re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")),
    # Generic long digit strings that could be account / customer IDs (10+ digits)
    ("id_number", re.compile(r"\b\d{10,}\b")),
]


# ── TypedDict return type ───────────────────────────────────────────────────────

class PostProcessResult(TypedDict):
    response: str
    refused: bool
    refused_reason: str | None
    sources: list[dict]
    answered: bool


# ── PII detection ───────────────────────────────────────────────────────────────

def check_pii(text: str) -> bool:
    """
    Return True if the text contains any PII pattern.

    Checks for: Aadhaar (12-digit), PAN (ABCDE1234F), Indian mobile phone,
    email address, and generic 10+ digit ID numbers.
    """
    for label, pattern in _PII_PATTERNS:
        if pattern.search(text):
            logger.info("PII detected: pattern=%s", label)
            return True
    return False


# ── Sentence enforcement ────────────────────────────────────────────────────────

def _enforce_sentence_limit(text: str, max_sentences: int = 3) -> str:
    """
    Trim the text to at most max_sentences sentences.

    Splits on sentence-ending punctuation (., !, ?) followed by whitespace
    or end-of-string. Preserves the citation line (starts with "Source:").
    """
    # Separate the body from any trailing citation line
    lines = text.strip().splitlines()
    citation_lines: list[str] = []
    body_lines: list[str] = []

    for line in lines:
        if line.strip().startswith("Source:"):
            citation_lines.append(line)
        else:
            body_lines.append(line)

    body = " ".join(body_lines).strip()

    # Split body into sentences
    sentence_pattern = re.compile(r"(?<=[.!?])\s+")
    sentences = sentence_pattern.split(body)
    trimmed_body = " ".join(sentences[:max_sentences]).strip()

    # Re-attach citation lines
    parts = [trimmed_body] + citation_lines
    return "\n".join(p for p in parts if p)


def _ensure_citation(text: str, sources: list[dict]) -> str:
    """
    If the text has no 'Source:' line but sources are available, append one.
    """
    if "Source:" in text or not sources:
        return text

    s = sources[0]
    citation = f"Source: {s['groww_url']} | Data as of: {s.get('ingestion_date', 'unknown')}"
    return f"{text}\n{citation}"


def _sanitize_pii_in_response(text: str) -> str:
    """
    Redact any PII patterns that leaked into the LLM output.
    Replaces matches with [REDACTED].
    """
    for _label, pattern in _PII_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text


# ── Public API ──────────────────────────────────────────────────────────────────

def postprocess(query: str, generator_result: dict) -> PostProcessResult:
    """
    Apply URL-attachment policy and privacy rules to the generator output.

    Args:
        query:            The original user query string.
        generator_result: Output from generator.generate() — a GeneratorResult dict.

    Returns:
        PostProcessResult with response, refused, refused_reason, sources, answered.
        sources is always empty when refused=True.
    """
    # ── Step 1: PII check on the query ─────────────────────────────────────────
    if check_pii(query):
        logger.warning("PII detected in query — refusing without URL")
        return PostProcessResult(
            response=_PII_REFUSAL,
            refused=True,
            refused_reason="pii",
            sources=[],
            answered=False,
        )

    answered    = generator_result.get("answered", False)
    raw_answer  = generator_result.get("answer", "").strip()
    sources     = generator_result.get("sources", [])

    # ── Step 2: No-answer check ─────────────────────────────────────────────────
    if not answered:
        logger.info("Generator returned no-answer — suppressing URL")
        return PostProcessResult(
            response=_NO_ANSWER_RESPONSE,
            refused=False,
            refused_reason="no_answer",
            sources=[],
            answered=False,
        )

    # ── Step 3: Format answered response ────────────────────────────────────────
    # Sanitize any PII that leaked into the LLM output
    cleaned = _sanitize_pii_in_response(raw_answer)

    # Enforce 3-sentence limit (preserves the Source: citation line)
    trimmed = _enforce_sentence_limit(cleaned, max_sentences=3)

    # Ensure source citation is present
    final = _ensure_citation(trimmed, sources)

    logger.info(
        "Postprocessed: answered=True  sources=%d  mode=%s",
        len(sources), generator_result.get("mode", "unknown"),
    )

    return PostProcessResult(
        response=final,
        refused=False,
        refused_reason=None,
        sources=sources,
        answered=True,
    )
