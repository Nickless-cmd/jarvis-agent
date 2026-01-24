import { useEffect, useMemo, useRef, useState } from 'react'
import { useChat } from '../contexts/ChatContext'

export default function ChatView() {
  const { activeSessionId, messages, loadMessages } = useChat()
  const feedRef = useRef<HTMLDivElement>(null)
  const [autoScroll, setAutoScroll] = useState(true)

  useEffect(() => {
    if (activeSessionId) loadMessages(activeSessionId)
  }, [activeSessionId])

  // keep scroll at bottom when close to bottom
  useEffect(() => {
    const el = feedRef.current
    if (!el) return
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 160
    if (nearBottom || autoScroll) {
      el.scrollTop = el.scrollHeight
      setAutoScroll(true)
    }
  }, [messages, autoScroll])

  const rendered = useMemo(() => {
    return messages.map((m, idx) => {
      const role = m.role || (m as any).author || 'assistant'
      const isUser = role === 'user'

      return (
        <div
          key={m.id || idx}
          className={[
            "rounded-2xl border border-neutral-800/60 px-4 py-3 text-sm leading-6",
            isUser ? "bg-neutral-900/80 border-neutral-800" : "bg-neutral-900/60",
          ].join(" ")}
        >
          <div className="flex items-center gap-2 text-xs text-neutral-500 mb-1">
            <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-neutral-800 text-neutral-200 text-[11px] font-semibold">
              {isUser ? 'You' : 'Jarvis'}
            </span>
            <span>{role === 'user' ? 'User' : 'Assistant'}</span>
          </div>
          <div className="whitespace-pre-wrap break-words text-neutral-100">
            {m.content || (m as any).text || ''}
          </div>
        </div>
      )
    })
  }, [messages])

  return (
    <div
      ref={feedRef}
      className="flex-1 overflow-y-auto px-4 md:px-6"
      onScroll={(e) => {
        const el = e.currentTarget
        const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 160
        setAutoScroll(nearBottom)
      }}
    >
      {!activeSessionId && (
        <div className="flex h-full items-center justify-center">
          <div className="text-center space-y-2">
            <div className="text-2xl font-semibold text-neutral-50">Velkommen til Jarvis</div>
            <div className="text-sm text-neutral-400">Start en ny chat eller vælg en i venstre side.</div>
          </div>
        </div>
      )}

      {activeSessionId && messages.length === 0 && (
        <div className="flex h-full items-center justify-center">
          <div className="text-center space-y-2">
            <div className="text-xl font-semibold text-neutral-50">Ingen beskeder endnu</div>
            <div className="text-sm text-neutral-400">Skriv til Jarvis for at komme i gang.</div>
          </div>
        </div>
      )}

      <div className="mx-auto w-full max-w-3xl py-6 flex flex-col gap-4">
        {rendered}
      </div>
    </div>
  )
}
