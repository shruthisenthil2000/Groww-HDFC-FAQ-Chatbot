/**
 * API client — FastAPI backend
 */

const BASE =
  import.meta.env.VITE_API_URL ||
  'https://groww-hdfc-faq-chatbot-production.up.railway.app'

/**
 * POST /query
 */
export async function askQuery(query) {
  const res = await fetch(`${BASE}/query`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ query }),
  })

  if (!res.ok) {
    const err = await res
      .json()
      .catch(() => ({ detail: res.statusText }))

    throw new Error(err.detail || `HTTP ${res.status}`)
  }

  return await res.json()
}

/**
 * GET /examples
 */
export async function fetchExamples() {
  const res = await fetch(`${BASE}/examples`)

  if (!res.ok) return []

  const data = await res.json()
  return data.examples ?? []
}

/**
 * GET /funds
 */
export async function fetchFunds() {
  const res = await fetch(`${BASE}/funds`)

  if (!res.ok) return []

  const data = await res.json()
  return data.funds ?? []
}

/**
 * GET /health
 */
export async function fetchHealth() {
  const res = await fetch(`${BASE}/health`)

  if (!res.ok) {
    throw new Error('Backend offline')
  }

  return await res.json()
}

let _navAllPromise = null

/**
 * GET /nav/all
 */
export async function fetchNavAll() {
  if (!_navAllPromise) {
    _navAllPromise = fetch(`${BASE}/nav/all`)
      .then(async (res) => {
        _navAllPromise = null

        if (!res.ok) {
          const err = await res
            .json()
            .catch(() => ({ detail: res.statusText }))

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