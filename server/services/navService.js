import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'
import axios from 'axios'
import { TRACKED_SCHEMES, SCHEME_TO_FUND_ID } from '../config/trackedSchemes.js'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const CACHE_PATH = path.join(__dirname, '../cache/navCache.json')
const MFAPI_TIMEOUT_MS = 14_000
const MFAPI_BASE = 'https://api.mfapi.in/mf'

const axiosNav = axios.create({
  timeout: MFAPI_TIMEOUT_MS,
  validateStatus: (s) => s >= 200 && s < 500,
})

/** DD-MM-YYYY → YYYY-MM-DD */
export function apiDateToIso(d) {
  if (!d || typeof d !== 'string') return null
  const parts = d.split('-')
  if (parts.length !== 3) return null
  const [day, month, year] = parts
  if (!year || !month || !day) return null
  return `${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}`
}

function round2(n) {
  return Math.round(n * 100) / 100
}

/**
 * @param {import('axios').AxiosResponse['data']} raw
 * @param {string} fundId
 */
export function normalizeMfApiResponse(raw, fundId) {
  const meta = raw?.meta ?? {}
  const rows = Array.isArray(raw?.data) ? raw.data : []
  if (rows.length < 1) {
    return {
      schemeCode: String(meta.scheme_code ?? ''),
      schemeName: meta.scheme_name ?? 'Unknown scheme',
      nav: null,
      date: null,
      change: null,
      fundId,
    }
  }
  const latest = rows[0]
  const prev = rows[1]
  const nav = latest?.nav != null ? Number(latest.nav) : null
  const prevNav = prev?.nav != null ? Number(prev.nav) : null
  let change = null
  if (nav != null && prevNav != null && prevNav !== 0) {
    change = round2(((nav - prevNav) / prevNav) * 100)
  }
  return {
    schemeCode: String(meta.scheme_code ?? ''),
    schemeName: meta.scheme_name ?? 'Unknown scheme',
    nav: nav != null && !Number.isNaN(nav) ? round2(nav) : null,
    date: apiDateToIso(latest?.date),
    change,
    fundId,
  }
}

export function readNavCacheFile() {
  try {
    const txt = fs.readFileSync(CACHE_PATH, 'utf8')
    const data = JSON.parse(txt)
    return data && typeof data === 'object' ? data : {}
  } catch {
    return {}
  }
}

function writeNavCacheFile(obj) {
  fs.mkdirSync(path.dirname(CACHE_PATH), { recursive: true })
  fs.writeFileSync(CACHE_PATH, `${JSON.stringify(obj, null, 2)}\n`, 'utf8')
}

/**
 * @returns {{ lastSyncedAt: string | null, lastRefreshOk: boolean, entries: Record<string, object> }}
 */
export function loadCachePayload() {
  const raw = readNavCacheFile()
  const meta = raw._meta && typeof raw._meta === 'object' ? raw._meta : {}
  const entries = { ...raw }
  delete entries._meta
  return {
    lastSyncedAt: meta.lastSyncedAt ?? null,
    lastRefreshOk: meta.lastRefreshOk !== false,
    entries,
  }
}

function saveFullCache(entries, lastSyncedAt, lastRefreshOk) {
  const out = {
    _meta: {
      lastSyncedAt,
      lastRefreshOk,
    },
    ...entries,
  }
  writeNavCacheFile(out)
}

export async function fetchLiveScheme(schemeCode) {
  const url = `${MFAPI_BASE}/${schemeCode}`
  const res = await axiosNav.get(url)
  if (res.status !== 200) {
    throw new Error(`MFAPI HTTP ${res.status}`)
  }
  const fundId = SCHEME_TO_FUND_ID[String(schemeCode)] ?? null
  return normalizeMfApiResponse(res.data, fundId)
}

/**
 * Refresh all tracked schemes; merges with previous cache on per-fund failure.
 */
export async function refreshAllTracked() {
  const prev = loadCachePayload()
  const nextEntries = { ...prev.entries }
  let ok = true
  const now = new Date().toISOString()

  for (const { fundId, schemeCode } of TRACKED_SCHEMES) {
    try {
      const normalized = await fetchLiveScheme(schemeCode)
      nextEntries[String(schemeCode)] = {
        schemeName: normalized.schemeName,
        nav: normalized.nav,
        date: normalized.date,
        change: normalized.change,
        fundId: normalized.fundId ?? fundId,
      }
      await new Promise((r) => setTimeout(r, 120))
    } catch (e) {
      ok = false
      if (!nextEntries[String(schemeCode)]) {
        nextEntries[String(schemeCode)] = {
          schemeName: '—',
          nav: null,
          date: null,
          change: null,
          fundId,
          error: String(e.message ?? e),
        }
      }
    }
  }

  saveFullCache(nextEntries, now, ok)
  return loadCachePayload()
}

export function buildApiResponse(usingCachedData) {
  const { lastSyncedAt, lastRefreshOk, entries } = loadCachePayload()
  const bySchemeCode = {}
  const byFundId = {}

  for (const [code, row] of Object.entries(entries)) {
    if (code === '_meta') continue
    bySchemeCode[code] = row
    const fid = row.fundId
    if (fid) {
      byFundId[fid] = { ...row, schemeCode: code }
    }
  }

  return {
    meta: {
      lastSyncedAt,
      usingCachedData: Boolean(usingCachedData),
      lastRefreshOk,
    },
    bySchemeCode,
    byFundId,
  }
}

export async function getSchemeWithFallback(schemeCode) {
  const cached = loadCachePayload()
  const key = String(schemeCode)
  let usingCached = false

  try {
    const live = await fetchLiveScheme(key)
    return {
      usingCachedData: false,
      data: {
        schemeCode: key,
        schemeName: live.schemeName,
        nav: live.nav,
        date: live.date,
        change: live.change,
        fundId: live.fundId,
      },
    }
  } catch {
    usingCached = true
    const row = cached.entries[key]
    if (!row) {
      return {
        usingCachedData: true,
        data: null,
        error: 'No live or cached data for this scheme',
      }
    }
    return {
      usingCachedData: true,
      data: { schemeCode: key, ...row },
    }
  }
}
