import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { RepositoryPicker } from '../../../components/repositories/RepositoryPicker'
import { repositoryAdapter } from '../../../lib/repositoryAdapter'

afterEach(() => vi.restoreAllMocks())

describe('RepositoryPicker', () => {
  it('loads repositories and reports the selected repository', async () => {
    const user = userEvent.setup()
    vi.spyOn(repositoryAdapter, 'list').mockResolvedValue([
      { id: 1, provider: 'github', providerLabel: 'GitHub', fullName: 'amosproj/legacy-migrator', description: 'Migration prototype', defaultBranch: 'main', isPrivate: false },
      { id: 2, provider: 'gitlab', providerLabel: 'GitLab', fullName: 'amosproj/target-system', description: null, defaultBranch: 'trunk', isPrivate: true },
    ])
    const onSelect = vi.fn()
    render(<RepositoryPicker value="" onSelect={onSelect} />)

    await user.click(await screen.findByRole('button', { name: /Select repository/ }))
    await user.click(screen.getByRole('option', { name: /amosproj\/legacy-migrator/ }))

    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ fullName: 'amosproj/legacy-migrator' }))
  })

  it('shows an error when repositories cannot be loaded', async () => {
    vi.spyOn(repositoryAdapter, 'list').mockRejectedValue(new Error('Repository service is unavailable.'))
    render(<RepositoryPicker value="" onSelect={vi.fn()} />)

    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Repository service is unavailable.'))
  })
})
