import { useCallback, useEffect, useReducer, useRef } from 'react'
import { chatAdapter, type ChatMessage } from '../../lib/chatAdapter'

type State = {
  messages: ChatMessage[]
  query: string
  status: 'idle' | 'loading' | 'error'
  error: string | null
}

type Action =
  | { type: 'query/updated'; query: string }
  | { type: 'request/started'; message: ChatMessage }
  | { type: 'request/succeeded'; message: ChatMessage }
  | { type: 'request/failed'; error: string }
  | { type: 'conversation/reset'; messages: ChatMessage[] }

const initialMessages: ChatMessage[] = [{
  id: 'welcome',
  role: 'assistant',
  content: 'Hi, I’m your migration assistant. Ask me about legacy components, target services, or the next decommissioning candidate.',
  createdAt: new Date().toISOString(),
}]

const initialState: State = { messages: initialMessages, query: '', status: 'idle', error: null }

export function chatReducer(state: State, action: Action): State {
  switch (action.type) {
    case 'query/updated': return { ...state, query: action.query }
    case 'request/started': return { ...state, query: '', status: 'loading', error: null, messages: [...state.messages, action.message] }
    case 'request/succeeded': return { ...state, status: 'idle', messages: [...state.messages, action.message] }
    case 'request/failed': return { ...state, status: 'error', error: action.error }
    case 'conversation/reset': return { ...initialState, messages: action.messages }
  }
}

export function useChat() {
  const [state, dispatch] = useReducer(chatReducer, initialState)
  const conversationId = useRef<string>()
  const requestController = useRef<AbortController | null>(null)

  useEffect(() => () => requestController.current?.abort(), [])

  const submit = useCallback(async () => {
    const query = state.query.trim()
    if (!query || state.status === 'loading') return

    requestController.current?.abort()
    const controller = new AbortController()
    requestController.current = controller
    dispatch({ type: 'request/started', message: { id: crypto.randomUUID(), role: 'user', content: query, createdAt: new Date().toISOString() } })

    try {
      const response = await chatAdapter.ask({ query, conversationId: conversationId.current }, controller.signal)
      if (controller.signal.aborted) return
      conversationId.current = response.conversationId
      dispatch({ type: 'request/succeeded', message: { id: crypto.randomUUID(), role: 'assistant', content: response.answer, sources: response.sources, createdAt: new Date().toISOString() } })
    } catch (requestError) {
      if (controller.signal.aborted) return
      dispatch({ type: 'request/failed', error: requestError instanceof Error ? requestError.message : 'Something went wrong. Please try again.' })
    }
  }, [state.query, state.status])

  const reset = useCallback(() => {
    requestController.current?.abort()
    conversationId.current = undefined
    dispatch({ type: 'conversation/reset', messages: initialMessages })
  }, [])

  return { ...state, isLoading: state.status === 'loading', showStarterQuestions: state.messages.length === 1, setQuery: (query: string) => dispatch({ type: 'query/updated', query }), submit, reset }
}
