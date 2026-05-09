import { memo, useMemo } from 'react'
import { NAV_IDS } from './dashboardNav'
import { FundDetailCard } from './FundDetailCard'
import { AMC_SNAPSHOT } from '../data/corpusFundModel'
import { formatInrNav, formatPct1d } from '../utils/navDisplay'

const MOCK_OVERVIEW = {
  activeSips: 12,
  equityPct: 68,
  debtPct: 18,
  hybridCommPct: 14,
  portfolioValueLakh: '42.6',
}

const MOCK_SIPS = [
  { name: 'HDFC Mid Cap · SIP', amount: '₹15,000', date: '08 May' },
  { name: 'HDFC ELSS · SIP', amount: '₹12,500', date: '05 May' },
  { name: 'HDFC Balanced Advantage · SIP', amount: '₹10,000', date: '01 May' },
]

const MOCK_WATCHLIST = ['HDFC Nifty 50 Index', 'HDFC Housing Opportunities', 'HDFC Short Term Debt']

/** Demo rows — linked to corpus fund_id for live NAV 1D. */
const DEMO_HOLDINGS = [
  { fundId: 'hdfc_mid_cap', scheme: 'HDFC Mid Cap Dir Gr', units: '1,842.3', value: '₹8.42 L' },
  { fundId: 'hdfc_elss', scheme: 'HDFC ELSS Dir Gr', units: '2,104.0', value: '₹6.18 L' },
  { fundId: 'hdfc_balanced_advantage', scheme: 'HDFC Balanced Adv Dir Gr', units: '3,956.1', value: '₹12.05 L' },
  { fundId: 'hdfc_short_term_debt', scheme: 'HDFC Short Term Debt Dir Gr', units: '8,200.0', value: '₹9.88 L' },
]

const MOCK_STATEMENTS = [
  { title: 'Consolidated CAS · Apr 2026', type: 'PDF', date: '30 Apr 2026' },
  { title: 'Capital gains statement · FY25–26', type: 'PDF', date: '15 Apr 2026' },
  { title: 'Annual transaction summary', type: 'PDF', date: '01 Apr 2026' },
]

function corpusAvgChange(funds) {
  const vals = funds.map((f) => f.liveNav?.change).filter((v) => v != null && !Number.isNaN(v))
  if (vals.length === 0) return null
  return Math.round((vals.reduce((a, b) => a + b, 0) / vals.length) * 100) / 100
}

function useMarketSnapshotRows(funds) {
  return useMemo(() => {
    const pick = (id) => funds.find((f) => f.fund_id === id)?.liveNav
    const nifty = pick('hdfc_nifty50_index')
    const sensex = pick('hdfc_bse_sensex_index')
    const debt = pick('hdfc_short_term_debt')
    return [
      { label: 'NIFTY 50', sub: 'Index fund 1D', raw: nifty?.change },
      { label: 'SENSEX', sub: 'Index fund 1D', raw: sensex?.change },
      { label: 'Short duration debt', sub: 'HDFC ST debt 1D', raw: debt?.change },
    ]
  }, [funds])
}

function GrowthSparkline() {
  return (
    <svg className="dw-chart-svg" viewBox="0 0 320 96" preserveAspectRatio="none" aria-hidden>
      <defs>
        <linearGradient id="dwFill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--accent-chart-fill-top)" />
          <stop offset="100%" stopColor="var(--accent-chart-fill-bottom)" />
        </linearGradient>
      </defs>
      <path
        className="dw-chart-area"
        d="M0,72 C40,68 60,52 100,48 S180,28 220,32 S280,18 320,22 L320,96 L0,96 Z"
        fill="url(#dwFill)"
      />
      <path
        className="dw-chart-line"
        d="M0,72 C40,68 60,52 100,48 S180,28 220,32 S280,18 320,22"
        fill="none"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  )
}

function AllocationDonut() {
  const { equityPct, debtPct, hybridCommPct } = MOCK_OVERVIEW
  const e = equityPct
  const d = debtPct
  const h = hybridCommPct
  const grad = `conic-gradient(
    var(--dw-donut-eq) 0% ${e}%,
    var(--dw-donut-de) ${e}% ${e + d}%,
    var(--dw-donut-hy) ${e + d}% 100%
  )`
  return (
    <div className="dw-donut-wrap">
      <div className="dw-donut" style={{ background: grad }} />
      <div className="dw-donut-hole" />
    </div>
  )
}

const DashboardHome = memo(function DashboardHome({ funds, corpusFundCount, onFundClick, allFunds, navLoading }) {
  const avg1d = useMemo(() => corpusAvgChange(allFunds), [allFunds])
  const marketRows = useMarketSnapshotRows(allFunds)

  return (
    <div className="dw-home dw-fade">
      <p className="dw-disclaimer">
        Illustrative portfolio view — not your actual holdings. Fund facts below match the assistant corpus.
      </p>

      <section className="dw-section">
        <h2 className="dw-h2">Overview</h2>
        <div className="dw-kpi-grid">
          <article className="dw-kpi">
            <span className="dw-kpi-label">AMC AUM (India)</span>
            <strong className="dw-kpi-value">₹{AMC_SNAPSHOT.totalAumCr} Cr</strong>
            <span className="dw-kpi-hint">{AMC_SNAPSHOT.rankNote}</span>
          </article>
          <article className="dw-kpi">
            <span className="dw-kpi-label">Active SIPs (demo)</span>
            <strong className="dw-kpi-value">{MOCK_OVERVIEW.activeSips}</strong>
            <span className="dw-kpi-hint">Across linked folios</span>
          </article>
          <article className="dw-kpi">
            <span className="dw-kpi-label">Equity allocation</span>
            <strong className="dw-kpi-value">{MOCK_OVERVIEW.equityPct}%</strong>
            <span className="dw-kpi-hint">Illustrative mix</span>
          </article>
          <article className="dw-kpi">
            <span className="dw-kpi-label">Corpus 1D Δ (avg)</span>
            {navLoading ? (
              <strong className="dw-kpi-value dw-kpi-skel-wrap">
                <span className="dw-skel-line dw-skel-line--kpi" />
              </strong>
            ) : (
              <strong className={`dw-kpi-value ${avg1d != null && avg1d >= 0 ? 'dw-kpi-pos' : avg1d != null ? 'dw-kpi-neg' : ''}`}>
                {formatPct1d(avg1d)}
              </strong>
            )}
            <span className="dw-kpi-hint">Across tracked schemes (MFAPI)</span>
          </article>
        </div>
      </section>

      <div className="dw-split-2">
        <section className="dw-card dw-chart-card">
          <div className="dw-card-head">
            <h3 className="dw-h3">Portfolio growth (illustrative)</h3>
            <span className="dw-chip dw-chip-muted">₹{MOCK_OVERVIEW.portfolioValueLakh} L</span>
          </div>
          <GrowthSparkline />
          <div className="dw-chart-legend">
            <span><i className="dw-dot dw-dot-eq" /> Model path</span>
            <span className="dw-legend-note">Past simulation only</span>
          </div>
        </section>

        <section className="dw-card">
          <h3 className="dw-h3">Asset mix</h3>
          <div className="dw-alloc-row">
            <AllocationDonut />
            <ul className="dw-alloc-bars">
              <li>
                <span>Equity</span>
                <div className="dw-bar"><span style={{ width: `${MOCK_OVERVIEW.equityPct}%` }} /></div>
                <span>{MOCK_OVERVIEW.equityPct}%</span>
              </li>
              <li>
                <span>Debt</span>
                <div className="dw-bar dw-bar-debt"><span style={{ width: `${MOCK_OVERVIEW.debtPct}%` }} /></div>
                <span>{MOCK_OVERVIEW.debtPct}%</span>
              </li>
              <li>
                <span>Hybrid / commodities</span>
                <div className="dw-bar dw-bar-hybrid"><span style={{ width: `${MOCK_OVERVIEW.hybridCommPct}%` }} /></div>
                <span>{MOCK_OVERVIEW.hybridCommPct}%</span>
              </li>
            </ul>
          </div>
        </section>
      </div>

      <section className="dw-card">
        <h3 className="dw-h3">Mutual fund allocation</h3>
        <div className="dw-mf-bars">
          {[
            { label: 'Equity active', pct: 42 },
            { label: 'Index / passive', pct: 18 },
            { label: 'Hybrid / BAF', pct: 16 },
            { label: 'Debt / liquid', pct: 14 },
            { label: 'Commodities FoF', pct: 10 },
          ].map((row) => (
            <div key={row.label} className="dw-mf-row">
              <span>{row.label}</span>
              <div className="dw-mf-track"><span style={{ width: `${row.pct}%` }} /></div>
              <span>{row.pct}%</span>
            </div>
          ))}
        </div>
      </section>

      <section className="dw-section">
        <h2 className="dw-h2">Fund insights · corpus schemes</h2>
        <p className="dw-sub">
          {funds.length === corpusFundCount
            ? `${corpusFundCount} HDFC schemes the assistant can answer about. Tap to open in Fund explorer.`
            : `${funds.length} matching · ${corpusFundCount} total in corpus. Tap to open in Fund explorer.`}
        </p>
        <div className="dw-fund-chips">
          {funds.map((f) => (
            <button
              key={f.fund_id}
              type="button"
              className="dw-fund-chip"
              onClick={() => onFundClick(f.fund_id)}
            >
              <span className="dw-fund-chip-title">{f.shortLabel}</span>
              {navLoading ? (
                <span className="dw-fund-chip-sub dw-fund-chip-sub--skel">
                  <span className="dw-skel-line dw-skel-line--chip" />
                </span>
              ) : (
                <span className="dw-fund-chip-sub">
                  NAV {formatInrNav(f.liveNav?.nav)} · {formatPct1d(f.liveNav?.change)}
                </span>
              )}
            </button>
          ))}
        </div>
      </section>

      <div className="dw-split-3">
        <section className="dw-card dw-card-soft">
          <h3 className="dw-h3">Recent SIP activity</h3>
          <ul className="dw-list">
            {MOCK_SIPS.map((r) => (
              <li key={r.name}>
                <span className="dw-list-main">{r.name}</span>
                <span className="dw-list-meta">{r.amount}</span>
                <span className="dw-list-date">{r.date}</span>
              </li>
            ))}
          </ul>
        </section>
        <section className="dw-card dw-card-soft">
          <h3 className="dw-h3">Watchlist</h3>
          <ul className="dw-watch">
            {MOCK_WATCHLIST.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
          <p className="dw-empty-hint">Add schemes from Fund explorer.</p>
        </section>
        <section className="dw-card dw-card-soft">
          <h3 className="dw-h3">Market snapshot</h3>
          <p className="dw-mkt-proxy-hint">1D change proxies via HDFC index / debt schemes (not spot indices).</p>
          <ul className="dw-market">
            {navLoading
              ? [1, 2, 3].map((i) => (
                  <li key={i}>
                    <span className="dw-skel-line dw-skel-line--mkt-label" />
                    <span className="dw-skel-line dw-skel-line--mkt-val" />
                  </li>
                ))
              : marketRows.map((m) => {
                  const up = m.raw == null ? true : m.raw >= 0
                  const cls = m.raw == null ? 'dw-mkt-flat' : up ? 'dw-mkt-up' : 'dw-mkt-flat'
                  return (
                    <li key={m.label}>
                      <span>
                        {m.label}
                        <span className="dw-mkt-sub">{m.sub}</span>
                      </span>
                      <span className={cls}>{formatPct1d(m.raw)}</span>
                    </li>
                  )
                })}
          </ul>
        </section>
      </div>

      <section className="dw-quick">
        <h3 className="dw-h3">Quick actions</h3>
        <div className="dw-quick-btns">
          <button type="button" className="dw-quick-btn">Start SIP</button>
          <button type="button" className="dw-quick-btn">Switch</button>
          <button type="button" className="dw-quick-btn">STP setup</button>
          <button type="button" className="dw-quick-btn">Download CAS</button>
        </div>
      </section>
    </div>
  )
})

const HoldingsPanel = memo(function HoldingsPanel({ allFunds, navLoading }) {
  const liveMap = useMemo(
    () => Object.fromEntries(allFunds.map((f) => [f.fund_id, f.liveNav])),
    [allFunds]
  )

  return (
    <div className="dw-panel dw-fade">
      <h2 className="dw-h2">My holdings</h2>
      <p className="dw-sub">Demo positions for UI — not linked to a real account.</p>
      <div className="dw-table-wrap">
        <table className="dw-table">
          <thead>
            <tr>
              <th>Scheme</th>
              <th>Units</th>
              <th>Value</th>
              <th>1D NAV Δ</th>
            </tr>
          </thead>
          <tbody>
            {DEMO_HOLDINGS.map((h) => {
              const ln = liveMap[h.fundId]
              return (
                <tr key={h.scheme}>
                  <td>{h.scheme}</td>
                  <td>{h.units}</td>
                  <td>{h.value}</td>
                  <td className={navLoading ? 'dw-td-skel' : ln?.change != null && ln.change >= 0 ? 'dw-td-pos' : 'dw-td-neg'}>
                    {navLoading ? <span className="dw-skel-line dw-skel-line--table" /> : formatPct1d(ln?.change)}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
})

const FundExplorerPanel = memo(function FundExplorerPanel({
  funds,
  corpusFundCount,
  selectedFundId,
  onSelectFund,
  onAskAssistant,
  navMeta,
  navLoading,
}) {
  const selected = useMemo(
    () => funds.find((f) => f.fund_id === selectedFundId) ?? null,
    [funds, selectedFundId]
  )

  return (
    <div className="dw-panel dw-fade dw-explorer">
      <h2 className="dw-h2">Fund explorer</h2>
      <p className="dw-sub">
        {funds.length === corpusFundCount
          ? `All ${corpusFundCount} HDFC schemes in the assistant corpus. Select one for facts — then ask the AI for deeper detail.`
          : `Showing ${funds.length} matching scheme${funds.length === 1 ? '' : 's'} (${corpusFundCount} total in corpus). Select one for facts — then ask the AI for deeper detail.`}
      </p>
      <div className="dw-explorer-grid">
        <div className="dw-explorer-cards">
          {funds.map((f) => (
            <button
              key={f.fund_id}
              type="button"
              className={`dw-scheme-card ${selectedFundId === f.fund_id ? 'is-selected' : ''}`}
              onClick={() => onSelectFund(f.fund_id)}
            >
              <span className="dw-scheme-name">{f.shortLabel}</span>
              <span className="dw-scheme-cat">{f.category} · {f.sub_category ?? '—'}</span>
              {navLoading ? (
                <span className="dw-scheme-live dw-scheme-live--skel">
                  <span className="dw-skel-line dw-skel-line--scheme" />
                </span>
              ) : (
                <span className="dw-scheme-live">
                  NAV {formatInrNav(f.liveNav?.nav)} · {formatPct1d(f.liveNav?.change)}
                </span>
              )}
            </button>
          ))}
        </div>
        <FundDetailCard
          fund={selected}
          onAskAssistant={onAskAssistant}
          navMeta={navMeta}
          navLoading={navLoading}
        />
      </div>
    </div>
  )
})

const StatementsPanel = memo(function StatementsPanel() {
  return (
    <div className="dw-panel dw-fade">
      <h2 className="dw-h2">Statements</h2>
      <p className="dw-sub">Sample documents — placeholders for a production CAS / tax workflow.</p>
      <ul className="dw-statements">
        {MOCK_STATEMENTS.map((s) => (
          <li key={s.title}>
            <button type="button" className="dw-statement-row">
              <span className="dw-st-title">{s.title}</span>
              <span className="dw-st-type">{s.type}</span>
              <span className="dw-st-date">{s.date}</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
})

const AssistantHintPanel = memo(function AssistantHintPanel() {
  return (
    <div className="dw-panel dw-fade dw-assistant-hint">
      <div className="dw-hint-card">
        <h2 className="dw-h2">Fund assistant</h2>
        <p className="dw-sub">
          The facts-only assistant is open on the right. Ask about exit loads, benchmarks, ELSS lock-in, Housing
          Opportunities, or any of the fifteen corpus schemes.
        </p>
        <ul className="dw-hint-list">
          <li>Answers use the fixed Groww-sourced corpus; dashboard NAVs are refreshed from MFAPI for display only.</li>
          <li>No investment advice or “which fund is better” recommendations.</li>
        </ul>
      </div>
    </div>
  )
})

export const DashboardWorkspace = memo(function DashboardWorkspace({
  section,
  funds,
  allFunds,
  corpusFundCount,
  selectedFundId,
  onSelectFund,
  onFundInsightClick,
  onAskAssistant,
  navMeta,
  navLoading,
}) {
  switch (section) {
    case NAV_IDS.holdings:
      return <HoldingsPanel allFunds={allFunds} navLoading={navLoading} />
    case NAV_IDS.explorer:
      return (
        <FundExplorerPanel
          funds={funds}
          corpusFundCount={corpusFundCount}
          selectedFundId={selectedFundId}
          onSelectFund={onSelectFund}
          onAskAssistant={onAskAssistant}
          navMeta={navMeta}
          navLoading={navLoading}
        />
      )
    case NAV_IDS.statements:
      return <StatementsPanel />
    case NAV_IDS.assistant:
      return <AssistantHintPanel />
    case NAV_IDS.dashboard:
    default:
      return (
        <DashboardHome
          funds={funds}
          corpusFundCount={corpusFundCount}
          onFundClick={onFundInsightClick}
          allFunds={allFunds}
          navLoading={navLoading}
        />
      )
  }
})
