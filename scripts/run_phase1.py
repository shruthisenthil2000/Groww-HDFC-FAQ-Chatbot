"""
Phase 1 Pipeline Runner — Chains subphases 1.1 → 1.7

Usage
-----
    python3 scripts/run_phase1.py

Runs each Phase 1 subphase in sequence:

  1.1  Load & validate corpus/sources.json      (manifest.py)
  1.2  Configure HTTP scraper session           (session.py)
  1.3  Fetch & save raw HTML (14 Groww pages)   (fetch.py)
  1.4  Integrity check all fetched files        (integrity.py)
  1.5  Write scrape_log.json audit trail        (scrape_log.py)
  1.7  Corpus integrity & readiness gate        (readiness.py)

Output
------
  corpus/raw/<fund_id>.html   — one saved page per fund
  corpus/raw/scrape_log.json  — machine-readable audit trail
  ReadinessReport             — logged summary; blocks Phase 2 if not ready

Exit codes
----------
  0  All phases completed successfully; corpus is ready for Phase 2
  1  A phase raised a blocking error (details printed to stderr)
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# ── project root on sys.path ──────────────────────────────────────────────────
# Run from the project root:  python3 scripts/run_phase1.py
# The script adds the project root so that "ingestion.*" imports resolve
# even without installing the package.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ingestion.phase1.manifest import ManifestError, load_and_validate
from ingestion.phase1.session import SESSION_CONFIG, build_session
from ingestion.phase1.fetch import fetch_all
from ingestion.phase1.integrity import IntegrityError, verify_raw_corpus
from ingestion.phase1.scrape_log import write_scrape_log
from ingestion.phase1.readiness import ReadinessError, check_readiness

# ── logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

RAW_DIR = PROJECT_ROOT / "corpus" / "raw"

# ── pipeline ──────────────────────────────────────────────────────────────────

def _sep(title: str) -> None:
    logger.info("─" * 60)
    logger.info("  %s", title)
    logger.info("─" * 60)


def main() -> int:
    # ── Phase 1.1: load & validate sources.json ───────────────────────────────
    _sep("Phase 1.1 — Load & Validate sources.json")
    try:
        funds = load_and_validate()
    except ManifestError as exc:
        logger.error("Phase 1.1 FAILED:\n%s", exc)
        return 1
    logger.info("  ✔  %d funds loaded from sources.json", len(funds))

    # ── Phase 1.2: build HTTP session ─────────────────────────────────────────
    _sep("Phase 1.2 — Configure HTTP Scraper Session")
    session = build_session()
    logger.info(
        "  ✔  Session ready  (timeout=%ds, delay=%ds, retries=%d)",
        SESSION_CONFIG["timeout_seconds"],
        SESSION_CONFIG["delay_between_requests_seconds"],
        SESSION_CONFIG["max_retries"],
    )

    # ── Phase 1.3: fetch all pages ────────────────────────────────────────────
    _sep("Phase 1.3 — Fetch & Save Raw HTML")
    logger.info("  Saving HTML files to: %s", RAW_DIR)
    results = fetch_all(funds, session, RAW_DIR)

    succeeded = sum(1 for r in results if r.scrape_status == "success")
    failed    = sum(1 for r in results if r.scrape_status == "failed")
    skipped   = sum(1 for r in results if r.scrape_status == "skipped")
    logger.info(
        "  ✔  Fetch complete — %d succeeded, %d failed, %d skipped",
        succeeded, failed, skipped,
    )
    if failed:
        logger.warning("  Failed funds:")
        for r in results:
            if r.scrape_status == "failed":
                logger.warning("    [%s] %s", r.fund_id, r.error_message)

    # ── Phase 1.4: integrity check ────────────────────────────────────────────
    _sep("Phase 1.4 — Integrity Check")
    try:
        verify_raw_corpus(results, funds, RAW_DIR)
        logger.info("  ✔  All integrity checks passed")
    except IntegrityError as exc:
        logger.error("Phase 1.4 FAILED:\n%s", exc)
        # Still write the scrape log so failures are documented
        _sep("Phase 1.5 — Write Scrape Log (partial — integrity failed)")
        log_path = write_scrape_log(results, RAW_DIR)
        logger.info("  ✔  Partial scrape log written → %s", log_path)
        return 1

    # ── Phase 1.5: write scrape log ───────────────────────────────────────────
    _sep("Phase 1.5 — Write Scrape Log")
    log_path = write_scrape_log(results, RAW_DIR)
    logger.info("  ✔  Scrape log written → %s", log_path)

    # ── Phase 1.7: corpus readiness gate ──────────────────────────────────────
    _sep("Phase 1.7 — Corpus Integrity & Readiness Check")
    processed_dir = PROJECT_ROOT / "corpus" / "processed"
    try:
        report = check_readiness(funds, RAW_DIR, processed_dir)
        logger.info("  ✔  Corpus is ready for Phase 2")
    except ReadinessError as exc:
        logger.error("Phase 1.7 FAILED — corpus is NOT ready for Phase 2:\n%s", exc)
        return 1

    _sep("Phase 1 COMPLETE")
    logger.info(
        "  Deliverables:\n"
        "    corpus/raw/               — %d HTML files\n"
        "    corpus/raw/scrape_log.json\n"
        "    ReadinessReport           — ready=%s",
        succeeded,
        report["ready"],
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
