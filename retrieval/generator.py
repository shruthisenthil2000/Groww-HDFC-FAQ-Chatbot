from __future__ import annotations

import re

from groq import Groq

from config import LLM_MODEL, LLM_TEMPERATURE, require_groq_key

NO_ANSWER = "I don't have this information in my current sources."

SYSTEM_PROMPT = """You are a facts-only HDFC mutual fund FAQ assistant.

The context chunks are excerpts from official Groww HDFC fund pages. Each chunk is prefixed with section metadata (e.g. `section: holdings`, `section: asset_allocation`, `section: sector_allocation`, `section: taxation`, `section: exit_load`, `section: benchmark`, `section: riskometer`, `section: fund_overview`, investment_objective, fund_manager, fund_house).

Rules:
- Use ONLY the provided context. Do not invent numbers, funds, or URLs not present in the context.
- Write at most 3 short sentences total.
- Include exactly one official Groww source URL in the answer body (https://groww.in/mutual-funds/... from the context).
- Answer the question using the most relevant chunk(s), including taxation, stamp duty, exit load, benchmark, risk, AUM, minimum investment, lock-in, manager, category, holdings, or allocation when that information appears in the context.
- Do NOT end with a separate "Last updated" line — the system appends that automatically.
- Reply with the exact sentence below ONLY if NONE of the chunks contain any information related to the question (ignore generic navigation):
I don't have this information in my current sources.
"""


# Strip any model-echoed footer so we append exactly one canonical line (post-LLM only).
_LAST_UPDATED_RE = re.compile(
    r"\n*\*?\*?Last updated from sources:\*?\*?\s*.+$",
    re.IGNORECASE | re.DOTALL,
)

_LAST_UPDATED_SENTINEL = "Last updated from sources:"


def _max_ingestion_date_from_chunks(chunks: list[dict]) -> str:
    """Latest snapshot date among retrieved chunks (ISO YYYY-MM-DD preferred)."""
    dates: list[str] = []
    for c in chunks:
        d = (c.get("ingestion_date") or "").strip()
        if d and re.match(r"^\d{4}-\d{2}-\d{2}", d):
            dates.append(d)
    if not dates:
        return "date unavailable"
    return max(dates)


def append_last_updated_line(answer: str, chunks: list[dict]) -> str:
    """
    Programmatically append a single footer using max(ingestion_date) over *chunks*
    (retrieved context). Does not call the LLM. Idempotent if already well-formed.
    """
    base = _LAST_UPDATED_RE.sub("", (answer or "").rstrip()).rstrip()
    dt = _max_ingestion_date_from_chunks(chunks)
    return f"{base}\n\n{_LAST_UPDATED_SENTINEL} {dt}"


def _build_context(chunks: list[dict]) -> tuple[str, list[dict]]:
    lines: list[str] = []
    sources: list[dict] = []
    seen: set[str] = set()
    for i, c in enumerate(chunks, 1):
        fund_name = c.get("fund_name", "")
        url = c.get("groww_url", "")
        dt = c.get("ingestion_date", "")
        sec = c.get("section_type", "")
        text = c.get("text", "")
        lines.append(
            f"[Chunk {i}] section={sec} fund={fund_name} url={url} date={dt}\n{text}"
        )
        if url and url not in seen:
            seen.add(url)
            sources.append(
                {"fund_name": fund_name, "groww_url": url, "ingestion_date": dt}
            )
    return "\n\n".join(lines), sources


def _token_overlap_score(query: str, text: str) -> int:
    qtok = set(re.findall(r"[a-z0-9]+", query.lower()))
    ttok = set(re.findall(r"[a-z0-9]+", text.lower()))
    if not qtok:
        return 0
    return len(qtok & ttok)


def _extractive_fallback_answer(query: str, chunks: list[dict]) -> str | None:
    """
    When the LLM is overly conservative but retrieval returned on-corpus chunks,
    surface the best-matching excerpt with one Groww URL (no fabrication).
    """
    if not chunks:
        return None
    best = max(
        chunks[:12],
        key=lambda c: (
            _token_overlap_score(query, c.get("text") or ""),
            float(c.get("score", 0.0)),
        ),
    )
    raw = (best.get("text") or "").strip()
    if len(raw) < 40:
        return None
    url = (best.get("groww_url") or "").strip()
    fname = (best.get("fund_name") or "the scheme").strip()
    # Strip leading section prefix lines for readability (present after re-index).
    body = re.sub(r"^(?:\[section:[^\]]+\]|section:\s*[^\n]+)\s*", "", raw, flags=re.I | re.MULTILINE)
    body = re.sub(r"^fund=[^\n]+\n+", "", body, flags=re.I)
    body = body.replace("\n\n", " ").strip()
    sentences = re.split(r"(?<=[.!?])\s+", body)
    snippet = " ".join(sentences[:3]).strip()
    if len(snippet) > 650:
        snippet = snippet[:650].rsplit(" ", 1)[0] + "…"
    if not snippet:
        return None
    if url:
        return (
            f"Per the indexed Groww page for {fname}: {snippet} "
            f"Full details: {url}"
        )
    return f"Per the indexed Groww page for {fname}: {snippet}"


def generate_answer(query: str, chunks: list[dict]) -> dict:
    if not chunks:
        return {"answer": NO_ANSWER, "sources": []}

    context, sources = _build_context(chunks)
    client = Groq(api_key=require_groq_key())
    completion = client.chat.completions.create(
        model=LLM_MODEL,
        temperature=LLM_TEMPERATURE,
        max_tokens=450,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}"},
        ],
    )
    answer = completion.choices[0].message.content.strip()
    top_score = float(chunks[0].get("score", 0.0)) if chunks else 0.0

    if NO_ANSWER.lower() in answer.lower():
        fb = _extractive_fallback_answer(query, chunks)
        if fb and top_score >= 0.08:
            answer = fb
        else:
            return {"answer": NO_ANSWER, "sources": []}

    answer = append_last_updated_line(answer, chunks)
    primary = sources[:1] if sources else []
    return {"answer": answer, "sources": primary}
