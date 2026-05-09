"""
Phase 1.2 — Configure HTTP Scraper Session

Responsibility
--------------
Build a reusable ``requests.Session`` with safe, respectful scraping
defaults.  Every Phase 1.3 fetch call must obtain its session from
``build_session()`` — no bare ``requests.get`` calls elsewhere.

Public API
----------
build_session() -> requests.Session
    Returns a fully configured session: custom headers, exponential-
    backoff retry adapter mounted on HTTPS, and a frozen timeout.

SESSION_CONFIG : dict
    Declarative constants that drive session construction. Import this
    in Phase 1.3 to read DELAY and TIMEOUT without circular deps.

Constraints (per architecture.md Phase 1.2)
-------------------------------------------
- No crawling or link-following; only the 14 URLs from sources.json.
- No authentication, cookies, or session tokens.
- No PII in request headers or query params.
- User-Agent clearly identifies the bot.
"""

from __future__ import annotations

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ── Session configuration ─────────────────────────────────────────────────────

SESSION_CONFIG: dict = {
    "headers": {
        "User-Agent": (
            "Mozilla/5.0 (compatible; HDFCFAQBot/1.0; +internal-research)"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml",
    },
    # Seconds to wait for the server to respond before timing out.
    "timeout_seconds": 30,
    # Polite delay between consecutive requests to avoid hammering the server.
    "delay_between_requests_seconds": 2,
    # Retry on transient server errors and rate-limit responses.
    "max_retries": 3,
    "retry_backoff_factor": 2.0,
    # HTTP status codes that trigger a retry.
    "retry_status_forcelist": [429, 500, 502, 503, 504],
}


# ── Public API ────────────────────────────────────────────────────────────────

def build_session() -> requests.Session:
    """
    Build and return a configured ``requests.Session``.

    The session is pre-configured with:
    - Custom User-Agent and Accept headers (from SESSION_CONFIG).
    - An HTTPAdapter with exponential-backoff retry logic mounted on
      ``https://``. The same adapter is NOT mounted on ``http://`` to
      enforce HTTPS-only access per the corpus scope constraint.
    - Cookies are intentionally left empty; ``session.cookies.clear()``
      is called after construction as an explicit guard.

    Returns:
        requests.Session ready to use for Phase 1.3 fetch calls.
    """
    retry_policy = Retry(
        total=SESSION_CONFIG["max_retries"],
        backoff_factor=SESSION_CONFIG["retry_backoff_factor"],
        status_forcelist=SESSION_CONFIG["retry_status_forcelist"],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry_policy)

    session = requests.Session()
    session.headers.update(SESSION_CONFIG["headers"])
    # Mount only on HTTPS — corpus URLs must all be https://groww.in/...
    session.mount("https://", adapter)
    # Explicit guard: no cookies, no auth tokens.
    session.cookies.clear()
    session.auth = None

    return session
