import { useState } from 'react'
import { useChat } from '../contexts/ChatContext'

export default function Header() {
  const { profile } = useChat()
  const [search, setSearch] = useState('')
  const name = profile?.username || 'Jarvis'

  return (
    <header className="h-14 shrink-0 border-b border-neutral-800 bg-neutral-900/80 backdrop-blur px-4 md:px-6">
      <div className="h-full grid grid-cols-[1fr,auto,1fr] items-center gap-4">
        {/* Left section */}
        <div className="flex items-center gap-3">
          <div className="text-base font-semibold">Jarvis AI</div>
          <span className="text-neutral-700">·</span>
          <div className="flex items-center gap-1.5 text-sm text-emerald-300">
            <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
            <span>Online</span>
          </div>
        </div>

        {/* Center scrolling banner */}
        <div className="hidden lg:block overflow-hidden max-w-md">
          <div className="animate-marquee whitespace-nowrap text-sm text-neutral-400">
            Velkommen til Jarvis AI · Din AI-assistent er klar til at hjælpe · Stil mig et spørgsmål · Jeg er her 24/7
          </div>
        </div>
        
        {/* Right section */}
        <div className="flex items-center gap-3 justify-end">
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Søg i chats..."
            className="hidden md:block w-64 px-3 py-1.5 text-sm bg-neutral-800 border border-neutral-700 rounded-lg focus:outline-none focus:ring-1 focus:ring-emerald-500 placeholder:text-neutral-500"
          />
        </div>
      </div>
    </header>
  )
}
