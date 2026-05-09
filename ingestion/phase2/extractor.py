"""
Phase 2.1 — Text Extraction & Cleaning

Parses raw Groww HTML files from corpus/raw/ and extracts the six named
sections defined in architecture.md Phase 2.2.1. Noise (navigation, holdings
table, footer, generic term definitions, "also-manages" lists) is discarded.

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


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_lines(html_bytes: bytes) -> list[str]:
    """Parse HTML and return non-empty stripped text lines."""
    soup = BeautifulSoup(html_bytes, "html.parser")
    # Remove script/style tags entirely before text extraction
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    raw = soup.get_text(separator="\n", strip=True)
    return [ln for ln in raw.splitlines() if ln.strip()]


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
        dict with keys: fund_overview, exit_load_tax, investment_objective,
                        about, fund_manager, fund_house

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
        lines = _get_lines(html_bytes)
    except Exception as exc:
        raise ExtractionError(f"Failed to parse HTML for {fund_id}: {exc}") from exc

    # Find approximate positions of heavy-boundary markers to guide sub-extractors
    mgmt_idx = _find(lines, _FUND_MGMT_START)
    mgmt_idx = max(mgmt_idx, 0)

    sections: dict[str, str] = {
        "fund_overview":        _extract_fund_overview(lines, fund_name),
        "exit_load_tax":        _extract_exit_load_tax(lines),
        "fund_manager":         _extract_fund_manager(lines),
        "about":                _extract_about(lines, fund_name, mgmt_idx),
        "investment_objective": _extract_investment_objective(lines, mgmt_idx),
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
        "  [%s] Extracted %d/6 sections  (%d lines total)",
        fund_id, non_empty, len(lines),
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
