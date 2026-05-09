/**
 * API client — all calls proxied to FastAPI backend (/api/*)
 */

const BASE = '/api'

/**
 * POST /api/query
 * @param {string} query
 * @returns {Promise<QueryResponse>}
 */
export async function askQuery(query) {
  const res = await fetch(`${BASE}/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

/**
 * GET /api/examples
 * @returns {Promise<string[]>}
 */
export async function fetchExamples() {
  const res = await fetch(`${BASE}/examples`)
  if (!res.ok) return []
  const data = await res.json()
  return data.examples ?? []
}

/**
 * GET /api/funds
 * @returns {Promise<FundInfo[]>}
 */
export async function fetchFunds() {
  const res = await fetch(`${BASE}/funds`)
  if (!res.ok) return []
  const data = await res.json()
  return data.funds ?? []
}

/**
 * GET /api/health
 * @returns {Promise<HealthResponse>}
 */
export async function fetchHealth() {
  const res = await fetch(`${BASE}/health`)
  if (!res.ok) throw new Error('Backend offline')
  return res.json()
}

let _navAllPromise = null

/**
 * GET /api/nav/all — single in-flight dedupe per page load.
 * @returns {Promise<{ meta: object, byFundId: Record<string, object>, bySchemeCode?: object }>}
 */
export async function fetchNavAll() {
  if (!_navAllPromise) {
    _navAllPromise = fetch(`${BASE}/nav/all`)
      .then(async (res) => {
        _navAllPromise = null
        if (!res.ok) {
          const err = await res.json().catch(() => ({ detail: res.statusText }))
          throw new Error(err.detail || `HTTP ${res.status}`)
        }
        return res.json()
      })
      .catch((e) => {
        _navAllPromise = null
        throw e
      })
  }
  return _navAllPromise
}
