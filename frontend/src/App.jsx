import { useEffect, useRef, useState } from 'react'
import { askChat } from './api'

const SUGGESTIONS = [
  'What is the expense ratio of HDFC Mid Cap Fund?',
  'What is the exit load for HDFC ELSS Tax Saver Fund?',
  'Who manages the HDFC Small Cap Fund?',
  'What is the investment objective of HDFC Nifty 50 Index Fund?',
  'What is the minimum SIP amount for HDFC Balanced Advantage Fund?',
  'What is the LTCG tax treatment for HDFC Large Cap Fund?',
]

const STARTER =
  "Hi, I'm Growbot, your HDFC mutual fund FAQ assistant. Ask me factual questions about HDFC AMC schemes."

const URL_DISPLAY_MAX = 68

function truncateUrl(url, max = URL_DISPLAY_MAX) {
  if (!url) return ''
  const t = url.trim()
  if (t.length <= max) return t
  return `${t.slice(0, max - 1)}…`
}

function pickSourceUrl(s) {
  if (!s || typeof s !== 'object') return ''
  return String(
    s.url ??
      s.link ??
      s.groww_url ??
      s.growwUrl ??
      s.document_url ??
      s.documentUrl ??
      ''
  ).trim()
}

function normalizeHref(raw) {
  const t = (raw ?? '').trim()
  if (!t) return ''
  if (/^https?:\/\//i.test(t)) return t
  return `https://${t}`
}

/** Remove a trailing "Source: …" line often echoed by the model when we render citations separately. */
function stripTrailingSourceLine(text) {
  if (!text || typeof text !== 'string') return text
  let t = text.replace(/\r\n/g, '\n').trimEnd()
  t = t.replace(/\n+\s*Source:\s[^\n]+\s*$/i, '').trimEnd()
  t = t.replace(/\s+Source:\s[^\n]+\s*$/i, '').trimEnd()
  return t
}

/** Split programmatic `Last updated from sources:` footer (must never be trimmed away). */
function splitAnswerLastUpdated(text) {
  if (!text || typeof text !== 'string') return { main: text, lastUpdated: null }
  const re = /\n+(Last updated from sources:\s*.+)$/im
  const m = text.match(re)
  if (!m) return { main: text, lastUpdated: null }
  return {
    main: text.slice(0, m.index).trimEnd(),
    lastUpdated: m[1].trim(),
  }
}

/** First citation row that has a URL — single clickable link in the UI. */
function getPrimarySourceLink(sources) {
  if (!Array.isArray(sources) || !sources.length) return null
  let raw = ''
  for (const s of sources) {
    raw = pickSourceUrl(s)
    if (raw) break
  }
  const href = normalizeHref(raw)
  if (!href) return null
  const display = truncateUrl(href.replace(/^https?:\/\//i, '').replace(/\/$/, ''))
  return { href, display }
}

function SourceBlock({ sources }) {
  const link = getPrimarySourceLink(sources)
  if (!link) return null
  return (
    <div className="sources-block">
      <p className="sources-line">
        <span className="sources-k">Source:</span>{' '}
        <a
          className="sources-a"
          href={link.href}
          target="_blank"
          rel="noreferrer"
        >
          {link.display}
        </a>
      </p>
    </div>
  )
}

function SendIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M22 2L11 13"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M22 2L15 22L11 13L2 9L22 2Z"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function GrowbotIcon({ className }) {
  return (
    <div className={className} aria-hidden>
      <span className="growbot-icon-antenna" />
      <span className="growbot-icon-face" />
    </div>
  )
}

function ChatBubbleIcon({ className }) {
  return (
    <svg className={className} width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M21 11.5a8.38 8.38 0 01-.9 3.8 8.5 8.5 0 01-7.6 4.7 8.38 8.38 0 01-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 01-.9-3.8 8.5 8.5 0 014.7-7.6 8.38 8.38 0 013.8-.9h.5a8.48 8.48 0 018 8v.5z"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

export default function App() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const chatScrollRef = useRef(null)
  const inputRef = useRef(null)
  const chatCardRef = useRef(null)

  useEffect(() => {
    const el = chatScrollRef.current
    if (!el) return
    el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
  }, [messages, loading])

  const focusComposer = () => {
    inputRef.current?.focus()
    chatCardRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }

  const send = async () => {
    const q = input.trim()
    if (!q || loading) return
    setInput('')
    setMessages((m) => [...m, { role: 'user', text: q }])
    setLoading(true)
    try {
      const data = await askChat(q)
      setMessages((m) => [
        ...m,
        { role: 'assistant', text: data.answer, sources: data.sources ?? [] },
      ])
    } catch (e) {
      setMessages((m) => [...m, { role: 'assistant', text: `Error: ${e.message}` }])
    } finally {
      setLoading(false)
    }
  }

  const onSuggestion = (q) => {
    setInput(q)
    focusComposer()
  }

  return (
    <div className="page-shell">
      <header className="top-nav">
        <div className="top-nav-inner">
          <div className="brand-cluster">
            <div className="brand-icon-bars" aria-hidden>
              <span className="brand-bar brand-bar--sm" />
              <span className="brand-bar brand-bar--md" />
              <span className="brand-bar brand-bar--lg" />
            </div>
            <div className="brand-text">
              <h1 className="brand-title">HDFC Mutual Fund FAQ</h1>
              <p className="brand-subtitle">FACTS-ONLY Q&amp;A</p>
            </div>
          </div>
        </div>
      </header>

      <div className="main-split">
        <section className="hero-col" aria-label="About Growbot">
          <div className="hero-stack">
            <p className="hero-eyebrow">Here to help you 24/7</p>
            <h2 className="hero-heading">
              Meet Growbot,
              <br aria-hidden="true" />
              <span className="hero-heading-line2">
                your <span className="hero-accent">digital assistant</span>
              </span>
            </h2>
            <p className="hero-intro">
              Growbot is a facts-only AI assistant for HDFC mutual funds. It can answer questions
              across 15 HDFC AMC schemes including expense ratios, exit loads, SIP amounts, tax
              treatment, investment objectives, and fund managers.
            </p>
            <button type="button" className="hero-cta" onClick={focusComposer}>
              <ChatBubbleIcon className="hero-cta-icon" />
              Chat to Growbot
            </button>
          </div>

          <div className="ask-block">
            <p className="try-asking-label">TRY ASKING:</p>
            <div className="suggestions">
              <div className="suggestions-grid">
                {SUGGESTIONS.map((q) => (
                  <button
                    key={q}
                    type="button"
                    className="suggestion-pill"
                    onClick={() => onSuggestion(q)}
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="hero-footnote">
            <span className="hero-footnote-icon" aria-hidden>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                <path
                  d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"
                  stroke="currentColor"
                  strokeWidth="1.75"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </span>
            <div className="hero-footnote-copy">
              <p className="hero-footnote-strong">
                I do not provide investment advice or recommendations.
              </p>
              <p className="hero-footnote-muted">
                Please read all scheme related documents carefully before investing.
              </p>
            </div>
          </div>
        </section>

        <aside className="chat-col">
          <div className="chat-card" ref={chatCardRef}>
            <header className="chat-card-header">
              <div className="chat-card-title-row">
                <GrowbotIcon className="chat-header-icon" />
                <span className="chat-card-title">Chat to Growbot</span>
              </div>
              <div className="chat-card-header-actions" aria-hidden>
                <span className="chat-header-dots">⋯</span>
                <span className="chat-header-min">−</span>
              </div>
            </header>

            <div className="chat-scroll" ref={chatScrollRef}>
              <div className="chat-thread">
                <div className="starter-row">
                  <GrowbotIcon className="starter-avatar" />
                  <div className="bubble assistant starter-bubble">
                    <p>{STARTER}</p>
                    <button type="button" className="inline-cta" onClick={focusComposer}>
                      Ask a factual question
                    </button>
                  </div>
                </div>

                {messages.map((msg, i) => {
                  const cite =
                    msg.role === 'assistant' ? getPrimarySourceLink(msg.sources) : null
                  const display =
                    msg.role === 'assistant' && cite
                      ? stripTrailingSourceLine(msg.text)
                      : msg.text
                  const { main, lastUpdated } =
                    msg.role === 'assistant' ? splitAnswerLastUpdated(display) : { main: display, lastUpdated: null }
                  return (
                    <article key={i} className={`bubble ${msg.role}`}>
                      <div className="bubble-body">
                        <p>{main}</p>
                        {lastUpdated ? (
                          <p className="answer-last-updated">{lastUpdated}</p>
                        ) : null}
                      </div>
                      {cite ? <SourceBlock sources={msg.sources} /> : null}
                    </article>
                  )
                })}
                {loading ? (
                  <div className="bubble assistant pending">
                    <p>Thinking…</p>
                  </div>
                ) : null}
              </div>
            </div>

            <footer className="chat-composer-wrap">
              <div className="composer">
                <textarea
                  ref={inputRef}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Type your question..."
                  rows={1}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault()
                      send()
                    }
                  }}
                />
                <button
                  type="button"
                  className="send-btn"
                  onClick={send}
                  disabled={loading}
                  aria-label="Send message"
                >
                  <SendIcon />
                </button>
              </div>
              <p className="composer-hint">Growbot can make mistakes. Please verify important information.</p>
            </footer>
          </div>
        </aside>
      </div>
    </div>
  )
}
