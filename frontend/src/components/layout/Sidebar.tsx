import { CircleHelp, ChevronDown, FileText, GitBranch, GitCompare, Plus, Sparkles, X } from 'lucide-react'

export type AppView = 'chat' | 'diff'

type NavigationItem = { view?: AppView; label: string; icon: typeof Sparkles; disabled?: boolean }

const navigationItems: NavigationItem[] = [
  { view: 'chat', label: 'Migration assistant', icon: Sparkles },
  { view: 'diff', label: 'Change explanations', icon: GitCompare },
  { label: 'Architecture views', icon: FileText, disabled: true },
]

type SidebarProps = {
  isOpen: boolean
  onClose: () => void
  onNewConversation: () => void
  activeView: AppView
  onViewChange: (view: AppView) => void
}

export function Sidebar({ isOpen, onClose, onNewConversation, activeView, onViewChange }: SidebarProps) {
  return (
    <aside className={`sidebar ${isOpen ? 'sidebar-open' : ''}`}>
      <div className="sidebar-header">
        <div className="brand-mark"><GitBranch size={18} /></div>
        <span>sunset tracker</span>
        <button className="icon-button mobile-close" onClick={onClose} aria-label="Close navigation"><X size={18} /></button>
      </div>
      <button className="new-chat" onClick={onNewConversation}><Plus size={16} /> New conversation</button>
      <div className="sidebar-section">
        <span className="section-label">Workspace</span>
        {navigationItems.map(({ view, label, icon: Icon, disabled }) => (
          <button className={`nav-item ${view === activeView ? 'active' : ''}`} disabled={disabled} key={label} onClick={() => view && onViewChange(view)}>
            <Icon size={16} /> {label} {disabled && <span className="soon">soon</span>}
          </button>
        ))}
      </div>
      <div className="sidebar-bottom">
        <button className="nav-item"><CircleHelp size={16} /> Help & documentation</button>
        <div className="user-card"><div className="avatar small">AR</div><div><strong>Demo workspace</strong><span>Local prototype</span></div><ChevronDown size={15} /></div>
      </div>
    </aside>
  )
}
