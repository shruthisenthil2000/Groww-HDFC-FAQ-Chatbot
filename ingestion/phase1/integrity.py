"""
Phase 1.4 — De-duplicate & Integrity Check

Responsibility
--------------
Cross-check the ``list[FetchResult]`` produced by Phase 1.3 against the
filesystem before the scrape log is written and Phase 2 begins.

Phase 1.3 is the ground truth for what was *attempted*.
The filesystem is the ground truth for what was *actually written*.
Phase 1.4 verifies both layers agree.

Public API (to be implemented)
-------------------------------
verify_raw_corpus(results, funds, raw_dir) -> None
    Run all integrity checks. Raises IntegrityError with a full list of
    all blocking failures (never raises on the first failure alone).
    Passes silently if all checks pass.

IntegrityError(RuntimeError)
    Raised when one or more blocking integrity checks fail.
    Inherits RuntimeError; message lists every failure.

Checks performed (per architecture.md Phase 1.4)
-------------------------------------------------
FetchResult-level (primary):
  1. Exactly 14 results in list (one per active fund in sources.json).
  2. All 14 results have scrape_status = "success".
     - "failed"  → blocking error (network/HTTP failure in Phase 1.3).
     - "skipped" → blocking error (unexpected duplicate leaked through
                    Phase 1.1 / Phase 1.3 de-dup guards).
  3. All 14 results have http_status = 200.
  4. All 14 results have file_size_bytes > 0.

Filesystem cross-checks (secondary):
  5. For every success result: local_file exists on disk.
  6. On-disk file size matches result.file_size_bytes.
  7. On-disk file size > MIN_FILE_SIZE_BYTES — warns if below threshold
     but does NOT raise (Groww SSR page sizes vary).
  8. No orphan .html files in raw_dir that are not in the fund manifest
     — warns only, does not raise.

Failure policy:
  Checks 1-6 → blocking → IntegrityError
  Checks 7-8 → warnings → logged, no exception

Input  : list[FetchResult] from fetch_all() (Phase 1.3)
         + list[dict] funds from load_and_validate() (Phase 1.1)
         + raw_dir: Path (corpus/raw/)
Output : Passes silently; raises IntegrityError on blocking failure.
"""

from __future__ import annotations

import logging
from pathlib import Path

from ingestion.phase1.fetch import FetchResult

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

EXPECTED_FUND_COUNT: int = 15

# Heuristic lower bound for a valid Groww fund page.
# Groww pages can range from ~50 KB (minimal SSR) to several hundred KB.
# 5 KB is intentionally low to catch empty/truncated files only.
MIN_FILE_SIZE_BYTES: int = 5_120  # 5 KB


# ── Exception ─────────────────────────────────────────────────────────────────

class IntegrityError(RuntimeError):
    """
    Raised when one or more Phase 1.4 blocking checks fail.

    The message contains a bullet-list of every failure so the caller
    can fix them all in one pass rather than chasing them one at a time.
    """


# ── Public API ────────────────────────────────────────────────────────────────

def verify_raw_corpus(
    results: list[FetchResult],
    funds: list[dict],
    raw_dir: Path,
) -> None:
    """
    Cross-check Phase 1.3 fetch results against the filesystem.

    Args:
        results: list[FetchResult] returned by fetch_all() in Phase 1.3.
        funds:   Validated fund list from load_and_validate() in Phase 1.1.
        raw_dir: Path to corpus/raw/ directory.

    Returns:
        None — passes silently if all blocking checks pass.

    Raises:
        IntegrityError: One or more blocking checks failed.
            Message lists every failure found.
    """
    errors: list[str] = []
    warnings: list[str] = []

    expected_filenames = {Path(f["local_file"]).name for f in funds}

    # ── FetchResult-level checks (primary) ───────────────────────────────────

    # Check 1: result count
    if len(results) != EXPECTED_FUND_COUNT:
        errors.append(
            f"Expected {EXPECTED_FUND_COUNT} FetchResult entries, "
            f"got {len(results)}."
        )

    for r in results:
        label = r.fund_id

        # Check 2: scrape_status
        if r.scrape_status == "failed":
            msg = r.error_message or f"HTTP {r.http_status}"
            errors.append(
                f"[{label}] scrape_status='failed' — {msg}"
            )
        elif r.scrape_status == "skipped":
            errors.append(
                f"[{label}] scrape_status='skipped' — unexpected duplicate URL "
                f"'{r.groww_url}' leaked through Phase 1.1/1.3 de-dup guards. "
                "Check excluded_duplicates in sources.json."
            )

        # Check 3: http_status (only meaningful for attempted fetches)
        if r.scrape_status != "skipped" and r.http_status != 200:
            errors.append(
                f"[{label}] http_status={r.http_status} (expected 200)."
            )

        # Check 4: file_size_bytes reported by fetch
        if r.scrape_status == "success" and r.file_size_bytes <= 0:
            errors.append(
                f"[{label}] file_size_bytes={r.file_size_bytes} — "
                "fetch reported success but wrote zero bytes."
            )

    # ── Filesystem cross-checks (secondary) ──────────────────────────────────

    for r in results:
        if r.scrape_status != "success":
            continue

        label = r.fund_id

        # Check 5: file exists on disk
        if not r.local_file.exists():
            errors.append(
                f"[{label}] File not found on disk: {r.local_file} "
                "(fetch reported success but file is missing)."
            )
            continue  # skip size checks for missing files

        actual_size = r.local_file.stat().st_size

        # Check 6: on-disk size matches reported size
        if actual_size != r.file_size_bytes:
            errors.append(
                f"[{label}] On-disk size ({actual_size} bytes) does not match "
                f"FetchResult.file_size_bytes ({r.file_size_bytes} bytes). "
                "File may be truncated or corrupted."
            )

        # Check 7 (warning): file meets minimum size heuristic
        if actual_size < MIN_FILE_SIZE_BYTES:
            warnings.append(
                f"[{label}] File is only {actual_size} bytes "
                f"(below heuristic threshold of {MIN_FILE_SIZE_BYTES} bytes). "
                "Page may be minimal SSR or a redirect page — verify manually."
            )

    # Check 8 (warning): orphan files in corpus/raw/
    if raw_dir.exists():
        actual_html = {p.name for p in raw_dir.glob("*.html")}
        orphans = actual_html - expected_filenames
        for name in sorted(orphans):
            warnings.append(
                f"Orphan file in corpus/raw/: '{name}' "
                "is not in the fund manifest — consider removing."
            )

    # ── Emit warnings and raise if any blocking errors ────────────────────────

    for w in warnings:
        logger.warning("  [WARN] %s", w)

    if errors:
        count = len(errors)
        bullet = "\n  • ".join(errors)
        raise IntegrityError(
            f"Phase 1.4 integrity check failed "
            f"({count} blocking error{'s' if count != 1 else ''}):\n  • {bullet}"
        )

    logger.info(
        "Phase 1.4 integrity check passed — "
        "%d/%d files verified on disk.",
        EXPECTED_FUND_COUNT,
        EXPECTED_FUND_COUNT,
    )
