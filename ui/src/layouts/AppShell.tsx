import { Outlet } from 'react-router-dom'
import { useState } from 'react'
import Sidebar from '../components/Sidebar'

export default function AppShell() {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  return (
    <div className="h-screen w-full bg-neutral-950 text-neutral-100 flex">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/50 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={[
          "fixed inset-y-0 left-0 z-40 w-72 transform bg-neutral-900 border-r border-neutral-800 transition-transform duration-200",
          sidebarOpen ? "translate-x-0" : "-translate-x-full",
          "md:relative md:translate-x-0 md:w-72",
        ].join(" ")}
      >
        <Sidebar onNavigate={() => setSidebarOpen(false)} />
      </aside>

      {/* Main */}
      <main className="flex-1 min-w-0 flex flex-col">
        {/* Mobile sidebar trigger */}
        <div className="md:hidden px-4 py-3 border-b border-neutral-800">
          <button
            type="button"
            onClick={() => setSidebarOpen(true)}
            className="inline-flex items-center gap-2 rounded-lg border border-neutral-800 px-3 py-2 text-sm bg-neutral-900 hover:bg-neutral-800"
            aria-label="Åbn menu"
          >
            <span className="text-lg">☰</span>
            <span>Menu</span>
          </button>
        </div>
        <Outlet />
      </main>
    </div>
  )
}
