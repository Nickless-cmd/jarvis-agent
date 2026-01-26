import { useState } from 'react'
import { useChat } from '../contexts/ChatContext'

export default function Composer() {
  const { activeSessionId, sendMessage, isStreaming, stopStreaming } = useChat()
  const [value, setValue] = useState('')
  const [busy, setBusy] = useState(false)

  async function onSend() {
    const text = value.trim()
    if (!text || busy) return
    setBusy(true)
    setValue('')
    try {
      await sendMessage({ sessionId: activeSessionId, prompt: text })
    } finally {
      setBusy(false)
    }
  }

  const disabled = busy || isStreaming || !value.trim() || !activeSessionId

  return (
    <div className="w-full px-4 py-4 bg-neutral-950">
      <div className="max-w-4xl w-full mx-auto">
        <div className="rounded-full bg-neutral-900 px-4 py-3">
          <div className="flex items-end gap-3">
            <button
              type="button"
              className="h-10 w-10 rounded-full bg-neutral-800 border border-neutral-700 text-lg leading-none text-neutral-300 hover:bg-neutral-700"
              title="Tilføj"
            >
              +
            </button>
            <textarea
              value={value}
              onChange={(e) => setValue(e.target.value)}
              placeholder={activeSessionId ? "Stil dit spørgsmål…" : "Vælg eller opret en chat for at skrive"}
              rows={1}
              className="flex-1 resize-none bg-transparent outline-none text-sm leading-6 text-neutral-50 placeholder:text-neutral-500 max-h-40"
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  onSend()
                }
              }}
            />
            <div className="flex items-center gap-2">
              <button
                type="button"
                className="h-10 w-10 rounded-full bg-neutral-800 border border-neutral-700 text-neutral-300 hover:bg-neutral-700"
                title="Stemme (placeholder)"
              >
                🎤
              </button>
              {!isStreaming && (
                <button
                  onClick={onSend}
                  disabled={disabled}
                  className="h-10 px-4 rounded-full bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 disabled:cursor-not-allowed text-sm font-medium text-neutral-50 transition"
                >
                  Send
                </button>
              )}
              {isStreaming && (
                <button
                  onClick={stopStreaming}
                  className="h-10 px-4 rounded-full bg-red-600 hover:bg-red-500 text-sm font-medium text-neutral-50 transition disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Stop
                </button>
              )}
            </div>
          </div>
        </div>
        <div className="text-[11px] text-neutral-500 mt-2 pl-[52px]">
          Enter = send · Shift+Enter = ny linje
        </div>
      </div>
    </div>
  )
}
