"""
Phase 1.3 — Fetch & Save Raw HTML (One File Per Fund)

Responsibility
--------------
Loop through the 14 active Groww URLs from the validated fund list
and save each page's full HTML to ``corpus/raw/<fund_id>.html``.

Public API
----------
fetch_and_save(fund, session, raw_dir) -> FetchResult
    Fetch one fund page and write raw bytes to disk.
    Never raises — errors are captured in FetchResult.scrape_status.

fetch_all(funds, session, raw_dir, *, delay=None) -> list[FetchResult]
    Call fetch_and_save for every fund in the list.
    Applies a polite delay between requests (default: SESSION_CONFIG value).
    Skips any URL already written to disk in this run (de-dup guard).

FetchResult
    fund_id          str   — matches fund["fund_id"] in sources.json
    groww_url        str   — the URL that was fetched
    local_file       Path  — absolute path to saved .html file
    http_status      int   — HTTP response code (0 on network error)
    file_size_bytes  int   — bytes written (0 on failure)
    fetched_at       str   — ISO-8601 UTC timestamp
    scrape_status    str   — "success" | "failed" | "skipped"
    error_message    str | None

Constraints (per architecture.md Phase 1.3)
-------------------------------------------
- Duplicate URLs must NOT produce a second file.
- Save raw response bytes; do not decode or modify HTML.
- On HTTP error or exception: mark status="failed", continue.
- Delay between requests comes from SESSION_CONFIG to keep it DRY.
"""

from __future__ import annotations

import time
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import requests

from ingestion.phase1.session import SESSION_CONFIG

# ── Logger ────────────────────────────────────────────────────────────────────

logger = logging.getLogger(__name__)

# ── Default paths ─────────────────────────────────────────────────────────────

# ingestion/phase1/fetch.py → .parent×3 = project root
_DEFAULT_RAW_DIR: Path = (
    Path(__file__).resolve().parent.parent.parent / "corpus" / "raw"
)

# ── FetchResult ───────────────────────────────────────────────────────────────

@dataclass
class FetchResult:
    """
    Immutable record of a single fund-page fetch attempt.

    Returned by ``fetch_and_save()`` and aggregated by ``fetch_all()``.
    Phase 1.5 serialises a list of FetchResult objects to scrape_log.json.
    """

    fund_id: str
    groww_url: str
    local_file: Path
    http_status: int = 0
    file_size_bytes: int = 0
    fetched_at: str = ""
    scrape_status: Literal["success", "failed", "skipped"] = "failed"
    error_message: str | None = None

    def is_success(self) -> bool:
        return self.scrape_status == "success"

    def as_log_dict(self) -> dict:
        """Serialisable dict for scrape_log.json (Phase 1.5)."""
        return {
            "fund_id": self.fund_id,
            "groww_url": self.groww_url,
            "local_file": str(self.local_file),
            "http_status": self.http_status,
            "file_size_bytes": self.file_size_bytes,
            "fetched_at": self.fetched_at,
            "scrape_status": self.scrape_status,
            "error_message": self.error_message,
        }


# ── Public API ────────────────────────────────────────────────────────────────

def fetch_and_save(
    fund: dict,
    session: requests.Session,
    raw_dir: Path | None = None,
) -> FetchResult:
    """
    Fetch one Groww fund page and write its raw HTML to disk.

    The file is saved to ``raw_dir / Path(fund["local_file"]).name``
    (e.g. ``corpus/raw/hdfc_mid_cap.html``).  If the file already
    exists from a prior run it is overwritten — the caller (fetch_all)
    tracks seen URLs to avoid redundant network calls.

    Args:
        fund:    A validated fund dict from Phase 1.1 load_and_validate().
                 Must contain "fund_id", "groww_url", "local_file".
        session: Configured requests.Session from Phase 1.2 build_session().
        raw_dir: Directory to write .html files into.
                 Defaults to corpus/raw/ at the project root.

    Returns:
        FetchResult with scrape_status "success" or "failed".
        Never raises — exceptions are caught and stored in error_message.
    """
    resolved_dir = raw_dir if raw_dir is not None else _DEFAULT_RAW_DIR

    fund_id = fund["fund_id"]
    url = fund["groww_url"]
    filename = Path(fund["local_file"]).name
    dest = resolved_dir / filename

    result = FetchResult(
        fund_id=fund_id,
        groww_url=url,
        local_file=dest,
        fetched_at=_utc_now(),
    )

    try:
        resolved_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Fetching [%s] %s", fund_id, url)
        response = session.get(
            url,
            timeout=SESSION_CONFIG["timeout_seconds"],
            allow_redirects=True,
        )
        result.http_status = response.status_code
        result.fetched_at = _utc_now()

        if response.status_code == 200:
            dest.write_bytes(response.content)
            result.file_size_bytes = len(response.content)
            result.scrape_status = "success"
            logger.info(
                "  Saved %s → %s (%d bytes)",
                fund_id,
                dest.name,
                result.file_size_bytes,
            )
        else:
            result.scrape_status = "failed"
            result.error_message = (
                f"HTTP {response.status_code} for {url}"
            )
            logger.warning(
                "  HTTP %d for [%s] %s",
                response.status_code,
                fund_id,
                url,
            )

    except requests.exceptions.Timeout:
        result.error_message = f"Timeout: request exceeded {SESSION_CONFIG['timeout_seconds']}s"
        result.scrape_status = "failed"
        logger.error("  Timeout [%s] %s", fund_id, url)

    except requests.exceptions.ConnectionError as exc:
        result.error_message = f"Connection error: {exc}"
        result.scrape_status = "failed"
        logger.error("  Connection error [%s]: %s", fund_id, exc)

    except requests.exceptions.RequestException as exc:
        result.error_message = f"Request error: {exc}"
        result.scrape_status = "failed"
        logger.error("  Request error [%s]: %s", fund_id, exc)

    except OSError as exc:
        result.error_message = f"File write error: {exc}"
        result.scrape_status = "failed"
        logger.error("  File write error [%s]: %s", fund_id, exc)

    return result


def fetch_all(
    funds: list[dict],
    session: requests.Session,
    raw_dir: Path | None = None,
    *,
    delay: float | None = None,
) -> list[FetchResult]:
    """
    Fetch all fund pages in the validated fund list.

    Iterates through every fund, calling ``fetch_and_save`` for each.
    A polite delay is applied between every request (even on failure)
    to avoid hammering the server.

    A URL already seen in this run is marked ``scrape_status="skipped"``
    and no network call is made — this is the de-duplication guard for
    the case where sources.json somehow still contains a duplicate URL
    that Phase 1.1 failed to catch.

    Args:
        funds:   Validated fund list from Phase 1.1 load_and_validate().
        session: Configured session from Phase 1.2 build_session().
        raw_dir: Target directory. Defaults to corpus/raw/.
        delay:   Override delay in seconds between requests.
                 Defaults to SESSION_CONFIG["delay_between_requests_seconds"].

    Returns:
        list[FetchResult] — one entry per fund, in input order.
    """
    effective_delay = (
        delay
        if delay is not None
        else SESSION_CONFIG["delay_between_requests_seconds"]
    )

    results: list[FetchResult] = []
    seen_urls: set[str] = set()
    resolved_dir = raw_dir if raw_dir is not None else _DEFAULT_RAW_DIR

    total = len(funds)
    for idx, fund in enumerate(funds, start=1):
        fund_id = fund.get("fund_id", f"unknown_{idx}")
        url = fund.get("groww_url", "")

        # De-duplication guard
        if url in seen_urls:
            dest = resolved_dir / Path(fund.get("local_file", f"{fund_id}.html")).name
            skipped = FetchResult(
                fund_id=fund_id,
                groww_url=url,
                local_file=dest,
                http_status=0,
                file_size_bytes=0,
                fetched_at=_utc_now(),
                scrape_status="skipped",
                error_message="Duplicate URL — skipped to avoid redundant fetch.",
            )
            results.append(skipped)
            logger.info(
                "[%d/%d] Skipped duplicate URL [%s]", idx, total, fund_id
            )
            continue

        seen_urls.add(url)
        logger.info("[%d/%d] Fetching %s", idx, total, fund_id)
        result = fetch_and_save(fund, session, resolved_dir)
        results.append(result)

        # Polite delay — applied after every request, including failures.
        if idx < total:
            logger.debug("  Waiting %.1fs before next request…", effective_delay)
            time.sleep(effective_delay)

    succeeded = sum(1 for r in results if r.is_success())
    failed = sum(1 for r in results if r.scrape_status == "failed")
    skipped = sum(1 for r in results if r.scrape_status == "skipped")
    logger.info(
        "fetch_all complete — %d succeeded, %d failed, %d skipped (of %d funds)",
        succeeded,
        failed,
        skipped,
        total,
    )
    return results


# ── Helpers ───────────────────────────────────────────────────────────────────

def _utc_now() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
