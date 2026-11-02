import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from '../../App'
import { chatAdapter } from '../../lib/chatAdapter'

afterEach(() => {
  vi.restoreAllMocks()
})

describe('App', () => {
  it('renders the welcome state and starter questions', async () => {
    render(<App />)

    expect(screen.getByRole('heading', { name: 'Migration assistant' })).toBeInTheDocument()
    expect(screen.getByText(/Hi, I’m your migration assistant/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'What should we decommission next?' })).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: 'Question' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Sign in with GitHub' })).toBeInTheDocument()
    expect(await screen.findByText('Mock API')).toBeInTheDocument()
  })

  it('allows a user to select a starter question and submit it', async () => {
    const user = userEvent.setup()
    vi.spyOn(chatAdapter, 'ask').mockResolvedValue({
      answer: 'The customer portal is ready for review.',
      conversationId: 'conversation-1',
    })
    render(<App />)

    await user.click(screen.getByRole('button', { name: 'What should we decommission next?' }))
    expect(screen.getByRole('textbox', { name: 'Question' })).toHaveValue('What should we decommission next?')

    await user.click(screen.getByRole('button', { name: 'Send question' }))

    await waitFor(() => expect(screen.getByText('The customer portal is ready for review.')).toBeInTheDocument())
    expect(chatAdapter.ask).toHaveBeenCalledWith({ query: 'What should we decommission next?', conversationId: undefined }, expect.any(AbortSignal))
    expect(screen.queryByRole('button', { name: 'What should we decommission next?' })).not.toBeInTheDocument()
  })

  it('submits with Enter and displays the loading state while waiting', async () => {
    const user = userEvent.setup()
    let resolveRequest!: (response: { answer: string }) => void
    vi.spyOn(chatAdapter, 'ask').mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveRequest = resolve
        }),
    )
    render(<App />)

    const input = screen.getByRole('textbox', { name: 'Question' })
    await user.type(input, 'What is still coupled?')
    await user.keyboard('{Enter}')

    expect(screen.getByText('Thinking...')).toBeInTheDocument()
    expect(input).toHaveValue('')

    await act(async () => resolveRequest({ answer: 'The billing worker still calls the legacy account service.' }))
    await waitFor(() => expect(screen.getByText(/billing worker still calls/)).toBeInTheDocument())
    expect(screen.queryByText('Thinking...')).not.toBeInTheDocument()
  })

  it('shows a useful error when the adapter fails', async () => {
    const user = userEvent.setup()
    vi.spyOn(chatAdapter, 'ask').mockRejectedValue(new Error('The backend is unavailable.'))
    render(<App />)

    await user.type(screen.getByRole('textbox', { name: 'Question' }), 'Check migration status')
    await user.keyboard('{Enter}')

    expect(await screen.findByRole('alert')).toHaveTextContent('The backend is unavailable.')
  })

  it('starts a new conversation when requested', async () => {
    const user = userEvent.setup()
    vi.spyOn(chatAdapter, 'ask').mockResolvedValue({ answer: 'A response.' })
    render(<App />)

    await user.type(screen.getByRole('textbox', { name: 'Question' }), 'Any updates?')
    await user.keyboard('{Enter}')
    expect(await screen.findByText('A response.')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /New conversation/ }))

    expect(screen.getByText(/Hi, I’m your migration assistant/)).toBeInTheDocument()
    expect(screen.queryByText('A response.')).not.toBeInTheDocument()
  })

  it('explains a Git comparison from the change explanations view', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.click(screen.getByRole('button', { name: /Change explanations/ }))
    expect(screen.getByRole('heading', { name: 'Change explanations' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /Explain changes/ }))

    expect(await screen.findByText(/Migrates account lookups from the legacy service/)).toBeInTheDocument()
    expect(screen.getByText('The billing worker still calls the legacy account service directly.')).toBeInTheDocument()
    expect(screen.getByText('src/account/account-service.ts')).toBeInTheDocument()
  })
})
