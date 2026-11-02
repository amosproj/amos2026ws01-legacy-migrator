import { Bot, Loader2, UserRound } from 'lucide-react'
import { ChatMessage as ChatMessageData } from '../../lib/chatAdapter'

type ChatMessageProps = {
  message: ChatMessageData
}

export function ChatMessage({ message }: ChatMessageProps) {
  return (
    <article className={`message-row ${message.role}`}>
      <div className={`avatar ${message.role === 'assistant' ? 'assistant-avatar' : ''}`}>{message.role === 'assistant' ? <Bot size={17} /> : <UserRound size={16} />}</div>
      <div className="message-content"><span className="message-author">{message.role === 'assistant' ? 'Migration assistant' : 'You'}</span><p>{message.content}</p></div>
    </article>
  )
}

export function LoadingMessage() {
  return (
  <div className="message-row assistant">
    <div className="avatar assistant-avatar">
      <Bot size={17} />
    </div>
    <div className="message-content">
      <span className="message-author">Migration assistant</span>
      <div className="loading">
        <Loader2 size={16} className="spin" /> Thinking...</div>
    </div>
  </div>
  )
}
