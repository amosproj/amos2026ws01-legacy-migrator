import { clientConfig } from '../config/env'

export type ApiHealth = 'mock' | 'checking' | 'connected' | 'unavailable'

export const healthAdapter = {
  async check(): Promise<ApiHealth> {
    if (clientConfig.useMockApi) return 'mock'

    try {
      const response = await fetch(`${clientConfig.backendUrl}${clientConfig.apiPaths.health}`)
      return response.ok ? 'connected' : 'unavailable'
    } catch {
      return 'unavailable'
    }
  },
}
