export type StreamOptions = {
  sessionId?: string
  prompt: string
  signal?: AbortSignal
}

function getAuthHeaders(): Record<string, string> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  // Prefer persisted token from localStorage; fallback to devkey
  try {
    const ls = typeof window !== 'undefined' ? window.localStorage.getItem('jarvis_token') : null
    if (ls) headers['Authorization'] = `Bearer ${ls}`
  } catch {}
  if (!headers['Authorization']) headers['Authorization'] = 'Bearer devkey'
  // Optionally include X-User-Token from non-httpOnly cookie if present
  try {
    const m = typeof document !== 'undefined' ? document.cookie.match(/jarvis_token=([^;]*)/) : null
    const cookie = m && m[1] ? decodeURIComponent(m[1]) : null
    if (cookie) headers['X-User-Token'] = cookie
  } catch {}
  return headers
}

export async function streamChat(
  opts: StreamOptions,
  onDelta: (text: string) => void,
  onDone: () => void,
  onError: (errText: string) => void,
  onStatus?: (status: string) => void,
  onRehydrate?: (messages: any[]) => void,
) {
  const { sessionId, prompt, signal } = opts
  const headers = getAuthHeaders()
  if (sessionId) headers['X-Session-Id'] = sessionId

  const ac = new AbortController()
  const outerSignal = signal
  if (outerSignal) {
    if (outerSignal.aborted) ac.abort()
    outerSignal.addEventListener('abort', () => ac.abort())
  }

  let reader: ReadableStreamDefaultReader<Uint8Array> | null = null

  try {
    const body = {
      prompt,
      messages: [{ role: 'user', content: prompt }],
      stream: true,
    }
    if (typeof process !== 'undefined' && process.env?.NODE_ENV === 'development') {
      console.debug('[stream] body size', JSON.stringify(body).length)
    }

    const res = await fetch('/v1/chat/completions', {
      method: 'POST',
      headers,
      credentials: 'include',
      body: JSON.stringify(body),
      signal: ac.signal,
    })

    if (!res.ok) {
      onError(`HTTP ${res.status}`)
      // Attempt to rehydrate on auth or network errors
      if (sessionId && onRehydrate) {
        try {
          const { getSessionMessages } = await import('./api')
          const msgs = await getSessionMessages(sessionId)
          onRehydrate(msgs)
        } catch {}
      }
      return { abort: () => ac.abort() }
    }

    reader = res.body?.getReader() || null
    if (!reader) {
      onError('No stream')
      return { abort: () => ac.abort() }
    }

    const dec = new TextDecoder()
    let buffer = ''
    let currentEvent = 'message'
    let dataLines: string[] = []

    async function pump() {
      try {
        while (true) {
          const { done, value } = await reader!.read()
          if (done) break
          buffer += dec.decode(value, { stream: true })
          const lines = buffer.split(/\n/)
          buffer = lines.pop() || ''

          for (const lineRaw of lines) {
            const line = lineRaw.replace(/\r$/, '')
            if (line.startsWith('event:')) {
              currentEvent = line.replace(/^event:\s*/, '').trim() || 'message'
              continue
            }
            if (line.startsWith('data:')) {
              dataLines.push(line.replace(/^data:\s*/, ''))
              continue
            }
            // blank line -> dispatch
            const trimmed = line.trim()
            if (trimmed === '') {
              const payload = dataLines.join('\n')
              dataLines = []
              const evt = currentEvent || 'message'
              currentEvent = 'message'

              if (!payload) continue
              if (payload === '[DONE]') {
                onDone()
                ac.abort()
                return
              }

              // ignore noise events
              if (evt === 'status' || evt === 'ping' || evt === 'heartbeat') {
                continue
              }

              try {
                const parsed = JSON.parse(payload)
                // ignore pure status blobs
                if (parsed.status && typeof parsed.status.state === 'string') {
                  onStatus?.(parsed.status.state)
                  continue
                }
                if (parsed.state && parsed.trace_id && !parsed.content && !parsed.delta) {
                  onStatus?.(parsed.state)
                  continue
                }
                if (parsed.error) {
                  onError(typeof parsed.error === 'string' ? parsed.error : 'Error')
                  ac.abort()
                  return
                }
                if (parsed.choices && parsed.choices[0]) {
                  const choice = parsed.choices[0]
                  const delta = choice.delta
                  const message = choice.message
                  const content =
                    (delta && delta.content) ||
                    (message && message.content) ||
                    parsed.text ||
                    ''
                  if (content) onDelta(content)
                  continue
                }
                if (typeof parsed.text === 'string') {
                  onDelta(parsed.text)
                  continue
                }
                // Otherwise ignore
              } catch (_) {
                // non-JSON payload; only emit raw text for non-status events
                onDelta(payload)
              }
            }
          }
        }
        // flush trailing buffer if any
        const pending = dataLines.join('\n')
        if (pending) {
          try {
            const parsed = JSON.parse(pending)
            if (parsed.status && typeof parsed.status.state === 'string') {
              onStatus?.(parsed.status.state)
            } else if (parsed.choices && parsed.choices[0]) {
              const choice = parsed.choices[0]
              const delta = choice.delta
              const message = choice.message
              const content =
                (delta && delta.content) ||
                (message && message.content) ||
                parsed.text ||
                ''
              if (content) onDelta(content)
            } else if (typeof parsed.text === 'string') {
              onDelta(parsed.text)
            }
          } catch (_) {
            onDelta(pending)
          }
        }
        onDone()
      } catch (err: any) {
        if (err?.name === 'AbortError') return
        onError('Stream aborted')
        // Rehydrate after aborted stream
        if (sessionId && onRehydrate) {
          try {
            const { getSessionMessages } = await import('./api')
            const msgs = await getSessionMessages(sessionId)
            onRehydrate(msgs)
          } catch {}
        }
      }
    }

    pump()
  } catch (err: any) {
    if (err?.name === 'AbortError') {
      // silent
    } else {
      onError('Network error')
      if (sessionId && onRehydrate) {
        try {
          const { getSessionMessages } = await import('./api')
          const msgs = await getSessionMessages(sessionId)
          onRehydrate(msgs)
        } catch {}
      }
    }
  }

  function abort() {
    try { reader?.cancel() } catch {}
    ac.abort()
  }

  return { abort }
}
