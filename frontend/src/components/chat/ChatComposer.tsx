import { FormEvent, KeyboardEvent } from 'react'
import { ArrowUp } from 'lucide-react'

type ChatComposerProps = {
  query: string
  isLoading: boolean
  showStarterQuestions: boolean
  onQueryChange: (query: string) => void
  onSubmit: (event?: FormEvent) => void
}

const starterQuestions = ['What should we decommission next?', 'Show me remaining shared-table dependencies', 'Which bounded contexts are already migrated?']

export function ChatComposer({ query, isLoading, showStarterQuestions, onQueryChange, onSubmit }: ChatComposerProps) {
  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      void onSubmit()
    }
  }

  return (
    <div className="composer-wrap">
      {showStarterQuestions && <div className="starter-grid">{starterQuestions.map((question) => <button key={question} onClick={() => onQueryChange(question)}>{question}<ArrowUp size={14} /></button>)}</div>}
      <form className="composer" onSubmit={onSubmit}><textarea value={query} onChange={(event) => onQueryChange(event.target.value)} onKeyDown={handleKeyDown} placeholder="Ask a question about your migration..." rows={1} aria-label="Question" /><button className="send-button" type="submit" disabled={!query.trim() || isLoading} aria-label="Send question"><ArrowUp size={18} /></button></form>
      <p className="composer-hint">Press <kbd>Enter</kbd> to send · <kbd>Shift + Enter</kbd> for a new line</p>
    </div>
  )
}
