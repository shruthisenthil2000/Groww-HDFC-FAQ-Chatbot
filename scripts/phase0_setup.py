"""
Phase 0 — AMC & Scheme Selection: Setup & Validation Script

Responsibilities:
  1. Validate corpus/sources.json against the required schema.
  2. Check for duplicate URLs and flag them.
  3. Verify that all required fields are present and non-null.
  4. Print a structured summary report.
  5. Set all fund validation_status fields to 'validated' on success.

Usage:
    python scripts/phase0_setup.py

Output:
    - Console report (pass / warn / fail per fund).
    - Updated corpus/sources.json with validation_status = 'validated' for passing funds.

Exit codes:
    0  — all funds valid
    1  — one or more funds failed validation
"""

import json
import sys
from datetime import date
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
SOURCES_FILE = ROOT / "corpus" / "sources.json"

# ── Schema: required keys per fund entry ─────────────────────────────────────
REQUIRED_FUND_KEYS = [
    "fund_id",
    "fund_name",
    "category",
    "sub_category",
    "risk_level",
    "expense_ratio",
    "aum_cr",
    "min_sip_inr",
    "exit_load",
    "benchmark",
    "groww_url",
    "doc_type",
    "local_file",
    "is_duplicate",
    "ingestion_date",
]

ALLOWED_CATEGORIES = {"Equity", "Hybrid", "Commodities", "Debt"}
ALLOWED_DOC_TYPES = {"groww_fund_page"}
GROWW_DOMAIN = "https://groww.in/mutual-funds/"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _green(text: str) -> str:
    return f"\033[92m{text}\033[0m"


def _yellow(text: str) -> str:
    return f"\033[93m{text}\033[0m"


def _red(text: str) -> str:
    return f"\033[91m{text}\033[0m"


def _bold(text: str) -> str:
    return f"\033[1m{text}\033[0m"


def load_sources() -> dict:
    if not SOURCES_FILE.exists():
        print(_red(f"[FAIL] sources.json not found at: {SOURCES_FILE}"))
        sys.exit(1)
    with open(SOURCES_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_sources(data: dict) -> None:
    with open(SOURCES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ── Validation Rules ──────────────────────────────────────────────────────────

def validate_fund(fund: dict) -> list[str]:
    """
    Returns a list of error strings for a fund entry.
    An empty list means the fund passed all checks.
    """
    errors = []
    fund_label = fund.get("fund_name", fund.get("fund_id", "UNKNOWN"))

    # 1. Required keys present and non-null
    for key in REQUIRED_FUND_KEYS:
        if key not in fund:
            errors.append(f"Missing required key: '{key}'")
        elif fund[key] is None and key not in ("lock_in_years", "min_lumpsum_inr"):
            errors.append(f"Key '{key}' must not be null")

    # 2. Category in allowed set
    if fund.get("category") not in ALLOWED_CATEGORIES:
        errors.append(
            f"category '{fund.get('category')}' not in allowed set: {ALLOWED_CATEGORIES}"
        )

    # 3. doc_type is correct
    if fund.get("doc_type") not in ALLOWED_DOC_TYPES:
        errors.append(
            f"doc_type '{fund.get('doc_type')}' not in allowed set: {ALLOWED_DOC_TYPES}"
        )

    # 4. Groww URL must start with the Groww domain
    url = fund.get("groww_url", "")
    if not url.startswith(GROWW_DOMAIN):
        errors.append(f"groww_url does not start with '{GROWW_DOMAIN}': {url}")

    # 5. local_file must be in corpus/raw/
    local_file = fund.get("local_file", "")
    if not local_file.startswith("corpus/raw/") or not local_file.endswith(".html"):
        errors.append(
            f"local_file '{local_file}' must follow pattern 'corpus/raw/<name>.html'"
        )

    # 6. min_sip_inr must be a positive integer
    sip = fund.get("min_sip_inr")
    if sip is not None and (not isinstance(sip, int) or sip <= 0):
        errors.append(f"min_sip_inr must be a positive integer, got: {sip!r}")

    # 7. ingestion_date must be parseable
    try:
        date.fromisoformat(fund.get("ingestion_date", ""))
    except ValueError:
        errors.append(
            f"ingestion_date '{fund.get('ingestion_date')}' is not a valid ISO date (YYYY-MM-DD)"
        )

    # 8. is_duplicate must be False for active funds
    if fund.get("is_duplicate") is True:
        errors.append("is_duplicate=True fund should not appear in the active funds list")

    return errors


def check_duplicate_urls(funds: list[dict]) -> list[str]:
    """Returns warnings for any duplicate groww_url values within the active fund list."""
    seen = {}
    warnings = []
    for fund in funds:
        url = fund.get("groww_url", "")
        fid = fund.get("fund_id", "?")
        if url in seen:
            warnings.append(
                f"Duplicate URL across active funds: '{url}' in both "
                f"'{seen[url]}' and '{fid}'"
            )
        else:
            seen[url] = fid
    return warnings


def check_unique_fund_ids(funds: list[dict]) -> list[str]:
    """Returns errors for duplicate fund_id values."""
    seen = {}
    errors = []
    for fund in funds:
        fid = fund.get("fund_id", "")
        if fid in seen:
            errors.append(f"Duplicate fund_id: '{fid}'")
        else:
            seen[fid] = True
    return errors


def check_unique_local_files(funds: list[dict]) -> list[str]:
    """Returns errors for duplicate local_file paths."""
    seen = {}
    errors = []
    for fund in funds:
        lf = fund.get("local_file", "")
        fid = fund.get("fund_id", "?")
        if lf in seen:
            errors.append(
                f"Duplicate local_file path: '{lf}' used by both '{seen[lf]}' and '{fid}'"
            )
        else:
            seen[lf] = fid
    return errors


# ── Main ──────────────────────────────────────────────────────────────────────

def run_phase0_validation() -> bool:
    print(_bold("\n═══════════════════════════════════════════════════"))
    print(_bold("  Phase 0 — AMC & Scheme Selection: Validation"))
    print(_bold("═══════════════════════════════════════════════════\n"))

    data = load_sources()
    funds: list[dict] = data.get("funds", [])

    print(f"  AMC            : {data.get('amc', {}).get('name', 'N/A')}")
    print(f"  Ingestion date : {data.get('_meta', {}).get('ingestion_date', 'N/A')}")
    print(f"  Total funds    : {len(funds)}")
    print(f"  Total URLs     : {data.get('url_manifest', {}).get('total_urls', 'N/A')}")
    print(f"  Unique URLs    : {data.get('url_manifest', {}).get('unique_urls', 'N/A')}")
    print()

    all_passed = True
    fund_results = {}

    # ── Per-fund validation
    for fund in funds:
        fid = fund.get("fund_id", "unknown")
        fname = fund.get("fund_name", fid)
        errors = validate_fund(fund)

        if errors:
            all_passed = False
            fund_results[fid] = "FAIL"
            print(_red(f"  [FAIL] {fname}"))
            for err in errors:
                print(_red(f"         → {err}"))
        else:
            fund_results[fid] = "PASS"
            print(_green(f"  [PASS] {fname}"))

    print()

    # ── Cross-fund checks
    dup_url_warnings = check_duplicate_urls(funds)
    dup_id_errors = check_unique_fund_ids(funds)
    dup_file_errors = check_unique_local_files(funds)

    if dup_url_warnings:
        for w in dup_url_warnings:
            print(_yellow(f"  [WARN] {w}"))

    if dup_id_errors:
        all_passed = False
        for e in dup_id_errors:
            print(_red(f"  [FAIL] {e}"))

    if dup_file_errors:
        all_passed = False
        for e in dup_file_errors:
            print(_red(f"  [FAIL] {e}"))

    # ── Verify excluded_duplicates section exists
    excluded = data.get("excluded_duplicates", [])
    if not excluded:
        print(_yellow("  [WARN] 'excluded_duplicates' section is empty. Expected 1 entry (URL #7)."))
    else:
        print(_green(f"  [PASS] excluded_duplicates: {len(excluded)} entry/entries documented"))

    # ── Summary
    print()
    passed_count = sum(1 for v in fund_results.values() if v == "PASS")
    failed_count = len(fund_results) - passed_count

    print(_bold("─── Summary ────────────────────────────────────────"))
    print(f"  Funds passed : {passed_count} / {len(fund_results)}")
    print(f"  Funds failed : {failed_count} / {len(fund_results)}")

    if all_passed:
        print(_green("\n  ✔  Phase 0 validation PASSED. sources.json is ready for Phase 1.\n"))
        # Update validation_status in sources.json
        for fund in funds:
            fund["validation_status"] = "validated"
        data["_meta"]["last_validated"] = str(date.today())
        save_sources(data)
        print(f"  Updated: {SOURCES_FILE}\n")
    else:
        print(_red("\n  ✖  Phase 0 validation FAILED. Fix errors above before proceeding to Phase 1.\n"))

    return all_passed


if __name__ == "__main__":
    success = run_phase0_validation()
    sys.exit(0 if success else 1)
