/**
 * Corpus fund metadata for dashboard / explorer (sources.json + short labels + summaries).
 * Vite resolves JSON from project corpus/.
 */
import sources from '../../../corpus/sources.json'

/** Display labels aligned with investor-facing names (corpus is source of truth for IDs). */
const SHORT_LABEL = {
  hdfc_flexi_cap: 'HDFC Flexi Cap',
  hdfc_mid_cap: 'HDFC Mid Cap',
  hdfc_focused: 'HDFC Focused Fund',
  hdfc_elss: 'HDFC ELSS Tax Saver',
  hdfc_large_cap: 'HDFC Large Cap',
  hdfc_small_cap: 'HDFC Small Cap',
  hdfc_defence: 'HDFC Defence',
  hdfc_housing_opportunities: 'HDFC Housing Opportunities',
  hdfc_balanced_advantage: 'HDFC Balanced Advantage',
  hdfc_pharma_healthcare: 'HDFC Pharma & Healthcare',
  hdfc_nifty50_index: 'HDFC Nifty 50 Index',
  hdfc_bse_sensex_index: 'HDFC BSE Sensex Index',
  hdfc_gold_etf_fof: 'HDFC Gold ETF FoF',
  hdfc_silver_etf_fof: 'HDFC Silver ETF FoF',
  hdfc_short_term_debt: 'HDFC Short Term Debt',
}

const OBJECTIVE_SUMMARY = {
  hdfc_flexi_cap:
    'Seeks long-term capital appreciation by investing across large, mid, and small-cap equities with a flexi-cap mandate.',
  hdfc_mid_cap:
    'Focuses predominantly on mid-cap companies with growth potential while managing portfolio risk.',
  hdfc_focused:
    'Concentrated equity portfolio in a limited number of stocks per SEBI focused-fund rules.',
  hdfc_elss:
    'ELSS equity fund with Section 80C benefit and a statutory lock-in; aims for long-term wealth creation.',
  hdfc_large_cap:
    'Invests primarily in large-cap equities for relatively stable core equity exposure.',
  hdfc_small_cap:
    'Targets small-cap opportunities with higher volatility and growth-oriented profile.',
  hdfc_defence:
    'Thematic equity exposure aligned to the defence sector and related value chain.',
  hdfc_housing_opportunities:
    'Invests in companies linked to housing and allied activities; thematic equity exposure.',
  hdfc_balanced_advantage:
    'Dynamic asset allocation between equity and debt to balance growth and downside management.',
  hdfc_pharma_healthcare:
    'Sectoral fund focused on pharma and healthcare-related equities.',
  hdfc_nifty50_index:
    'Passive fund tracking NIFTY 50 TRI with low tracking error objective.',
  hdfc_bse_sensex_index:
    'Passive fund tracking SENSEX TRI for broad large-cap index exposure.',
  hdfc_gold_etf_fof:
    'Fund of fund investing in gold ETFs; exposure to domestic gold price movement.',
  hdfc_silver_etf_fof:
    'Fund of fund investing in silver ETFs; commodity FoF exposure.',
  hdfc_short_term_debt:
    'Short-duration debt portfolio aiming for income with relatively lower interest-rate sensitivity than longer debt.',
}

export function getCorpusFunds() {
  return sources.funds.map((f) => ({
    ...f,
    shortLabel: SHORT_LABEL[f.fund_id] ?? f.fund_name.replace(/\s+Direct.*$/i, '').trim(),
    objectiveSummary:
      OBJECTIVE_SUMMARY[f.fund_id] ??
      `${f.category} scheme (${f.sub_category ?? 'HDFC MF'}). See fund documents for full objective.`,
    benchmark:
      f.benchmark ??
      (f.fund_id === 'hdfc_housing_opportunities'
        ? 'Nifty Housing Total Return Index'
        : '—'),
  }))
}

export const AMC_SNAPSHOT = {
  name: sources.amc?.name ?? 'HDFC Mutual Fund',
  totalAumCr: sources.amc?.total_aum_cr ?? '—',
  rankNote: sources.amc?.rank_note ?? '',
}
