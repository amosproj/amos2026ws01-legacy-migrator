import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { DiffReview } from '../../../components/diff/DiffReview'
import { diffAdapter } from '../../../lib/diffAdapter'

afterEach(() => {
  vi.restoreAllMocks()
})

describe('DiffReview', () => {
  it('starts with comparison controls and an empty state', async () => {
    render(<DiffReview />)

    expect(screen.getByRole('heading', { name: 'Change explanations' })).toBeInTheDocument()
    expect(screen.getByText('amosproj/legacy-migrator')).toBeInTheDocument()
    expect(screen.getByLabelText('Base')).toHaveValue('main')
    expect(screen.getByLabelText('Compare with')).toHaveValue('develop')
    expect(screen.getByText('Choose a comparison to get started')).toBeInTheDocument()
  })

  it('submits the selected refs and renders the structured explanation', async () => {
    const user = userEvent.setup()
    const explain = vi.spyOn(diffAdapter, 'explain').mockResolvedValue({
      summary: 'Moves account reads to the target API.',
      risk: 'low',
      files: [{ path: 'src/account.ts', status: 'modified', additions: 3, deletions: 1, explanation: 'Updates the read path.', patch: '- legacy\n+ target' }],
      warnings: ['Review the worker dependency.'],
    })
    render(<DiffReview />)

    await user.click(screen.getByRole('button', { name: /Explain changes/ }))

    await waitFor(() => expect(screen.getByText('Moves account reads to the target API.')).toBeInTheDocument())
    expect(explain).toHaveBeenCalledWith({
      repository: 'amosproj/legacy-migrator',
      provider: 'github',
      base: 'main',
      head: 'develop',
    })
    expect(screen.getByText('src/account.ts')).toBeInTheDocument()
    expect(screen.getByText('Review the worker dependency.')).toBeInTheDocument()
  })

  it('shows an error when diff explanation fails', async () => {
    const user = userEvent.setup()
    vi.spyOn(diffAdapter, 'explain').mockRejectedValue(new Error('Diff service unavailable.'))
    render(<DiffReview />)

    await user.click(screen.getByRole('button', { name: /Explain changes/ }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Diff service unavailable.')
  })
})
