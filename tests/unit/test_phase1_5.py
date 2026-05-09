"""
Phase 1.5 — Unit tests for ingestion/phase1/scrape_log.py

All filesystem operations use pytest's tmp_path fixture.

Coverage
--------
_compute_hash()
  - Returns correct SHA-256 hex digest for a known file
  - Returns "" when file does not exist

write_scrape_log()
  - Creates scrape_log.json in raw_dir
  - Top-level keys match schema (run_date, totals, entries)
  - run_date is today's date in YYYY-MM-DD format
  - total_urls_attempted == len(results)
  - total_urls_succeeded counts only "success" entries
  - total_urls_failed counts only "failed" entries (skipped not counted)
  - Entries list length matches results list
  - Per-entry keys match schema exactly
  - local_file stored as relative "corpus/raw/<name>.html" not absolute
  - content_hash_sha256 is correct SHA-256 for success results
  - content_hash_sha256 is "" for failed results
  - content_hash_sha256 is "" for skipped results
  - content_hash_sha256 is "" when success file missing from disk (defensive)
  - Returns the Path of the written file
  - Written file is valid JSON
  - raw_dir created if it does not exist
  - Mixed results (success + failed + skipped) serialised correctly

load_scrape_log()
  - Returns dict with correct top-level keys
  - Entries are preserved round-trip
  - Raises FileNotFoundError when scrape_log.json absent
  - Raises json.JSONDecodeError on corrupt file
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

import pytest

from ingestion.phase1.fetch import FetchResult
from ingestion.phase1.scrape_log import (
    SCRAPE_LOG_FILENAME,
    _compute_hash,
    load_scrape_log,
    write_scrape_log,
)

# ── Helpers ───────────────────────────────────────────────────────────────────

_HTML = b"<html><body>Groww fund page content</body></html>" * 200  # ~10 KB


def _result(
    fund_id: str,
    raw_dir: Path,
    scrape_status: str = "success",
    http_status: int = 200,
    content: bytes = _HTML,
    error_message: str | None = None,
) -> FetchResult:
    dest = raw_dir / f"{fund_id}.html"
    size = len(content) if scrape_status == "success" else 0
    return FetchResult(
        fund_id=fund_id,
        groww_url=f"https://groww.in/mutual-funds/{fund_id}-direct-growth",
        local_file=dest,
        http_status=http_status,
        file_size_bytes=size,
        fetched_at="2026-05-08T14:00:00Z",
        scrape_status=scrape_status,  # type: ignore[arg-type]
        error_message=error_message,
    )


def _write_file(r: FetchResult, content: bytes = _HTML) -> None:
    r.local_file.parent.mkdir(parents=True, exist_ok=True)
    r.local_file.write_bytes(content)


def _make_results(raw_dir: Path, n: int = 3) -> list[FetchResult]:
    """Return n success FetchResults with files written to disk."""
    results = []
    for i in range(n):
        r = _result(f"hdfc_fund_{i:02d}", raw_dir)
        _write_file(r)
        results.append(r)
    return results


# ── _compute_hash ─────────────────────────────────────────────────────────────

class TestComputeHash:
    def test_known_content_matches_hashlib(self, tmp_path):
        f = tmp_path / "test.html"
        f.write_bytes(_HTML)
        expected = hashlib.sha256(_HTML).hexdigest()
        assert _compute_hash(f) == expected

    def test_returns_lowercase_hex(self, tmp_path):
        f = tmp_path / "test.html"
        f.write_bytes(b"hello")
        result = _compute_hash(f)
        assert result == result.lower()
        assert len(result) == 64  # SHA-256 hex is always 64 chars

    def test_missing_file_returns_empty_string(self, tmp_path):
        assert _compute_hash(tmp_path / "nonexistent.html") == ""

    def test_different_contents_different_hashes(self, tmp_path):
        f1 = tmp_path / "a.html"
        f2 = tmp_path / "b.html"
        f1.write_bytes(b"content A")
        f2.write_bytes(b"content B")
        assert _compute_hash(f1) != _compute_hash(f2)

    def test_same_content_same_hash(self, tmp_path):
        f1 = tmp_path / "a.html"
        f2 = tmp_path / "b.html"
        f1.write_bytes(_HTML)
        f2.write_bytes(_HTML)
        assert _compute_hash(f1) == _compute_hash(f2)


# ── write_scrape_log — output file ────────────────────────────────────────────

class TestWriteScrapeLogOutputFile:
    def test_returns_path(self, tmp_path):
        raw_dir = tmp_path / "raw"
        results = _make_results(raw_dir)
        path = write_scrape_log(results, raw_dir)
        assert isinstance(path, Path)

    def test_file_created_at_correct_location(self, tmp_path):
        raw_dir = tmp_path / "raw"
        results = _make_results(raw_dir)
        path = write_scrape_log(results, raw_dir)
        assert path == raw_dir / SCRAPE_LOG_FILENAME
        assert path.exists()

    def test_file_is_valid_json(self, tmp_path):
        raw_dir = tmp_path / "raw"
        results = _make_results(raw_dir)
        path = write_scrape_log(results, raw_dir)
        data = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(data, dict)

    def test_raw_dir_created_if_missing(self, tmp_path):
        raw_dir = tmp_path / "raw" / "nested"
        results = _make_results(tmp_path / "raw")
        # Point to a different (non-existent) raw_dir; still creates it
        raw_dir2 = tmp_path / "newraw"
        assert not raw_dir2.exists()
        results2 = _make_results(raw_dir2)
        write_scrape_log(results2, raw_dir2)
        assert raw_dir2.exists()


# ── write_scrape_log — top-level schema ───────────────────────────────────────

class TestWriteScrapeLogTopLevel:
    def _load(self, tmp_path, results=None, n=3) -> dict:
        raw_dir = tmp_path / "raw"
        if results is None:
            results = _make_results(raw_dir, n)
        write_scrape_log(results, raw_dir)
        return json.loads((raw_dir / SCRAPE_LOG_FILENAME).read_text())

    def test_top_level_keys_present(self, tmp_path):
        data = self._load(tmp_path)
        assert set(data.keys()) == {
            "run_date", "total_urls_attempted",
            "total_urls_succeeded", "total_urls_failed", "entries"
        }

    def test_run_date_is_today(self, tmp_path):
        data = self._load(tmp_path)
        assert data["run_date"] == str(date.today())

    def test_run_date_format(self, tmp_path):
        data = self._load(tmp_path)
        parts = data["run_date"].split("-")
        assert len(parts) == 3
        assert len(parts[0]) == 4  # YYYY
        assert len(parts[1]) == 2  # MM
        assert len(parts[2]) == 2  # DD

    def test_total_urls_attempted(self, tmp_path):
        data = self._load(tmp_path, n=3)
        assert data["total_urls_attempted"] == 3

    def test_total_urls_succeeded_all_success(self, tmp_path):
        data = self._load(tmp_path, n=3)
        assert data["total_urls_succeeded"] == 3

    def test_total_urls_failed_all_success(self, tmp_path):
        data = self._load(tmp_path, n=3)
        assert data["total_urls_failed"] == 0

    def test_mixed_counts(self, tmp_path):
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir(parents=True)
        r0 = _result("fund_ok", raw_dir)
        _write_file(r0)
        r1 = _result("fund_fail", raw_dir, scrape_status="failed", http_status=0,
                     error_message="timeout")
        r2 = _result("fund_skip", raw_dir, scrape_status="skipped", http_status=0)
        write_scrape_log([r0, r1, r2], raw_dir)
        data = json.loads((raw_dir / SCRAPE_LOG_FILENAME).read_text())
        assert data["total_urls_attempted"] == 3
        assert data["total_urls_succeeded"] == 1
        assert data["total_urls_failed"] == 1  # skipped not counted as failed

    def test_entries_length_matches_results(self, tmp_path):
        data = self._load(tmp_path, n=5)
        assert len(data["entries"]) == 5

    def test_zero_results_writes_empty_entries(self, tmp_path):
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        write_scrape_log([], raw_dir)
        data = json.loads((raw_dir / SCRAPE_LOG_FILENAME).read_text())
        assert data["entries"] == []
        assert data["total_urls_attempted"] == 0


# ── write_scrape_log — per-entry schema ───────────────────────────────────────

class TestWriteScrapeLogEntrySchema:
    REQUIRED_ENTRY_KEYS = {
        "fund_id", "groww_url", "local_file",
        "http_status", "file_size_bytes",
        "content_hash_sha256", "fetched_at", "scrape_status",
    }

    def _entry(self, tmp_path, **kwargs) -> dict:
        raw_dir = tmp_path / "raw"
        r = _result("hdfc_test", raw_dir, **kwargs)
        if kwargs.get("scrape_status", "success") == "success":
            _write_file(r)
        write_scrape_log([r], raw_dir)
        data = json.loads((raw_dir / SCRAPE_LOG_FILENAME).read_text())
        return data["entries"][0]

    def test_entry_has_all_required_keys(self, tmp_path):
        entry = self._entry(tmp_path)
        assert set(entry.keys()) == self.REQUIRED_ENTRY_KEYS

    def test_fund_id_matches(self, tmp_path):
        entry = self._entry(tmp_path)
        assert entry["fund_id"] == "hdfc_test"

    def test_groww_url_matches(self, tmp_path):
        entry = self._entry(tmp_path)
        assert entry["groww_url"] == "https://groww.in/mutual-funds/hdfc_test-direct-growth"

    def test_local_file_is_relative_path(self, tmp_path):
        entry = self._entry(tmp_path)
        assert entry["local_file"] == "corpus/raw/hdfc_test.html"
        # Must NOT be an absolute path
        assert not entry["local_file"].startswith("/")

    def test_local_file_starts_with_corpus_raw(self, tmp_path):
        entry = self._entry(tmp_path)
        assert entry["local_file"].startswith("corpus/raw/")

    def test_http_status_200(self, tmp_path):
        entry = self._entry(tmp_path)
        assert entry["http_status"] == 200

    def test_http_status_0_for_failed(self, tmp_path):
        entry = self._entry(tmp_path, scrape_status="failed", http_status=0)
        assert entry["http_status"] == 0

    def test_file_size_bytes_positive_for_success(self, tmp_path):
        entry = self._entry(tmp_path)
        assert entry["file_size_bytes"] == len(_HTML)

    def test_file_size_bytes_zero_for_failed(self, tmp_path):
        entry = self._entry(tmp_path, scrape_status="failed", http_status=0)
        assert entry["file_size_bytes"] == 0

    def test_content_hash_is_64_char_hex_for_success(self, tmp_path):
        entry = self._entry(tmp_path)
        h = entry["content_hash_sha256"]
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_content_hash_correct_value(self, tmp_path):
        entry = self._entry(tmp_path)
        expected = hashlib.sha256(_HTML).hexdigest()
        assert entry["content_hash_sha256"] == expected

    def test_content_hash_empty_for_failed(self, tmp_path):
        entry = self._entry(tmp_path, scrape_status="failed", http_status=0)
        assert entry["content_hash_sha256"] == ""

    def test_content_hash_empty_for_skipped(self, tmp_path):
        entry = self._entry(tmp_path, scrape_status="skipped", http_status=0)
        assert entry["content_hash_sha256"] == ""

    def test_content_hash_empty_when_success_file_missing(self, tmp_path):
        """Defensive: success result but file deleted before log is written."""
        raw_dir = tmp_path / "raw"
        r = _result("hdfc_test", raw_dir)
        # Do NOT write the file — simulate mid-run deletion
        raw_dir.mkdir(parents=True, exist_ok=True)
        write_scrape_log([r], raw_dir)
        data = json.loads((raw_dir / SCRAPE_LOG_FILENAME).read_text())
        assert data["entries"][0]["content_hash_sha256"] == ""

    def test_fetched_at_preserved(self, tmp_path):
        entry = self._entry(tmp_path)
        assert entry["fetched_at"] == "2026-05-08T14:00:00Z"

    def test_scrape_status_success(self, tmp_path):
        entry = self._entry(tmp_path)
        assert entry["scrape_status"] == "success"

    def test_scrape_status_failed(self, tmp_path):
        entry = self._entry(tmp_path, scrape_status="failed", http_status=503)
        assert entry["scrape_status"] == "failed"

    def test_scrape_status_skipped(self, tmp_path):
        entry = self._entry(tmp_path, scrape_status="skipped", http_status=0)
        assert entry["scrape_status"] == "skipped"


# ── write_scrape_log — round-trip / ordering ──────────────────────────────────

class TestWriteScrapeLogRoundTrip:
    def test_entry_order_matches_results_order(self, tmp_path):
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        ids = ["hdfc_fund_a", "hdfc_fund_b", "hdfc_fund_c"]
        results = []
        for fid in ids:
            r = _result(fid, raw_dir)
            _write_file(r)
            results.append(r)
        write_scrape_log(results, raw_dir)
        data = json.loads((raw_dir / SCRAPE_LOG_FILENAME).read_text())
        assert [e["fund_id"] for e in data["entries"]] == ids

    def test_overwrite_updates_file(self, tmp_path):
        raw_dir = tmp_path / "raw"
        results1 = _make_results(raw_dir, 2)
        write_scrape_log(results1, raw_dir)
        results2 = _make_results(raw_dir, 3)
        write_scrape_log(results2, raw_dir)
        data = json.loads((raw_dir / SCRAPE_LOG_FILENAME).read_text())
        assert data["total_urls_attempted"] == 3


# ── load_scrape_log ───────────────────────────────────────────────────────────

class TestLoadScrapeLog:
    def test_returns_dict(self, tmp_path):
        raw_dir = tmp_path / "raw"
        results = _make_results(raw_dir, 2)
        write_scrape_log(results, raw_dir)
        data = load_scrape_log(raw_dir)
        assert isinstance(data, dict)

    def test_round_trip_preserves_entries(self, tmp_path):
        raw_dir = tmp_path / "raw"
        results = _make_results(raw_dir, 2)
        write_scrape_log(results, raw_dir)
        data = load_scrape_log(raw_dir)
        assert len(data["entries"]) == 2
        assert data["entries"][0]["fund_id"] == results[0].fund_id

    def test_raises_file_not_found_when_missing(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_scrape_log(tmp_path / "raw_missing")

    def test_raises_json_decode_error_on_corrupt_file(self, tmp_path):
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        (raw_dir / SCRAPE_LOG_FILENAME).write_text("NOT VALID JSON {{{{", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError):
            load_scrape_log(raw_dir)

    def test_error_message_mentions_run_phase1_5(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="write_scrape_log"):
            load_scrape_log(tmp_path / "empty_dir")
