import { memo } from 'react'

export const MessageBubble = memo(function MessageBubble({ msg }) {
  const isUser = msg.role === 'user'

  if (isUser) {
    return (
      <div className="ap-msg-row ap-msg-user">
        <div className="ap-bubble ap-bubble-user">{msg.text}</div>
      </div>
    )
  }

  const { response, answered, sources } = msg.data ?? {}
  const isRefused = msg.data?.refused || !answered
  const domainUrl = sources?.[0]?.groww_url

  return (
    <div className="ap-msg-row ap-msg-assistant">
      <div className={`ap-bubble ap-bubble-assistant ${isRefused ? 'ap-bubble-refused' : ''}`}>
        <p className="ap-bubble-text">{response}</p>

        {answered && sources?.length > 0 && (
          <div className="ap-source-card">
            <span className="ap-source-icon" aria-hidden>🔗</span>
            <div className="ap-source-details">
              <span className="ap-source-fund">{sources[0].fund_name}</span>
              <a
                className="ap-source-url"
                href={domainUrl}
                target="_blank"
                rel="noopener noreferrer"
              >
                {domainUrl}
              </a>
              {sources[0].ingestion_date && (
                <span className="ap-source-date">Data as of: {sources[0].ingestion_date}</span>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
})

export function TypingIndicator() {
  return (
    <div className="ap-msg-row ap-msg-assistant">
      <div className="ap-bubble ap-bubble-assistant ap-bubble-typing">
        <span /><span /><span />
      </div>
    </div>
  )
}
