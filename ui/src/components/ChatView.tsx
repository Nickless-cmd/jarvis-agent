import { useEffect, useMemo, useRef, useState } from 'react'
import { useChat } from '../contexts/ChatContext'

export default function ChatView({ scrollRef }: { scrollRef: React.RefObject<HTMLDivElement> }) {
  const { activeSessionId, messages, loadMessages } = useChat()
  const [atBottom, setAtBottom] = useState(true)

  useEffect(() => {
    if (activeSessionId) loadMessages(activeSessionId)
  }, [activeSessionId])

  // Track scroll and auto-scroll when near bottom
  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    function onScroll() {
      const dist = el.scrollHeight - el.scrollTop - el.clientHeight
      setAtBottom(dist <= 80)
    }
    el.addEventListener('scroll', onScroll)
    return () => el.removeEventListener('scroll', onScroll)
  }, [scrollRef])

  useEffect(() => {
    if (!messages.length || !scrollRef.current) return
    if (!atBottom) return
    requestAnimationFrame(() => {
      const el = scrollRef.current!
      el.scrollTop = el.scrollHeight
    })
  }, [messages, scrollRef, atBottom])

  const rendered = useMemo(() => {
    return messages.map((m, idx) => {
      const role = m.role || (m as any).author || 'assistant'
      const isUser = role === 'user'
      const timestamp = m.created_at || (m as any).timestamp || new Date().toISOString()
      const timeStr = new Date(timestamp).toLocaleTimeString('da-DK', { 
        hour: '2-digit', 
        minute: '2-digit' 
      })

      return (
        <div
          key={m.id || idx}
          className={[
            "rounded-2xl border border-neutral-800/60 px-4 py-3 text-sm leading-6",
            isUser ? "bg-neutral-900/80 border-neutral-800" : "bg-neutral-900/60",
          ].join(" ")}
        >
          <div className="flex items-center justify-between gap-2 text-xs text-neutral-500 mb-1">
            {isUser ? (
              <>
                <span>{timeStr}</span>
                <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-neutral-800 text-neutral-200 text-[11px] font-semibold">
                  You
                </span>
              </>
            ) : (
              <>
                <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-neutral-800 text-neutral-200 text-[11px] font-semibold">
                  Jarvis
                </span>
                <span>{timeStr}</span>
              </>
            )}
          </div>
          <div className={[
            "whitespace-pre-wrap break-words text-neutral-100",
            isUser ? "text-right" : ""
          ].join(" ")}>
            {m.content || (m as any).text || ''}
          </div>
        </div>
      )
    })
  }, [messages])

  return (
    <>
      {!activeSessionId && (
        <div className="flex h-[60vh] items-center justify-center">
          <div className="text-center space-y-2">
            <div className="text-2xl font-semibold text-neutral-50">Velkommen til Jarvis</div>
            <div className="text-sm text-neutral-400">Start en ny chat eller vælg en i venstre side.</div>
          </div>
        </div>
      )}

      {activeSessionId && messages.length === 0 && (
        <div className="flex h-[60vh] items-center justify-center">
          <div className="text-center space-y-2">
            <div className="text-xl font-semibold text-neutral-50">Ingen beskeder endnu</div>
            <div className="text-sm text-neutral-400">Skriv til Jarvis for at komme i gang.</div>
          </div>
        </div>
      )}

      {activeSessionId && messages.length > 0 && (
        <div className="flex flex-col gap-4 relative">
          {rendered}
          {!atBottom && (
            <div className="absolute bottom-2 right-2">
              <button
                className="px-3 py-1.5 text-xs rounded-full bg-neutral-800 border border-neutral-700 text-neutral-200 hover:bg-neutral-700"
                onClick={() => {
                  const el = scrollRef.current
                  if (el) {
                    el.scrollTop = el.scrollHeight
                    setAtBottom(true)
                  }
                }}
              >
                Jump to bottom
              </button>
            </div>
          )}
        </div>
      )}
    </>
  )
}
