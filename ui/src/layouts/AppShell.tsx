import { Outlet } from 'react-router-dom'
import { useState } from 'react'
import Sidebar from '../components/Sidebar'
import Header from '../components/Header'
import Footer from '../components/Footer'
import RightPanel from '../components/RightPanel'
import { useChat } from '../contexts/ChatContext'

export default function AppShell() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const { profile } = useChat()
  const showAdminPanel = !!profile?.is_admin

  return (
    <div className="h-full w-full bg-neutral-950 text-neutral-100 flex flex-col overflow-hidden">
      {/* Fixed Header */}
      <Header />

      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/50 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Main content area - 3 columns */}
      <main className="flex-1 min-h-0 flex overflow-hidden">
        {/* Left Sidebar - fixed width */}
        <aside
          className={[
            "w-72 min-w-[18rem] bg-neutral-900 border-r border-neutral-800 overflow-hidden",
            "hidden md:flex md:flex-col",
            /* Mobile: fixed overlay */
            sidebarOpen ? "fixed inset-y-0 left-0 z-40 flex flex-col" : "hidden",
          ].join(" ")}
        >
          <Sidebar onNavigate={() => setSidebarOpen(false)} />
        </aside>

        {/* Center column - flex-1, contains ChatView + Composer */}
        <div className="flex-1 min-w-0 flex flex-col overflow-hidden">
          {/* Mobile menu trigger */}
          <div className="md:hidden flex items-center gap-2 h-14 shrink-0 px-4 border-b border-neutral-800 bg-neutral-900">
            <button
              type="button"
              onClick={() => setSidebarOpen(true)}
              className="inline-flex items-center gap-2 rounded-lg border border-neutral-800 px-3 py-1.5 text-sm bg-neutral-800 hover:bg-neutral-700"
              aria-label="Åbn menu"
            >
              <span className="text-lg">☰</span>
              <span>Menu</span>
            </button>
          </div>

          {/* ChatView - scrollable */}
          <div className="flex-1 min-h-0 overflow-y-auto">
            <Outlet />
          </div>
        </div>

        {/* Right Admin Panel - fixed width, admin only */}
        {showAdminPanel && <RightPanel />}
      </main>

      {/* Fixed Footer */}
      <Footer />
    </div>
  )
}
