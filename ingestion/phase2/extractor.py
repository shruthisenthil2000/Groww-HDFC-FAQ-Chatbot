"""
Phase 2.1 — Text Extraction & Cleaning

Parses raw Groww HTML files from corpus/raw/ and extracts named sections for
Phase 2.2 chunking. Core blocks: overview, exit/tax, objective, about, manager,
AMC. Optional blocks (when present in the text export): holdings, asset
allocation, sector allocation. Navigation noise and long "also manages" lists
are trimmed where possible.

Public API
----------
extract(fund, raw_dir) -> dict[str, str]
    Parse one fund's HTML. Returns a dict mapping section_type → clean text.
    Raises ExtractionError if the HTML cannot be parsed or critical sections
    are missing.

extract_all(funds, raw_dir) -> list[dict[str, str]]
    Run extract() for all funds. Logs per-fund results.

Section types returned
----------------------
    fund_overview        Fund name, category, risk, NAV, AUM, expense ratio, min SIP
    exit_load_tax        Exit load + stamp duty + tax implication (always together)
    investment_objective Investment objective text + benchmark index
    about                Summary paragraph describing the fund
    fund_manager         Manager name, education, experience (per manager)
    fund_house           AMC details (name, AUM, contact info)

Input  : corpus/raw/<fund_id>.html  (Phase 1.3 output)
Output : dict[section_type, text]   (consumed by Phase 2.2 chunker)
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ── Exception ─────────────────────────────────────────────────────────────────

class ExtractionError(RuntimeError):
    """Raised when a fund HTML file cannot be parsed or critical sections are absent."""


# ── Section boundary patterns (tuned against actual Groww HTML) ───────────────
# These match plain-text lines produced by BeautifulSoup.get_text(strip=True).

_CATEGORIES = {"equity", "debt", "hybrid", "elss", "index", "etf", "fof", "solution", "other"}

_OVERVIEW_END          = "return calculator"
_MIN_INVEST_START      = "minimum investments"
_MIN_INVEST_END        = "understand terms"
_EXIT_LOAD_START       = "exit load, stamp duty and tax"
_EXIT_LOAD_END         = "check past data"
_COMPARE_START         = "compare similar funds"
_FUND_MGMT_START       = "fund management"
_ALSO_MANAGES          = "also manages these schemes"
_ABOUT_START           = "about"          # standalone line, followed by fund name
_INVEST_OBJ_START      = "investment objective"
_FUND_HOUSE_START      = "fund house"     # standalone (not "mutual fund houses")
_FUND_HOUSE_END_MARKERS = {"home", "contact us", "download the app"}
_FOOTER_MARKER         = "© 20"

# Optional sections (Groww text dump — present on many scheme pages)
_HOLDINGS_START_MARKERS = (
    "top holdings",
    "major holdings",
    "fund holdings",
    "equity holdings",
    "portfolio holdings",
    "stock holdings",
    "scheme portfolio",
    "key holdings",
    "portfolio constituents",
)
_ASSET_ALLOC_START = (
    "equity / debt split",
    "equity and debt",
    "equity debt cash split",
    "equity debt split",
)
_SECTOR_ALLOC_START = (
    "sector allocation",
    "sector exposure",
    "sector distribution",
    "allocation across sectors",
    "industry allocation",
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_html(html_bytes: bytes) -> tuple[BeautifulSoup, list[str]]:
    """Parse HTML once; return (soup, text lines) for line- and DOM-based extractors."""
    soup = BeautifulSoup(html_bytes, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    raw = soup.get_text(separator="\n", strip=True)
    lines = [ln for ln in raw.splitlines() if ln.strip()]
    return soup, lines


def _merge_longer(a: str, b: str) -> str:
    a, b = (a or "").strip(), (b or "").strip()
    if len(a) >= len(b):
        return a
    return b


def _soup_cluster_text(
    soup: BeautifulSoup,
    heading_needles: tuple[str, ...],
    stop_needles: tuple[str, ...],
    cap: int = 6000,
) -> str:
    """Collect text after a short heading-like node until a likely section boundary."""
    best = ""
    for tag in soup.find_all(["h2", "h3", "h4", "h5", "div", "p", "section"]):
        label = tag.get_text(" ", strip=True)
        if len(label) > 160:
            continue
        low = label.lower()
        if not any(n in low for n in heading_needles):
            continue
        acc: list[str] = [label]
        for sib in tag.find_next_siblings(limit=50):
            if sib.name in ("h2", "h3", "h4", "h5", "section"):
                lab2 = sib.get_text(" ", strip=True).lower()
                if len(lab2) < 120 and any(st in lab2 for st in stop_needles):
                    break
            t = sib.get_text(" ", strip=True)
            if t:
                acc.append(t)
            if sum(len(x) for x in acc) > cap:
                break
        blob = " ".join(acc).strip()
        if len(blob) > len(best):
            best = blob[:cap]
    return best


def _supplement_sections_from_soup(soup: BeautifulSoup) -> dict[str, str]:
    """DOM-walk supplements when plain-line slicing misses table-heavy blocks."""
    computed_asset, computed_sector = _extract_asset_and_sector_from_sector_table(soup)
    return {
        "holdings": _soup_cluster_text(
            soup,
            (
                "top holdings",
                "portfolio holdings",
                "stock holdings",
                "scheme portfolio",
                "key holdings",
                "portfolio constituents",
            ),
            (
                "sector allocation",
                "asset allocation",
                "compare similar funds",
                "fund management",
                "valuation metrics",
            ),
        ),
        "asset_allocation": computed_asset
        or _soup_cluster_text(
            soup,
            (
                "equity / debt",
                "equity allocation",
                "debt allocation",
                "allocation across",
            ),
            (
                "sector allocation",
                "top holdings",
                "compare similar funds",
                "fund management",
                "geographic allocation",
            ),
        ),
        "sector_allocation": computed_sector
        or _soup_cluster_text(
            soup,
            ("sector allocation", "sector exposure", "industry allocation", "allocation across sectors"),
            (
                "asset allocation",
                "top holdings",
                "geographic allocation",
                "compare similar funds",
                "fund management",
            ),
        ),
    }


def _extract_asset_and_sector_from_sector_table(soup: BeautifulSoup) -> tuple[str, str]:
    """
    Extract allocation-like totals from the holdings table:
      Name | Sector | Instruments | Assets(%)

    For many Groww pages, the actual "sector allocation" chart is rendered into a
    table that is still present in the static HTML snapshot.
    """
    tables = soup.find_all("table")
    for table in tables:
        ths = table.find_all("th")
        header = [th.get_text(" ", strip=True).lower() for th in ths]
        if not header:
            continue

        # Require the specific structure we observed on pages we ingest.
        if not any("sector" == h or h.startswith("sector") for h in header):
            continue
        if not any("instruments" == h or h.startswith("instrument") for h in header):
            continue
        if not any("assets" == h or h.startswith("asset") for h in header):
            continue

        idx_sector = next(
            (i for i, h in enumerate(header) if h == "sector" or h.startswith("sector")),
            None,
        )
        idx_instr = next(
            (i for i, h in enumerate(header) if h == "instruments" or h.startswith("instrument")),
            None,
        )
        idx_assets = next(
            (i for i, h in enumerate(header) if h == "assets" or h.startswith("asset")),
            None,
        )
        if idx_sector is None or idx_instr is None or idx_assets is None:
            continue

        asset_totals: dict[str, float] = {}
        sector_totals: dict[str, float] = {}

        for tr in table.find_all("tr"):
            tds = tr.find_all("td")
            if not tds or len(tds) <= max(idx_sector, idx_instr, idx_assets):
                continue
            sector_val = tds[idx_sector].get_text(" ", strip=True)
            instr_val = tds[idx_instr].get_text(" ", strip=True)
            assets_val = tds[idx_assets].get_text(" ", strip=True)

            if not sector_val or not instr_val or not assets_val:
                continue

            # Parse values like "4.50%" or "3.88 %".
            m = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*%?", assets_val)
            if not m:
                continue
            pct = float(m.group(1))

            instr_low = instr_val.lower()
            if "equity" in instr_low:
                asset_key = "Equity"
            elif "debt" in instr_low:
                asset_key = "Debt"
            elif "cash" in instr_low:
                asset_key = "Cash"
            else:
                asset_key = instr_val

            asset_totals[asset_key] = asset_totals.get(asset_key, 0.0) + pct
            sector_totals[sector_val] = sector_totals.get(sector_val, 0.0) + pct

        if asset_totals and sector_totals:
            # Keep output deterministic + short enough for embedding.
            asset_parts = []
            for k in sorted(asset_totals.keys()):
                asset_parts.append(f"{k}: {asset_totals[k]:.2f}%")
            asset_text = "Equity/Debt/Cash split from instruments table — " + "; ".join(asset_parts)

            top_sectors = sorted(sector_totals.items(), key=lambda kv: kv[1], reverse=True)[:10]
            sector_parts = [f"{k}: {v:.2f}%" for k, v in top_sectors]
            sector_text = "Sector allocation from sector table — " + "; ".join(sector_parts)
            return asset_text, sector_text

    return "", ""


def _slice_exit_and_taxation(exit_tax_text: str) -> tuple[str, str]:
    """Split combined Groww block into exit/stamp vs taxation sentences when possible."""
    et = (exit_tax_text or "").strip()
    if not et:
        return "", ""
    low = et.lower()
    cut = -1
    for marker in ("tax implication", "tax treatment", "capital gains"):
        j = low.find(marker)
        if j != -1 and (cut == -1 or j < cut):
            cut = j
    if cut == -1:
        return et, ""
    exit_part = et[:cut].strip()
    tax_part = et[cut:].strip()
    return exit_part, tax_part


def _benchmark_snippet(investment_objective: str) -> str:
    if not (investment_objective or "").strip():
        return ""
    s = investment_objective.strip()
    for sent in re.split(r"(?<=[.!?])\s+", s):
        sl = sent.lower()
        if "benchmark" in sl or " total return index" in sl or "nifty" in sl or "sensex" in sl:
            return sent.strip()
    m = re.search(r"Fund\s+benchmark[^\n.]{0,220}", s, re.I)
    return m.group(0).strip() if m else ""


def _riskometer_snippet(lines: list[str], overview: str) -> str:
    buf: list[str] = []
    for i, ln in enumerate(lines):
        low = ln.lower()
        if "riskometer" in low or "risk-o-meter" in low:
            buf = lines[i : min(len(lines), i + 18)]
            break
        if "value research" in low and "rating" in low:
            buf = lines[max(0, i - 2) : min(len(lines), i + 14)]
            break
    if buf:
        return _clean(buf)
    if overview:
        for sent in re.split(r"(?<=[.!?])\s+", overview.strip()):
            sl = sent.lower()
            if "risk" in sl and ("very high" in sl or "high" in sl or "moderate" in sl or "low" in sl):
                return sent.strip()
    return ""


def _find(lines: list[str], pattern: str, start: int = 0) -> int:
    """Return index of first line containing pattern (case-insensitive) from start."""
    p = pattern.lower()
    for i in range(start, len(lines)):
        if p in lines[i].lower():
            return i
    return -1


def _find_exact(lines: list[str], pattern: str, start: int = 0) -> int:
    """Return index of first line exactly matching pattern (case-insensitive)."""
    p = pattern.lower().strip()
    for i in range(start, len(lines)):
        if lines[i].lower().strip() == p:
            return i
    return -1


def _is_manager_initials(line: str) -> bool:
    """Return True if line looks like fund manager initials (2-3 uppercase letters)."""
    return bool(re.fullmatch(r"[A-Z]{2,3}", line.strip()))


def _clean(parts: list[str]) -> str:
    """Join non-empty, non-placeholder lines into clean text."""
    kept = []
    for p in parts:
        p = p.strip()
        if not p or p in ("--", "-", ";", "View details"):
            continue
        # Strip obfuscated email placeholders
        if "[email" in p.lower():
            continue
        kept.append(p)
    return " ".join(kept)


# ── Core extraction ───────────────────────────────────────────────────────────

def _extract_fund_overview(lines: list[str], fund_name: str) -> str:
    """
    Extract the fund overview block: header stats + minimum investments.

    The overview starts at the line exactly matching the fund name in the content
    area (distinguished from the page title by being followed by a category word),
    and ends at "Return calculator". Minimum investments (further down) are merged
    in because they answer the same set of FAQ queries.
    """
    # Find overview start: fund name followed within a few lines by a category word
    start = -1
    for i, line in enumerate(lines):
        if line.strip() == fund_name:
            # Check if the next 3 lines contain a known category keyword
            window = " ".join(lines[i+1:i+4]).lower()
            if any(cat in window for cat in _CATEGORIES):
                start = i
                break

    if start == -1:
        # Fallback: first occurrence of fund name anywhere
        start = _find(lines, fund_name)
    if start == -1:
        return ""

    end = _find(lines, _OVERVIEW_END, start)
    if end == -1:
        end = start + 20  # safety cap

    overview_lines = lines[start:end]

    # Also collect the minimum investments block and merge
    mi_start = _find(lines, _MIN_INVEST_START, end)
    mi_end   = _find(lines, _MIN_INVEST_END, mi_start) if mi_start != -1 else -1
    if mi_start != -1 and mi_end != -1:
        overview_lines += lines[mi_start:mi_end]

    return _clean(overview_lines)


def _extract_exit_load_tax(lines: list[str], search_from: int = 0) -> str:
    """
    Extract the exit load + stamp duty + tax implication block.

    Uses the heading "Exit load, stamp duty and tax" as the precise boundary
    (not the generic "Exit load" term definition that appears earlier on the page).
    """
    start = _find(lines, _EXIT_LOAD_START, search_from)
    if start == -1:
        return ""
    end = _find(lines, _EXIT_LOAD_END, start)
    if end == -1:
        end = start + 15

    return _clean(lines[start:end])


def _extract_fund_manager(lines: list[str], search_from: int = 0) -> str:
    """
    Extract fund manager section: name, dates, education, experience.

    "Also manages these schemes" lists are stripped because they add
    cross-fund noise (30–40 scheme names) that degrades retrieval.
    """
    start = _find_exact(lines, _FUND_MGMT_START, search_from)
    if start == -1:
        start = _find(lines, _FUND_MGMT_START, search_from)
    if start == -1:
        return ""

    # Section ends at "About" standalone line
    end = _find_exact(lines, _ABOUT_START, start + 1)
    if end == -1:
        end = _find(lines, _ABOUT_START, start + 1)
    if end == -1:
        end = start + 100

    manager_lines: list[str] = []
    skip = False
    for line in lines[start + 1 : end]:
        low = line.lower().strip()
        if _ALSO_MANAGES in low:
            skip = True
            continue
        # A new manager's initials reset the skip flag
        if skip and _is_manager_initials(line):
            skip = False
        if not skip:
            manager_lines.append(line)

    return _clean(manager_lines)


def _extract_about(lines: list[str], fund_name: str, search_from: int = 0) -> str:
    """
    Extract the "About [Fund Name]" summary paragraph.

    The standalone "About" line appears after the fund manager section,
    followed immediately by the fund name and 2-3 description sentences.
    """
    # Find "About" standalone that is followed by the fund name
    idx = search_from
    while True:
        idx = _find_exact(lines, _ABOUT_START, idx)
        if idx == -1:
            break
        # Check if fund name appears within the next 2 lines
        window = " ".join(lines[idx : idx + 3]).lower()
        if fund_name.lower() in window:
            break
        idx += 1

    if idx == -1:
        return ""

    end = _find(lines, _INVEST_OBJ_START, idx + 1)
    if end == -1:
        end = idx + 10

    return _clean(lines[idx + 1 : end])


def _extract_investment_objective(lines: list[str], search_from: int = 0) -> str:
    """Extract investment objective text + fund benchmark name."""
    start = _find(lines, _INVEST_OBJ_START, search_from)
    if start == -1:
        return ""

    # Section ends at "Fund house" standalone line
    end = _find_exact(lines, _FUND_HOUSE_START, start + 1)
    if end == -1:
        end = _find(lines, _FUND_HOUSE_START, start + 1)
    if end == -1:
        end = start + 10

    return _clean(lines[start : end])


def _slice_block(lines: list[str], start: int, end_markers: tuple[str, ...], max_lines: int = 120) -> str:
    """Slice lines[start:] until the earliest line matching any end_marker (case-insensitive)."""
    if start < 0 or start >= len(lines):
        return ""
    end = -1
    for em in end_markers:
        j = _find(lines, em, start + 1)
        if j != -1 and (end == -1 or j < end):
            end = j
    if end == -1:
        end = min(len(lines), start + max_lines)
    return _clean(lines[start:end])


def _extract_holdings(lines: list[str], search_from: int = 0) -> str:
    """Top holdings / portfolio composition when present in the text export."""
    start = -1
    for pat in _HOLDINGS_START_MARKERS:
        i = _find(lines, pat, search_from)
        if i != -1 and (start == -1 or i < start):
            start = i
    if start == -1:
        return ""
    end_markers = (
        "sector allocation",
        "asset allocation",
        "geographic allocation",
        "compare similar funds",
        "fund management",
        "valuation metrics",
        "portfolio turnover",
    )
    return _slice_block(lines, start, end_markers)


def _extract_asset_allocation(lines: list[str], search_from: int = 0) -> str:
    """Equity / debt / cash (or hybrid) split when present."""
    start = -1
    for pat in _ASSET_ALLOC_START:
        i = _find(lines, pat, search_from)
        if i != -1 and (start == -1 or i < start):
            start = i
    if start == -1:
        return ""
    end_markers = (
        "geographic allocation",
        "top holdings",
        "sector allocation",
        "compare similar funds",
        "fund management",
        "holdings",
    )
    return _slice_block(lines, start, end_markers)


def _extract_sector_allocation(lines: list[str], search_from: int = 0) -> str:
    """Sector-wise weights when present."""
    start = -1
    for pat in _SECTOR_ALLOC_START:
        i = _find(lines, pat, search_from)
        if i != -1 and (start == -1 or i < start):
            start = i
    if start == -1:
        return ""
    end_markers = (
        "asset allocation",
        "top holdings",
        "compare similar funds",
        "fund management",
        "geographic allocation",
        "market cap allocation",
    )
    return _slice_block(lines, start, end_markers)


def _extract_fund_house(lines: list[str], search_from: int = 0) -> str:
    """
    Extract AMC/fund house details.

    "Fund house" (standalone) is used, not "Mutual Fund Houses" (navigation).
    Stops at breadcrumb "Home >" marker or footer.
    """
    # Find standalone "Fund house" — not "Mutual Fund Houses"
    start = -1
    for i in range(search_from, len(lines)):
        if lines[i].strip().lower() == _FUND_HOUSE_START:
            start = i
            break

    if start == -1:
        return ""

    fund_house_lines: list[str] = []
    for line in lines[start + 1 :]:
        low = line.lower().strip()
        if low in _FUND_HOUSE_END_MARKERS or _FOOTER_MARKER in line:
            break
        # Stop at breadcrumb "Home > Mutual Funds > ..."
        if low == "home":
            break
        fund_house_lines.append(line)

    return _clean(fund_house_lines)


# ── Public API ────────────────────────────────────────────────────────────────

def extract(fund: dict, raw_dir: Path) -> dict[str, str]:
    """
    Parse one fund's raw HTML and return a dict of section_type → clean text.

    Args:
        fund:    Validated fund dict from Phase 1.1 (must have fund_id, fund_name).
        raw_dir: Path to corpus/raw/ directory.

    Returns:
        dict with keys including: fund_overview, holdings, asset_allocation,
        sector_allocation, exit_load_tax, exit_load_rules, taxation, benchmark,
        riskometer, investment_objective, about, fund_manager, fund_house

    Raises:
        ExtractionError: HTML file missing, or fund_overview / exit_load_tax absent.
    """
    fund_id   = fund["fund_id"]
    fund_name = fund["fund_name"]
    html_path = raw_dir / f"{fund_id}.html"

    if not html_path.exists():
        raise ExtractionError(f"HTML file not found: {html_path}")

    try:
        html_bytes = html_path.read_bytes()
        soup, lines = _parse_html(html_bytes)
    except Exception as exc:
        raise ExtractionError(f"Failed to parse HTML for {fund_id}: {exc}") from exc

    sup = _supplement_sections_from_soup(soup)

    # Find approximate positions of heavy-boundary markers to guide sub-extractors
    mgmt_idx = _find(lines, _FUND_MGMT_START)
    mgmt_idx = max(mgmt_idx, 0)

    ov = _extract_fund_overview(lines, fund_name)
    iob = _extract_investment_objective(lines, mgmt_idx)
    et_full = _extract_exit_load_tax(lines)
    exit_rules, taxation_body = _slice_exit_and_taxation(et_full)

    sections: dict[str, str] = {
        "fund_overview":        ov,
        "holdings":             _merge_longer(_extract_holdings(lines), sup.get("holdings", "")),
        "asset_allocation":     _merge_longer(_extract_asset_allocation(lines), sup.get("asset_allocation", "")),
        "sector_allocation":    _merge_longer(_extract_sector_allocation(lines), sup.get("sector_allocation", "")),
        "exit_load_tax":        et_full,
        # Split chunks only when taxation is separable (avoids duplicating the full block twice).
        "exit_load_rules":      (exit_rules or "").strip() if taxation_body.strip() else "",
        "taxation":             taxation_body.strip(),
        "benchmark":            _benchmark_snippet(iob) or _benchmark_snippet(ov),
        "riskometer":           _riskometer_snippet(lines, ov),
        "fund_manager":         _extract_fund_manager(lines),
        "about":                _extract_about(lines, fund_name, mgmt_idx),
        "investment_objective": iob,
        "fund_house":           _extract_fund_house(lines, mgmt_idx),
    }

    # Validate critical sections
    missing = [k for k in ("fund_overview", "exit_load_tax") if not sections[k]]
    if missing:
        raise ExtractionError(
            f"[{fund_id}] Critical sections missing after extraction: {missing}. "
            "HTML structure may have changed — re-run Phase 1.3 to refresh."
        )

    non_empty = sum(1 for v in sections.values() if v)
    logger.info(
        "  [%s] Extracted %d/%d sections  (%d lines total)",
        fund_id, non_empty, len(sections), len(lines),
    )
    return sections


def extract_all(funds: list[dict], raw_dir: Path) -> list[dict[str, str]]:
    """
    Run extract() for all funds.

    Args:
        funds:   Validated fund list from Phase 1.1 load_and_validate().
        raw_dir: Path to corpus/raw/.

    Returns:
        list of section dicts (same order as input funds).
        Raises ExtractionError on the first failure.
    """
    all_sections: list[dict[str, str]] = []
    for fund in funds:
        sections = extract(fund, raw_dir)
        all_sections.append(sections)

    logger.info("extract_all complete — %d funds processed", len(all_sections))
    return all_sections
