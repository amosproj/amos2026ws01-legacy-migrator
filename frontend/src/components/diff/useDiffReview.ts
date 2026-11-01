import { useCallback, useReducer } from 'react'
import { diffAdapter, type DiffExplanation } from '../../lib/diffAdapter'
import type { Repository, RepositoryProvider } from '../../lib/repositoryAdapter'

export type DiffReviewStatus = 'idle' | 'loading' | 'success' | 'error'

export type Comparison = {
  repository: string
  provider: RepositoryProvider
  base: string
  head: string
}

type State = {
  comparison: Comparison
  result: DiffExplanation | null
  status: DiffReviewStatus
  error: string | null
}

type Action =
  | { type: 'comparison/updated'; updates: Partial<Comparison> }
  | { type: 'request/started' }
  | { type: 'request/succeeded'; result: DiffExplanation }
  | { type: 'request/failed'; error: string }
  | { type: 'request/reset' }

export const initialComparison: Comparison = {
  repository: 'amosproj/legacy-migrator',
  provider: 'github',
  base: 'main',
  head: 'develop',
}

export const initialDiffReviewState: State = {
  comparison: initialComparison,
  result: null,
  status: 'idle',
  error: null,
}

export function diffReviewReducer(state: State, action: Action): State {
  switch (action.type) {
    case 'comparison/updated':
      return { ...state, comparison: { ...state.comparison, ...action.updates }, error: null }
    case 'request/started':
      return { ...state, status: 'loading', error: null }
    case 'request/succeeded':
      return { ...state, result: action.result, status: 'success', error: null }
    case 'request/failed':
      return { ...state, status: 'error', error: action.error }
    case 'request/reset':
      return { ...initialDiffReviewState, comparison: state.comparison }
  }
}

export function useDiffReview() {
  const [state, dispatch] = useReducer(diffReviewReducer, initialDiffReviewState)

  const updateComparison = useCallback((updates: Partial<Comparison>) => {
    dispatch({ type: 'comparison/updated', updates })
  }, [])

  const selectRepository = useCallback((repository: Repository) => {
    updateComparison({
      repository: repository.fullName,
      provider: repository.provider,
      base: repository.defaultBranch,
    })
  }, [updateComparison])

  const explainComparison = useCallback(async () => {
    dispatch({ type: 'request/started' })
    try {
      const result = await diffAdapter.explain(state.comparison)
      dispatch({ type: 'request/succeeded', result })
    } catch (requestError) {
      dispatch({
        type: 'request/failed',
        error: requestError instanceof Error ? requestError.message : 'Unable to explain this diff.',
      })
    }
  }, [state.comparison])

  const reset = useCallback(() => {
    dispatch({ type: 'request/reset' })
  }, [])

  return {
    ...state,
    isLoading: state.status === 'loading',
    updateComparison,
    selectRepository,
    explainComparison,
    reset,
  }
}
