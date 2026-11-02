import { useCallback, useEffect, useMemo, useReducer } from 'react'
import { repositoryAdapter, type Repository } from '../../lib/repositoryAdapter'

export type RepositoryPickerStatus = 'loading' | 'success' | 'error'

type State = {
  repositories: Repository[]
  status: RepositoryPickerStatus
  search: string
  isOpen: boolean
  error: string | null
}

type Action =
  | { type: 'repositories/loading' }
  | { type: 'repositories/loaded'; repositories: Repository[] }
  | { type: 'repositories/failed'; error: string }
  | { type: 'menu/toggled' }
  | { type: 'menu/closed' }
  | { type: 'search/updated'; search: string }

export const initialRepositoryPickerState: State = {
  repositories: [],
  status: 'loading',
  search: '',
  isOpen: false,
  error: null,
}

export function repositoryPickerReducer(state: State, action: Action): State {
  switch (action.type) {
    case 'repositories/loading':
      return { ...state, status: 'loading', error: null }
    case 'repositories/loaded':
      return { ...state, repositories: action.repositories, status: 'success', error: null }
    case 'repositories/failed':
      return { ...state, status: 'error', error: action.error }
    case 'menu/toggled':
      return { ...state, isOpen: !state.isOpen }
    case 'menu/closed':
      return { ...state, isOpen: false, search: '' }
    case 'search/updated':
      return { ...state, search: action.search }
  }
}

export function useRepositoryPicker() {
  const [state, dispatch] = useReducer(repositoryPickerReducer, initialRepositoryPickerState)

  useEffect(() => {
    let isCurrent = true
    dispatch({ type: 'repositories/loading' })

    repositoryAdapter.list()
      .then((repositories) => {
        if (isCurrent) dispatch({ type: 'repositories/loaded', repositories })
      })
      .catch((requestError: unknown) => {
        if (isCurrent) {
          dispatch({
            type: 'repositories/failed',
            error: requestError instanceof Error ? requestError.message : 'Repositories could not be loaded.',
          })
        }
      })

    return () => {
      isCurrent = false
    }
  }, [])

  const filteredRepositories = useMemo(() => {
    const normalizedSearch = state.search.trim().toLowerCase()
    if (!normalizedSearch) return state.repositories
    return state.repositories.filter((repository) => repository.fullName.toLowerCase().includes(normalizedSearch))
  }, [state.repositories, state.search])

  const toggleMenu = useCallback(() => {
    dispatch({ type: 'menu/toggled' })
  }, [])

  const closeMenu = useCallback(() => {
    dispatch({ type: 'menu/closed' })
  }, [])

  const updateSearch = useCallback((search: string) => {
    dispatch({ type: 'search/updated', search })
  }, [])

  return {
    ...state,
    filteredRepositories,
    isLoading: state.status === 'loading',
    toggleMenu,
    closeMenu,
    updateSearch,
  }
}
