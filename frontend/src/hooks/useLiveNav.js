import { useState, useEffect, useCallback, useMemo } from 'react'
import { fetchNavAll } from '../api'

const SESSION_KEY = 'navAll:v1'
const SESSION_TTL_MS = 120_000

function readSessionNav() {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY)
    if (!raw) return null
    const { t, payload } = JSON.parse(raw)
    if (typeof t !== 'number' || Date.now() - t > SESSION_TTL_MS) {
      sessionStorage.removeItem(SESSION_KEY)
      return null
    }
    return payload
  } catch {
    return null
  }
}

function writeSessionNav(payload) {
  try {
    sessionStorage.setItem(SESSION_KEY, JSON.stringify({ t: Date.now(), payload }))
  } catch {
    /* ignore quota */
  }
}

/**
 * Single fetch per page load (sessionStorage dedupe for StrictMode / remounts).
 */
function hasSessionFunds() {
  if (typeof sessionStorage === 'undefined') return false
  const c = readSessionNav()
  return Boolean(c?.byFundId && Object.keys(c.byFundId).length > 0)
}

export function useLiveNav() {
  const [loading, setLoading] = useState(() => !hasSessionFunds())
  const [meta, setMeta] = useState(
    () =>
      readSessionNav()?.meta ?? {
        lastSyncedAt: null,
        usingCachedData: false,
        lastRefreshOk: true,
      }
  )
  const [byFundId, setByFundId] = useState(() => readSessionNav()?.byFundId ?? {})

  const load = useCallback(async () => {
    const cached = readSessionNav()
    if (cached?.byFundId && Object.keys(cached.byFundId).length > 0) {
      setMeta(cached.meta)
      setByFundId(cached.byFundId)
      setLoading(false)
      return
    }

    setLoading(true)
    try {
      const data = await fetchNavAll()
      const nextMeta = data.meta ?? {}
      const nextByFund = data.byFundId ?? {}
      setMeta(nextMeta)
      setByFundId(nextByFund)
      writeSessionNav({ meta: nextMeta, byFundId: nextByFund })
    } catch {
      setMeta((m) => ({
        ...m,
        usingCachedData: true,
        lastRefreshOk: false,
      }))
      setByFundId({})
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const value = useMemo(
    () => ({
      loading,
      meta,
      byFundId,
      reload: load,
    }),
    [loading, meta, byFundId, load]
  )

  return value
}
