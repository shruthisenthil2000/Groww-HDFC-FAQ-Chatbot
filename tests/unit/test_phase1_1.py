"""
Phase 1.1 — Unit tests for ingestion/manifest.py

Test classes
------------
TestLoadSources           — load_sources(): file I/O and JSON parsing
TestValidateSources       — validate_sources(): each of the 6 rules in isolation
TestLoadAndValidate       — load_and_validate(): combined contract tests
TestRealSourcesJson       — smoke tests against the real corpus/sources.json
                            (skipped automatically if the file is absent)

Coverage checklist (maps to architecture.md Phase 1.1 rules)
-------------------------------------------------------------
Rule 1  — exactly 14 fund entries
Rule 2  — all required fields present and non-null
Rule 3  — groww_url starts with GROWW_URL_PREFIX
Rule 4  — doc_type == EXPECTED_DOC_TYPE
Rule 5  — no duplicate fund_id values
Rule 6  — excluded_duplicates key exists
Bonus   — ingestion_date is ISO-8601
Extra   — errors are accumulated (not short-circuited after first failure)
"""

import json
from pathlib import Path

import pytest

from ingestion.phase1.manifest import (
    EXPECTED_DOC_TYPE,
    EXPECTED_FUND_COUNT,
    GROWW_URL_PREFIX,
    REQUIRED_FUND_FIELDS,
    ManifestError,
    load_and_validate,
    load_sources,
    validate_sources,
)

# ── Helpers ───────────────────────────────────────────────────────────────────

_REAL_SOURCES = Path(__file__).resolve().parents[2] / "corpus" / "sources.json"


def _fund(
    fund_id: str = "hdfc_test",
    fund_name: str = "HDFC Test Fund Direct Growth",
    groww_url: str = "https://groww.in/mutual-funds/hdfc-test-fund-direct-growth",
    doc_type: str = "groww_fund_page",
    local_file: str = "corpus/raw/hdfc_test.html",
    category: str = "Equity",
    risk_level: str = "Very High",
    ingestion_date: str = "2026-05-08",
    **extra,
) -> dict:
    """Return a minimal valid fund dict."""
    return {
        "fund_id": fund_id,
        "fund_name": fund_name,
        "groww_url": groww_url,
        "doc_type": doc_type,
        "local_file": local_file,
        "category": category,
        "risk_level": risk_level,
        "ingestion_date": ingestion_date,
        "is_duplicate": False,
        **extra,
    }


def _manifest(n: int = EXPECTED_FUND_COUNT, **top_level_overrides) -> dict:
    """Return a minimal valid manifest dict with n fund entries."""
    base = {
        "_meta": {"ingestion_date": "2026-05-08"},
        "amc": {"name": "HDFC Mutual Fund"},
        "excluded_duplicates": [
            {"url": "https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth",
             "reason": "duplicate of fund_id hdfc_flexi_cap"}
        ],
        "funds": [
            _fund(
                fund_id=f"hdfc_fund_{i}",
                fund_name=f"HDFC Fund {i} Direct Growth",
                groww_url=f"https://groww.in/mutual-funds/hdfc-fund-{i}-direct-growth",
                local_file=f"corpus/raw/hdfc_fund_{i}.html",
            )
            for i in range(n)
        ],
    }
    base.update(top_level_overrides)
    return base


def _write(tmp_path: Path, data: dict) -> Path:
    """Write data as JSON to a temp sources.json and return the path."""
    p = tmp_path / "sources.json"
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return p


# ── TestLoadSources ───────────────────────────────────────────────────────────

class TestLoadSources:
    """load_sources() — file I/O and JSON parsing."""

    def test_returns_dict_for_valid_file(self, tmp_path):
        p = _write(tmp_path, _manifest())
        result = load_sources(p)
        assert isinstance(result, dict)

    def test_funds_key_present_in_result(self, tmp_path):
        p = _write(tmp_path, _manifest())
        result = load_sources(p)
        assert "funds" in result

    def test_raises_manifest_error_when_file_missing(self, tmp_path):
        with pytest.raises(ManifestError, match="not found"):
            load_sources(tmp_path / "no_file.json")

    def test_raises_manifest_error_for_invalid_json(self, tmp_path):
        bad = tmp_path / "sources.json"
        bad.write_text("{ this is not json }", encoding="utf-8")
        with pytest.raises(ManifestError, match="not valid JSON"):
            load_sources(bad)

    def test_raises_when_top_level_is_array(self, tmp_path):
        bad = tmp_path / "sources.json"
        bad.write_text("[1, 2, 3]", encoding="utf-8")
        with pytest.raises(ManifestError, match="top-level"):
            load_sources(bad)

    def test_raises_when_top_level_is_string(self, tmp_path):
        bad = tmp_path / "sources.json"
        bad.write_text('"just a string"', encoding="utf-8")
        with pytest.raises(ManifestError, match="top-level"):
            load_sources(bad)

    def test_uses_default_path_when_none_given(self, monkeypatch, tmp_path):
        """load_sources() should use the default path when path=None."""
        p = _write(tmp_path, _manifest())
        import ingestion.phase1.manifest as m_mod
        monkeypatch.setattr(m_mod, "_DEFAULT_SOURCES_PATH", p)
        result = load_sources(None)
        assert isinstance(result, dict)


# ── TestValidateSources ───────────────────────────────────────────────────────

class TestValidateSources:
    """validate_sources() — each rule in isolation."""

    # Happy path
    def test_valid_manifest_returns_list(self):
        funds = validate_sources(_manifest())
        assert isinstance(funds, list)

    def test_valid_manifest_returns_correct_count(self):
        funds = validate_sources(_manifest())
        assert len(funds) == EXPECTED_FUND_COUNT

    def test_returned_funds_are_dicts(self):
        funds = validate_sources(_manifest())
        assert all(isinstance(f, dict) for f in funds)

    # Rule 1 — fund count
    def test_raises_when_fewer_than_14_funds(self):
        with pytest.raises(ManifestError, match=f"Expected {EXPECTED_FUND_COUNT}"):
            validate_sources(_manifest(n=13))

    def test_raises_when_more_than_14_funds(self):
        with pytest.raises(ManifestError, match=f"Expected {EXPECTED_FUND_COUNT}"):
            validate_sources(_manifest(n=EXPECTED_FUND_COUNT + 1))

    def test_raises_for_zero_funds(self):
        with pytest.raises(ManifestError):
            validate_sources(_manifest(n=0))

    # Rule 2 — required fields
    @pytest.mark.parametrize("field", REQUIRED_FUND_FIELDS)
    def test_raises_when_required_field_missing(self, field):
        data = _manifest()
        del data["funds"][0][field]
        with pytest.raises(ManifestError, match=field):
            validate_sources(data)

    @pytest.mark.parametrize("field", REQUIRED_FUND_FIELDS)
    def test_raises_when_required_field_is_null(self, field):
        data = _manifest()
        data["funds"][0][field] = None
        with pytest.raises(ManifestError, match="must not be null"):
            validate_sources(data)

    # Rule 3 — groww_url prefix
    def test_raises_for_non_groww_url(self):
        data = _manifest()
        data["funds"][0]["groww_url"] = "https://amfiindia.com/some-fund"
        with pytest.raises(ManifestError, match=f"must start with '{GROWW_URL_PREFIX}'"):
            validate_sources(data)

    def test_raises_for_http_instead_of_https(self):
        data = _manifest()
        data["funds"][0]["groww_url"] = "http://groww.in/mutual-funds/hdfc-test"
        with pytest.raises(ManifestError, match="must start with"):
            validate_sources(data)

    def test_raises_for_empty_url(self):
        data = _manifest()
        data["funds"][0]["groww_url"] = None
        with pytest.raises(ManifestError, match="must not be null"):
            validate_sources(data)

    # Rule 4 — doc_type
    def test_raises_for_wrong_doc_type(self):
        data = _manifest()
        data["funds"][0]["doc_type"] = "pdf_factsheet"
        with pytest.raises(ManifestError, match=f"must be '{EXPECTED_DOC_TYPE}'"):
            validate_sources(data)

    def test_raises_for_empty_doc_type_string(self):
        data = _manifest()
        data["funds"][0]["doc_type"] = None
        with pytest.raises(ManifestError, match="must not be null"):
            validate_sources(data)

    # Rule 5 — duplicate fund_id
    def test_raises_for_duplicate_fund_id(self):
        data = _manifest()
        data["funds"][1]["fund_id"] = data["funds"][0]["fund_id"]
        with pytest.raises(ManifestError, match="Duplicate fund_id"):
            validate_sources(data)

    def test_different_fund_ids_do_not_raise(self):
        data = _manifest()
        funds = validate_sources(data)
        ids = [f["fund_id"] for f in funds]
        assert len(ids) == len(set(ids))

    # Rule 6 — excluded_duplicates key
    def test_raises_when_excluded_duplicates_missing(self):
        data = _manifest()
        del data["excluded_duplicates"]
        with pytest.raises(ManifestError, match="excluded_duplicates"):
            validate_sources(data)

    def test_empty_excluded_duplicates_list_is_allowed(self):
        """Key must exist, but an empty list is valid."""
        data = _manifest()
        data["excluded_duplicates"] = []
        funds = validate_sources(data)
        assert len(funds) == EXPECTED_FUND_COUNT

    # Bonus — ingestion_date format
    def test_raises_for_invalid_ingestion_date_format(self):
        data = _manifest()
        data["funds"][0]["ingestion_date"] = "08/05/2026"
        with pytest.raises(ManifestError, match="not a valid ISO-8601 date"):
            validate_sources(data)

    def test_raises_for_non_date_ingestion_date(self):
        data = _manifest()
        data["funds"][0]["ingestion_date"] = "yesterday"
        with pytest.raises(ManifestError, match="not a valid ISO-8601 date"):
            validate_sources(data)

    def test_valid_iso_date_does_not_raise(self):
        data = _manifest()
        data["funds"][0]["ingestion_date"] = "2025-01-01"
        funds = validate_sources(data)
        assert len(funds) == EXPECTED_FUND_COUNT

    # Error accumulation — must not short-circuit
    def test_accumulates_multiple_errors_before_raising(self):
        """All failures should appear in a single ManifestError, not just the first."""
        data = _manifest()
        data["funds"][0]["doc_type"] = "bad_type_1"
        data["funds"][1]["doc_type"] = "bad_type_2"
        data["funds"][2]["doc_type"] = "bad_type_3"
        with pytest.raises(ManifestError) as exc_info:
            validate_sources(data)
        msg = str(exc_info.value)
        assert "bad_type_1" in msg
        assert "bad_type_2" in msg
        assert "bad_type_3" in msg

    def test_raises_manifest_error_not_generic_value_error(self):
        data = _manifest()
        del data["funds"][0]["fund_id"]
        with pytest.raises(ManifestError):
            validate_sources(data)

    def test_funds_array_must_be_list_not_dict(self):
        data = _manifest()
        data["funds"] = {"bad": "structure"}
        with pytest.raises(ManifestError, match="expected a JSON array"):
            validate_sources(data)


# ── TestLoadAndValidate ───────────────────────────────────────────────────────

class TestLoadAndValidate:
    """load_and_validate() — combined contract (the Phase 1.1 entry point)."""

    def test_valid_file_returns_14_funds(self, tmp_path):
        p = _write(tmp_path, _manifest())
        funds = load_and_validate(p)
        assert len(funds) == EXPECTED_FUND_COUNT

    def test_every_fund_has_all_required_fields(self, tmp_path):
        p = _write(tmp_path, _manifest())
        funds = load_and_validate(p)
        for fund in funds:
            for field in REQUIRED_FUND_FIELDS:
                assert field in fund, (
                    f"Field '{field}' missing from fund '{fund.get('fund_id')}'"
                )


    def test_every_fund_has_correct_doc_type(self, tmp_path):
        p = _write(tmp_path, _manifest())
        funds = load_and_validate(p)
        for fund in funds:
            assert fund["doc_type"] == EXPECTED_DOC_TYPE

    def test_every_fund_has_valid_groww_url(self, tmp_path):
        p = _write(tmp_path, _manifest())
        funds = load_and_validate(p)
        for fund in funds:
            assert fund["groww_url"].startswith(GROWW_URL_PREFIX), (
                f"Bad URL in fund '{fund.get('fund_id')}': {fund['groww_url']}"
            )

    def test_fund_ids_are_unique(self, tmp_path):
        p = _write(tmp_path, _manifest())
        funds = load_and_validate(p)
        ids = [f["fund_id"] for f in funds]
        assert len(ids) == len(set(ids)), f"Duplicate fund_ids found: {ids}"

    def test_raises_manifest_error_on_missing_file(self, tmp_path):
        with pytest.raises(ManifestError):
            load_and_validate(tmp_path / "no_such_file.json")

    def test_raises_manifest_error_on_invalid_json(self, tmp_path):
        bad = tmp_path / "sources.json"
        bad.write_text("{bad json}", encoding="utf-8")
        with pytest.raises(ManifestError):
            load_and_validate(bad)

    def test_raises_manifest_error_on_wrong_count(self, tmp_path):
        p = _write(tmp_path, _manifest(n=10))
        with pytest.raises(ManifestError, match=f"Expected {EXPECTED_FUND_COUNT}"):
            load_and_validate(p)

    def test_manifest_error_is_subclass_of_value_error(self, tmp_path):
        p = _write(tmp_path, _manifest(n=5))
        with pytest.raises(ValueError):
            load_and_validate(p)


# ── TestRealSourcesJson ───────────────────────────────────────────────────────

class TestRealSourcesJson:
    """
    Smoke tests against the actual corpus/sources.json produced by Phase 0.
    All tests in this class are auto-skipped if the file does not exist.
    """

    @pytest.fixture(autouse=True)
    def skip_if_missing(self):
        if not _REAL_SOURCES.exists():
            pytest.skip(
                "corpus/sources.json not found — "
                "run `python3 scripts/phase0_setup.py` first."
            )

    def test_passes_full_validation(self):
        funds = load_and_validate(_REAL_SOURCES)
        assert len(funds) == EXPECTED_FUND_COUNT

    def test_all_funds_are_hdfc(self):
        funds = load_and_validate(_REAL_SOURCES)
        for fund in funds:
            assert "hdfc" in fund["fund_name"].lower(), (
                f"Non-HDFC fund in corpus: {fund['fund_name']}"
            )

    def test_all_urls_point_to_groww(self):
        funds = load_and_validate(_REAL_SOURCES)
        for fund in funds:
            assert fund["groww_url"].startswith("https://groww.in/mutual-funds/"), (
                f"Non-Groww URL: {fund['groww_url']}"
            )

    def test_all_doc_types_are_groww_fund_page(self):
        funds = load_and_validate(_REAL_SOURCES)
        for fund in funds:
            assert fund["doc_type"] == "groww_fund_page"

    def test_no_duplicate_fund_ids(self):
        funds = load_and_validate(_REAL_SOURCES)
        ids = [f["fund_id"] for f in funds]
        assert len(ids) == len(set(ids))

    def test_all_funds_have_non_empty_local_file(self):
        funds = load_and_validate(_REAL_SOURCES)
        for fund in funds:
            assert fund.get("local_file"), (
                f"Empty local_file in fund '{fund.get('fund_id')}'"
            )

    def test_validation_status_is_validated(self):
        """Phase 0 setup marks each fund 'validated' — confirm it persists."""
        funds = load_and_validate(_REAL_SOURCES)
        for fund in funds:
            status = fund.get("validation_status", "")
            assert status == "validated", (
                f"Fund '{fund.get('fund_id')}' has status '{status}', expected 'validated'. "
                "Run scripts/phase0_setup.py to refresh."
            )
