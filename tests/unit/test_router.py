"""
Unit tests for retrieval/router.py — Phase 3.2.1

Tests cover:
  - Fund name detection (all 15 funds, including alias variants)
  - Section routing (all 6 section types, including synonym variants)
  - Combined route() output
  - No-match fallback (both signals None)
  - Case insensitivity
  - Priority: longer/specific alias matches before shorter ones
"""

import pytest
from retrieval.router import route, _detect_fund, _detect_section, _normalise


# ── _normalise ─────────────────────────────────────────────────────────────────

class TestNormalise:
    def test_lowercases(self):
        assert _normalise("HDFC Mid Cap") == "hdfc mid cap"

    def test_collapses_whitespace(self):
        assert _normalise("HDFC  Mid   Cap") == "hdfc mid cap"

    def test_strips_edges(self):
        assert _normalise("  expense ratio  ") == "expense ratio"


# ── Fund detection ─────────────────────────────────────────────────────────────

FUND_CASES = [
    # (query, expected_fund_id)
    ("What is the exit load for HDFC Mid Cap Fund?",        "hdfc_mid_cap"),
    ("Tell me about HDFC midcap",                           "hdfc_mid_cap"),
    ("HDFC mid-cap expense ratio",                          "hdfc_mid_cap"),
    ("What does the ELSS fund invest in?",                  "hdfc_elss"),
    ("HDFC Tax Saver fund details",                         "hdfc_elss"),
    ("HDFC tax saving details",                             "hdfc_elss"),
    ("Who manages HDFC Large Cap?",                         "hdfc_large_cap"),
    ("HDFC Large-Cap minimum SIP",                          "hdfc_large_cap"),
    ("HDFC Small Cap Fund exit load",                       "hdfc_small_cap"),
    ("HDFC SmallCap benchmark",                             "hdfc_small_cap"),
    ("HDFC Nifty 50 Index Fund expense ratio",              "hdfc_nifty50_index"),
    ("nifty50 fund details",                                "hdfc_nifty50_index"),
    ("HDFC BSE Sensex Index Fund",                          "hdfc_bse_sensex_index"),
    ("hdfc sensex index expense ratio",                     "hdfc_bse_sensex_index"),
    ("HDFC Flexi Cap direct plan",                          "hdfc_flexi_cap"),
    ("HDFC Equity Fund is it same as flexi cap?",           "hdfc_flexi_cap"),
    ("HDFC Focused Fund investment objective",              "hdfc_focused"),
    ("HDFC Housing Opportunities Fund expense ratio",       "hdfc_housing_opportunities"),
    ("What is the benchmark for housing opportunities fund?", "hdfc_housing_opportunities"),
    ("HDFC Defence Fund minimum investment",                "hdfc_defence"),
    ("HDFC Pharma fund benchmark",                          "hdfc_pharma_healthcare"),
    ("healthcare fund exit load",                           "hdfc_pharma_healthcare"),
    ("HDFC Gold ETF FoF minimum SIP",                       "hdfc_gold_etf_fof"),
    ("HDFC Silver ETF FoF",                                 "hdfc_silver_etf_fof"),
    ("HDFC Balanced Advantage Fund details",                "hdfc_balanced_advantage"),
    ("dynamic asset allocation fund",                       "hdfc_balanced_advantage"),
    ("HDFC Short Term Debt fund",                           "hdfc_short_term_debt"),
    ("HDFC debt fund expense ratio",                        "hdfc_short_term_debt"),
]

@pytest.mark.parametrize("query,expected", FUND_CASES)
def test_detect_fund(query, expected):
    assert _detect_fund(_normalise(query)) == expected


def test_detect_fund_no_match():
    assert _detect_fund(_normalise("What is a mutual fund?")) is None

def test_detect_fund_generic_hdfc_no_match():
    assert _detect_fund(_normalise("Tell me about HDFC Mutual Fund")) is None

def test_nifty50_beats_generic():
    """'nifty 50' should match hdfc_nifty50_index, not a broader rule."""
    assert _detect_fund(_normalise("nifty 50 index fund")) == "hdfc_nifty50_index"


# ── Section routing ────────────────────────────────────────────────────────────

SECTION_CASES = [
    # (query, expected_section_type)
    ("What is the expense ratio?",                          "fund_overview"),
    ("Tell me the TER for this fund",                       "fund_overview"),
    ("What is the minimum SIP amount?",                     "fund_overview"),
    ("What is the NAV of the fund?",                        "fund_overview"),
    ("What is the AUM of HDFC Mid Cap?",                    "fund_overview"),
    ("What is the riskometer level?",                       "fund_overview"),
    ("What is the exit load for redemption within 1 year?", "exit_load_tax"),
    ("Is there an early withdrawal charge?",                "exit_load_tax"),
    ("What is the LTCG tax on this fund?",                  "exit_load_tax"),
    ("What is the STCG on equity funds?",                   "exit_load_tax"),
    ("What is the stamp duty?",                             "exit_load_tax"),
    ("Tell me the tax treatment for this fund",             "exit_load_tax"),
    ("What is the investment objective?",                   "investment_objective"),
    ("What index does this fund track?",                    "investment_objective"),
    ("What is the benchmark index?",                        "investment_objective"),
    ("Who manages the fund?",                               "fund_manager"),
    ("Who is the fund manager?",                            "fund_manager"),
    ("Tell me about the portfolio manager",                 "fund_manager"),
    ("What is HDFC AMC?",                                   "fund_house"),
    ("Tell me about the fund house",                        "fund_house"),
    ("What is the AMC details?",                            "fund_house"),
    ("Tell me about HDFC Mid Cap Fund",                     "about"),
    ("What is HDFC Mutual Fund? Describe it",               "about"),
    ("Give me an overview of the fund",                     "about"),
]

@pytest.mark.parametrize("query,expected", SECTION_CASES)
def test_detect_section(query, expected):
    assert _detect_section(_normalise(query)) == expected


def test_detect_section_no_match():
    assert _detect_section(_normalise("What is the weather today?")) is None

def test_detect_section_out_of_scope():
    assert _detect_section(_normalise("Should I invest in this fund?")) is None


# ── route() combined ───────────────────────────────────────────────────────────

class TestRoute:

    def test_both_signals(self):
        fund, section = route("What is the exit load for HDFC Mid Cap Fund?")
        assert fund == "hdfc_mid_cap"
        assert section == "exit_load_tax"

    def test_fund_only(self):
        fund, section = route("HDFC ELSS details please")
        assert fund == "hdfc_elss"
        assert section is None

    def test_section_only(self):
        fund, section = route("What is the expense ratio?")
        assert fund is None
        assert section == "fund_overview"

    def test_no_signals(self):
        fund, section = route("What is a mutual fund?")
        assert fund is None
        assert section is None

    def test_case_insensitive(self):
        fund, section = route("WHAT IS THE EXIT LOAD FOR HDFC MID CAP?")
        assert fund == "hdfc_mid_cap"
        assert section == "exit_load_tax"

    def test_who_manages_elss(self):
        fund, section = route("Who manages the ELSS fund?")
        assert fund == "hdfc_elss"
        assert section == "fund_manager"

    def test_about_gold_fund(self):
        fund, section = route("Tell me about HDFC Gold ETF fund")
        assert fund == "hdfc_gold_etf_fof"
        assert section == "about"   # "tell me about" → about

    def test_benchmark_sensex(self):
        fund, section = route("What is the benchmark index for HDFC Sensex fund?")
        assert fund == "hdfc_bse_sensex_index"
        assert section == "investment_objective"

    def test_tax_treatment_nifty(self):
        fund, section = route("What is the LTCG tax on HDFC Nifty 50 Index Fund?")
        assert fund == "hdfc_nifty50_index"
        assert section == "exit_load_tax"

    def test_returns_tuple(self):
        result = route("any query")
        assert isinstance(result, tuple)
        assert len(result) == 2
