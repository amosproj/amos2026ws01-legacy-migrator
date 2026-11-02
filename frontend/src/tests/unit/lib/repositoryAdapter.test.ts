import { describe, expect, it } from 'vitest'
import { repositoryAdapter } from '../../../lib/repositoryAdapter'

describe('repositoryAdapter', () => {
  it('returns selectable mock repositories in mock mode', async () => {
    const repositories = await repositoryAdapter.list()

    expect(repositories.length).toBeGreaterThan(0)
    expect(repositories[0]).toEqual(expect.objectContaining({
      fullName: expect.any(String),
      provider: expect.stringMatching(/github|gitlab|bitbucket|azure-devops|gitea/),
      providerLabel: expect.any(String),
      defaultBranch: expect.any(String),
    }))
  })
})
