"""
Phase 1.3 — Unit tests for ingestion/phase1/fetch.py

All HTTP calls are mocked — no real network access.

Coverage
--------
FetchResult
  - Dataclass fields default correctly
  - is_success() reflects scrape_status
  - as_log_dict() has all required keys and correct types

fetch_and_save()
  - HTTP 200: file is written, result is success, file_size_bytes correct
  - HTTP 404: result is failed, file NOT written, http_status captured
  - HTTP 500: result is failed, error_message set
  - Timeout:  result is failed, error_message mentions timeout
  - ConnectionError: result is failed, error_message set
  - Generic RequestException: result is failed
  - OSError on write: result is failed, error_message set
  - Result always has non-empty fetched_at timestamp
  - File is saved to correct path (raw_dir / filename from local_file)

fetch_all()
  - Returns one FetchResult per fund
  - Calls fetch_and_save for each unique URL
  - Duplicate URL in fund list → second entry scrape_status="skipped"
  - delay=0 used in tests to suppress real sleeping
  - No delay call after the last fund
  - All results returned even when some fail
"""

import time
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest
import requests

from ingestion.phase1.fetch import FetchResult, _utc_now, fetch_all, fetch_and_save


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fund(
    fund_id: str = "hdfc_test",
    groww_url: str = "https://groww.in/mutual-funds/hdfc-test-direct-growth",
    local_file: str = "corpus/raw/hdfc_test.html",
) -> dict:
    return {
        "fund_id": fund_id,
        "groww_url": groww_url,
        "local_file": local_file,
    }


def _mock_response(status_code: int = 200, content: bytes = b"<html>test</html>"):
    resp = MagicMock()
    resp.status_code = status_code
    resp.content = content
    return resp


def _mock_session(status_code: int = 200, content: bytes = b"<html>test</html>"):
    session = MagicMock(spec=requests.Session)
    session.get.return_value = _mock_response(status_code, content)
    return session


# ── FetchResult tests ─────────────────────────────────────────────────────────

class TestFetchResult:
    def test_default_scrape_status_is_failed(self):
        r = FetchResult("fid", "https://x.com", Path("/tmp/f.html"))
        assert r.scrape_status == "failed"

    def test_is_success_true_when_status_success(self):
        r = FetchResult("fid", "https://x.com", Path("/tmp/f.html"), scrape_status="success")
        assert r.is_success() is True

    def test_is_success_false_when_status_failed(self):
        r = FetchResult("fid", "https://x.com", Path("/tmp/f.html"), scrape_status="failed")
        assert r.is_success() is False

    def test_is_success_false_when_status_skipped(self):
        r = FetchResult("fid", "https://x.com", Path("/tmp/f.html"), scrape_status="skipped")
        assert r.is_success() is False

    def test_as_log_dict_has_all_keys(self):
        r = FetchResult(
            fund_id="hdfc_mid_cap",
            groww_url="https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth",
            local_file=Path("corpus/raw/hdfc_mid_cap.html"),
            http_status=200,
            file_size_bytes=12345,
            fetched_at="2026-05-08T00:00:00Z",
            scrape_status="success",
        )
        d = r.as_log_dict()
        required = {
            "fund_id", "groww_url", "local_file", "http_status",
            "file_size_bytes", "fetched_at", "scrape_status", "error_message",
        }
        assert required == set(d.keys())

    def test_as_log_dict_local_file_is_string(self):
        r = FetchResult("fid", "https://x.com", Path("/tmp/f.html"))
        assert isinstance(r.as_log_dict()["local_file"], str)


# ── fetch_and_save tests ──────────────────────────────────────────────────────

class TestFetchAndSave:
    def test_http_200_returns_success(self, tmp_path):
        session = _mock_session(200, b"<html>fund data</html>")
        result = fetch_and_save(_fund(), session, tmp_path)
        assert result.scrape_status == "success"

    def test_http_200_writes_file(self, tmp_path):
        content = b"<html>fund page content</html>"
        session = _mock_session(200, content)
        fetch_and_save(_fund(local_file="corpus/raw/hdfc_test.html"), session, tmp_path)
        saved = tmp_path / "hdfc_test.html"
        assert saved.exists()
        assert saved.read_bytes() == content

    def test_http_200_sets_correct_file_size(self, tmp_path):
        content = b"x" * 500
        session = _mock_session(200, content)
        result = fetch_and_save(_fund(), session, tmp_path)
        assert result.file_size_bytes == 500

    def test_http_200_sets_http_status(self, tmp_path):
        session = _mock_session(200)
        result = fetch_and_save(_fund(), session, tmp_path)
        assert result.http_status == 200

    def test_http_404_returns_failed(self, tmp_path):
        session = _mock_session(404, b"not found")
        result = fetch_and_save(_fund(), session, tmp_path)
        assert result.scrape_status == "failed"

    def test_http_404_sets_http_status(self, tmp_path):
        session = _mock_session(404, b"not found")
        result = fetch_and_save(_fund(), session, tmp_path)
        assert result.http_status == 404

    def test_http_404_does_not_write_file(self, tmp_path):
        session = _mock_session(404, b"not found")
        fetch_and_save(_fund(local_file="corpus/raw/hdfc_test.html"), session, tmp_path)
        assert not (tmp_path / "hdfc_test.html").exists()

    def test_http_404_sets_error_message(self, tmp_path):
        session = _mock_session(404)
        result = fetch_and_save(_fund(), session, tmp_path)
        assert result.error_message is not None
        assert "404" in result.error_message

    def test_http_500_returns_failed(self, tmp_path):
        session = _mock_session(500)
        result = fetch_and_save(_fund(), session, tmp_path)
        assert result.scrape_status == "failed"

    def test_timeout_returns_failed(self, tmp_path):
        session = MagicMock(spec=requests.Session)
        session.get.side_effect = requests.exceptions.Timeout()
        result = fetch_and_save(_fund(), session, tmp_path)
        assert result.scrape_status == "failed"

    def test_timeout_error_message_mentions_timeout(self, tmp_path):
        session = MagicMock(spec=requests.Session)
        session.get.side_effect = requests.exceptions.Timeout()
        result = fetch_and_save(_fund(), session, tmp_path)
        msg = result.error_message.lower()
        assert "timeout" in msg or "timed out" in msg

    def test_connection_error_returns_failed(self, tmp_path):
        session = MagicMock(spec=requests.Session)
        session.get.side_effect = requests.exceptions.ConnectionError("conn refused")
        result = fetch_and_save(_fund(), session, tmp_path)
        assert result.scrape_status == "failed"

    def test_connection_error_sets_error_message(self, tmp_path):
        session = MagicMock(spec=requests.Session)
        session.get.side_effect = requests.exceptions.ConnectionError("refused")
        result = fetch_and_save(_fund(), session, tmp_path)
        assert result.error_message is not None

    def test_generic_request_exception_returns_failed(self, tmp_path):
        session = MagicMock(spec=requests.Session)
        session.get.side_effect = requests.exceptions.RequestException("generic")
        result = fetch_and_save(_fund(), session, tmp_path)
        assert result.scrape_status == "failed"

    def test_os_error_on_write_returns_failed(self, tmp_path):
        session = _mock_session(200, b"<html/>")
        fund = _fund(local_file="corpus/raw/hdfc_test.html")
        with patch("ingestion.phase1.fetch.Path.write_bytes", side_effect=OSError("disk full")):
            result = fetch_and_save(fund, session, tmp_path)
        assert result.scrape_status == "failed"
        assert result.error_message is not None

    def test_result_has_non_empty_fetched_at(self, tmp_path):
        session = _mock_session(200)
        result = fetch_and_save(_fund(), session, tmp_path)
        assert result.fetched_at != ""

    def test_result_fund_id_matches_input(self, tmp_path):
        session = _mock_session(200)
        result = fetch_and_save(_fund(fund_id="hdfc_mid_cap"), session, tmp_path)
        assert result.fund_id == "hdfc_mid_cap"

    def test_result_groww_url_matches_input(self, tmp_path):
        session = _mock_session(200)
        fund = _fund(groww_url="https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth")
        result = fetch_and_save(fund, session, tmp_path)
        assert result.groww_url == "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth"

    def test_file_saved_to_raw_dir_not_local_file_path(self, tmp_path):
        """File must be saved under raw_dir, ignoring the directory part of local_file."""
        session = _mock_session(200, b"data")
        fund = _fund(local_file="corpus/raw/hdfc_test.html")
        result = fetch_and_save(fund, session, tmp_path)
        assert result.local_file.parent == tmp_path

    def test_raw_dir_created_if_missing(self, tmp_path):
        """fetch_and_save must create raw_dir if it does not exist."""
        session = _mock_session(200, b"data")
        new_dir = tmp_path / "new_subdir"
        assert not new_dir.exists()
        fetch_and_save(_fund(), session, new_dir)
        assert new_dir.exists()

    def test_session_get_called_with_correct_url(self, tmp_path):
        session = _mock_session(200)
        url = "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth"
        fetch_and_save(_fund(groww_url=url), session, tmp_path)
        session.get.assert_called_once()
        args, kwargs = session.get.call_args
        assert args[0] == url


# ── fetch_all tests ───────────────────────────────────────────────────────────

class TestFetchAll:
    def _funds(self, n: int) -> list[dict]:
        return [
            _fund(
                fund_id=f"hdfc_fund_{i}",
                groww_url=f"https://groww.in/mutual-funds/hdfc-fund-{i}-direct-growth",
                local_file=f"corpus/raw/hdfc_fund_{i}.html",
            )
            for i in range(n)
        ]

    def test_returns_one_result_per_fund(self, tmp_path):
        session = _mock_session(200)
        funds = self._funds(3)
        results = fetch_all(funds, session, tmp_path, delay=0)
        assert len(results) == 3

    def test_all_results_are_fetch_result_instances(self, tmp_path):
        session = _mock_session(200)
        results = fetch_all(self._funds(3), session, tmp_path, delay=0)
        assert all(isinstance(r, FetchResult) for r in results)

    def test_success_results_for_200_responses(self, tmp_path):
        session = _mock_session(200)
        results = fetch_all(self._funds(3), session, tmp_path, delay=0)
        assert all(r.scrape_status == "success" for r in results)

    def test_each_unique_url_fetched_once(self, tmp_path):
        session = _mock_session(200)
        funds = self._funds(4)
        fetch_all(funds, session, tmp_path, delay=0)
        assert session.get.call_count == 4

    def test_duplicate_url_is_skipped_not_fetched(self, tmp_path):
        session = _mock_session(200)
        # Fund 0 and fund 1 share the same URL — simulates manifest duplicate
        funds = [
            _fund(fund_id="hdfc_a", groww_url="https://groww.in/mutual-funds/hdfc-x"),
            _fund(fund_id="hdfc_b", groww_url="https://groww.in/mutual-funds/hdfc-x"),
        ]
        results = fetch_all(funds, session, tmp_path, delay=0)
        # Only one real fetch; duplicate is skipped
        assert session.get.call_count == 1
        assert results[1].scrape_status == "skipped"

    def test_skipped_result_has_correct_fund_id(self, tmp_path):
        session = _mock_session(200)
        funds = [
            _fund(fund_id="hdfc_a", groww_url="https://groww.in/mutual-funds/hdfc-x"),
            _fund(fund_id="hdfc_b", groww_url="https://groww.in/mutual-funds/hdfc-x"),
        ]
        results = fetch_all(funds, session, tmp_path, delay=0)
        assert results[1].fund_id == "hdfc_b"

    def test_failed_fetch_does_not_stop_remaining_funds(self, tmp_path):
        session = MagicMock(spec=requests.Session)
        session.get.side_effect = [
            requests.exceptions.ConnectionError("fail"),
            _mock_response(200, b"<html/>"),
            _mock_response(200, b"<html/>"),
        ]
        funds = self._funds(3)
        results = fetch_all(funds, session, tmp_path, delay=0)
        assert len(results) == 3
        assert results[0].scrape_status == "failed"
        assert results[1].scrape_status == "success"
        assert results[2].scrape_status == "success"

    def test_delay_is_applied_between_requests(self, tmp_path):
        session = _mock_session(200)
        funds = self._funds(3)
        with patch("ingestion.phase1.fetch.time.sleep") as mock_sleep:
            fetch_all(funds, session, tmp_path, delay=1.5)
        # Delay called between fund 0→1 and fund 1→2 (not after last)
        assert mock_sleep.call_count == 2
        mock_sleep.assert_called_with(1.5)

    def test_no_delay_after_last_fund(self, tmp_path):
        session = _mock_session(200)
        funds = self._funds(2)
        with patch("ingestion.phase1.fetch.time.sleep") as mock_sleep:
            fetch_all(funds, session, tmp_path, delay=1.0)
        assert mock_sleep.call_count == 1

    def test_empty_funds_list_returns_empty(self, tmp_path):
        session = _mock_session(200)
        results = fetch_all([], session, tmp_path, delay=0)
        assert results == []

    def test_single_fund_no_delay_called(self, tmp_path):
        session = _mock_session(200)
        with patch("ingestion.phase1.fetch.time.sleep") as mock_sleep:
            fetch_all(self._funds(1), session, tmp_path, delay=1.0)
        mock_sleep.assert_not_called()

    def test_delay_defaults_to_session_config_value(self, tmp_path):
        from ingestion.phase1.session import SESSION_CONFIG
        session = _mock_session(200)
        funds = self._funds(2)
        with patch("ingestion.phase1.fetch.time.sleep") as mock_sleep:
            fetch_all(funds, session, tmp_path)  # no explicit delay
        mock_sleep.assert_called_with(
            SESSION_CONFIG["delay_between_requests_seconds"]
        )

    def test_result_order_matches_fund_order(self, tmp_path):
        session = _mock_session(200)
        funds = self._funds(4)
        results = fetch_all(funds, session, tmp_path, delay=0)
        for fund, result in zip(funds, results):
            assert result.fund_id == fund["fund_id"]


# ── _utc_now helper tests ─────────────────────────────────────────────────────

class TestUtcNow:
    def test_returns_string(self):
        assert isinstance(_utc_now(), str)

    def test_format_is_iso8601(self):
        ts = _utc_now()
        # Should match YYYY-MM-DDTHH:MM:SSZ
        from datetime import datetime
        parsed = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")
        assert parsed is not None
