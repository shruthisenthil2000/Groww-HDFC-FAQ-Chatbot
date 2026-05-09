import { useState, useEffect, useCallback, useRef, useMemo } from 'react'
import { askQuery, fetchHealth } from './api'
import { DashboardLayout } from './dashboard/DashboardLayout'
import { AssistantPanel } from './assistant/AssistantPanel'
import { ROTATING_PLACEHOLDERS } from './assistant/constants'
import { NAV_IDS } from './dashboard/dashboardNav'
import { getCorpusFunds } from './data/corpusFundModel'
import { useLiveNav } from './hooks/useLiveNav'

function fundSearchHaystack(fund) {
  const ln = fund.liveNav
  const parts = [
    fund.shortLabel,
    fund.fund_name,
    fund.category,
    fund.sub_category,
    fund.benchmark,
    fund.isin,
    fund.fund_id?.replace(/_/g, ' '),
    ...(fund.aliases ?? []),
    ln?.schemeName,
    ln?.schemeCode,
    ln?.date,
    ln?.nav != null ? String(ln.nav) : '',
    ln?.change != null ? String(ln.change) : '',
  ]
  return parts.filter(Boolean).join(' ').toLowerCase()
}

export default function App() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [backendError, setBackendError] = useState(false)
  const [phIndex, setPhIndex] = useState(0)
  const [navSection, setNavSection] = useState(NAV_IDS.dashboard)
  const [selectedFundId, setSelectedFundId] = useState(null)
  const [searchQuery, setSearchQuery] = useState('')

  const inputRef = useRef(null)
  const corpusFunds = useMemo(() => getCorpusFunds(), [])
  const { loading: navLoading, meta: navMeta, byFundId } = useLiveNav()

  const enrichedFunds = useMemo(
    () =>
      corpusFunds.map((f) => ({
        ...f,
        liveNav: byFundId[f.fund_id] ?? null,
      })),
    [corpusFunds, byFundId]
  )

  const filteredFunds = useMemo(() => {
    if (!searchQuery.trim()) return enrichedFunds
    const q = searchQuery.toLowerCase().trim()
    return enrichedFunds.filter((fund) => fundSearchHaystack(fund).includes(q))
  }, [enrichedFunds, searchQuery])

  useEffect(() => {
    if (!selectedFundId) return
    if (!filteredFunds.some((f) => f.fund_id === selectedFundId)) {
      setSelectedFundId(null)
    }
  }, [filteredFunds, selectedFundId])

  const checkHealth = useCallback(() => {
    fetchHealth()
      .then(() => setBackendError(false))
      .catch(() => setBackendError(true))
  }, [])

  useEffect(() => {
    checkHealth()
  }, [checkHealth])

  useEffect(() => {
    if (input.trim()) return undefined
    const id = setInterval(() => {
      setPhIndex((i) => (i + 1) % ROTATING_PLACEHOLDERS.length)
    }, 4000)
    return () => clearInterval(id)
  }, [input])

  const onAskAssistant = useCallback((query) => {
    const q = String(query).trim()
    if (!q) return
    setInput(q)
    setNavSection(NAV_IDS.assistant)
    setTimeout(() => inputRef.current?.focus({ preventScroll: true }), 80)
  }, [])

  const onFundInsightClick = useCallback((fundId) => {
    setSelectedFundId(fundId)
    setNavSection(NAV_IDS.explorer)
  }, [])

  const send = useCallback(
    async (text) => {
      const q = (text ?? input).trim()
      if (!q || loading) return

      setInput('')
      setMessages((prev) => [...prev, { role: 'user', text: q, id: Date.now() }])
      setLoading(true)

      try {
        const data = await askQuery(q)
        setMessages((prev) => [...prev, { role: 'assistant', data, id: Date.now() + 1 }])
      } catch (err) {
        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            data: {
              response: `Something went wrong: ${err.message}`,
              answered: false,
              refused: true,
              refused_reason: 'error',
              sources: [],
              intent: 'error',
              latency_s: null,
            },
            id: Date.now() + 1,
          },
        ])
      } finally {
        setLoading(false)
        setTimeout(() => inputRef.current?.focus({ preventScroll: true }), 50)
      }
    },
    [input, loading]
  )

  return (
    <DashboardLayout
      navSection={navSection}
      onNavigate={setNavSection}
      funds={filteredFunds}
      allFunds={enrichedFunds}
      corpusFundCount={corpusFunds.length}
      selectedFundId={selectedFundId}
      onSelectFund={setSelectedFundId}
      onFundInsightClick={onFundInsightClick}
      onAskAssistant={onAskAssistant}
      searchQuery={searchQuery}
      setSearchQuery={setSearchQuery}
      navMeta={navMeta}
      navLoading={navLoading}
    >
      <AssistantPanel
        inputRef={inputRef}
        messages={messages}
        input={input}
        setInput={setInput}
        loading={loading}
        send={send}
        backendError={backendError}
        onRetryHealth={checkHealth}
        phIndex={phIndex}
      />
    </DashboardLayout>
  )
}
