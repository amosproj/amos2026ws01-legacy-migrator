import { afterEach, describe, expect, it, vi } from 'vitest'
import { healthAdapter } from '../../../lib/healthAdapter'

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllEnvs()
})

describe('healthAdapter', () => {
  it('reports mock mode without making a network request', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch')

    await expect(healthAdapter.check()).resolves.toBe('mock')
    expect(fetchSpy).not.toHaveBeenCalled()
  })

  it('reports a reachable backend health endpoint', async () => {
    vi.stubEnv('VITE_USE_MOCK_API', 'false')
    vi.resetModules()
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('{"status":"ok"}', { status: 200 }))
    const { healthAdapter: backendHealthAdapter } = await import('../../../lib/healthAdapter')

    await expect(backendHealthAdapter.check()).resolves.toBe('connected')
    expect(fetchSpy).toHaveBeenCalledWith('/api/health')
  })

  it('reports an unavailable backend when the health request fails', async () => {
    vi.stubEnv('VITE_USE_MOCK_API', 'false')
    vi.resetModules()
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('Network unavailable'))
    const { healthAdapter: backendHealthAdapter } = await import('../../../lib/healthAdapter')

    await expect(backendHealthAdapter.check()).resolves.toBe('unavailable')
  })
})
