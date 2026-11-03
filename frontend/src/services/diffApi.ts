import { DiffExplanation, DiffRequest, Repository } from '../types/diff'

const API_BASE_URL = '/api'

export const MOCK_REPOSITORIES: Repository[] = [
  {
    id: 'legacy-migrator',
    provider: 'github',
    fullName: 'amosproj/amos2026ws01-legacy-migrator',
    defaultBranch: 'main',
    branches: ['main', 'develop', 'feature/account-api'],
    description: 'Legacy migration knowledge base',
    url: 'https://github.com/amosproj/amos2026ws01-legacy-migrator',
  },
]

const MOCK_EXPLANATION: DiffExplanation = {
  summary: 'Moves account lookups from the legacy service to the target API while preserving the billing worker contract.',
  risk: 'medium',
  files: [
    {
      path: 'src/account/account-service.ts',
      status: 'modified',
      additions: 24,
      deletions: 8,
      explanation: 'Replaces the direct legacy database lookup with the typed target Account API client.',
      patch: '- const account = legacyDb.findAccount(accountId)\n+ const account = await accountApi.getAccount(accountId)\n+ return account',
    },
    {
      path: 'src/account/account-api.ts',
      status: 'added',
      additions: 38,
      deletions: 0,
      explanation: 'Adds the HTTP boundary used by the migrated account service.',
      patch: '+ export async function getAccount(accountId: string) {\n+   return client.get(`/accounts/${accountId}`)\n+ }',
    },
  ],
  warnings: ['The billing worker still calls the legacy account service directly.'],
}

export async function listRepositories(signal?: AbortSignal): Promise<Repository[]> {
  try {
    const response = await fetch(`${API_BASE_URL}/repositories`, { signal })
    if (!response.ok) throw new Error(await responseError(response))
    const repositories = await response.json() as Repository[]
    if (!Array.isArray(repositories)) throw new Error('The repository service returned an invalid list.')
    return repositories.map((repository) => ({
      ...repository,
      branches: repository.branches?.length
        ? repository.branches
        : MOCK_REPOSITORIES.find((mock) => mock.fullName === repository.fullName)?.branches ?? [
            repository.defaultBranch,
          ],
    }))
  } catch (error) {
    if (signal?.aborted) throw error
    return MOCK_REPOSITORIES
  }
}

export async function explainDiff(request: DiffRequest, signal?: AbortSignal): Promise<DiffExplanation> {
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}/diff/explain`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
      signal,
    })
  } catch (error) {
    if (signal?.aborted) throw error
    await new Promise((resolve) => window.setTimeout(resolve, 350))
    return MOCK_EXPLANATION
  }
  if (!response.ok) throw new Error(await responseError(response))
  return await response.json() as DiffExplanation
}

async function responseError(response: Response): Promise<string> {
  if (response.status === 404) {
    return 'The backend does not have the Git comparison endpoint. Restart the backend and try again.'
  }
  const fallback = `The backend returned ${response.status}. Please try again.`
  const body = await response.text()
  try {
    const payload = JSON.parse(body) as { detail?: unknown }
    return typeof payload.detail === 'string' && payload.detail.trim() ? payload.detail : fallback
  } catch {
    return fallback
  }
}
