import { clientConfig } from '../config/env'

export type ChatRole = 'user' | 'assistant'

export type ChatMessage = {
  id: string
  role: ChatRole
  content: string
  createdAt: string
}

export type ChatRequest = {
  query: string
  conversationId?: string
}

export type ChatResponse = {
  answer: string
  conversationId?: string
  sources?: string[]
}

export interface ChatAdapter {
  ask(request: ChatRequest, signal?: AbortSignal): Promise<ChatResponse>
}

type BackendResponse = {
  answer?: unknown
  response?: unknown
  message?: unknown
  conversation_id?: unknown
  sources?: unknown
}

const mockAnswer =
  'The customer portal is the next strong decommissioning candidate. Its legacy read path has no remaining shared-table dependencies, while the billing worker still has a direct call into the legacy account service. I would verify the worker migration before switching it off.'

const wait = (milliseconds: number, signal?: AbortSignal) =>
  new Promise<void>((resolve, reject) => {
    const timer = window.setTimeout(resolve, milliseconds)
    signal?.addEventListener(
      'abort',
      () => {
        window.clearTimeout(timer)
        reject(new DOMException('Request cancelled', 'AbortError'))
      },
      { once: true },
    )
  })

export const chatAdapter: ChatAdapter = {
  async ask(request, signal) {
    if (clientConfig.useMockApi) {
      await wait(clientConfig.mockDelays.chat, signal)
      return { answer: mockAnswer, conversationId: 'mock-conversation', sources: ['Migration graph', 'Service inventory'] }
    }

    const response = await fetch(`${clientConfig.backendUrl}${clientConfig.apiPaths.chat}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: request.query, conversation_id: request.conversationId }),
      signal,
    })

    if (!response.ok) {
      throw new Error(`The backend returned ${response.status}. Please try again.`)
    }

    const payload = (await response.json()) as BackendResponse
    const answer = payload.answer ?? payload.response ?? payload.message
    if (typeof answer !== 'string' || answer.trim().length === 0) {
      throw new Error('The backend returned an empty answer.')
    }

    return {
      answer,
      conversationId: typeof payload.conversation_id === 'string' ? payload.conversation_id : undefined,
      sources: Array.isArray(payload.sources) && payload.sources.every((source) => typeof source === 'string') ? payload.sources : undefined,
    }
  },
}