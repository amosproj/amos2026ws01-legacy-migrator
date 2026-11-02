import { afterEach, describe, expect, it, vi } from 'vitest'

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllEnvs()
})

describe('chatAdapter', () => {
  it('uses the FastAPI detail message for backend errors', async () => {
    vi.stubEnv('VITE_USE_MOCK_API', 'false')
    vi.resetModules()
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ detail: 'The language model is unavailable.' }), { status: 502 }))

    const { chatAdapter } = await import('../../../lib/chatAdapter')

    await expect(chatAdapter.ask({ query: 'Check the migration status' })).rejects.toThrow('The language model is unavailable.')
  })

  it('accepts the backend chat response contract', async () => {
    vi.stubEnv('VITE_USE_MOCK_API', 'false')
    vi.resetModules()
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({
      answer: 'The customer portal is ready.',
      conversation_id: 'conversation-42',
      sources: ['llm:openai-compatible (qwen3.5:0.8b)'],
    }), { status: 200 }))

    const { chatAdapter } = await import('../../../lib/chatAdapter')
    await expect(chatAdapter.ask({ query: 'What is ready?', conversationId: 'conversation-42' })).resolves.toEqual({
      answer: 'The customer portal is ready.',
      conversationId: 'conversation-42',
      sources: ['llm:openai-compatible (qwen3.5:0.8b)'],
    })
  })
})
