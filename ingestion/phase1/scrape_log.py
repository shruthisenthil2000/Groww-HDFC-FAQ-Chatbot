"""
Phase 1.5 — Write Scrape Log

Responsibility
--------------
Serialise the list[FetchResult] produced by Phase 1.3 (and validated by
Phase 1.4) into a machine-readable JSON audit trail at
``corpus/raw/scrape_log.json``.

The log serves three downstream purposes:
  1. Debugging   — human-readable record of what was fetched, when, and why
                   anything failed.
  2. Change detection — the ``content_hash_sha256`` field lets a corpus refresh
                   (Phase 7.2) detect which pages changed without re-fetching
                   all 14 URLs.
  3. Evaluation traceability — the log pins exact fetch timestamps so any
                   evaluation metric can be labelled with the ingestion date.

Public API
----------
write_scrape_log(results, raw_dir) -> Path
    Serialise results to scrape_log.json.
    Computes SHA-256 of each on-disk HTML file for change detection.
    Failed / skipped entries get an empty hash ("").
    Returns the Path of the written file.

load_scrape_log(raw_dir) -> dict
    Read and JSON-parse an existing scrape_log.json.
    Raises FileNotFoundError if the file does not exist.
    Useful for corpus-refresh diffing (Phase 7.2).

Log schema (per architecture.md Phase 1.5)
------------------------------------------
{
  "run_date":              "YYYY-MM-DD",
  "total_urls_attempted":  int,
  "total_urls_succeeded":  int,
  "total_urls_failed":     int,
  "entries": [
    {
      "fund_id":             str,
      "groww_url":           str,
      "local_file":          str,   // relative path: "corpus/raw/<name>.html"
      "http_status":         int,
      "file_size_bytes":     int,
      "content_hash_sha256": str,   // SHA-256 hex; "" for failed/skipped
      "fetched_at":          str,   // ISO-8601 UTC
      "scrape_status":       "success" | "failed" | "skipped"
    }
  ]
}

Input  : list[FetchResult] from Phase 1.3 fetch_all()
Output : corpus/raw/scrape_log.json
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import date
from pathlib import Path

from ingestion.phase1.fetch import FetchResult

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

SCRAPE_LOG_FILENAME: str = "scrape_log.json"

# Prefix used when recording local_file as a relative path in the log.
# Matches the format used in sources.json ("corpus/raw/<fund_id>.html").
_RELATIVE_PREFIX: str = "corpus/raw"

# ── Public API ────────────────────────────────────────────────────────────────

def write_scrape_log(
    results: list[FetchResult],
    raw_dir: Path,
) -> Path:
    """
    Serialise fetch results to ``corpus/raw/scrape_log.json``.

    For every successful result the on-disk HTML file is read and hashed
    (SHA-256) for change-detection in future corpus refresh runs.
    Failed and skipped results get ``content_hash_sha256 = ""``.

    Args:
        results: list[FetchResult] returned by Phase 1.3 fetch_all().
        raw_dir: Directory that contains the saved .html files and will
                 receive scrape_log.json.  Typically ``corpus/raw/``.

    Returns:
        Path of the written scrape_log.json file.
    """
    entries = []
    for r in results:
        sha256 = _compute_hash(r.local_file) if r.scrape_status == "success" else ""
        entries.append({
            "fund_id":             r.fund_id,
            "groww_url":           r.groww_url,
            "local_file":          f"{_RELATIVE_PREFIX}/{r.local_file.name}",
            "http_status":         r.http_status,
            "file_size_bytes":     r.file_size_bytes,
            "content_hash_sha256": sha256,
            "fetched_at":          r.fetched_at,
            "scrape_status":       r.scrape_status,
        })

    succeeded = sum(1 for r in results if r.scrape_status == "success")
    failed    = sum(1 for r in results if r.scrape_status == "failed")

    log: dict = {
        "run_date":             str(date.today()),
        "total_urls_attempted": len(results),
        "total_urls_succeeded": succeeded,
        "total_urls_failed":    failed,
        "entries":              entries,
    }

    raw_dir.mkdir(parents=True, exist_ok=True)
    out = raw_dir / SCRAPE_LOG_FILENAME
    out.write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")

    logger.info(
        "Scrape log written → %s  (%d succeeded, %d failed, %d total)",
        out,
        succeeded,
        failed,
        len(results),
    )
    return out


def load_scrape_log(raw_dir: Path) -> dict:
    """
    Read and return an existing scrape_log.json as a dict.

    Args:
        raw_dir: Directory that contains scrape_log.json.

    Returns:
        Parsed dict matching the Phase 1.5 log schema.

    Raises:
        FileNotFoundError: scrape_log.json is not present in raw_dir.
        json.JSONDecodeError: file exists but contains invalid JSON.
    """
    path = raw_dir / SCRAPE_LOG_FILENAME
    if not path.exists():
        raise FileNotFoundError(
            f"scrape_log.json not found at {path}. "
            "Run Phase 1.5 write_scrape_log() first."
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    logger.debug("Loaded scrape log from %s (%d entries)", path, len(data.get("entries", [])))
    return data


# ── Helpers ───────────────────────────────────────────────────────────────────

def _compute_hash(file_path: Path) -> str:
    """
    Return the lowercase hex SHA-256 digest of a file's raw bytes.
    Returns "" if the file does not exist (defensive — caller should
    only pass success-result paths, but guards against mid-run deletion).
    """
    if not file_path.exists():
        logger.warning("Cannot hash %s — file not found; storing empty hash.", file_path)
        return ""
    return hashlib.sha256(file_path.read_bytes()).hexdigest()
