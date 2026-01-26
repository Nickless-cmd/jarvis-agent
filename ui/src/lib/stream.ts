export type StreamOptions = {
  sessionId?: string
  prompt: string
  signal?: AbortSignal
  requestId?: string  // Track request to avoid stale event processing
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
  onDelta: (text: string, requestId?: string) => void,
  onDone: (requestId?: string) => void,
  onError: (errText: string, requestId?: string) => void,
  onStatus?: (status: string, requestId?: string) => void,
  onRehydrate?: (messages: any[]) => void,
  onComplete?: () => void,  // New: called when stream fully completes for cleanup
) {
  const { sessionId, prompt, signal, requestId } = opts
  const headers = getAuthHeaders()
  headers['Accept'] = 'text/event-stream, application/json'
  if (sessionId) headers['X-Session-Id'] = sessionId

  // Track request ID to prevent stale event processing
  const currentRequestId = requestId || `req-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`

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
    const env = (typeof globalThis !== 'undefined' && (globalThis as any).process?.env?.NODE_ENV) || ''
    if (env === 'development') {
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
      onComplete?.()
      return { abort: () => ac.abort() }
    }

    const contentType = res.headers.get('content-type') || ''
    const isSse = contentType.includes('text/event-stream')

    // Fallback: non-stream JSON response (backward compatible)
    if (!isSse) {
      try {
        const json = await res.json()
        const text = json?.choices?.[0]?.message?.content || json?.text || ''
        if (text) onDelta(text, currentRequestId)
        onDone(currentRequestId)
      } catch (err: any) {
        onError('Invalid response', currentRequestId)
      }
      onComplete?.()
      return { abort: () => ac.abort() }
    }

    reader = res.body?.getReader() || null
    if (!reader) {
      onError('No stream', currentRequestId)
      onComplete?.()
      return { abort: () => ac.abort() }
    }

    // Emit thinking status immediately so UI knows streaming is starting
    onStatus?.('thinking', currentRequestId)

    const dec = new TextDecoder()
    let buffer = ''

    async function pump() {
      const handlePayload = (raw: string) => {
        // Skip empty lines
        if (!raw.trim()) return
        
        try {
          const parsed = JSON.parse(raw)
          const eventType = parsed.type
          const eventRequestId = parsed.request_id || parsed.stream_id || currentRequestId
          
          // Guard: ignore events from different request (prevents stale updates)
          if (eventRequestId !== currentRequestId) {
            console.debug('[stream] Ignoring event from different request:', {
              expected: currentRequestId,
              received: eventRequestId,
              type: eventType,
            })
            return
          }
          
          if (eventType === 'status' || eventType === 'thinking') {
            onStatus?.(parsed.status || parsed.content, currentRequestId)
            return
          }
          
          if (eventType === 'token') {
            onDelta(parsed.content || '', currentRequestId)
            return
          }
          
          if (eventType === 'done' || eventType === 'final') {
            onDone(currentRequestId)
            ac.abort()
            return
          }
          
          if (eventType === 'error') {
            onError(parsed.content || parsed.error || 'Unknown error', currentRequestId)
            ac.abort()
            return
          }
        } catch (err) {
          // Non-JSON line, skip it
          // (could be intermediate newline or malformed chunk)
        }
      }

      try {
        while (true) {
          const { done, value } = await reader!.read()
          if (done) {
            // Reader end reached - flush buffer and mark complete
            const pending = buffer.trim()
            if (pending) {
              handlePayload(pending)
            }
            // Signal completion for cleanup
            onComplete?.()
            break
          }
          buffer += dec.decode(value, { stream: true })
          const lines = buffer.split(/\n/)
          buffer = lines.pop() || ''

          for (const lineRaw of lines) {
            const line = lineRaw.replace(/\r$/, '')
            if (line) handlePayload(line)
          }
        }
      } catch (err: any) {
        if (err?.name === 'AbortError') {
          // User abort - cleanup immediately
          onComplete?.()
          return
        }
        onError('Stream error', currentRequestId)
        // Ensure cleanup even on error
        onComplete?.()
        if (sessionId && onRehydrate) {
          try {
            const { getSessionMessages } = await import('./api')
            const msgs = await getSessionMessages(sessionId)
            onRehydrate(msgs)
          } catch {}
        }
      }
    }

    await pump()
  } catch (err: any) {
    if (err?.name === 'AbortError') {
      // Silent: user-initiated abort - cleanup
      onComplete?.()
    } else {
      onError('Network error', currentRequestId)
      onComplete?.()
      if (sessionId && onRehydrate) {
        try {
          const { getSessionMessages } = await import('./api')
          const msgs = await getSessionMessages(sessionId)
          onRehydrate(msgs)
        } catch {}
      }
    }
  } finally {
    // Always cleanup reader to prevent resource leaks
    try {
      reader?.cancel()
    } catch (err: any) {
      // Ignore AbortError from cancel during cleanup
      if (err?.name !== 'AbortError') {
        console.warn('[stream] Reader cancel error:', err)
      }
    }
  }

  function abort() {
    try { reader?.cancel() } catch {}
    ac.abort()
    // Ensure cleanup on abort
    onComplete?.()
  }

  return { abort }
}
