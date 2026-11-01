import { useEffect, useState } from 'react'
import { LogOut, Menu, Search } from 'lucide-react'
import { authAdapter } from '../../lib/authAdapter'
import type { AuthSession } from '../../lib/authAdapter'
import { healthAdapter, type ApiHealth } from '../../lib/healthAdapter'

type TopbarProps = {
  onOpenNavigation: () => void
}

export function Topbar({ onOpenNavigation }: TopbarProps) {
  const [session, setSession] = useState<AuthSession | null>(null)
  const [authError, setAuthError] = useState<string | null>(null)
  const [apiHealth, setApiHealth] = useState<ApiHealth>('checking')

  useEffect(() => {
    healthAdapter.check().then(setApiHealth)
    if (authAdapter.isMockMode) {
      setSession({ authenticated: false })
      return
    }
    authAdapter.session().then(setSession).catch((error: unknown) => setAuthError(error instanceof Error ? error.message : 'Authentication status unavailable.'))
  }, [])

  const handleLogout = async () => {
    try {
      await authAdapter.logout()
      setSession({ authenticated: false })
    } catch (error) {
      setAuthError(error instanceof Error ? error.message : 'Could not sign out.')
    }
  }

  return (
    <header className="topbar">
      <button className="icon-button mobile-menu" onClick={onOpenNavigation} aria-label="Open navigation"><Menu size={20} /></button>
      <div className="breadcrumbs"><span>Workspace</span><span className="crumb-separator">/</span><strong>Migration assistant</strong></div>
      <div className="topbar-actions"><span className={`status-dot ${apiHealth}`} /> {healthLabel(apiHealth)} {session?.authenticated ? <button className="sign-in-button" onClick={handleLogout}><LogOut size={13} /> {session.user?.username ?? 'Sign out'}</button> : <button className="sign-in-button" onClick={() => authAdapter.signIn('github')}>Sign in with GitHub</button>}<button className="icon-button" aria-label="Search"><Search size={18} /></button></div>
      {authError && <span className="auth-error" role="alert">{authError}</span>}
    </header>
  )
}

function healthLabel(status: ApiHealth) {
  switch (status) {
    case 'mock': return 'Mock API'
    case 'checking': return 'Checking API…'
    case 'connected': return 'API connected'
    case 'unavailable': return 'API unavailable'
  }
}
