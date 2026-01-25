import { useChat } from '../contexts/ChatContext'

export default function RightPanel() {
  const { profile } = useChat()
  if (!profile?.is_admin) return null

  const cards = [
    { title: 'Status', body: 'Systemstatus (placeholder).' },
    { title: 'Logs', body: 'Seneste logs (placeholder).' },
    { title: 'Tools', body: 'Værktøjer og jobs (placeholder).' },
  ]

  return (
    <aside className="flex flex-col w-72 shrink-0 border-l border-neutral-800 bg-neutral-900/60 overflow-hidden">
      <div className="shrink-0 border-b border-neutral-800 px-4 py-3 text-sm font-semibold">
        Admin panel
      </div>
      <div className="flex-1 min-h-0 overflow-y-auto p-4 space-y-3">
        {cards.map((c) => (
          <div key={c.title} className="rounded-xl border border-neutral-800 bg-neutral-950 p-3">
            <div className="text-sm font-semibold mb-1">{c.title}</div>
            <div className="text-xs text-neutral-400">{c.body}</div>
          </div>
        ))}
      </div>
    </aside>
  )
}
