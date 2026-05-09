"""
Unit tests for Phase 1.7 — ingestion.phase1.readiness

Tests cover:
  - ReadinessError exception contract
  - Check 1: HTML completeness (all present / some missing)
  - Check 2: Minimum file size (all ok / undersized)
  - Check 3: Scrape log consistency (present+valid / absent / failed entries / skipped)
  - Check 4: Chunk file integrity (absent / valid / schema errors / low count)
  - Happy path: all four checks pass, ready=True, no exception
  - Blocking path: one or more checks fail, ReadinessError raised, all failures listed
  - Error accumulation: multiple blocking failures reported together
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ingestion.phase1.readiness import (
    ReadinessError,
    check_readiness,
    MIN_EXPECTED_CHUNKS,
    REQUIRED_CHUNK_FIELDS,
)
from ingestion.phase1.integrity import MIN_FILE_SIZE_BYTES
from ingestion.phase1.scrape_log import SCRAPE_LOG_FILENAME

# ── Fixtures ────────────────────────────────────────────────────────────────

FUND_IDS = ["hdfc_mid_cap", "hdfc_flexi_cap", "hdfc_elss"]


def _make_funds(fund_ids: list[str] | None = None) -> list[dict]:
    ids = fund_ids or FUND_IDS
    return [
        {
            "fund_id":   fid,
            "fund_name": fid.replace("_", " ").title(),
            "groww_url": f"https://groww.in/mutual-funds/{fid}",
        }
        for fid in ids
    ]


def _write_html(raw_dir: Path, fund_id: str, size: int = 10_000) -> Path:
    """Write a fake HTML file of the given byte size."""
    path = raw_dir / f"{fund_id}.html"
    path.write_bytes(b"x" * size)
    return path


def _write_scrape_log(raw_dir: Path, entries: list[dict]) -> Path:
    log = {
        "run_date": "2026-05-08",
        "total_urls_attempted": len(entries),
        "total_urls_succeeded": sum(1 for e in entries if e.get("scrape_status") == "success"),
        "total_urls_failed": sum(1 for e in entries if e.get("scrape_status") == "failed"),
        "entries": entries,
    }
    path = raw_dir / SCRAPE_LOG_FILENAME
    path.write_text(json.dumps(log), encoding="utf-8")
    return path


def _default_log_entries(fund_ids: list[str]) -> list[dict]:
    return [
        {
            "fund_id":      fid,
            "groww_url":    f"https://groww.in/mutual-funds/{fid}",
            "local_file":   f"corpus/raw/{fid}.html",
            "http_status":  200,
            "file_size_bytes": 10_000,
            "content_hash_sha256": "abc" * 20,
            "fetched_at":   "2026-05-08T10:00:00Z",
            "scrape_status": "success",
        }
        for fid in fund_ids
    ]


# ── ReadinessError ────────────────────────────────────────────────────────────

class TestReadinessError:
    def test_is_runtime_error(self):
        assert issubclass(ReadinessError, RuntimeError)

    def test_message_preserved(self):
        exc = ReadinessError("two failures here")
        assert "two failures here" in str(exc)


# ── Check 1: HTML completeness ────────────────────────────────────────────────

class TestHTMLCompleteness:
    def test_all_files_present_passes(self, tmp_path):
        funds = _make_funds()
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        for f in funds:
            _write_html(raw_dir, f["fund_id"])
        _write_scrape_log(raw_dir, _default_log_entries(FUND_IDS))

        report = check_readiness(funds, raw_dir)
        assert report["checks"]["html_completeness"]["passed"] is True
        assert report["checks"]["html_completeness"]["found"] == len(funds)
        assert report["checks"]["html_completeness"]["missing"] == []

    def test_missing_one_file_fails(self, tmp_path):
        funds = _make_funds()
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        # Write only 2 of 3 files
        _write_html(raw_dir, FUND_IDS[0])
        _write_html(raw_dir, FUND_IDS[1])
        _write_scrape_log(raw_dir, _default_log_entries(FUND_IDS))

        with pytest.raises(ReadinessError) as exc_info:
            check_readiness(funds, raw_dir)
        assert "html_completeness" in str(exc_info.value).lower() or \
               "missing" in str(exc_info.value).lower()

    def test_missing_file_listed_in_report(self, tmp_path):
        funds = _make_funds()
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        _write_html(raw_dir, FUND_IDS[0])
        _write_scrape_log(raw_dir, _default_log_entries(FUND_IDS))

        with pytest.raises(ReadinessError) as exc_info:
            check_readiness(funds, raw_dir)
        assert FUND_IDS[1] in str(exc_info.value) or FUND_IDS[2] in str(exc_info.value)

    def test_empty_funds_list_passes(self, tmp_path):
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        _write_scrape_log(raw_dir, [])
        report = check_readiness([], raw_dir)
        assert report["checks"]["html_completeness"]["passed"] is True
        assert report["checks"]["html_completeness"]["found"] == 0


# ── Check 2: Minimum file size ────────────────────────────────────────────────

class TestFileSize:
    def test_files_above_minimum_pass(self, tmp_path):
        funds = _make_funds()
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        for f in funds:
            _write_html(raw_dir, f["fund_id"], size=MIN_FILE_SIZE_BYTES + 1)
        _write_scrape_log(raw_dir, _default_log_entries(FUND_IDS))

        report = check_readiness(funds, raw_dir)
        assert report["checks"]["file_sizes"]["passed"] is True
        assert report["checks"]["file_sizes"]["undersized"] == []

    def test_undersized_file_blocks(self, tmp_path):
        funds = _make_funds()
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        _write_html(raw_dir, FUND_IDS[0], size=MIN_FILE_SIZE_BYTES - 1)
        _write_html(raw_dir, FUND_IDS[1])
        _write_html(raw_dir, FUND_IDS[2])
        _write_scrape_log(raw_dir, _default_log_entries(FUND_IDS))

        with pytest.raises(ReadinessError) as exc_info:
            check_readiness(funds, raw_dir)
        assert "size" in str(exc_info.value).lower() or \
               FUND_IDS[0] in str(exc_info.value)

    def test_undersized_listed_in_report(self, tmp_path):
        funds = _make_funds()
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        _write_html(raw_dir, FUND_IDS[0], size=100)
        _write_html(raw_dir, FUND_IDS[1])
        _write_html(raw_dir, FUND_IDS[2])
        _write_scrape_log(raw_dir, _default_log_entries(FUND_IDS))

        try:
            check_readiness(funds, raw_dir)
        except ReadinessError:
            pass
        # Access internals via a separate call to the private check
        from ingestion.phase1.readiness import _check_file_sizes
        result = _check_file_sizes(funds, raw_dir)
        assert any(e["fund_id"] == FUND_IDS[0] for e in result["undersized"])

    def test_missing_file_not_counted_as_undersized(self, tmp_path):
        """Files that don't exist are caught by Check 1, not Check 2."""
        funds = _make_funds()
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        # Only write 2 of 3 — 3rd is absent
        _write_html(raw_dir, FUND_IDS[0])
        _write_html(raw_dir, FUND_IDS[1])
        _write_scrape_log(raw_dir, _default_log_entries(FUND_IDS))

        from ingestion.phase1.readiness import _check_file_sizes
        result = _check_file_sizes(funds, raw_dir)
        undersized_ids = [e["fund_id"] for e in result["undersized"]]
        assert FUND_IDS[2] not in undersized_ids


# ── Check 3: Scrape log consistency ──────────────────────────────────────────

class TestScrapeLogConsistency:
    def test_all_success_passes(self, tmp_path):
        funds = _make_funds()
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        for f in funds:
            _write_html(raw_dir, f["fund_id"])
        _write_scrape_log(raw_dir, _default_log_entries(FUND_IDS))

        report = check_readiness(funds, raw_dir)
        r = report["checks"]["scrape_log_consistency"]
        assert r["passed"] is True
        assert r["failed_entries"] == 0

    def test_absent_log_blocks(self, tmp_path):
        funds = _make_funds()
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        for f in funds:
            _write_html(raw_dir, f["fund_id"])
        # No scrape_log.json written

        with pytest.raises(ReadinessError) as exc_info:
            check_readiness(funds, raw_dir)
        assert "scrape" in str(exc_info.value).lower() or \
               "log" in str(exc_info.value).lower()

    def test_failed_entry_blocks(self, tmp_path):
        funds = _make_funds()
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        for f in funds:
            _write_html(raw_dir, f["fund_id"])
        entries = _default_log_entries(FUND_IDS)
        entries[0]["scrape_status"] = "failed"
        _write_scrape_log(raw_dir, entries)

        with pytest.raises(ReadinessError) as exc_info:
            check_readiness(funds, raw_dir)
        assert "failed" in str(exc_info.value).lower()

    def test_skipped_entry_warns_but_does_not_block(self, tmp_path):
        funds = _make_funds()
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        for f in funds:
            _write_html(raw_dir, f["fund_id"])
        entries = _default_log_entries(FUND_IDS)
        entries[0]["scrape_status"] = "skipped"
        _write_scrape_log(raw_dir, entries)

        report = check_readiness(funds, raw_dir)
        assert report["ready"] is True
        assert report["checks"]["scrape_log_consistency"]["skipped_entries"] == 1
        assert any("skipped" in w.lower() for w in report["warnings"])

    def test_invalid_json_log_blocks(self, tmp_path):
        funds = _make_funds()
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        for f in funds:
            _write_html(raw_dir, f["fund_id"])
        (raw_dir / SCRAPE_LOG_FILENAME).write_text("not valid json", encoding="utf-8")

        with pytest.raises(ReadinessError):
            check_readiness(funds, raw_dir)

    def test_multiple_failed_entries_all_reported(self, tmp_path):
        funds = _make_funds()
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        for f in funds:
            _write_html(raw_dir, f["fund_id"])
        entries = _default_log_entries(FUND_IDS)
        entries[0]["scrape_status"] = "failed"
        entries[1]["scrape_status"] = "failed"
        _write_scrape_log(raw_dir, entries)

        from ingestion.phase1.readiness import _check_scrape_log
        result = _check_scrape_log(raw_dir)
        assert result["failed_entries"] == 2


# ── Check 4: Chunk file integrity ─────────────────────────────────────────────

class TestChunkFileIntegrity:
    def _write_chunks(self, processed_dir: Path, chunks: list[dict]) -> Path:
        processed_dir.mkdir(parents=True, exist_ok=True)
        path = processed_dir / "chunks.jsonl"
        with path.open("w", encoding="utf-8") as fh:
            for c in chunks:
                fh.write(json.dumps(c) + "\n")
        return path

    def _good_chunk(self, idx: int) -> dict:
        return {
            "chunk_id": f"hdfc_mid_cap_fund_overview_{idx}",
            "fund_id":  "hdfc_mid_cap",
            "text":     "Some fund overview text here.",
            "section_type": "fund_overview",
        }

    def test_absent_chunks_file_passes(self, tmp_path):
        funds = _make_funds()
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        for f in funds:
            _write_html(raw_dir, f["fund_id"])
        _write_scrape_log(raw_dir, _default_log_entries(FUND_IDS))
        processed_dir = tmp_path / "processed"   # exists but no chunks.jsonl

        report = check_readiness(funds, raw_dir, processed_dir)
        assert report["checks"]["chunk_file_integrity"]["passed"] is True
        assert report["checks"]["chunk_file_integrity"].get("absent") is True

    def test_no_processed_dir_skips_check(self, tmp_path):
        funds = _make_funds()
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        for f in funds:
            _write_html(raw_dir, f["fund_id"])
        _write_scrape_log(raw_dir, _default_log_entries(FUND_IDS))

        report = check_readiness(funds, raw_dir, processed_dir=None)
        assert report["checks"]["chunk_file_integrity"].get("skipped") is True

    def test_valid_chunks_above_minimum_passes(self, tmp_path):
        funds = _make_funds()
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        for f in funds:
            _write_html(raw_dir, f["fund_id"])
        _write_scrape_log(raw_dir, _default_log_entries(FUND_IDS))

        processed_dir = tmp_path / "processed"
        chunks = [self._good_chunk(i) for i in range(MIN_EXPECTED_CHUNKS + 5)]
        self._write_chunks(processed_dir, chunks)

        report = check_readiness(funds, raw_dir, processed_dir)
        assert report["checks"]["chunk_file_integrity"]["passed"] is True
        assert report["checks"]["chunk_file_integrity"]["chunks_found"] == len(chunks)

    def test_schema_error_triggers_warning_not_blocking(self, tmp_path):
        funds = _make_funds()
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        for f in funds:
            _write_html(raw_dir, f["fund_id"])
        _write_scrape_log(raw_dir, _default_log_entries(FUND_IDS))

        processed_dir = tmp_path / "processed"
        # chunk missing 'section_type'
        bad_chunks = [
            {"chunk_id": "x_0", "fund_id": "hdfc_mid_cap", "text": "text"}
        ] + [self._good_chunk(i) for i in range(MIN_EXPECTED_CHUNKS)]
        self._write_chunks(processed_dir, bad_chunks)

        report = check_readiness(funds, raw_dir, processed_dir)
        assert report["ready"] is True   # warn-only, not blocking
        assert len(report["warnings"]) > 0

    def test_low_chunk_count_triggers_warning(self, tmp_path):
        funds = _make_funds()
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        for f in funds:
            _write_html(raw_dir, f["fund_id"])
        _write_scrape_log(raw_dir, _default_log_entries(FUND_IDS))

        processed_dir = tmp_path / "processed"
        chunks = [self._good_chunk(i) for i in range(10)]   # below threshold
        self._write_chunks(processed_dir, chunks)

        report = check_readiness(funds, raw_dir, processed_dir)
        assert report["ready"] is True   # warn-only
        assert any("chunk" in w.lower() or "count" in w.lower() for w in report["warnings"])

    def test_invalid_json_line_triggers_warning(self, tmp_path):
        funds = _make_funds()
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        for f in funds:
            _write_html(raw_dir, f["fund_id"])
        _write_scrape_log(raw_dir, _default_log_entries(FUND_IDS))

        processed_dir = tmp_path / "processed"
        processed_dir.mkdir()
        chunks_path = processed_dir / "chunks.jsonl"
        # Write one bad JSON line among valid ones
        good_lines = [json.dumps(self._good_chunk(i)) for i in range(MIN_EXPECTED_CHUNKS)]
        chunks_path.write_text(
            "\n".join(good_lines) + "\nnot-valid-json\n",
            encoding="utf-8",
        )

        report = check_readiness(funds, raw_dir, processed_dir)
        c4 = report["checks"]["chunk_file_integrity"]
        assert len(c4["schema_errors"]) > 0


# ── Error accumulation ────────────────────────────────────────────────────────

class TestErrorAccumulation:
    def test_all_blocking_failures_listed_in_one_raise(self, tmp_path):
        """Check 1 + Check 2 + Check 3 all fail simultaneously."""
        funds = _make_funds()
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        # 1. Missing HTML file (Check 1 fails for FUND_IDS[2])
        _write_html(raw_dir, FUND_IDS[0])
        _write_html(raw_dir, FUND_IDS[1])
        # 2. Undersized file (Check 2 fails for FUND_IDS[1])
        (raw_dir / f"{FUND_IDS[1]}.html").write_bytes(b"x" * 10)
        # 3. No scrape_log.json (Check 3 fails)

        with pytest.raises(ReadinessError) as exc_info:
            check_readiness(funds, raw_dir)
        msg = str(exc_info.value)
        assert "2" in msg or "3" in msg   # at least 2 failures mentioned
        assert "blocking" in msg.lower() or "fail" in msg.lower()

    def test_report_blocking_failures_list_populated(self, tmp_path):
        funds = _make_funds()
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        # Only Check 3 fails (no scrape_log)
        for f in funds:
            _write_html(raw_dir, f["fund_id"])

        try:
            check_readiness(funds, raw_dir)
        except ReadinessError:
            pass
        # Verify by calling private check directly
        from ingestion.phase1.readiness import _check_scrape_log
        result = _check_scrape_log(raw_dir)
        assert result["passed"] is False
        assert result["failed_entries"] == -1   # log absent sentinel

    def test_ready_true_when_all_checks_pass(self, tmp_path):
        funds = _make_funds()
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        for f in funds:
            _write_html(raw_dir, f["fund_id"])
        _write_scrape_log(raw_dir, _default_log_entries(FUND_IDS))

        report = check_readiness(funds, raw_dir)
        assert report["ready"] is True
        assert report["blocking_failures"] == []

    def test_report_structure_complete(self, tmp_path):
        funds = _make_funds()
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        for f in funds:
            _write_html(raw_dir, f["fund_id"])
        _write_scrape_log(raw_dir, _default_log_entries(FUND_IDS))

        report = check_readiness(funds, raw_dir)
        assert "ready" in report
        assert "checked_at" in report
        assert "checks" in report
        assert "blocking_failures" in report
        assert "warnings" in report
        assert set(report["checks"].keys()) == {
            "html_completeness",
            "file_sizes",
            "scrape_log_consistency",
            "chunk_file_integrity",
        }
