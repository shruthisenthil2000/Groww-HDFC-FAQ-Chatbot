"""
Phase 1.1 — Load & Validate sources.json

Public API
----------
load_and_validate(path=None) -> list[dict]
    Single entry point for Phase 1.1. Returns the validated list of 14
    active fund dicts. Raises ManifestError on any validation failure.
    All subsequent Phase 1 subphases (1.2 → 1.5) must call this first.

load_sources(path=None) -> dict
    Load and JSON-parse sources.json. Raises ManifestError on file/parse
    errors. Separated so callers can inspect raw data if needed.

validate_sources(data) -> list[dict]
    Run all 6 Phase 1.1 validation rules against a parsed dict.
    Accumulates all failures before raising so the full error list is
    visible in one shot.

Validation rules (per architecture.md Phase 1.1)
-------------------------------------------------
1. "funds" list contains exactly EXPECTED_FUND_COUNT (14) active entries.
2. Every fund has all REQUIRED_FUND_FIELDS present and non-null.
3. Every groww_url starts with GROWW_URL_PREFIX.
4. Every doc_type equals EXPECTED_DOC_TYPE ("groww_fund_page").
5. No duplicate fund_id values across the active fund list.
6. Top-level "excluded_duplicates" key exists in the manifest.
   (Bonus) ingestion_date must be ISO-8601 format (YYYY-MM-DD).

Exceptions
----------
ManifestError(ValueError)
    Raised on any validation failure. Message lists every failing check.
    Callers catch this to abort Phase 1 before any network calls.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

# ── Constants ────────────────────────────────────────────────────────────────

GROWW_URL_PREFIX: str = "https://groww.in/mutual-funds/"
EXPECTED_DOC_TYPE: str = "groww_fund_page"
EXPECTED_FUND_COUNT: int = 15

REQUIRED_FUND_FIELDS: tuple[str, ...] = (
    "fund_id",
    "fund_name",
    "groww_url",
    "doc_type",
    "local_file",
    "category",
    "risk_level",
    "ingestion_date",
)

# ingestion/phase1/manifest.py → .parent = phase1/, .parent.parent = ingestion/,
# .parent.parent.parent = project root
_DEFAULT_SOURCES_PATH: Path = (
    Path(__file__).resolve().parent.parent.parent / "corpus" / "sources.json"
)


# ── Exception ────────────────────────────────────────────────────────────────

class ManifestError(ValueError):
    """
    Raised when sources.json fails any Phase 1.1 validation rule.

    Inherits from ValueError so callers can catch the broader class if
    they prefer, while still being distinguishable from generic errors.
    """


# ── Public API ────────────────────────────────────────────────────────────────

def load_sources(path: Path | str | None = None) -> dict[str, Any]:
    """
    Load and JSON-parse sources.json.

    Args:
        path: Explicit path to sources.json. Defaults to
              ``corpus/sources.json`` relative to the project root.

    Returns:
        Parsed top-level dict from sources.json.

    Raises:
        ManifestError: File not found, unreadable, or invalid JSON.
    """
    resolved = Path(path) if path is not None else _DEFAULT_SOURCES_PATH

    if not resolved.exists():
        raise ManifestError(
            f"sources.json not found at: {resolved}\n"
            "Run scripts/phase0_setup.py first to generate it."
        )

    try:
        text = resolved.read_text(encoding="utf-8")
    except OSError as exc:
        raise ManifestError(f"Cannot read sources.json: {exc}") from exc

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ManifestError(f"sources.json is not valid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise ManifestError(
            "sources.json top-level structure must be a JSON object (dict), "
            f"got {type(data).__name__}."
        )

    return data


def validate_sources(data: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Run all Phase 1.1 validation rules against a parsed sources.json dict.

    Collects every failure before raising so the caller sees the complete
    list of problems in a single ManifestError.

    Args:
        data: Parsed dict returned by ``load_sources()``.

    Returns:
        Validated list of ``EXPECTED_FUND_COUNT`` active fund dicts.

    Raises:
        ManifestError: One or more validation rules failed. Message
            contains a bullet-list of every failure.
    """
    errors: list[str] = []

    # Rule 6 — excluded_duplicates key must exist at the top level
    if "excluded_duplicates" not in data:
        errors.append(
            "Missing top-level key 'excluded_duplicates'. "
            "This section documents de-duplicated URLs from the original manifest."
        )

    # Funds list must be present and be an array
    funds = data.get("funds")
    if not isinstance(funds, list):
        errors.append(
            "Missing or invalid 'funds' key — expected a JSON array of fund objects."
        )
        _raise_if_errors(errors)
        return []

    # Rule 1 — exactly EXPECTED_FUND_COUNT entries
    if len(funds) != EXPECTED_FUND_COUNT:
        errors.append(
            f"Expected {EXPECTED_FUND_COUNT} fund entries in 'funds', "
            f"found {len(funds)}."
        )

    seen_fund_ids: dict[str, int] = {}

    for idx, fund in enumerate(funds):
        if not isinstance(fund, dict):
            errors.append(f"funds[{idx}] must be a JSON object, got {type(fund).__name__}.")
            continue

        label = fund.get("fund_name") or fund.get("fund_id") or f"funds[{idx}]"

        # Rule 2 — all required fields present and non-null
        for field in REQUIRED_FUND_FIELDS:
            if field not in fund:
                errors.append(f"[{label}] Missing required field: '{field}'.")
            elif fund[field] is None:
                errors.append(
                    f"[{label}] Required field '{field}' must not be null."
                )

        # Rule 3 — groww_url prefix
        url = fund.get("groww_url") or ""
        if url and not url.startswith(GROWW_URL_PREFIX):
            errors.append(
                f"[{label}] groww_url must start with '{GROWW_URL_PREFIX}', "
                f"got: '{url}'."
            )

        # Rule 4 — doc_type
        doc_type = fund.get("doc_type") or ""
        if doc_type and doc_type != EXPECTED_DOC_TYPE:
            errors.append(
                f"[{label}] doc_type must be '{EXPECTED_DOC_TYPE}', "
                f"got: '{doc_type}'."
            )

        # Rule 5 — no duplicate fund_id
        fid = fund.get("fund_id") or ""
        if fid:
            if fid in seen_fund_ids:
                errors.append(
                    f"Duplicate fund_id '{fid}' found at "
                    f"funds[{seen_fund_ids[fid]}] and funds[{idx}]."
                )
            else:
                seen_fund_ids[fid] = idx

        # Bonus — ingestion_date must be ISO-8601
        ing_date = fund.get("ingestion_date") or ""
        if ing_date:
            try:
                date.fromisoformat(ing_date)
            except ValueError:
                errors.append(
                    f"[{label}] ingestion_date '{ing_date}' is not a valid "
                    "ISO-8601 date (expected YYYY-MM-DD)."
                )

    _raise_if_errors(errors)
    return funds


def load_and_validate(path: Path | str | None = None) -> list[dict[str, Any]]:
    """
    Phase 1.1 single entry point: load + validate sources.json.

    All subsequent Phase 1 subphases (1.2 → 1.5) call this function
    before making any network or filesystem changes.

    Args:
        path: Optional explicit path to sources.json.
              Defaults to ``corpus/sources.json`` at the project root.

    Returns:
        Validated list of 14 active fund dicts, each guaranteed to have:
        fund_id, fund_name, groww_url, doc_type, local_file,
        category, risk_level, ingestion_date — all non-null.

    Raises:
        ManifestError: Any Phase 1.1 validation rule failed.
            The error message lists every failure found.
    """
    data = load_sources(path)
    return validate_sources(data)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _raise_if_errors(errors: list[str]) -> None:
    """Raise ManifestError listing all accumulated errors, if any."""
    if not errors:
        return
    count = len(errors)
    bullet_list = "\n  • ".join(errors)
    raise ManifestError(
        f"sources.json failed Phase 1.1 validation "
        f"({count} error{'s' if count != 1 else ''}):\n  • {bullet_list}"
    )
