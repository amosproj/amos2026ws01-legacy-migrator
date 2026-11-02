import { useState } from 'react'
import { DiffReview } from './components/diff/DiffReview'
import { ChatView } from './components/chat/ChatView'
import { Sidebar, type AppView } from './components/layout/Sidebar'
import { Topbar } from './components/layout/Topbar'

function App() {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false)
  const [activeView, setActiveView] = useState<AppView>('chat')
  const [chatSessionKey, setChatSessionKey] = useState(0)

  const selectView = (view: AppView) => {
    setActiveView(view)
    setIsSidebarOpen(false)
  }

  return (
    <div className="app-shell">
      <Sidebar isOpen={isSidebarOpen} onClose={() => setIsSidebarOpen(false)} onNewConversation={() => setChatSessionKey((key) => key + 1)} activeView={activeView} onViewChange={selectView} />
      <main className="main-content">
        <Topbar onOpenNavigation={() => setIsSidebarOpen(true)} />
        {activeView === 'diff' ? <DiffReview /> : <ChatView key={chatSessionKey} />}
      </main>
    </div>
  )
}

export default App
