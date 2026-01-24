import ChatView from '../components/ChatView'
import Composer from '../components/Composer'
import { useChat } from '../contexts/ChatContext'

export default function ChatPage() {
  const { profile, profileLoading } = useChat()

  if (profileLoading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-sm text-neutral-400">Loader din profil…</div>
      </div>
    )
  }

  if (!profile) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center space-y-3">
          <div className="text-2xl font-semibold text-neutral-50">Log ind for at fortsætte</div>
          <div className="text-sm text-neutral-400">Din session er ikke aktiv. Log ind for at bruge Jarvis.</div>
          <button
            onClick={() => { window.location.href = '/login' }}
            className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-sm font-medium"
          >
            Gå til login
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 min-h-0 flex flex-col">
      {/* Feed */}
      <div className="flex-1 min-h-0">
        <ChatView />
      </div>

      {/* Composer sticky */}
      <div className="border-t border-neutral-800 bg-neutral-950/95 backdrop-blur sticky bottom-0">
        <Composer />
      </div>
    </div>
  )
}
