"""
RAG Generator — Phase 3.5

Constructs the final answer by passing retrieved context + user query to the LLM.

Execution modes (selected automatically, in priority order)
-----------------------------------------------------------
1. Groq mode  (LLM_PROVIDER=groq, GROQ_API_KEY set):
   - Calls Groq's inference API (OpenAI-compatible).
   - Default model: llama-3.1-8b-instant (fast, free tier available).
   - Groq provides ~500 tokens/s — suitable for real-time FAQ responses.

2. OpenAI mode (LLM_PROVIDER=openai, OPENAI_API_KEY set):
   - Calls OpenAI API (gpt-4o-mini or configured LLM_MODEL).
   - Used when Groq is unavailable or a different model is preferred.

3. Retrieval-only fallback (no API key set for the configured provider):
   - Formats the top retrieved chunk text directly as the answer.
   - No LLM call — suitable for local testing and demos without any key.

No-answer sentinel
------------------
The LLM is instructed to output exactly this string when the context
is insufficient to answer the query:

    "I don't have this information in my current sources."

The generator detects this string and sets `answered = False`. The
postprocessor uses this flag to suppress the source URL.

Groq supported models (as of May 2026)
---------------------------------------
  llama-3.1-8b-instant      — fast, good quality for FAQ (default)
  llama-3.3-70b-versatile   — highest quality, slightly slower
  mixtral-8x7b-32768        — large context window

Set LLM_MODEL in .env to switch.

Public API
----------
generate(query, retrieved_chunks) -> GeneratorResult
    GeneratorResult is a TypedDict:
        answer:      str   — raw LLM text (or formatted chunk in fallback)
        answered:    bool  — False when no-answer sentinel is present
        sources:     list  — [{fund_name, groww_url, ingestion_date}]
        tokens_used: int   — 0 in fallback mode
        mode:        str   — "groq" | "openai" | "fallback"
"""

from __future__ import annotations

import logging
from typing import TypedDict

from config import (
    LLM_PROVIDER,
    LLM_MODEL,
    LLM_TEMPERATURE,
    GROQ_API_KEY,
    OPENAI_API_KEY,
    require_groq_key,
    require_openai_key,
)

logger = logging.getLogger(__name__)

# ── No-answer sentinel ──────────────────────────────────────────────────────────
NO_ANSWER_SENTINEL = "I don't have this information in my current sources."

# ── System prompt ───────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """\
You are a facts-only FAQ assistant for HDFC Mutual Fund schemes on Groww.

CORPUS GROUNDING (absolute):
- Your ONLY permitted knowledge source is the context provided below.
- The context contains exclusively HDFC Mutual Fund data scraped from Groww.
- You must NEVER use external knowledge, general fund knowledge, or any
  information about funds or companies NOT present in the context.
- If a chunk in the context is not from an HDFC Mutual Fund, ignore it entirely.

STRICT RULES:
1. Answer ONLY using the information present in the context below.
   Do NOT use any training-time knowledge, even if you believe it is correct.
2. Keep your response to 3 sentences or fewer.
3. Do NOT give investment advice, recommendations, or performance predictions.
4. Do NOT include or reproduce any personal information (names, phone numbers,
   email addresses, Aadhaar numbers, PAN cards, or any other identifiers).
5. Answer in plain, factual English. Be concise.
6. Do NOT mention any fund, company, platform, or product that does not appear
   in the context provided. This includes NextLeap, Zerodha, Groww funds other
   than HDFC, Mirae, Axis, SBI, or any other AMC.

NO-ANSWER RULE (critical):
- If the context does not contain enough information to answer the question,
  respond with EXACTLY this phrase and nothing else:
  "I don't have this information in my current sources."
- Do NOT guess, infer, or supplement from general knowledge.
- Do NOT include a source citation when you cannot answer.
- When in doubt, use the no-answer phrase — do not risk hallucination.

SOURCE CITATION RULE:
- When you provide a real answer, end with:
  "Source: {groww_url} | Data as of: {ingestion_date}"
  (Replace placeholders with the actual values from the context metadata.)
- When you output the no-answer phrase, do NOT include any URL or date.
"""


# ── TypedDict return type ───────────────────────────────────────────────────────

class GeneratorResult(TypedDict):
    answer: str
    answered: bool
    sources: list[dict]
    tokens_used: int
    mode: str


# ── Context builder ─────────────────────────────────────────────────────────────

def _build_context(chunks: list[dict]) -> tuple[str, list[dict]]:
    """
    Format retrieved chunks into a context block for the prompt.

    Returns (context_text, sources_list).
    sources_list contains deduped {fund_name, groww_url, ingestion_date}.
    """
    if not chunks:
        return "", []

    lines: list[str] = []
    seen_urls: set[str] = set()
    sources: list[dict] = []

    for i, chunk in enumerate(chunks, 1):
        fund_name      = chunk.get("fund_name", "Unknown Fund")
        section_type   = chunk.get("section_type", "")
        text           = chunk.get("text", "").strip()
        groww_url      = chunk.get("groww_url", "")
        ingestion_date = chunk.get("ingestion_date", "")

        lines.append(
            f"[Chunk {i}] Fund: {fund_name} | Section: {section_type}\n"
            f"URL: {groww_url} | Data as of: {ingestion_date}\n"
            f"{text}\n"
        )

        if groww_url and groww_url not in seen_urls:
            seen_urls.add(groww_url)
            sources.append({
                "fund_name":      fund_name,
                "groww_url":      groww_url,
                "ingestion_date": ingestion_date,
            })

    return "\n".join(lines), sources


# ── Groq generation ─────────────────────────────────────────────────────────────

def _generate_groq(query: str, context: str, sources: list[dict]) -> GeneratorResult:
    """Call the Groq inference API (OpenAI-compatible) and parse the response."""
    try:
        from groq import Groq
    except ImportError as exc:
        raise RuntimeError(
            "groq package is not installed. Run: pip install groq"
        ) from exc

    api_key = require_groq_key()
    client = Groq(api_key=api_key)

    user_prompt = f"Context:\n{context}\n\nQuestion: {query}"

    logger.info(
        "Calling Groq  model=%s  temperature=%.2f", LLM_MODEL, LLM_TEMPERATURE
    )

    completion = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_prompt},
        ],
        temperature=LLM_TEMPERATURE,
        max_tokens=256,
        top_p=1.0,
    )

    answer = completion.choices[0].message.content.strip()
    tokens_used = completion.usage.total_tokens if completion.usage else 0
    answered = _is_answered(answer)

    return GeneratorResult(
        answer=answer,
        answered=answered,
        sources=sources if answered else [],
        tokens_used=tokens_used,
        mode="groq",
    )


# ── OpenAI generation ───────────────────────────────────────────────────────────

def _generate_openai(query: str, context: str, sources: list[dict]) -> GeneratorResult:
    """Call the OpenAI chat API and parse the response."""
    try:
        import openai
    except ImportError as exc:
        raise RuntimeError(
            "openai package is not installed. Run: pip install openai"
        ) from exc

    api_key = require_openai_key()
    client = openai.OpenAI(api_key=api_key)

    user_prompt = f"Context:\n{context}\n\nQuestion: {query}"

    logger.info(
        "Calling OpenAI  model=%s  temperature=%.2f", LLM_MODEL, LLM_TEMPERATURE
    )

    completion = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_prompt},
        ],
        temperature=LLM_TEMPERATURE,
        max_tokens=256,
        top_p=1.0,
    )

    answer = completion.choices[0].message.content.strip()
    tokens_used = completion.usage.total_tokens if completion.usage else 0
    answered = _is_answered(answer)

    return GeneratorResult(
        answer=answer,
        answered=answered,
        sources=sources if answered else [],
        tokens_used=tokens_used,
        mode="openai",
    )


# ── Retrieval-only fallback ─────────────────────────────────────────────────────

def _generate_fallback(
    query: str, chunks: list[dict], sources: list[dict]
) -> GeneratorResult:
    """
    Format the top retrieved chunk as the answer without an LLM call.

    Used when no API key is configured. Applies the same answered/not-answered
    logic based on retrieval result presence.
    """
    if not chunks:
        logger.info("Fallback mode: no chunks retrieved — returning no-answer")
        return GeneratorResult(
            answer=NO_ANSWER_SENTINEL,
            answered=False,
            sources=[],
            tokens_used=0,
            mode="fallback",
        )

    top = chunks[0]
    fund_name      = top.get("fund_name", "Unknown Fund")
    text           = top.get("text", "").strip()
    groww_url      = top.get("groww_url", "")
    ingestion_date = top.get("ingestion_date", "")
    section_type   = top.get("section_type", "")

    answer_lines = [
        f"As per the ingestion-time data for {fund_name}"
        f" ({section_type.replace('_', ' ').title()}):",
        text,
        f"Source: {groww_url} | Data as of: {ingestion_date}",
    ]
    answer = "\n".join(answer_lines)

    logger.info(
        "Fallback mode: returning top chunk  fund=%s  section=%s",
        top.get("fund_id"), section_type,
    )

    return GeneratorResult(
        answer=answer,
        answered=True,
        sources=sources[:1],
        tokens_used=0,
        mode="fallback",
    )


# ── Key availability helpers ────────────────────────────────────────────────────

def _has_groq_key() -> bool:
    key = GROQ_API_KEY.strip()
    return bool(key) and key not in ("your_groq_key_here", "gsk_...")


def _has_openai_key() -> bool:
    key = OPENAI_API_KEY.strip()
    return bool(key) and key not in ("your_key_here", "sk-...")


def _is_answered(text: str) -> bool:
    """Return False if the LLM returned the no-answer sentinel."""
    return NO_ANSWER_SENTINEL.lower() not in text.lower()


# ── Public API ──────────────────────────────────────────────────────────────────

def generate(query: str, retrieved_chunks: list[dict]) -> GeneratorResult:
    """
    Generate a factual answer grounded in the retrieved chunks.

    Backend selection order:
      1. Groq     — if LLM_PROVIDER=groq  AND GROQ_API_KEY is set
      2. OpenAI   — if LLM_PROVIDER=openai AND OPENAI_API_KEY is set
      3. Fallback — if no valid API key is available (formats top chunk directly)

    Args:
        query:            User's natural-language question.
        retrieved_chunks: Ordered list of chunk dicts from retrieve().

    Returns:
        GeneratorResult with answer, answered flag, sources, tokens_used, mode.
        When answered=False, sources is always an empty list.
    """
    # ── Safety gate: never call LLM with empty context ──────────────────────────
    # If the retriever returned no chunks (corpus grounding filter removed all,
    # relevance threshold excluded all, or pipeline returned [] for any reason),
    # short-circuit immediately with NO_ANSWER_SENTINEL.  This prevents the LLM
    # from drawing on general training knowledge to invent an answer.
    if not retrieved_chunks:
        logger.info("No retrieved chunks — returning NO_ANSWER_SENTINEL without LLM call")
        return GeneratorResult(
            answer=NO_ANSWER_SENTINEL,
            answered=False,
            sources=[],
            tokens_used=0,
            mode="no_context",
        )

    context, sources = _build_context(retrieved_chunks)

    # ── Primary: Groq ───────────────────────────────────────────────────────────
    if LLM_PROVIDER == "groq" and _has_groq_key():
        try:
            return _generate_groq(query, context, sources)
        except Exception as exc:
            logger.warning(
                "Groq generation failed (%s); trying OpenAI fallback.", exc
            )

    # ── Secondary: OpenAI ───────────────────────────────────────────────────────
    if LLM_PROVIDER == "openai" and _has_openai_key():
        try:
            return _generate_openai(query, context, sources)
        except Exception as exc:
            logger.warning(
                "OpenAI generation failed (%s); using retrieval-only fallback.", exc
            )

    # ── Tertiary: Retrieval-only fallback ───────────────────────────────────────
    if LLM_PROVIDER not in ("groq", "openai"):
        logger.warning(
            "Unknown LLM_PROVIDER=%r — using retrieval-only fallback.", LLM_PROVIDER
        )
    else:
        logger.info(
            "No valid API key for LLM_PROVIDER=%r — using retrieval-only fallback.",
            LLM_PROVIDER,
        )

    return _generate_fallback(query, retrieved_chunks, sources)
