"""
Phase 1.7 — Corpus Integrity & Readiness Check

Hard gate before Phase 2: validates the persisted on-disk corpus state.

Unlike Phase 1.4 (which validates in-memory FetchResult objects right after
fetching), this module reads only from disk and can be run independently —
at the start of a new session, after manual edits, or as the GitHub Actions
gate before triggering re-ingestion.

Four checks are run (see architecture.md §1.7 for the full rationale):

  Check 1  HTML completeness      (blocking) — all 14 .html files present
  Check 2  Minimum file size      (blocking) — each file ≥ MIN_HTML_BYTES
  Check 3  Scrape log consistency (blocking) — scrape_log.json valid, no failures
  Check 4  Chunk file integrity   (warn-only) — chunks.jsonl schema + count

All blocking checks run before raising so the caller sees every problem
at once (fail loudly, fail completely — no silent skips).

Public API
----------
check_readiness(funds, raw_dir, processed_dir) -> ReadinessReport
    Validate corpus readiness. Raises ReadinessError if blocking checks fail.
    Returns the ReadinessReport dict in all cases (even if exception is raised
    the report is populated before the raise so callers can inspect it).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from ingestion.phase1.integrity import MIN_FILE_SIZE_BYTES
from ingestion.phase1.scrape_log import SCRAPE_LOG_FILENAME

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

# Minimum number of chunks expected in a well-formed chunks.jsonl
# (14 funds × 5 sections minimum = 70; architecture targets ~85)
MIN_EXPECTED_CHUNKS: int = 70

# Required fields in every chunks.jsonl entry (architecture.md §2.2.4)
REQUIRED_CHUNK_FIELDS: frozenset[str] = frozenset(
    {"chunk_id", "fund_id", "text", "section_type"}
)

CHUNKS_JSONL_FILENAME: str = "chunks.jsonl"


# ── Exception ──────────────────────────────────────────────────────────────────

class ReadinessError(RuntimeError):
    """
    Raised when one or more blocking readiness checks fail.

    The exception message lists every blocking failure so the operator can
    fix all issues in a single iteration rather than discovering them one
    by one.
    """


# ── Individual checks ──────────────────────────────────────────────────────────

def _check_html_completeness(
    funds: list[dict],
    raw_dir: Path,
) -> dict:
    """
    Check 1 (blocking): all fund HTML files are present in raw_dir.

    Returns a result dict with keys: passed, found, missing.
    """
    missing: list[str] = []
    for fund in funds:
        html_path = raw_dir / f"{fund['fund_id']}.html"
        if not html_path.exists():
            missing.append(fund["fund_id"])

    return {
        "passed":  len(missing) == 0,
        "found":   len(funds) - len(missing),
        "missing": missing,
    }


def _check_file_sizes(
    funds: list[dict],
    raw_dir: Path,
) -> dict:
    """
    Check 2 (blocking): every HTML file is at least MIN_FILE_SIZE_BYTES.

    Files that don't exist are skipped here — Check 1 already caught them.
    Returns a result dict with keys: passed, undersized.
    """
    undersized: list[dict] = []
    for fund in funds:
        html_path = raw_dir / f"{fund['fund_id']}.html"
        if not html_path.exists():
            continue
        size = html_path.stat().st_size
        if size < MIN_FILE_SIZE_BYTES:
            undersized.append({"fund_id": fund["fund_id"], "size_bytes": size})

    return {
        "passed":     len(undersized) == 0,
        "undersized": undersized,
    }


def _check_scrape_log(raw_dir: Path) -> dict:
    """
    Check 3 (blocking): scrape_log.json exists and contains no 'failed' entries.

    Skipped entries produce a warning but are not blocking (they represent
    duplicate URLs intentionally excluded by Phase 1.3). Failed entries
    mean the HTTP fetch itself broke and the HTML is not trustworthy.

    Returns a result dict with keys: passed, failed_entries, skipped_entries.
    """
    log_path = raw_dir / SCRAPE_LOG_FILENAME
    if not log_path.exists():
        return {
            "passed":          False,
            "failed_entries":  -1,    # -1 = log absent (special sentinel)
            "skipped_entries": 0,
            "error":           f"{log_path} not found — run Phase 1.5 first.",
        }

    try:
        log_data = json.loads(log_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {
            "passed":          False,
            "failed_entries":  -1,
            "skipped_entries": 0,
            "error":           f"scrape_log.json is not valid JSON: {exc}",
        }

    entries = log_data.get("entries", [])
    failed_entries  = [e["fund_id"] for e in entries if e.get("scrape_status") == "failed"]
    skipped_entries = [e["fund_id"] for e in entries if e.get("scrape_status") == "skipped"]

    return {
        "passed":          len(failed_entries) == 0,
        "failed_entries":  len(failed_entries),
        "skipped_entries": len(skipped_entries),
        **({"failed_fund_ids": failed_entries} if failed_entries else {}),
    }


def _check_chunk_file(processed_dir: Path | None) -> dict:
    """
    Check 4 (warn-only): if chunks.jsonl exists from a prior Phase 2 run,
    validate its schema and total count.

    Absence of chunks.jsonl is not an error — it will be created by Phase 2.
    Returns a result dict with keys: passed, chunks_found, schema_errors.
    """
    if processed_dir is None:
        return {"passed": True, "chunks_found": 0, "schema_errors": [], "skipped": True}

    chunks_path = processed_dir / CHUNKS_JSONL_FILENAME
    if not chunks_path.exists():
        return {"passed": True, "chunks_found": 0, "schema_errors": [], "absent": True}

    schema_errors: list[str] = []
    count = 0

    try:
        for lineno, line in enumerate(
            chunks_path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            line = line.strip()
            if not line:
                continue
            try:
                chunk = json.loads(line)
            except json.JSONDecodeError as exc:
                schema_errors.append(f"Line {lineno}: JSON parse error — {exc}")
                continue

            count += 1
            missing_fields = REQUIRED_CHUNK_FIELDS - set(chunk.keys())
            if missing_fields:
                schema_errors.append(
                    f"Line {lineno} (chunk_id={chunk.get('chunk_id','?')}): "
                    f"missing fields {sorted(missing_fields)}"
                )
    except OSError as exc:
        schema_errors.append(f"Could not read {chunks_path}: {exc}")

    count_ok = count >= MIN_EXPECTED_CHUNKS
    passed   = len(schema_errors) == 0 and count_ok

    result: dict = {
        "passed":       passed,
        "chunks_found": count,
        "schema_errors": schema_errors[:10],  # cap at 10 to keep report readable
    }
    if not count_ok and count > 0:
        result["count_warning"] = (
            f"Only {count} chunks found; expected ≥ {MIN_EXPECTED_CHUNKS}. "
            "Re-run Phase 2 to regenerate."
        )
    return result


# ── Public API ─────────────────────────────────────────────────────────────────

def check_readiness(
    funds: list[dict],
    raw_dir: Path,
    processed_dir: Path | None = None,
) -> dict:
    """
    Validate corpus is complete and ready for Phase 2.

    Runs all four checks (§1.7) and returns a ReadinessReport dict.
    Raises ReadinessError if any blocking check fails, but the report is
    fully populated before the exception is raised.

    Args:
        funds:         Validated fund list from Phase 1.1 load_and_validate().
        raw_dir:       Path to corpus/raw/ (HTML files + scrape_log.json).
        processed_dir: Path to corpus/processed/ (optional; enables Check 4).

    Returns:
        ReadinessReport dict (see architecture.md §1.7 for schema).

    Raises:
        ReadinessError: One or more blocking checks failed. All failures are
                        listed in the exception message and in the report's
                        "blocking_failures" field.
    """
    checked_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # ── Run all four checks ────────────────────────────────────────────────────
    html_check   = _check_html_completeness(funds, raw_dir)
    size_check   = _check_file_sizes(funds, raw_dir)
    log_check    = _check_scrape_log(raw_dir)
    chunk_check  = _check_chunk_file(processed_dir)

    # ── Collect blocking failures ──────────────────────────────────────────────
    blocking_failures: list[str] = []
    warnings: list[str] = []

    if not html_check["passed"]:
        blocking_failures.append(
            f"Check 1 HTML completeness FAILED: "
            f"{len(html_check['missing'])} file(s) missing — {html_check['missing']}"
        )

    if not size_check["passed"]:
        details = [
            f"{e['fund_id']} ({e['size_bytes']} bytes)"
            for e in size_check["undersized"]
        ]
        blocking_failures.append(
            f"Check 2 File size FAILED: {len(details)} file(s) below "
            f"{MIN_FILE_SIZE_BYTES} bytes — {details}"
        )

    if not log_check["passed"]:
        err = log_check.get("error", "")
        failed_ids = log_check.get("failed_fund_ids", [])
        blocking_failures.append(
            f"Check 3 Scrape log FAILED: "
            + (err if err else f"{len(failed_ids)} failed fund(s) — {failed_ids}")
        )

    # Check 4 is warn-only
    if not chunk_check["passed"]:
        schema_errs = chunk_check.get("schema_errors", [])
        count_warn  = chunk_check.get("count_warning", "")
        if schema_errs:
            warnings.append(
                f"Check 4 Chunk file schema: {len(schema_errs)} error(s) — "
                f"{schema_errs[0]}"
            )
        if count_warn:
            warnings.append(f"Check 4 Chunk count: {count_warn}")

    # Log scrape-log skipped entries as a warning (not blocking)
    if log_check.get("skipped_entries", 0) > 0:
        warnings.append(
            f"{log_check['skipped_entries']} fund(s) were skipped during scraping "
            "(likely duplicate URLs — this is expected)."
        )

    # ── Assemble report ────────────────────────────────────────────────────────
    ready = len(blocking_failures) == 0
    report: dict = {
        "ready":      ready,
        "checked_at": checked_at,
        "checks": {
            "html_completeness":      html_check,
            "file_sizes":             size_check,
            "scrape_log_consistency": log_check,
            "chunk_file_integrity":   chunk_check,
        },
        "blocking_failures": blocking_failures,
        "warnings":          warnings,
    }

    # ── Log summary ────────────────────────────────────────────────────────────
    check_symbols = {
        "html_completeness":      "1",
        "file_sizes":             "2",
        "scrape_log_consistency": "3",
        "chunk_file_integrity":   "4",
    }
    for name, symbol in check_symbols.items():
        result = report["checks"][name]
        status = "PASS" if result["passed"] else ("WARN" if name == "chunk_file_integrity" else "FAIL")
        logger.info("  Check %s %-26s %s", symbol, name, status)

    for w in warnings:
        logger.warning("  [WARN] %s", w)

    if ready:
        logger.info(
            "  ✔  Corpus is ready — %d HTML files verified, scrape log consistent.",
            html_check["found"],
        )
    else:
        logger.error(
            "  ✖  Corpus NOT ready — %d blocking failure(s). Phase 2 must not run.",
            len(blocking_failures),
        )
        raise ReadinessError(
            f"Corpus readiness check failed ({len(blocking_failures)} blocking failure(s)):\n"
            + "\n".join(f"  • {f}" for f in blocking_failures)
        )

    return report
