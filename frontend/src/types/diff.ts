export type RepositoryProvider = 'github' | 'gitlab' | 'bitbucket'

export interface Repository {
  id: string
  provider: RepositoryProvider
  fullName: string
  defaultBranch: string
  branches?: string[]
  description?: string
  url: string
}

export interface DiffFile {
  path: string
  status: 'modified' | 'added' | 'deleted'
  additions: number
  deletions: number
  explanation: string
  patch: string
}

export interface DiffExplanation {
  summary: string
  risk: 'low' | 'medium' | 'high'
  files: DiffFile[]
  warnings: string[]
}

export interface DiffRequest {
  repository: string
  provider: RepositoryProvider
  base: string
  head: string
}
