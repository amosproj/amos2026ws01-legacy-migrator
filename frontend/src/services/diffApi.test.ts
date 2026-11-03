import { describe, expect, it, vi } from 'vitest'
import { explainDiff, listRepositories } from './diffApi'

describe('Diff API service', () => {
  it('fills branch metadata when an older backend omits it', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify([
      {
        id: 2,
        provider: 'github',
        providerLabel: 'GitHub',
        fullName: 'amosproj/amos2026ws01-legacy-migrator',
        defaultBranch: 'main',
        isPrivate: false,
      },
    ])))

    await expect(listRepositories()).resolves.toEqual([
      expect.objectContaining({ branches: ['main', 'develop', 'feature/account-api'] }),
    ])
  })

  it('loads provider-neutral repositories from the backend', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify([
      { id: '1', provider: 'github', fullName: 'amosproj/example', defaultBranch: 'main', url: 'https://github.com/amosproj/example' },
    ])))

    await expect(listRepositories()).resolves.toMatchObject([{ provider: 'github', fullName: 'amosproj/example' }])
  })

  it('uses the backend detail message for diff failures', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ detail: 'GitHub token is missing.' }), { status: 401 }))

    await expect(explainDiff({ repository: 'amosproj/example', provider: 'github', base: 'main', head: 'feature' }))
      .rejects.toThrow('GitHub token is missing.')
  })

  it('falls back to the local repository fixture when the repository API is offline', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('Backend offline'))

    await expect(listRepositories()).resolves.toEqual(expect.arrayContaining([
      expect.objectContaining({ provider: 'github', fullName: 'amosproj/amos2026ws01-legacy-migrator' }),
    ]))
  })

  it('falls back to a deterministic explanation when diff analysis is offline', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('Backend offline'))

    await expect(explainDiff({ repository: 'amosproj/example', provider: 'github', base: 'main', head: 'feature' }))
      .resolves.toMatchObject({ risk: 'medium', files: expect.any(Array) })
  })
})
