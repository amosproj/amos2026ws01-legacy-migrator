import { act, renderHook } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { diffAdapter } from '../../../lib/diffAdapter'
import { diffReviewReducer, initialDiffReviewState, useDiffReview } from '../../../components/diff/useDiffReview'

const result = {
  summary: 'A migration summary.',
  risk: 'low' as const,
  files: [],
  warnings: [],
}

describe('diffReviewReducer', () => {
  it('derives loading and success transitions from explicit actions', () => {
    const loading = diffReviewReducer(initialDiffReviewState, { type: 'request/started' })
    const success = diffReviewReducer(loading, { type: 'request/succeeded', result })

    expect(loading.status).toBe('loading')
    expect(success).toMatchObject({ status: 'success', result, error: null })
  })

  it('keeps comparison values when resetting request state', () => {
    const changed = diffReviewReducer(initialDiffReviewState, {
      type: 'comparison/updated',
      updates: { head: 'release/1.0' },
    })
    const reset = diffReviewReducer(changed, { type: 'request/reset' })

    expect(reset.comparison.head).toBe('release/1.0')
    expect(reset.result).toBeNull()
    expect(reset.status).toBe('idle')
  })
})

describe('useDiffReview', () => {
  it('loads a result and exposes derived loading state', async () => {
    vi.spyOn(diffAdapter, 'explain').mockResolvedValue(result)
    const { result: hook } = renderHook(() => useDiffReview())

    await act(async () => {
      await hook.current.explainComparison()
    })

    expect(hook.current.isLoading).toBe(false)
    expect(hook.current.result).toEqual(result)
    expect(hook.current.status).toBe('success')
  })
})
