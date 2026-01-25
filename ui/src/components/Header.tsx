import { useState } from 'react'
import { useChat } from '../contexts/ChatContext'

export default function Header() {
  const { profile } = useChat()
  const [search, setSearch] = useState('')
  const name = profile?.username || 'Jarvis'

  return (
    <header className="h-14 shrink-0 border-b border-neutral-800 bg-neutral-900/80 backdrop-blur flex items-center justify-between px-4 md:px-6">
      <div className="flex items-center gap-2">
        <div className="h-8 w-8 rounded-lg bg-emerald-600 grid place-items-center text-sm font-semibold">
          J
        </div>
        <div className="text-sm font-semibold">Jarvis</div>
        <div className="flex items-center gap-1 text-xs text-emerald-300">
          <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
          <span>Online</span>
        </div>
      </div>
      
      <div className="flex items-center gap-3">
        <input
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Søg i chats..."
          className="hidden md:block w-64 px-3 py-1.5 text-sm bg-neutral-800 border border-neutral-700 rounded-lg focus:outline-none focus:ring-1 focus:ring-emerald-500 placeholder:text-neutral-500"
        />
        <div className="text-xs text-neutral-400 truncate">
          {profile ? name : 'Ikke logget ind'}
        </div>
      </div>
    </header>
  )
}
