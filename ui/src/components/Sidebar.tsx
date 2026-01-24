import { NavLink, useNavigate } from 'react-router-dom'
import { useChat } from '../contexts/ChatContext'

type Props = { onNavigate?: () => void }

export default function Sidebar({ onNavigate }: Props) {
  const { sessions, activeSessionId, setActiveSessionId, createNewChat, profile, logout } = useChat()
  const navigate = useNavigate()

  const username = profile?.username || profile?.user || 'Bruger'
  const initials = username?.slice(0, 1)?.toUpperCase() || 'U'

  function handleSelectSession(id: string) {
    setActiveSessionId(id)
    onNavigate?.()
  }

  function handleAdminClick() {
    navigate('/admin')
    onNavigate?.()
  }

  function handleSettings() {
    navigate('/settings')
    onNavigate?.()
  }

  return (
    <div className="h-full flex flex-col bg-neutral-900">
      {/* Top */}
      <div className="px-3 pt-4 pb-3 border-b border-neutral-800">
        <button
          onClick={createNewChat}
          className="w-full rounded-lg border border-neutral-700 bg-neutral-800 hover:bg-neutral-700 px-3 py-2 text-sm font-medium transition"
        >
          + New chat
        </button>
        <div className="mt-3">
          <input
            type="search"
            placeholder="Search chats"
            className="w-full rounded-lg bg-neutral-800 border border-neutral-700 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-emerald-500"
          />
        </div>
      </div>

      {/* Sessions */}
      <div className="flex-1 overflow-y-auto px-3 py-3 space-y-2">
        <div className="text-xs text-neutral-400 uppercase tracking-wide px-1">Your chats</div>
        {sessions.length === 0 && (
          <div className="text-sm text-neutral-500 px-1">No chats yet.</div>
        )}
        <div className="space-y-1">
          {sessions.map((s) => {
            const id = s.id || (s as any).session_id || (s as any).sessionId
            const title = s.name || (s as any).title || 'Untitled'
            const active = id === activeSessionId

            return (
              <div
                key={id}
                className={[
                  "group flex items-center gap-2 rounded-lg px-2 py-2 text-sm transition",
                  active ? "bg-neutral-800 border border-neutral-700" : "hover:bg-neutral-800/60 border border-transparent",
                ].join(" ")}
              >
                <button
                  onClick={() => handleSelectSession(id)}
                  className="flex-1 text-left truncate"
                >
                  {title}
                </button>
                <button
                  className="opacity-0 group-hover:opacity-100 text-neutral-400 hover:text-neutral-200 transition"
                  title="More"
                >
                  …
                </button>
              </div>
            )
          })}
        </div>
      </div>

      {/* Bottom profile/actions */}
      <div className="border-t border-neutral-800 px-3 py-4 space-y-3">
        {profile ? (
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-full bg-neutral-800 grid place-items-center text-sm font-semibold">
              {initials}
            </div>
            <div className="min-w-0">
              <div className="text-sm font-medium truncate">{username}</div>
              <div className="text-xs text-neutral-400 truncate">{profile?.email || ''}</div>
            </div>
          </div>
        ) : (
          <div className="text-sm text-neutral-400">Not logged in</div>
        )}

        <div className="space-y-2 text-sm">
          <button
            onClick={handleSettings}
            className="w-full text-left px-3 py-2 rounded-lg bg-neutral-800 hover:bg-neutral-700 border border-neutral-700 transition"
          >
            Settings
          </button>
          {profile?.is_admin && (
            <button
              onClick={handleAdminClick}
              className="w-full text-left px-3 py-2 rounded-lg bg-neutral-800 hover:bg-neutral-700 border border-neutral-700 transition"
            >
              Admin
            </button>
          )}
          <NavLink
            to="/logout"
            onClick={(e) => { e.preventDefault(); logout(); }}
            className="block px-3 py-2 rounded-lg bg-neutral-800 hover:bg-neutral-700 border border-neutral-700 transition"
          >
            Logout
          </NavLink>
        </div>
      </div>
    </div>
  )
}
