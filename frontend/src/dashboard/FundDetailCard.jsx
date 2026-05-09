import { memo } from 'react'
import { formatInrNav, formatNavSynced, formatPct1d } from '../utils/navDisplay'

export const FundDetailCard = memo(function FundDetailCard({
  fund,
  onAskAssistant,
  navMeta,
  navLoading,
}) {
  if (!fund) {
    return (
      <div className="fund-detail fund-detail--empty">
        <p className="fund-detail-empty-title">Select a scheme</p>
        <p className="fund-detail-empty-text">
          Choose a fund from the corpus list to view category, benchmark, risk, and a short objective
          summary.
        </p>
      </div>
    )
  }

  const askLine = `Tell me about ${fund.fund_name} — investment objective, benchmark, and risk level.`
  const ln = fund.liveNav

  return (
    <div className="fund-detail">
      <div className="fund-detail-head">
        <h3 className="fund-detail-title">{fund.shortLabel}</h3>
        <span className="fund-detail-badge">{fund.category}</span>
      </div>
      <p className="fund-detail-fullname">{fund.fund_name}</p>

      {navLoading ? (
        <div className="fund-detail-live fund-detail-live--skel" aria-hidden>
          <div className="dw-skel-line dw-skel-line--wide" />
          <div className="dw-skel-line" />
        </div>
      ) : (
        <dl className="fund-detail-dl fund-detail-live">
          <div>
            <dt>NAV</dt>
            <dd>{formatInrNav(ln?.nav)}</dd>
          </div>
          <div>
            <dt>1D change</dt>
            <dd className={ln?.change != null && ln.change >= 0 ? 'fund-detail-pos' : 'fund-detail-neg'}>
              {formatPct1d(ln?.change)}
            </dd>
          </div>
          <div>
            <dt>NAV date</dt>
            <dd>{ln?.date ?? '—'}</dd>
          </div>
          <div>
            <dt>Scheme code</dt>
            <dd>{ln?.schemeCode ?? '—'}</dd>
          </div>
        </dl>
      )}

      <dl className="fund-detail-dl">
        <div>
          <dt>Sub-category</dt>
          <dd>{fund.sub_category ?? '—'}</dd>
        </div>
        <div>
          <dt>Benchmark</dt>
          <dd>{fund.benchmark}</dd>
        </div>
        <div>
          <dt>Risk level</dt>
          <dd>{fund.risk_level ?? '—'}</dd>
        </div>
      </dl>

      <div className="fund-detail-objective">
        <span className="fund-detail-obj-label">Objective (summary)</span>
        <p>{fund.objectiveSummary}</p>
      </div>

      <div className="fund-detail-sync">
        <span className="fund-detail-sync-label">
          Last synced: {formatNavSynced(navMeta?.lastSyncedAt)}
        </span>
        {navMeta?.usingCachedData ? (
          <span className="dash-cache-badge dash-cache-badge--inline">Using cached market data</span>
        ) : null}
      </div>

      <button
        type="button"
        className="fund-detail-cta"
        onClick={() => onAskAssistant(askLine)}
      >
        Ask assistant about this fund
      </button>
    </div>
  )
})
