"""
Phase 1.2 — Unit tests for ingestion/phase1/session.py

Coverage
--------
- SESSION_CONFIG has all required keys with correct types
- build_session() returns a requests.Session
- Session has correct User-Agent header
- Session has Accept and Accept-Language headers
- HTTPS adapter is mounted (retry logic attached)
- HTTP adapter is NOT mounted (corpus is HTTPS-only)
- Session has no cookies or auth by default
- Retry policy has correct total, backoff, and status_forcelist
"""

import requests
from requests.adapters import HTTPAdapter

from ingestion.phase1.session import SESSION_CONFIG, build_session


class TestSessionConfig:
    """SESSION_CONFIG structure and value validation."""

    def test_has_headers_key(self):
        assert "headers" in SESSION_CONFIG

    def test_headers_has_user_agent(self):
        assert "User-Agent" in SESSION_CONFIG["headers"]

    def test_user_agent_identifies_bot(self):
        ua = SESSION_CONFIG["headers"]["User-Agent"]
        assert "HDFCFAQBot" in ua

    def test_headers_has_accept_language(self):
        assert "Accept-Language" in SESSION_CONFIG["headers"]

    def test_headers_has_accept(self):
        assert "Accept" in SESSION_CONFIG["headers"]

    def test_timeout_is_positive_number(self):
        t = SESSION_CONFIG["timeout_seconds"]
        assert isinstance(t, (int, float)) and t > 0

    def test_delay_is_positive_number(self):
        d = SESSION_CONFIG["delay_between_requests_seconds"]
        assert isinstance(d, (int, float)) and d > 0

    def test_max_retries_is_positive_int(self):
        r = SESSION_CONFIG["max_retries"]
        assert isinstance(r, int) and r > 0

    def test_retry_backoff_factor_is_positive(self):
        b = SESSION_CONFIG["retry_backoff_factor"]
        assert isinstance(b, (int, float)) and b > 0

    def test_retry_status_forcelist_is_list(self):
        assert isinstance(SESSION_CONFIG["retry_status_forcelist"], list)

    def test_retry_status_forcelist_includes_429(self):
        assert 429 in SESSION_CONFIG["retry_status_forcelist"]

    def test_retry_status_forcelist_includes_5xx(self):
        force = SESSION_CONFIG["retry_status_forcelist"]
        assert any(500 <= code <= 599 for code in force)


class TestBuildSession:
    """build_session() return-value contract."""

    def test_returns_requests_session(self):
        session = build_session()
        assert isinstance(session, requests.Session)

    def test_session_has_user_agent_header(self):
        session = build_session()
        ua = session.headers.get("User-Agent", "")
        assert "HDFCFAQBot" in ua

    def test_session_has_accept_language_header(self):
        session = build_session()
        assert "Accept-Language" in session.headers

    def test_session_has_accept_header(self):
        session = build_session()
        assert "Accept" in session.headers

    def test_https_adapter_is_mounted(self):
        session = build_session()
        adapter = session.get_adapter("https://groww.in/mutual-funds/test")
        assert isinstance(adapter, HTTPAdapter)

    def test_https_adapter_has_retry_policy(self):
        session = build_session()
        adapter = session.get_adapter("https://groww.in/mutual-funds/test")
        assert adapter.max_retries is not None
        assert adapter.max_retries.total == SESSION_CONFIG["max_retries"]

    def test_retry_backoff_matches_config(self):
        session = build_session()
        adapter = session.get_adapter("https://groww.in/mutual-funds/test")
        assert adapter.max_retries.backoff_factor == SESSION_CONFIG["retry_backoff_factor"]

    def test_retry_status_forcelist_matches_config(self):
        session = build_session()
        adapter = session.get_adapter("https://groww.in/mutual-funds/test")
        # urllib3 Retry stores forcelist as a frozenset
        forcelist = set(adapter.max_retries.status_forcelist)
        for code in SESSION_CONFIG["retry_status_forcelist"]:
            assert code in forcelist

    def test_http_adapter_is_not_custom(self):
        """HTTP (non-HTTPS) should use the default adapter — corpus is HTTPS-only."""
        session = build_session()
        https_adapter = session.get_adapter("https://groww.in/")
        http_adapter = session.get_adapter("http://groww.in/")
        # The two adapters should be different objects
        assert https_adapter is not http_adapter

    def test_session_has_no_cookies(self):
        session = build_session()
        assert len(session.cookies) == 0

    def test_session_has_no_auth(self):
        session = build_session()
        assert session.auth is None

    def test_build_session_creates_independent_instances(self):
        """Each call returns a new, independent session."""
        s1 = build_session()
        s2 = build_session()
        assert s1 is not s2
