import { clientConfig } from '../config/env'

export type RepositoryProvider = 'github' | 'gitlab' | 'bitbucket' | 'azure-devops' | 'gitea'

export type Repository = {
  id: number
  provider: RepositoryProvider
  providerLabel: string
  fullName: string
  description: string | null
  defaultBranch: string
  isPrivate: boolean
}

export interface RepositoryAdapter {
  list(): Promise<Repository[]>
}

const mockRepositories: Repository[] = [
  { id: 1, provider: 'github', providerLabel: 'GitHub', fullName: 'amosproj/legacy-migrator', description: 'Migration prototype', defaultBranch: 'main', isPrivate: false },
  { id: 2, provider: 'gitlab', providerLabel: 'GitLab', fullName: 'amosproj/target-system', description: 'Target application', defaultBranch: 'trunk', isPrivate: true },
  { id: 3, provider: 'bitbucket', providerLabel: 'Bitbucket', fullName: 'amosproj/architecture-views', description: 'Generated architecture views', defaultBranch: 'main', isPrivate: false },
]

export const repositoryAdapter: RepositoryAdapter = {
  async list() {
    if (clientConfig.useMockApi) {
      await new Promise((resolve) => window.setTimeout(resolve, clientConfig.mockDelays.repositories))
      return mockRepositories
    }

    const response = await fetch(`${clientConfig.backendUrl}${clientConfig.apiPaths.repositories}`)
    if (!response.ok) throw new Error(`Repositories could not be loaded (${response.status}).`)
    const repositories = (await response.json()) as unknown
    if (!Array.isArray(repositories)) throw new Error('The repository service returned an invalid repository list.')
    return repositories as Repository[]
  },
}