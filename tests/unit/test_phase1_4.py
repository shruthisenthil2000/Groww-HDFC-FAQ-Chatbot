"""
Phase 1.4 — Unit tests for ingestion/phase1/integrity.py

All filesystem interactions use pytest's tmp_path fixture.
No real network calls are made.

Coverage
--------
IntegrityError
  - Is a subclass of RuntimeError
  - Can be raised and caught as RuntimeError

verify_raw_corpus() — Check 1: result count
  - Exactly 14 results → passes
  - 13 results          → IntegrityError
  - 15 results          → IntegrityError
  - 0 results           → IntegrityError

verify_raw_corpus() — Check 2: scrape_status
  - All "success"                      → passes
  - One "failed"                       → IntegrityError, fund_id in message
  - One "skipped"                      → IntegrityError, "unexpected duplicate" in message
  - Multiple "failed"                  → single IntegrityError listing all fund_ids
  - "failed" with error_message        → error_message included in IntegrityError text
  - "failed" with no error_message     → falls back to HTTP status in message

verify_raw_corpus() — Check 3: http_status
  - http_status=200 on success         → passes
  - http_status=404 on success         → IntegrityError
  - http_status=503 on success         → IntegrityError
  - http_status=0 on "skipped"         → NOT a blocking error (skipped exempt)
  - http_status=0 on "failed"          → not re-raised by check 3 (check 2 already caught it)

verify_raw_corpus() — Check 4: file_size_bytes
  - file_size_bytes > 0 on success     → passes
  - file_size_bytes = 0 on success     → IntegrityError
  - file_size_bytes = 0 on failed      → not raised (check 4 only applies to "success")

verify_raw_corpus() — Check 5: file exists on disk
  - File present for every success     → passes
  - File absent for a success result   → IntegrityError, path in message
  - Missing file: size checks skipped  → only one error per missing file (no double-error)

verify_raw_corpus() — Check 6: on-disk size vs reported size
  - Exact match                        → passes
  - On-disk size > reported            → IntegrityError
  - On-disk size < reported            → IntegrityError

verify_raw_corpus() — Check 7: min-size warning (non-blocking)
  - File size >= MIN_FILE_SIZE_BYTES   → no warning
  - File size < MIN_FILE_SIZE_BYTES    → warning logged, no IntegrityError raised
  - File size == 1 byte                → warning logged only

verify_raw_corpus() — Check 8: orphan files (non-blocking)
  - No orphan .html files              → passes silently
  - Orphan .html in raw_dir            → warning logged, no IntegrityError
  - Multiple orphans                   → warning per orphan

Error accumulation
  - All blocking checks run before raising — single IntegrityError lists every failure
  - Warning-only run (checks 7+8 trigger) → no exception raised

Happy path
  - 14 success results, all files on disk, correct sizes → passes silently
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from ingestion.phase1.fetch import FetchResult
from ingestion.phase1.integrity import (
    EXPECTED_FUND_COUNT,
    MIN_FILE_SIZE_BYTES,
    IntegrityError,
    verify_raw_corpus,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

_GOOD_HTML = b"<html><body>Fund page content</body></html>" * 300  # ~13 KB


def _fund(
    fund_id: str,
    raw_dir: Path,
    groww_url: str | None = None,
) -> dict:
    """Return a minimal fund dict as produced by Phase 1.1 load_and_validate()."""
    url = groww_url or f"https://groww.in/mutual-funds/{fund_id}-direct-growth"
    return {
        "fund_id": fund_id,
        "groww_url": url,
        "local_file": f"corpus/raw/{fund_id}.html",
    }


def _result(
    fund_id: str,
    raw_dir: Path,
    scrape_status: str = "success",
    http_status: int = 200,
    content: bytes = _GOOD_HTML,
    error_message: str | None = None,
    groww_url: str | None = None,
) -> FetchResult:
    """Build a FetchResult pointing at tmp_path."""
    url = groww_url or f"https://groww.in/mutual-funds/{fund_id}-direct-growth"
    dest = raw_dir / f"{fund_id}.html"
    size = len(content) if scrape_status == "success" else 0
    return FetchResult(
        fund_id=fund_id,
        groww_url=url,
        local_file=dest,
        http_status=http_status,
        file_size_bytes=size,
        fetched_at="2026-05-08T12:00:00Z",
        scrape_status=scrape_status,  # type: ignore[arg-type]
        error_message=error_message,
    )


def _make_14(raw_dir: Path) -> tuple[list[FetchResult], list[dict]]:
    """Return 14 success FetchResults and matching fund dicts, files written to disk."""
    fund_ids = [f"hdfc_fund_{i:02d}" for i in range(EXPECTED_FUND_COUNT)]
    raw_dir.mkdir(parents=True, exist_ok=True)
    results = []
    funds = []
    for fid in fund_ids:
        r = _result(fid, raw_dir)
        r.local_file.write_bytes(_GOOD_HTML)
        results.append(r)
        funds.append(_fund(fid, raw_dir))
    return results, funds


# ── IntegrityError ─────────────────────────────────────────────────────────────

class TestIntegrityError:
    def test_is_runtime_error(self):
        assert issubclass(IntegrityError, RuntimeError)

    def test_can_be_raised_and_caught_as_runtime_error(self):
        with pytest.raises(RuntimeError):
            raise IntegrityError("test failure")

    def test_message_preserved(self):
        msg = "something went wrong"
        exc = IntegrityError(msg)
        assert msg in str(exc)


# ── Check 1: result count ──────────────────────────────────────────────────────

class TestCheck1ResultCount:
    def test_exactly_14_passes(self, tmp_path):
        raw_dir = tmp_path / "raw"
        results, funds = _make_14(raw_dir)
        verify_raw_corpus(results, funds, raw_dir)  # no exception

    def test_13_results_raises(self, tmp_path):
        raw_dir = tmp_path / "raw"
        results, funds = _make_14(raw_dir)
        with pytest.raises(IntegrityError) as exc_info:
            verify_raw_corpus(results[:13], funds, raw_dir)
        assert "13" in str(exc_info.value)

    def test_15_results_raises(self, tmp_path):
        raw_dir = tmp_path / "raw"
        results, funds = _make_14(raw_dir)
        extra = _result("hdfc_extra", raw_dir)
        raw_dir.mkdir(parents=True, exist_ok=True)
        extra.local_file.write_bytes(_GOOD_HTML)
        with pytest.raises(IntegrityError) as exc_info:
            verify_raw_corpus(results + [extra], funds, raw_dir)
        assert "15" in str(exc_info.value)

    def test_zero_results_raises(self, tmp_path):
        raw_dir = tmp_path / "raw"
        _, funds = _make_14(raw_dir)
        with pytest.raises(IntegrityError):
            verify_raw_corpus([], funds, raw_dir)


# ── Check 2: scrape_status ─────────────────────────────────────────────────────

class TestCheck2ScrapeStatus:
    def test_all_success_passes(self, tmp_path):
        raw_dir = tmp_path / "raw"
        results, funds = _make_14(raw_dir)
        verify_raw_corpus(results, funds, raw_dir)

    def test_one_failed_raises(self, tmp_path):
        raw_dir = tmp_path / "raw"
        results, funds = _make_14(raw_dir)
        results[0] = _result(
            results[0].fund_id, raw_dir,
            scrape_status="failed",
            http_status=0,
            error_message="Connection refused",
        )
        with pytest.raises(IntegrityError) as exc_info:
            verify_raw_corpus(results, funds, raw_dir)
        assert results[0].fund_id in str(exc_info.value)

    def test_failed_error_message_included(self, tmp_path):
        raw_dir = tmp_path / "raw"
        results, funds = _make_14(raw_dir)
        results[3] = _result(
            results[3].fund_id, raw_dir,
            scrape_status="failed",
            error_message="Timeout: request exceeded 30s",
        )
        with pytest.raises(IntegrityError) as exc_info:
            verify_raw_corpus(results, funds, raw_dir)
        assert "Timeout" in str(exc_info.value)

    def test_failed_no_error_message_uses_http_status(self, tmp_path):
        raw_dir = tmp_path / "raw"
        results, funds = _make_14(raw_dir)
        results[0] = _result(
            results[0].fund_id, raw_dir,
            scrape_status="failed",
            http_status=503,
            error_message=None,
        )
        with pytest.raises(IntegrityError) as exc_info:
            verify_raw_corpus(results, funds, raw_dir)
        assert "503" in str(exc_info.value)

    def test_one_skipped_raises_with_duplicate_message(self, tmp_path):
        raw_dir = tmp_path / "raw"
        results, funds = _make_14(raw_dir)
        results[2] = _result(
            results[2].fund_id, raw_dir,
            scrape_status="skipped",
            http_status=0,
        )
        with pytest.raises(IntegrityError) as exc_info:
            verify_raw_corpus(results, funds, raw_dir)
        msg = str(exc_info.value)
        assert "skipped" in msg.lower() or "duplicate" in msg.lower()

    def test_multiple_failed_all_listed_in_one_error(self, tmp_path):
        raw_dir = tmp_path / "raw"
        results, funds = _make_14(raw_dir)
        results[0] = _result(results[0].fund_id, raw_dir, scrape_status="failed")
        results[5] = _result(results[5].fund_id, raw_dir, scrape_status="failed")
        results[9] = _result(results[9].fund_id, raw_dir, scrape_status="failed")
        with pytest.raises(IntegrityError) as exc_info:
            verify_raw_corpus(results, funds, raw_dir)
        msg = str(exc_info.value)
        assert results[0].fund_id in msg
        assert results[5].fund_id in msg
        assert results[9].fund_id in msg


# ── Check 3: http_status ───────────────────────────────────────────────────────

class TestCheck3HttpStatus:
    def test_http_200_passes(self, tmp_path):
        raw_dir = tmp_path / "raw"
        results, funds = _make_14(raw_dir)
        verify_raw_corpus(results, funds, raw_dir)

    def test_http_404_on_success_raises(self, tmp_path):
        raw_dir = tmp_path / "raw"
        results, funds = _make_14(raw_dir)
        # Manually set http_status to 404 while keeping scrape_status = "success"
        r = results[1]
        results[1] = FetchResult(
            fund_id=r.fund_id,
            groww_url=r.groww_url,
            local_file=r.local_file,
            http_status=404,
            file_size_bytes=r.file_size_bytes,
            fetched_at=r.fetched_at,
            scrape_status="success",
        )
        with pytest.raises(IntegrityError) as exc_info:
            verify_raw_corpus(results, funds, raw_dir)
        assert "404" in str(exc_info.value)

    def test_http_503_on_success_raises(self, tmp_path):
        raw_dir = tmp_path / "raw"
        results, funds = _make_14(raw_dir)
        r = results[4]
        results[4] = FetchResult(
            fund_id=r.fund_id,
            groww_url=r.groww_url,
            local_file=r.local_file,
            http_status=503,
            file_size_bytes=r.file_size_bytes,
            fetched_at=r.fetched_at,
            scrape_status="success",
        )
        with pytest.raises(IntegrityError) as exc_info:
            verify_raw_corpus(results, funds, raw_dir)
        assert "503" in str(exc_info.value)

    def test_skipped_with_http_0_not_a_blocking_error(self, tmp_path):
        """A skipped result has http_status=0 by design — check 3 must not fire for it."""
        raw_dir = tmp_path / "raw"
        results, funds = _make_14(raw_dir)
        # Replace with skipped (http_status=0) — this should trigger check 2, not check 3
        results[0] = _result(
            results[0].fund_id, raw_dir,
            scrape_status="skipped",
            http_status=0,
        )
        with pytest.raises(IntegrityError) as exc_info:
            verify_raw_corpus(results, funds, raw_dir)
        # Must mention "skipped"/"duplicate", NOT a bare "http_status=0" error
        msg = str(exc_info.value)
        assert "skipped" in msg.lower() or "duplicate" in msg.lower()
        assert "http_status=0" not in msg


# ── Check 4: file_size_bytes ───────────────────────────────────────────────────

class TestCheck4FileSizeBytes:
    def test_positive_size_passes(self, tmp_path):
        raw_dir = tmp_path / "raw"
        results, funds = _make_14(raw_dir)
        verify_raw_corpus(results, funds, raw_dir)

    def test_zero_bytes_on_success_raises(self, tmp_path):
        raw_dir = tmp_path / "raw"
        results, funds = _make_14(raw_dir)
        r = results[6]
        results[6] = FetchResult(
            fund_id=r.fund_id,
            groww_url=r.groww_url,
            local_file=r.local_file,
            http_status=200,
            file_size_bytes=0,        # zero bytes but success
            fetched_at=r.fetched_at,
            scrape_status="success",
        )
        with pytest.raises(IntegrityError) as exc_info:
            verify_raw_corpus(results, funds, raw_dir)
        assert r.fund_id in str(exc_info.value)

    def test_zero_bytes_on_failed_not_blocked_by_check4(self, tmp_path):
        """file_size_bytes=0 on a failed result is normal — check 4 must not fire."""
        raw_dir = tmp_path / "raw"
        results, funds = _make_14(raw_dir)
        results[0] = _result(
            results[0].fund_id, raw_dir,
            scrape_status="failed",
            http_status=0,
            content=b"",
            error_message="timeout",
        )
        # Check 2 will fire (scrape_status="failed"). Check 4 must NOT add a second error.
        with pytest.raises(IntegrityError) as exc_info:
            verify_raw_corpus(results, funds, raw_dir)
        msg = str(exc_info.value)
        # Only one blocking error (check 2), not two
        assert msg.count("•") == 1 or "file_size_bytes" not in msg


# ── Check 5: file exists on disk ───────────────────────────────────────────────

class TestCheck5FileExists:
    def test_all_files_present_passes(self, tmp_path):
        raw_dir = tmp_path / "raw"
        results, funds = _make_14(raw_dir)
        verify_raw_corpus(results, funds, raw_dir)

    def test_missing_file_raises(self, tmp_path):
        raw_dir = tmp_path / "raw"
        results, funds = _make_14(raw_dir)
        # Remove one of the files from disk
        results[3].local_file.unlink()
        with pytest.raises(IntegrityError) as exc_info:
            verify_raw_corpus(results, funds, raw_dir)
        assert results[3].fund_id in str(exc_info.value)

    def test_missing_file_skips_size_checks(self, tmp_path):
        """When file is missing, check 6 (size mismatch) must NOT add a redundant error."""
        raw_dir = tmp_path / "raw"
        results, funds = _make_14(raw_dir)
        results[0].local_file.unlink()
        with pytest.raises(IntegrityError) as exc_info:
            verify_raw_corpus(results, funds, raw_dir)
        # One error for missing file (check 5), not two (check 5 + check 6)
        assert str(exc_info.value).count("•") == 1

    def test_failed_result_not_checked_for_file(self, tmp_path):
        """Filesystem checks only apply to success results."""
        raw_dir = tmp_path / "raw"
        results, funds = _make_14(raw_dir)
        fid = results[0].fund_id
        # Replace with failed result — its local_file does not exist
        results[0] = FetchResult(
            fund_id=fid,
            groww_url=results[0].groww_url,
            local_file=raw_dir / f"{fid}_missing.html",  # does not exist
            http_status=0,
            file_size_bytes=0,
            fetched_at="2026-05-08T12:00:00Z",
            scrape_status="failed",
            error_message="timeout",
        )
        # Should raise IntegrityError for check 2 (failed), NOT check 5
        with pytest.raises(IntegrityError) as exc_info:
            verify_raw_corpus(results, funds, raw_dir)
        msg = str(exc_info.value)
        assert "failed" in msg.lower()
        assert "_missing.html" not in msg  # check 5 should not have fired


# ── Check 6: on-disk size matches reported size ────────────────────────────────

class TestCheck6SizeMatch:
    def test_exact_size_match_passes(self, tmp_path):
        raw_dir = tmp_path / "raw"
        results, funds = _make_14(raw_dir)
        verify_raw_corpus(results, funds, raw_dir)

    def test_disk_larger_than_reported_raises(self, tmp_path):
        raw_dir = tmp_path / "raw"
        results, funds = _make_14(raw_dir)
        # Append extra bytes to the file so disk size > reported
        results[2].local_file.write_bytes(_GOOD_HTML + b"EXTRA")
        # file_size_bytes in FetchResult still holds the original len(_GOOD_HTML)
        with pytest.raises(IntegrityError) as exc_info:
            verify_raw_corpus(results, funds, raw_dir)
        assert results[2].fund_id in str(exc_info.value)

    def test_disk_smaller_than_reported_raises(self, tmp_path):
        raw_dir = tmp_path / "raw"
        results, funds = _make_14(raw_dir)
        # Truncate the file on disk
        results[7].local_file.write_bytes(b"<html>truncated</html>")
        # file_size_bytes still holds len(_GOOD_HTML), so they won't match
        with pytest.raises(IntegrityError) as exc_info:
            verify_raw_corpus(results, funds, raw_dir)
        assert results[7].fund_id in str(exc_info.value)

    def test_size_mismatch_message_mentions_both_sizes(self, tmp_path):
        raw_dir = tmp_path / "raw"
        results, funds = _make_14(raw_dir)
        results[0].local_file.write_bytes(b"short")
        with pytest.raises(IntegrityError) as exc_info:
            verify_raw_corpus(results, funds, raw_dir)
        msg = str(exc_info.value)
        assert "5" in msg  # on-disk size (len(b"short"))
        assert str(len(_GOOD_HTML)) in msg  # reported size


# ── Check 7: min-size warning (non-blocking) ───────────────────────────────────

class TestCheck7MinSizeWarning:
    def test_large_file_no_warning(self, tmp_path, caplog):
        raw_dir = tmp_path / "raw"
        results, funds = _make_14(raw_dir)
        with caplog.at_level(logging.WARNING, logger="ingestion.phase1.integrity"):
            verify_raw_corpus(results, funds, raw_dir)
        assert not any("below" in r.message for r in caplog.records)

    def test_tiny_file_logs_warning_but_no_exception(self, tmp_path, caplog):
        raw_dir = tmp_path / "raw"
        results, funds = _make_14(raw_dir)
        # Overwrite one file with < 5 KB content (must still match file_size_bytes)
        small = b"<html>x</html>"
        results[4].local_file.write_bytes(small)
        results[4] = FetchResult(
            fund_id=results[4].fund_id,
            groww_url=results[4].groww_url,
            local_file=results[4].local_file,
            http_status=200,
            file_size_bytes=len(small),   # match to avoid check 6 failure
            fetched_at="2026-05-08T12:00:00Z",
            scrape_status="success",
        )
        with caplog.at_level(logging.WARNING, logger="ingestion.phase1.integrity"):
            verify_raw_corpus(results, funds, raw_dir)   # must NOT raise
        assert any("below" in r.message.lower() or str(len(small)) in r.message
                   for r in caplog.records)

    def test_exactly_min_size_no_warning(self, tmp_path, caplog):
        raw_dir = tmp_path / "raw"
        results, funds = _make_14(raw_dir)
        exact = b"x" * MIN_FILE_SIZE_BYTES
        results[0].local_file.write_bytes(exact)
        results[0] = FetchResult(
            fund_id=results[0].fund_id,
            groww_url=results[0].groww_url,
            local_file=results[0].local_file,
            http_status=200,
            file_size_bytes=len(exact),
            fetched_at="2026-05-08T12:00:00Z",
            scrape_status="success",
        )
        with caplog.at_level(logging.WARNING, logger="ingestion.phase1.integrity"):
            verify_raw_corpus(results, funds, raw_dir)
        assert not any("below" in r.message.lower() for r in caplog.records)


# ── Check 8: orphan files (non-blocking) ──────────────────────────────────────

class TestCheck8OrphanFiles:
    def test_no_orphans_passes_silently(self, tmp_path, caplog):
        raw_dir = tmp_path / "raw"
        results, funds = _make_14(raw_dir)
        with caplog.at_level(logging.WARNING, logger="ingestion.phase1.integrity"):
            verify_raw_corpus(results, funds, raw_dir)
        assert not any("orphan" in r.message.lower() for r in caplog.records)

    def test_orphan_file_logs_warning_no_exception(self, tmp_path, caplog):
        raw_dir = tmp_path / "raw"
        results, funds = _make_14(raw_dir)
        orphan = raw_dir / "unexpected_fund.html"
        orphan.write_bytes(b"<html>surprise</html>")
        with caplog.at_level(logging.WARNING, logger="ingestion.phase1.integrity"):
            verify_raw_corpus(results, funds, raw_dir)   # must NOT raise
        assert any("orphan" in r.message.lower() for r in caplog.records)
        assert any("unexpected_fund.html" in r.message for r in caplog.records)

    def test_multiple_orphans_each_logged(self, tmp_path, caplog):
        raw_dir = tmp_path / "raw"
        results, funds = _make_14(raw_dir)
        (raw_dir / "orphan_a.html").write_bytes(b"a")
        (raw_dir / "orphan_b.html").write_bytes(b"b")
        with caplog.at_level(logging.WARNING, logger="ingestion.phase1.integrity"):
            verify_raw_corpus(results, funds, raw_dir)
        warning_msgs = [r.message for r in caplog.records if "orphan" in r.message.lower()]
        assert len(warning_msgs) == 2

    def test_raw_dir_missing_does_not_crash_orphan_scan(self, tmp_path):
        """
        If the raw_dir passed to verify_raw_corpus does not exist, the orphan
        scan (check 8) must skip gracefully — no AttributeError or crash.

        The implementation guards this with ``if raw_dir.exists()``.
        All other checks still use the absolute local_file paths stored on
        each FetchResult, so they pass independently of raw_dir.
        """
        real_raw_dir = tmp_path / "raw"
        results, funds = _make_14(real_raw_dir)

        # Pass a different, non-existent directory as raw_dir.
        # Files exist at their absolute paths (real_raw_dir), so checks 5/6 pass.
        # The orphan scan must not crash when raw_dir is absent.
        nonexistent = tmp_path / "raw_nonexistent"
        verify_raw_corpus(results, funds, nonexistent)  # must not raise or crash


# ── Error accumulation ─────────────────────────────────────────────────────────

class TestErrorAccumulation:
    def test_multiple_different_checks_all_listed(self, tmp_path):
        """Blocking failures from different checks must all appear in one IntegrityError."""
        raw_dir = tmp_path / "raw"
        results, funds = _make_14(raw_dir)

        # Check 2: one failed
        results[0] = _result(results[0].fund_id, raw_dir, scrape_status="failed",
                             error_message="timeout")
        # Check 3: one bad http_status
        r3 = results[1]
        results[1] = FetchResult(
            fund_id=r3.fund_id,
            groww_url=r3.groww_url,
            local_file=r3.local_file,
            http_status=404,
            file_size_bytes=r3.file_size_bytes,
            fetched_at=r3.fetched_at,
            scrape_status="success",
        )
        # Check 5: one missing file
        results[2].local_file.unlink()

        with pytest.raises(IntegrityError) as exc_info:
            verify_raw_corpus(results, funds, raw_dir)

        msg = str(exc_info.value)
        assert results[0].fund_id in msg   # check 2
        assert "404" in msg                # check 3
        assert results[2].fund_id in msg   # check 5

    def test_warning_only_does_not_raise(self, tmp_path, caplog):
        """Checks 7 and 8 trigger warnings; no IntegrityError must be raised."""
        raw_dir = tmp_path / "raw"
        results, funds = _make_14(raw_dir)

        # Check 7: tiny file (size must match to avoid check 6 blocking)
        small = b"<html>x</html>"
        results[0].local_file.write_bytes(small)
        results[0] = FetchResult(
            fund_id=results[0].fund_id,
            groww_url=results[0].groww_url,
            local_file=results[0].local_file,
            http_status=200,
            file_size_bytes=len(small),
            fetched_at="2026-05-08T12:00:00Z",
            scrape_status="success",
        )

        # Check 8: orphan file
        (raw_dir / "orphan.html").write_bytes(b"extra")

        with caplog.at_level(logging.WARNING, logger="ingestion.phase1.integrity"):
            verify_raw_corpus(results, funds, raw_dir)   # must NOT raise

        assert len(caplog.records) >= 2  # at least one size warning + one orphan warning


# ── Happy path ─────────────────────────────────────────────────────────────────

class TestHappyPath:
    def test_14_success_files_on_disk_passes_silently(self, tmp_path):
        raw_dir = tmp_path / "raw"
        results, funds = _make_14(raw_dir)
        # Should return None and raise nothing
        result = verify_raw_corpus(results, funds, raw_dir)
        assert result is None

    def test_happy_path_logs_info(self, tmp_path, caplog):
        raw_dir = tmp_path / "raw"
        results, funds = _make_14(raw_dir)
        with caplog.at_level(logging.INFO, logger="ingestion.phase1.integrity"):
            verify_raw_corpus(results, funds, raw_dir)
        assert any("passed" in r.message.lower() for r in caplog.records)
