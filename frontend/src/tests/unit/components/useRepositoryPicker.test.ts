import { act, renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { repositoryAdapter } from '../../../lib/repositoryAdapter'
import { initialRepositoryPickerState, repositoryPickerReducer, useRepositoryPicker } from '../../../components/repositories/useRepositoryPicker'

const repositories = [
  { id: 1, provider: 'github' as const, providerLabel: 'GitHub', fullName: 'amosproj/legacy-migrator', description: null, defaultBranch: 'main', isPrivate: false },
  { id: 2, provider: 'gitlab' as const, providerLabel: 'GitLab', fullName: 'amosproj/target-system', description: null, defaultBranch: 'trunk', isPrivate: true },
]

describe('repositoryPickerReducer', () => {
  it('handles repository loading and menu transitions', () => {
    const loaded = repositoryPickerReducer(initialRepositoryPickerState, { type: 'repositories/loaded', repositories })
    const opened = repositoryPickerReducer(loaded, { type: 'menu/toggled' })
    const closed = repositoryPickerReducer({ ...opened, search: 'legacy' }, { type: 'menu/closed' })

    expect(loaded.status).toBe('success')
    expect(opened.isOpen).toBe(true)
    expect(closed).toMatchObject({ isOpen: false, search: '' })
  })

  it('stores loading failures', () => {
    const failed = repositoryPickerReducer(initialRepositoryPickerState, { type: 'repositories/failed', error: 'Unavailable' })

    expect(failed).toMatchObject({ status: 'error', error: 'Unavailable' })
  })
})

describe('useRepositoryPicker', () => {
  it('loads and filters repositories', async () => {
    vi.spyOn(repositoryAdapter, 'list').mockResolvedValue(repositories)
    const { result } = renderHook(() => useRepositoryPicker())

    await waitFor(() => expect(result.current.isLoading).toBe(false))
    act(() => result.current.updateSearch('target'))

    expect(result.current.filteredRepositories).toHaveLength(1)
    expect(result.current.filteredRepositories[0].fullName).toBe('amosproj/target-system')
  })
})
