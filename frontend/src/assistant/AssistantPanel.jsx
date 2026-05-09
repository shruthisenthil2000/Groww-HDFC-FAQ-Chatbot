import { useEffect, useLayoutEffect, useRef, useState, useCallback, memo } from 'react'
import { IconSend, IconInfo, IconShield } from '../ui/icons'
import { PROMPT_CHIPS, ROTATING_PLACEHOLDERS, TRUST_TOOLTIP } from './constants'
import { MessageBubble, TypingIndicator } from './MessageBubble'

const OfflineBanner = memo(function OfflineBanner({ onRetry }) {
  return (
    <div className="ap-offline" role="alert">
      <span>Connection issue — retry when ready.</span>
      <button type="button" className="ap-offline-retry" onClick={onRetry}>
        Retry
      </button>
    </div>
  )
})

const COMPOSER_LINE_PX = 24
const COMPOSER_MAX_PX = 120

const PromptChip = memo(function PromptChip({ label, query, onSelect, disabled }) {
  return (
    <button
      type="button"
      className="ap-chip"
      onClick={() => onSelect(query)}
      disabled={disabled}
    >
      {label}
    </button>
  )
})

export function AssistantPanel({
  messages,
  input,
  setInput,
  loading,
  send,
  backendError,
  onRetryHealth,
  phIndex,
  inputRef: inputRefProp,
}) {
  const chatScrollRef = useRef(null)
  const inputRefLocal = useRef(null)
  const inputRef = inputRefProp ?? inputRefLocal
  const trustPopoverRef = useRef(null)
  const [trustOpen, setTrustOpen] = useState(false)

  const empty = messages.length === 0

  const scrollSnapRef = useRef({ msgLen: 0, loading: false })

  const resizeTextarea = useCallback(() => {
    const ta = inputRef.current
    if (!ta) return
    ta.style.height = `${COMPOSER_LINE_PX}px`
    const sh = ta.scrollHeight
    const next = Math.min(Math.max(sh, COMPOSER_LINE_PX), COMPOSER_MAX_PX)
    ta.style.height = `${next}px`
    ta.style.overflowY = next >= COMPOSER_MAX_PX ? 'auto' : 'hidden'
  }, [inputRef])

  useLayoutEffect(() => {
    resizeTextarea()
  }, [input, resizeTextarea])

  useLayoutEffect(() => {
    const el = chatScrollRef.current
    if (!el) return

    const prev = scrollSnapRef.current
    const len = messages.length
    const appended = len > prev.msgLen
    const loadingStarted = loading && !prev.loading
    const loadingEnded = !loading && prev.loading
    scrollSnapRef.current = { msgLen: len, loading }

    if (!appended && !loadingStarted && !loadingEnded) return

    requestAnimationFrame(() => {
      el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
    })
  }, [messages.length, loading])

  useEffect(() => {
    if (!trustOpen) return undefined
    const onKey = (e) => {
      if (e.key === 'Escape') setTrustOpen(false)
    }
    const onDown = (e) => {
      if (trustPopoverRef.current && !trustPopoverRef.current.contains(e.target)) {
        setTrustOpen(false)
      }
    }
    document.addEventListener('keydown', onKey)
    document.addEventListener('mousedown', onDown)
    return () => {
      document.removeEventListener('keydown', onKey)
      document.removeEventListener('mousedown', onDown)
    }
  }, [trustOpen])

  const handleKey = useCallback(
    (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        e.stopPropagation()
        send()
      }
    },
    [send]
  )

  return (
    <div className="assistant-panel" role="complementary" aria-label="Fund assistant">
      <div className="assistant-panel-inner">
        {backendError && <OfflineBanner onRetry={onRetryHealth} />}

        <header className="ap-header">
          <div className="ap-header-brand">
            <div className="ap-avatar" aria-hidden>AI</div>
            <div className="ap-header-text">
              <h2 className="ap-title">HDFC Fund Assistant</h2>
              <p className="ap-subtitle">Facts-only AI assistant</p>
            </div>
          </div>
          <div className="ap-status">
            <span className="ap-status-dot" aria-hidden />
            <span className="ap-status-label">Online</span>
          </div>
        </header>

        <div className="ap-chat-scroll" ref={chatScrollRef}>
          {empty && (
            <div className="ap-welcome">
              <p className="ap-welcome-greeting">Hi — how can I help?</p>
              <p className="ap-welcome-hint">
                Ask about HDFC schemes in this corpus — expense ratio, exit load, benchmarks, ELSS
                lock-in, and more.
              </p>
              <div className="ap-chip-wrap" aria-label="Suggested prompts">
                {PROMPT_CHIPS.map((c) => (
                  <PromptChip
                    key={c.label}
                    label={c.label}
                    query={c.query}
                    onSelect={send}
                    disabled={loading}
                  />
                ))}
              </div>
            </div>
          )}

          <div className="ap-msg-list">
            {messages.map((msg) => (
              <MessageBubble key={msg.id} msg={msg} />
            ))}
            {loading && <TypingIndicator />}
          </div>
        </div>

        <footer className="assistant-footer">
          <div className="trust-row">
            <IconShield className="trust-row-icon" aria-hidden />
            <span className="trust-row-label">Facts only — no investment advice</span>
            <div className="trust-row-pop" ref={trustPopoverRef}>
              <button
                type="button"
                className="trust-row-info"
                aria-expanded={trustOpen}
                aria-label="About data scope"
                title={TRUST_TOOLTIP}
                onClick={() => setTrustOpen((o) => !o)}
              >
                <IconInfo className="trust-row-info-svg" />
              </button>
              {trustOpen && (
                <div className="trust-row-tooltip" role="tooltip">
                  {TRUST_TOOLTIP}
                </div>
              )}
            </div>
          </div>

          <form
            className="assistant-compose-form"
            onSubmit={(e) => {
              e.preventDefault()
              send()
            }}
          >
            <div className="composer-shell">
              <div className="composer-row">
                <textarea
                  ref={inputRef}
                  className="assistant-textarea"
                  rows={1}
                  placeholder={ROTATING_PLACEHOLDERS[phIndex]}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKey}
                  onKeyDownCapture={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) e.stopPropagation()
                  }}
                  disabled={loading}
                  aria-label="Message"
                />
                <button
                  type="submit"
                  className={`send-button ${loading ? 'send-button--loading' : ''}`}
                  disabled={!input.trim() || loading}
                  aria-label="Send"
                >
                  {loading ? (
                    <span className="send-button-dots" aria-hidden>
                      <span /><span /><span />
                    </span>
                  ) : (
                    <IconSend className="send-button-icon" />
                  )}
                </button>
              </div>
            </div>
          </form>
        </footer>
      </div>
    </div>
  )
}
