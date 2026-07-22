from __future__ import annotations

import re

from groq import Groq

from config import LLM_MODEL, LLM_TEMPERATURE, require_groq_key


NO_ANSWER = "I don't have this information in my current sources."


SYSTEM_PROMPT = """You are a facts-only HDFC mutual fund FAQ assistant.

The context chunks are excerpts from official Groww HDFC fund pages. Each chunk is prefixed with section metadata such as holdings, asset_allocation, sector_allocation, taxation, exit_load, benchmark, riskometer, fund_overview, investment_objective, fund_manager, and fund_house.

Rules:
- Use ONLY the provided context.
- Do not invent numbers, fund details, URLs, sources, or dates.
- Answer the user's exact question directly.
- Write at most 2 short sentences.
- Do not include URLs, source labels, citations, or last-updated dates in the answer.
- Do not say "According to Groww", "Per the indexed Groww page", or similar phrases.
- Give only the clean factual answer in natural language.
- The application displays the source and last-updated date separately.
- Reply with the exact sentence below ONLY if none of the chunks contain information related to the question:

I don't have this information in my current sources.
"""


def _build_context(chunks: list[dict]) -> tuple[str, list[dict]]:
    lines: list[str] = []
    sources: list[dict] = []
    seen: set[str] = set()

    for index, chunk in enumerate(chunks, 1):
        fund_name = chunk.get("fund_name", "")
        url = chunk.get("groww_url", "")
        ingestion_date = chunk.get("ingestion_date", "")
        section = chunk.get("section_type", "")
        text = chunk.get("text", "")

        lines.append(
            f"[Chunk {index}] "
            f"section={section} "
            f"fund={fund_name} "
            f"url={url} "
            f"date={ingestion_date}\n"
            f"{text}"
        )

        if url and url not in seen:
            seen.add(url)
            sources.append(
                {
                    "fund_name": fund_name,
                    "groww_url": url,
                    "ingestion_date": ingestion_date,
                }
            )

    return "\n\n".join(lines), sources


def _token_overlap_score(query: str, text: str) -> int:
    query_tokens = set(
        re.findall(r"[a-z0-9]+", (query or "").lower())
    )
    text_tokens = set(
        re.findall(r"[a-z0-9]+", (text or "").lower())
    )

    if not query_tokens:
        return 0

    return len(query_tokens & text_tokens)


def _clean_chunk_text(raw: str) -> str:
    body = re.sub(
        r"^(?:\[section:[^\]]+\]|section:\s*[^\n]+)\s*",
        "",
        raw,
        flags=re.IGNORECASE | re.MULTILINE,
    )

    body = re.sub(
        r"^fund=[^\n]+\n+",
        "",
        body,
        flags=re.IGNORECASE,
    )

    body = re.sub(
        r"https?://\S+",
        "",
        body,
    )

    body = re.sub(
        r"\s+",
        " ",
        body,
    ).strip()

    return body


def _extractive_fallback_answer(
    query: str,
    chunks: list[dict],
) -> str | None:
    """
    Return a concise excerpt when the LLM is too conservative.

    The frontend already displays the source and ingestion date separately,
    so this fallback must not include URLs, source labels, or dates.
    """
    if not chunks:
        return None

    best = max(
        chunks[:12],
        key=lambda chunk: (
            _token_overlap_score(
                query,
                chunk.get("text") or "",
            ),
            float(chunk.get("score", 0.0)),
        ),
    )

    raw = (best.get("text") or "").strip()

    if len(raw) < 20:
        return None

    body = _clean_chunk_text(raw)

    if not body:
        return None

    sentences = re.split(
        r"(?<=[.!?])\s+",
        body,
    )

    snippet = " ".join(sentences[:2]).strip()

    if len(snippet) > 350:
        snippet = (
            snippet[:350]
            .rsplit(" ", 1)[0]
            .rstrip(" ,;:")
            + "…"
        )

    return snippet or None


def _clean_model_answer(answer: str) -> str:
    """
    Remove source URLs, source labels, and date lines if the model includes
    them despite the system prompt.
    """
    cleaned = (answer or "").strip()

    cleaned = re.sub(
        r"https?://\S+",
        "",
        cleaned,
    )

    cleaned = re.sub(
        r"\n*\s*Source\s*:\s*.*$",
        "",
        cleaned,
        flags=re.IGNORECASE | re.DOTALL,
    )

    cleaned = re.sub(
        r"\n*\s*Last updated(?: from sources| on)?\s*:\s*.*$",
        "",
        cleaned,
        flags=re.IGNORECASE | re.DOTALL,
    )

    cleaned = re.sub(
        r"\bFull details\s*:\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    cleaned = re.sub(
        r"\bPer the indexed Groww page for [^:]+:\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    cleaned = re.sub(
        r"\bAccording to (?:the )?(?:official )?Groww(?: page)?[:,]?\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    cleaned = re.sub(
        r"\s+",
        " ",
        cleaned,
    ).strip()

    cleaned = cleaned.rstrip(" -–—,;:")

    return cleaned


def generate_answer(
    query: str,
    chunks: list[dict],
) -> dict:
    if not chunks:
        return {
            "answer": NO_ANSWER,
            "sources": [],
        }

    context, sources = _build_context(chunks)

    client = Groq(
        api_key=require_groq_key()
    )

    completion = client.chat.completions.create(
        model=LLM_MODEL,
        temperature=LLM_TEMPERATURE,
        max_tokens=220,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": (
                    f"Context:\n{context}\n\n"
                    f"Question: {query}"
                ),
            },
        ],
    )

    answer = (
        completion.choices[0]
        .message.content
        .strip()
    )

    top_score = float(
        chunks[0].get("score", 0.0)
    )

    if NO_ANSWER.lower() in answer.lower():
        fallback = _extractive_fallback_answer(
            query,
            chunks,
        )

        if fallback and top_score >= 0.08:
            answer = fallback
        else:
            return {
                "answer": NO_ANSWER,
                "sources": [],
            }

    answer = _clean_model_answer(answer)

    if not answer:
        fallback = _extractive_fallback_answer(
            query,
            chunks,
        )

        if fallback:
            answer = fallback
        else:
            return {
                "answer": NO_ANSWER,
                "sources": [],
            }

    primary_source = sources[:1] if sources else []

    return {
        "answer": answer,
        "sources": primary_source,
    }