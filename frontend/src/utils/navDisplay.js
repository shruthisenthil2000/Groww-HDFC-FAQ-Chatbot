/** @param {string | null | undefined} iso */
export function formatNavSynced(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  const day = String(d.getDate()).padStart(2, '0')
  const mon = d.toLocaleString('en-GB', { month: 'short' })
  const yr = d.getFullYear()
  const hh = String(d.getHours()).padStart(2, '0')
  const mm = String(d.getMinutes()).padStart(2, '0')
  return `${day} ${mon} ${yr} · ${hh}:${mm}`
}

/** @param {number | null | undefined} change */
export function formatPct1d(change) {
  if (change == null || Number.isNaN(change)) return '—'
  const sign = change > 0 ? '+' : ''
  return `${sign}${change.toFixed(2)}%`
}

export function formatInrNav(nav) {
  if (nav == null || Number.isNaN(nav)) return '—'
  return `₹${nav.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 4 })}`
}
