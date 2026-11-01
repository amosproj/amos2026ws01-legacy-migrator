export type DiffFile = {
  path: string
  status: 'modified' | 'added' | 'deleted'
  additions: number
  deletions: number
  explanation: string
  patch: string
}

export type DiffExplanation = {
  summary: string
  risk: 'low' | 'medium' | 'high'
  files: DiffFile[]
  warnings: string[]
}

export type DiffRequest = {
  repository: string
  provider: RepositoryProvider
  base: string
  head: string
}

export interface DiffAdapter {
  explain(request: DiffRequest): Promise<DiffExplanation>
}

const mockDiff: DiffExplanation = {
  summary: 'Migrates account lookups from the legacy service to the target API while preserving the billing worker contract.',
  risk: 'medium',
  files: [
    {
      path: 'src/account/account-service.ts',
      status: 'modified',
      additions: 24,
      deletions: 8,
      explanation: 'Replaces the direct legacy database lookup with the target Account API client and keeps the existing domain response shape.',
      patch: '- const account = legacyDb.findAccount(accountId)\n+ const account = await accountApi.getAccount(accountId)\n+ return account',
    },
    {
      path: 'src/account/account-api.ts',
      status: 'added',
      additions: 38,
      deletions: 0,
      explanation: 'Adds the typed HTTP boundary used by the migrated account service.',
      patch: '+ export async function getAccount(accountId: string) {\n+   return client.get(`/accounts/${accountId}`)\n+ }',
    },
  ],
  warnings: ['The billing worker still calls the legacy account service directly.'],
}

export const diffAdapter: DiffAdapter = {
  async explain(request) {
    if (clientConfig.useMockApi) {
      await new Promise((resolve) => window.setTimeout(resolve, clientConfig.mockDelays.diff))
      return mockDiff
    }

    const response = await fetch(`${clientConfig.backendUrl}${clientConfig.apiPaths.diffExplain}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    })
    if (!response.ok) throw new Error(`The backend returned ${response.status}. Please try again.`)
    return (await response.json()) as DiffExplanation
  },
}
import { clientConfig } from '../config/env'
import type { RepositoryProvider } from './repositoryAdapter'
