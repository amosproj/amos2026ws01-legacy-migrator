const backendUrl = (import.meta.env.VITE_BACKEND_URL ?? '').replace(/\/+$/, '')

export const clientConfig = {
  backendUrl,
  useMockApi: import.meta.env.VITE_USE_MOCK_API !== 'false',
  apiPaths: {
    chat: import.meta.env.VITE_API_CHAT_PATH ?? '/api/chat',
    diffExplain: import.meta.env.VITE_API_DIFF_EXPLAIN_PATH ?? '/api/diff/explain',
    repositories: import.meta.env.VITE_API_REPOSITORIES_PATH ?? '/api/repositories',
    health: import.meta.env.VITE_API_HEALTH_PATH ?? '/api/health',
    authSession: import.meta.env.VITE_API_AUTH_SESSION_PATH ?? '/api/auth/session',
    authStart: import.meta.env.VITE_API_AUTH_START_PATH ?? '/api/auth/{provider}/start',
    authLogout: import.meta.env.VITE_API_AUTH_LOGOUT_PATH ?? '/api/auth/logout',
  },
  mockDelays: {
    chat: Number(import.meta.env.VITE_MOCK_CHAT_DELAY_MS ?? 650),
    diff: Number(import.meta.env.VITE_MOCK_DIFF_DELAY_MS ?? 450),
    repositories: Number(import.meta.env.VITE_MOCK_REPOSITORIES_DELAY_MS ?? 250),
  },
} as const
