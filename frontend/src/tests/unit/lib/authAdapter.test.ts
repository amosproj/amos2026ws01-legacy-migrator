import { afterEach, describe, expect, it, vi } from 'vitest'
import { authAdapter } from '../../../lib/authAdapter'

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllEnvs()
})

describe('authAdapter', () => {
  it('uses the mock session without network access', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch')

    await expect(authAdapter.session()).resolves.toEqual({ authenticated: false })
    expect(fetchSpy).not.toHaveBeenCalled()
  })

  it('does not call a backend when logging out in mock mode', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch')

    await expect(authAdapter.logout()).resolves.toBeUndefined()
    expect(fetchSpy).not.toHaveBeenCalled()
  })

  it('loads the backend session through the provider-neutral contract', async () => {
    vi.stubEnv('VITE_USE_MOCK_API', 'false')
    vi.stubEnv('VITE_USE_MOCK_AUTH_API', 'false')
    vi.resetModules()
    const session = { authenticated: true, user: { provider: 'github', username: 'demo', display_name: 'Demo', avatar_url: null } }
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify(session), { status: 200 }))
    const { authAdapter: backendAuthAdapter } = await import('../../../lib/authAdapter')

    await expect(backendAuthAdapter.session()).resolves.toEqual(session)
    expect(fetchSpy).toHaveBeenCalledWith('/api/auth/session', { credentials: 'include' })
  })
})
