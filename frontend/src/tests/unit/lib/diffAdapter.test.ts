import { afterEach, describe, expect, it, vi } from 'vitest'
import { diffAdapter } from '../../../lib/diffAdapter'

afterEach(() => {
  vi.restoreAllMocks()
})

describe('diffAdapter', () => {
  it('returns a mock explanation with migration details in mock mode', async () => {
    const result = await diffAdapter.explain({
      repository: 'example/repository',
      provider: 'gitlab',
      base: 'main',
      head: 'feature/migration',
    })

    expect(result.summary).toMatch(/legacy service/)
    expect(result.files.length).toBeGreaterThan(0)
    expect(result.files[0]).toEqual(expect.objectContaining({ path: expect.any(String), patch: expect.any(String) }))
    expect(result.warnings.length).toBeGreaterThan(0)
  })
})
