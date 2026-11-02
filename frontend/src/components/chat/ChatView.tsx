import { Bot } from 'lucide-react'
import { ChatComposer } from './ChatComposer'
import { ChatMessage, LoadingMessage } from './ChatMessage'
import { useChat } from './useChat'

export function ChatView() {
  const chat = useChat()

  return (
    <section className="chat-area">
      <div className="chat-heading">
        <div className="bot-avatar"><Bot size={22} /></div>
        <div><h1>Migration assistant</h1><p>Ask questions about your legacy system and migration progress.</p></div>
      </div>
      <div className="messages">
        {chat.messages.map((message) => <ChatMessage key={message.id} message={message} />)}
        {chat.isLoading && <LoadingMessage />}
        {chat.error && <div className="error-banner" role="alert">{chat.error}</div>}
      </div>
      <ChatComposer query={chat.query} isLoading={chat.isLoading} showStarterQuestions={chat.showStarterQuestions} onQueryChange={chat.setQuery} onSubmit={chat.submit} />
    </section>
  )
}
