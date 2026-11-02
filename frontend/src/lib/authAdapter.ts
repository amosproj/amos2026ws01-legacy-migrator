import { clientConfig } from '../config/env'

export type AuthProvider = 'github'

export type AuthSession = {
  authenticated: boolean
  user?: {
    provider: AuthProvider
    username: string
    display_name: string | null
    avatar_url: string | null
  }
}

export interface AuthAdapter {
  readonly isMockMode: boolean
  session(): Promise<AuthSession>
  signIn(provider: AuthProvider): void
  logout(): Promise<void>
}

export const authAdapter: AuthAdapter = {
  isMockMode: clientConfig.useMockApi,

  async session() {
    if (clientConfig.useMockApi) return { authenticated: false }

    const response = await fetch(`${clientConfig.backendUrl}${clientConfig.apiPaths.authSession}`, {
      credentials: 'include',
    })
    if (!response.ok) throw new Error('Authentication status could not be loaded.')
    return (await response.json()) as AuthSession
  },

  signIn(provider) {
    const authPath = clientConfig.apiPaths.authStart.replace('{provider}', provider)
    window.location.assign(`${clientConfig.backendUrl}${authPath}`)
  },

  async logout() {
    if (clientConfig.useMockApi) return

    const response = await fetch(`${clientConfig.backendUrl}${clientConfig.apiPaths.authLogout}`, {
      method: 'POST',
      credentials: 'include',
    })
    if (!response.ok) throw new Error('Could not sign out.')
  },
}
