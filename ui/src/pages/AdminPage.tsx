import { useMemo } from 'react'
import { useChat } from '../contexts/ChatContext'

export default function AdminPage() {
  const { profile } = useChat()

  const cards = useMemo(() => ([
    { title: 'Users', desc: 'Administration af brugere (kommer senere)' },
    { title: 'Sessions', desc: 'Overblik over aktive chats (placeholder)' },
  ]), [])

  if (!profile?.is_admin) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center space-y-2">
          <div className="text-xl font-semibold text-neutral-50">Admin kræver adgang</div>
          <div className="text-sm text-neutral-400">Du skal være admin for at se denne side.</div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 min-h-0 flex flex-col">
      <div className="px-6 py-5 border-b border-neutral-800">
        <h1 className="text-2xl font-semibold">Admin</h1>
        <p className="text-sm text-neutral-400 mt-1">Placeholder visning – udbygges senere.</p>
      </div>
      <div className="p-6 grid gap-4 md:grid-cols-2 max-w-5xl">
        {cards.map((c) => (
          <div key={c.title} className="rounded-xl border border-neutral-800 bg-neutral-900 p-4">
            <div className="text-lg font-semibold mb-1">{c.title}</div>
            <div className="text-sm text-neutral-400">{c.desc}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
