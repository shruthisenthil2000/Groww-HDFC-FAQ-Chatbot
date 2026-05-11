"""Fuzzy scheme-name resolution + query enrichment for retrieval."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SOURCES_PATH = _PROJECT_ROOT / "corpus" / "sources.json"

# Minimum rapidfuzz score (0–100) to treat a query as referring to a known scheme.
SCHEME_MATCH_MIN_SCORE: float = 72.0


@lru_cache(maxsize=1)
def _fund_catalog() -> list[dict]:
    """Each entry: canonical_name, fund_id, match_strings (lowercased)."""
    if not _SOURCES_PATH.exists():
        return []
    data = json.loads(_SOURCES_PATH.read_text(encoding="utf-8"))
    funds = data.get("funds") or []
    out: list[dict] = []
    for f in funds:
        if f.get("is_duplicate"):
            continue
        name = (f.get("fund_name") or "").strip()
        if not name:
            continue
        fund_id = (f.get("fund_id") or "").strip()
        variants: set[str] = set()
        variants.add(name.lower())
        variants.add(re.sub(r"\s+", " ", name.lower()))
        for a in f.get("aliases") or []:
            if isinstance(a, str) and a.strip():
                variants.add(a.strip().lower())
        sub = f.get("sub_category")
        if isinstance(sub, str) and sub.strip():
            variants.add(f"hdfc {sub.lower()}".strip())
        out.append(
            {
                "canonical_name": name,
                "fund_id": fund_id,
                "variants": sorted(variants, key=len, reverse=True),
            }
        )
    return out


def best_scheme_match(query: str) -> tuple[str | None, str | None, float]:
    """
    Returns (canonical_fund_name, fund_id, score) or (None, None, 0.0).
    Uses rapidfuzz when available; falls back to simple ratio.
    """
    q = (query or "").strip()
    if len(q) < 2:
        return None, None, 0.0

    catalog = _fund_catalog()
    if not catalog:
        return None, None, 0.0

    try:
        from rapidfuzz import fuzz
    except ImportError:
        return _fallback_match(q, catalog)

    best_name: str | None = None
    best_id: str | None = None
    best_score = 0.0

    q_low = q.lower()
    for entry in catalog:
        for v in entry["variants"]:
            s = max(
                fuzz.WRatio(q_low, v),
                fuzz.partial_ratio(q_low, v),
                fuzz.token_set_ratio(q_low, v),
            )
            if s > best_score:
                best_score = float(s)
                best_name = entry["canonical_name"]
                best_id = entry["fund_id"]

    if best_score < SCHEME_MATCH_MIN_SCORE:
        return None, None, best_score
    return best_name, best_id, best_score


def _fallback_match(query: str, catalog: list[dict]) -> tuple[str | None, str | None, float]:
    q = query.lower()
    best = (None, None, 0.0)
    for entry in catalog:
        for v in entry["variants"]:
            if v in q or q in v:
                return entry["canonical_name"], entry["fund_id"], 85.0
            overlap = len(set(q.split()) & set(v.split()))
            score = min(100.0, overlap * 18.0)
            if score > best[2]:
                best = (entry["canonical_name"], entry["fund_id"], score)
    if best[2] < SCHEME_MATCH_MIN_SCORE:
        return None, None, best[2]
    return best  # type: ignore[return-value]


# Phrase-level synonym / intent expansion (query text, not regex replacement targets)
_SYNONYM_RE: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"holdings?\s+analysis", re.I), " top holdings portfolio composition stock weights "),
    (re.compile(r"portfolio\s+composition", re.I), " top holdings portfolio stocks "),
    (re.compile(r"equity\s*,?\s*debt\s*,?\s*cash\s*split", re.I), " asset allocation equity debt cash hybrid "),
    (re.compile(r"equity\s+and\s+debt\s+split", re.I), " asset allocation equity debt "),
    (re.compile(r"equity\s+debt\s+split", re.I), " asset allocation equity debt cash hybrid "),
    (re.compile(r"equity\s*split", re.I), " asset allocation equity debt cash hybrid "),
    (re.compile(r"sector\s*split", re.I), " sector allocation industry weights "),
    # Generic "allocation" most commonly maps to asset allocation (unless the query is explicitly sector-focused).
    (re.compile(r"\ballocation\b(?!.*\bsector\b)", re.I), " asset allocation equity debt cash "),
    (re.compile(r"\bmin\.?\s*investment\b|\bminimum\s+investment\b", re.I), " minimum SIP minimum lumpsum first investment "),
    (re.compile(r"\brisk\s+level\b", re.I), " riskometer risk category very high high moderate "),
    (re.compile(r"\block\s*in\b|\blockin\b", re.I), " lock-in period ELSS 3 year "),
    (re.compile(r"\btax\b(?!\s*statement)", re.I), " taxation LTCG STCG stamp duty tax implication redeem "),
    (re.compile(r"\bAUM\b|assets\s+under\s+management|fund\s+size", re.I), " AUM fund size corpus "),
    (re.compile(r"scheme\s+information|scheme\s+document", re.I), " SID KIM factsheet offer document "),
]

_TOPIC_HINTS: list[tuple[str, str]] = [
    (r"(?i)expense\s*ratio|ter\b|total\s*expense", " expense ratio ongoing charges "),
    (r"(?i)exit\s*load|redemption\s*charge", " exit load redemption "),
    (r"(?i)minimum\s*sip|min\.?\s*sip|sip\s*amount", " minimum SIP investment "),
    (r"(?i)lump\s*sum|one[- ]time|lumpsum|1st\s+investment|2nd\s+investment", " minimum lumpsum investment "),
    (r"(?i)lock[- ]?in|lockin|three\s*year\s*lock", " lock-in period ELSS "),
    (r"(?i)benchmark|index\s*tracked|underlying\s+index", " benchmark index "),
    (r"(?i)riskometer|risk\s*meter|risk\s*level|risk\s+category", " riskometer risk level very high "),
    (r"(?i)fund\s*manager|portfolio\s*manager|CIO\b", " fund manager "),
    (r"(?i)category|flexi\s*cap|mid\s*cap|large\s*cap|elss|tax\s*saver|thematic|index\s+fund", " fund category scheme type "),
    (r"(?i)statement\s*download|account\s*statement|CAS\b", " statement download CAS "),
    (r"(?i)tax\s*statement|capital\s*gain|form\s*16", " tax statement capital gains LTCG STCG "),
    (r"(?i)\bSID\b|KIM|factsheet|scheme\s*information|offer\s*document", " SID KIM factsheet scheme document link "),
    (r"(?i)holdings?\b|portfolio\s+holdings|stock\s+allocation", " top holdings portfolio composition "),
    (r"(?i)asset\s+allocation|debt\s+allocation|equity\s+allocation", " asset allocation equity debt cash "),
    (r"(?i)portfolio\s+allocation|allocation\s+across\s+sectors|allocation\s+across\s+asset", " section: allocation sector asset allocation "),
    (r"(?i)sector\s+allocation|industry\s+allocation|sector\s+exposure", " sector allocation industry weights "),
    (r"(?i)stamp\s+duty", " stamp duty 0.005% "),
    (r"(?i)LTCG|long\s*term\s*capital|STCG|short\s*term\s*capital", " LTCG STCG tax implication redeem "),
    (r"(?i)portfolio\s+turnover|turnover\s+ratio", " portfolio turnover "),
    (r"(?i)geographic|country\s+allocation", " geographic allocation "),
]


def _section_intent_tags(query: str) -> str:
    """Dense section labels for embedding (aligns with chunker `section: …` prefixes after re-index)."""
    ql = query.lower()
    tags: list[str] = []
    if re.search(r"holding|portfolio\s+composition|stock\s+weight|equity\s+exposure\s+stock", ql):
        tags.append("section: holdings top holdings portfolio")
    if re.search(r"asset\s+allocation|equity.*debt|debt.*equity|cash\s+allocation|hybrid\s+split", ql):
        tags.append("section: asset_allocation equity debt cash")
    if re.search(r"\ballocation\b", ql) and "sector" not in ql:
        tags.append("section: asset_allocation equity debt cash")
    if re.search(r"equity\s*split", ql):
        tags.append("section: asset_allocation equity debt cash")
    if re.search(r"sector\s*split", ql):
        tags.append("section: sector_allocation sectors industry")
    if re.search(r"sector\s+allocation|sector\s+exposure|industry\s+weight", ql):
        tags.append("section: sector_allocation sectors industry")
    if re.search(r"tax|ltcg|stcg|capital\s+gain|stamp\s+duty|withholding", ql):
        tags.append("section: taxation LTCG STCG stamp duty")
    if re.search(r"exit\s*load|redemption\s+fee|exit\s+fee", ql):
        tags.append("section: exit_load exit_load_rules")
    if re.search(r"riskometer|risk\s*meter|risk\s+level|risk\s+category|very\s+high\s+risk", ql):
        tags.append("section: riskometer risk rating")
    if re.search(r"benchmark|index\s+tracked|nifty|sensex", ql):
        tags.append("section: benchmark index objective")
    return " ".join(dict.fromkeys(tags))


def preferred_sections_for_query(query: str) -> set[str]:
    """
    Map a query to section types that should get a small rerank bonus.
    """
    ql = (query or "").lower()
    preferred: set[str] = set()
    if re.search(r"holding|portfolio\s+composition|stock\s+weight|constituent", ql):
        preferred.add("holdings")
    if re.search(r"asset\s+allocation|equity.*debt|debt.*equity|cash\s+split|equity\s+debt\s+cash", ql):
        preferred.add("asset_allocation")
    if re.search(r"\ballocation\b", ql) and "sector" not in ql:
        preferred.add("asset_allocation")
    if re.search(r"equity\s*split", ql):
        preferred.add("asset_allocation")
    if re.search(r"sector\s+allocation|sector\s+exposure|industry\s+allocation", ql):
        preferred.add("sector_allocation")
    if re.search(r"sector\s*split", ql):
        preferred.add("sector_allocation")
    if re.search(r"tax|ltcg|stcg|capital\s+gain|stamp\s+duty|taxation", ql):
        preferred.update({"taxation", "exit_load_tax", "exit_load_rules"})
    if re.search(r"exit\s*load|redemption\s+fee|exit\s+fee", ql):
        preferred.update({"exit_load_rules", "exit_load_tax"})
    if re.search(r"benchmark|index\s+tracked|nifty|sensex", ql):
        preferred.update({"benchmark", "investment_objective"})
    if re.search(r"riskometer|risk\s*meter|risk\s+level|risk\s+category", ql):
        preferred.add("riskometer")
    return preferred


def enrich_query_for_retrieval(query: str) -> str:
    q = query.strip()
    if not q:
        return q
    for pat, repl in _SYNONYM_RE:
        q = pat.sub(repl, q)
    extra = ""
    for pat, hint in _TOPIC_HINTS:
        if re.search(pat, q):
            extra += hint
    tags = _section_intent_tags(q)
    if tags:
        extra += " " + tags
    return (q + extra).strip() if extra else q


def retrieval_query_variants(query: str) -> list[str]:
    """
    Ordered list of query strings to embed for FAISS (deduped).
    Combines topic enrichment + best fuzzy scheme match.

    When a scheme is resolved, scheme-prefixed strings are listed first so the
    embedding is closer to chunk lines that start with ``fund=<canonical name>``.
    Scores are still merged as the max across variants per chunk_id.
    """
    raw = (query or "").strip()
    base = enrich_query_for_retrieval(raw)
    name, fund_id, score = best_scheme_match(raw)

    out: list[str] = []
    seen: set[str] = set()

    def add(s: str) -> None:
        s = s.strip()
        if s and s not in seen:
            seen.add(s)
            out.append(s)

    if name and score >= SCHEME_MATCH_MIN_SCORE:
        add(f"{name} {base}")
        add(f"{name} — {base}")
        add(f"{name} {fund_id} {base}")
        add(f"{name} official Groww fund page facts {base}")
    add(base)
    if raw and raw != base:
        add(raw)
    return out
