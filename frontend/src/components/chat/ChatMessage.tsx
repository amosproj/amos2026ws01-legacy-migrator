import { useEffect, useState } from 'react'
import { Bot, ExternalLink, Loader2, UserRound } from 'lucide-react'
import { ChatMessage as ChatMessageData } from '../../lib/chatAdapter'

type ChatMessageProps = {
  message: ChatMessageData
}

export function ChatMessage({ message }: ChatMessageProps) {
  return (
    <article className={`message-row ${message.role}`}>
      <div className={`avatar ${message.role === 'assistant' ? 'assistant-avatar' : ''}`}>{message.role === 'assistant' ? <Bot size={17} /> : <UserRound size={16} />}</div>
      <div className="message-content">
        <span className="message-author">{message.role === 'assistant' ? 'Migration assistant' : 'You'}</span>
        <p>{message.content}</p>
        {message.sources && message.sources.length > 0 && <div className="message-sources" aria-label="Sources">{message.sources.map((source) => <Source key={source} value={source} />)}</div>}
      </div>
    </article>
  )
}

function Source({ value }: { value: string }) {
  let url: URL | null = null
  try {
    const parsedUrl = new URL(value)
    if (parsedUrl.protocol === 'http:' || parsedUrl.protocol === 'https:') url = parsedUrl
  } catch {
    url = null
  }
  if (!url) return <span className="source-badge">{value}</span>

  return <a className="source-badge source-link" href={url.href} target="_blank" rel="noreferrer">{value}<ExternalLink size={11} /></a>
}

export function LoadingMessage() {
  const [showHint, setShowHint] = useState(false)

  useEffect(() => {
    const timer = window.setTimeout(() => setShowHint(true), 3000)
    return () => window.clearTimeout(timer)
  }, [])

  return (
  <div className="message-row assistant">
    <div className="avatar assistant-avatar">
      <Bot size={17} />
    </div>
    <div className="message-content">
      <span className="message-author">Migration assistant</span>
      <div className="loading">
        <Loader2 size={16} className="spin" /> Thinking...
        {showHint && <span className="loading-hint">The first response can take a few minutes while the model loads.</span>}
      </div>
    </div>
  </div>
  )
}
