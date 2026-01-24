export type FetchInit = RequestInit

async function apiFetch(path: string, init: FetchInit = {}) {
  const res = await fetch(path, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...(init.headers || {}) },
    ...init,
  })
  if (res.status === 401 || res.status === 403) {
    const err: any = new Error('Unauthorized')
    err.status = res.status
    throw err
  }
  const text = await res.text()
  try { return { status: res.status, data: text ? JSON.parse(text) : null } }
  catch (e) { return { status: res.status, data: text } }
}

export async function getProfile() {
  const r = await apiFetch('/account/profile')
  return r.data
}

export async function listSessions() {
  const r = await apiFetch('/sessions')
  return r.data?.sessions || []
}

export async function createSession(name?: string) {
  const r = await apiFetch('/sessions', { method: 'POST', body: JSON.stringify({ name }) })
  return r.data?.session_id
}

export async function getSessionMessages(sessionId: string) {
  const r = await apiFetch(`/share/${sessionId}`)
  return r.data?.messages || []
}

type SendOpts = { sessionId?: string, prompt: string, stream?: boolean }
export async function sendChatMessage(opts: SendOpts) {
  const { sessionId, prompt, stream } = opts
  const headers: Record<string,string> = {}
  if (sessionId) headers['X-Session-Id'] = sessionId
  const body = { prompt, stream: !!stream }
  const r = await apiFetch('/v1/chat/completions', { method: 'POST', headers, body: JSON.stringify(body) })
  // Non-stream response: parse assistant text
  if (r.data && r.data.choices && r.data.choices[0] && r.data.choices[0].message) {
    return { text: r.data.choices[0].message.content, raw: r.data }
  }
  return { text: '', raw: r.data }
}

// Streaming helper: calls `onChunk` for each text increment received from the server.
// Returns an object with `abort()` to cancel the stream.
export async function sendChatMessageStream(opts: { sessionId?: string; prompt: string }, onChunk: (chunk: string) => void) {
  const { sessionId, prompt } = opts
  const headers: Record<string,string> = { 'Content-Type': 'application/json' }
  if (sessionId) headers['X-Session-Id'] = sessionId
  const ac = new AbortController()
  const res = await fetch('/v1/chat/completions', {
    method: 'POST',
    headers,
    body: JSON.stringify({ prompt, stream: true }),
    credentials: 'include',
    signal: ac.signal,
  })
  if (!res.ok) {
    const err: any = new Error('Network error')
    err.status = res.status
    throw err
  }

  const ct = res.headers.get('content-type') || ''
  const reader = res.body?.getReader()
  if (!reader) return { abort: () => ac.abort() }
  const dec = new TextDecoder()
  let buf = ''

  async function pump() {
    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += dec.decode(value, { stream: true })
        // Try to split by SSE style `data: ...\n\n` or by newline-delimited JSON/text
        let parts = buf.split(/\n\n|\n/)
        // Keep last partial chunk in buffer
        if (!buf.endsWith('\n') && !buf.endsWith('\n\n')) {
          buf = parts.pop() || ''
        } else {
          buf = ''
        }
        for (const part of parts) {
          const line = part.trim()
          if (!line) continue
          const data = line.startsWith('data:') ? line.replace(/^data:\s*/, '') : line
          // Try JSON parse, otherwise treat as plain text
          try {
            const parsed = JSON.parse(data)
            // If OpenAI-style delta chunks
            if (parsed.choices && parsed.choices[0] && parsed.choices[0].delta) {
              const delta = parsed.choices[0].delta
              const txt = (delta?.content || '')
              if (txt) onChunk(txt)
            } else if (parsed.text) {
              onChunk(parsed.text)
            } else {
              // fallback: stringify
              onChunk(JSON.stringify(parsed))
            }
          } catch (e) {
            // plain text chunk
            onChunk(data)
          }
        }
      }
    } catch (err) {
      // propagate aborts silently
      if ((err as any)?.name !== 'AbortError') throw err
    }
  }

  // Start pumping in background
  pump().catch(() => {})

  return {
    abort: () => ac.abort(),
  }
}

export default apiFetch
