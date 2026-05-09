/**
 * Corpus fund_id → MFAPI scheme codes (direct growth / direct plan variants).
 * Verified against https://api.mfapi.in/mf master list (HDFC + Direct + Growth).
 */
export const TRACKED_SCHEMES = [
  { fundId: 'hdfc_flexi_cap', schemeCode: '118955' },
  { fundId: 'hdfc_mid_cap', schemeCode: '118989' },
  { fundId: 'hdfc_focused', schemeCode: '118950' },
  { fundId: 'hdfc_elss', schemeCode: '119060' },
  { fundId: 'hdfc_large_cap', schemeCode: '119018' },
  { fundId: 'hdfc_silver_etf_fof', schemeCode: '150737' },
  { fundId: 'hdfc_small_cap', schemeCode: '130503' },
  { fundId: 'hdfc_defence', schemeCode: '151750' },
  { fundId: 'hdfc_gold_etf_fof', schemeCode: '119132' },
  { fundId: 'hdfc_nifty50_index', schemeCode: '119063' },
  { fundId: 'hdfc_balanced_advantage', schemeCode: '118968' },
  { fundId: 'hdfc_pharma_healthcare', schemeCode: '152082' },
  { fundId: 'hdfc_bse_sensex_index', schemeCode: '119065' },
  { fundId: 'hdfc_short_term_debt', schemeCode: '119016' },
  { fundId: 'hdfc_housing_opportunities', schemeCode: '141924' },
]

export const SCHEME_TO_FUND_ID = Object.fromEntries(
  TRACKED_SCHEMES.map((t) => [t.schemeCode, t.fundId])
)
