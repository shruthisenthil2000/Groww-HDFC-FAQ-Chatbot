import express from 'express'
import { createProxyMiddleware } from 'http-proxy-middleware'
import { startNavRefreshJob } from './jobs/navRefreshJob.js'
import {
  buildApiResponse,
  getSchemeWithFallback,
  refreshAllTracked,
  loadCachePayload
} from './services/navService.js'

const PORT = Number(process.env.API_GATEWAY_PORT || 8090)

const FASTAPI_TARGET =
  process.env.FASTAPI_URL || 'http://127.0.0.1:8000'

const STALE_MS = 36 * 3600 * 1000

function navSnapshotIsStale(payload) {
  if (!payload.lastSyncedAt) return true

  const t = new Date(payload.lastSyncedAt).getTime()

  if (Number.isNaN(t)) return true

  return Date.now() - t > STALE_MS
}

const app = express()

app.disable('x-powered-by')

/* ROOT ROUTE */
app.get('/', (_req, res) => {
  res.send('Groww HDFC FAQ Backend Running')
})

/* HEALTH ROUTE */
app.get('/health', (_req, res) => {
  res.json({
    status: 'ok',
    service: 'groww-hdfc-api-gateway'
  })
})

/* FASTAPI DOCS */
app.use(
  '/docs',
  createProxyMiddleware({
    target: FASTAPI_TARGET,
    changeOrigin: true
  })
)

app.use(
  '/redoc',
  createProxyMiddleware({
    target: FASTAPI_TARGET,
    changeOrigin: true
  })
)

app.use(
  '/openapi.json',
  createProxyMiddleware({
    target: FASTAPI_TARGET,
    changeOrigin: true
  })
)

/* CACHE API */
app.get('/api/nav/all', (_req, res) => {
  const payload = loadCachePayload()

  const hasRows = Object.keys(payload.entries).length > 0

  const usingCached =
    !hasRows ||
    payload.lastRefreshOk === false ||
    navSnapshotIsStale(payload)

  res.json(buildApiResponse(usingCached))
})

/* SCHEME API */
app.get('/api/nav/:schemeCode', async (req, res) => {
  const code = String(req.params.schemeCode)

  try {
    const out = await getSchemeWithFallback(code)

    if (!out.data) {
      return res.status(404).json({
        detail: out.error ?? 'Not found',
        usingCachedData: out.usingCachedData
      })
    }

    return res.json({
      usingCachedData: out.usingCachedData,
      schemeCode: code,
      ...out.data
    })
  } catch (e) {
    return res.status(502).json({
      detail: String(e.message ?? e),
      usingCachedData: true
    })
  }
})

/* FASTAPI PROXY */
app.use(
  '/api',
  createProxyMiddleware({
    target: FASTAPI_TARGET,
    changeOrigin: true,
    pathRewrite: (path) =>
      `/api${path.startsWith('/') ? path : `/${path}`}`
  })
)

async function main() {
  try {
    const p = loadCachePayload()

    if (
      !p.lastSyncedAt ||
      Object.keys(p.entries).length === 0
    ) {
      console.info(
        '[nav] Empty cache — refreshing tracked funds…'
      )

      await refreshAllTracked()
    }
  } catch (e) {
    console.warn(
      '[nav] Startup refresh failed (will use cache on requests):',
      e.message
    )
  }

  app.listen(PORT, () => {
    console.info(
      `API gateway listening on :${PORT} → FastAPI ${FASTAPI_TARGET}`
    )

    startNavRefreshJob()
  })
}

main()