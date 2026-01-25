export type FetchInit = RequestInit

async function apiFetch(path: string, init: FetchInit = {}) {
  const res = await fetch(path, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...(init.headers || {}) },
    ...init,
  })

  const text = await res.text()
  let data: any = text
  try { data = text ? JSON.parse(text) : null } catch (_) { /* keep text */ }

  if (!res.ok) {
    const err: any = new Error(`HTTP ${res.status}`)
    err.status = res.status
    err.body = data
    throw err
  }

  return { status: res.status, data }
}

export async function getProfile() {
  const r = await apiFetch('/account/profile')
  return r.data
}

export async function loginUser(username: string, password: string) {
  const r = await apiFetch('/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) })
  return r.data
}

export async function logoutUser() {
  // try multiple common logout endpoints
  try { await apiFetch('/auth/logout', { method: 'POST' }) } catch (_) {}
  try { await apiFetch('/logout', { method: 'POST' }) } catch (_) {}
  return true
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
  // Backend accepts either prompt or OpenAI-style messages. Send both for safety.
  const body = {
    prompt,
    messages: [{ role: 'user', content: prompt }],
    stream: !!stream,
  }
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
    body: JSON.stringify({
      prompt,
      messages: [{ role: 'user', content: prompt }],
      stream: true
    }),
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
        // Split into SSE-style records: "data: ...\n\n" or newline-delimited JSON/text
        const parts = buf.split(/\n\n/)
        buf = parts.pop() || ''

        for (const part of parts) {
          // part may contain multiple lines (event:, data:, etc.) – focus on data lines
          const lines = part.split(/\n/).map(l => l.trim()).filter(Boolean)
          for (const line of lines) {
            if (!line.startsWith('data:')) continue
            const payload = line.replace(/^data:\s*/, '')
            if (payload === '[DONE]') {
              ac.abort()
              return
            }
            try {
              const parsed = JSON.parse(payload)
              // OpenAI-ish delta
              if (parsed.choices && parsed.choices[0]) {
                const delta = parsed.choices[0].delta || parsed.choices[0]
                const txt = delta?.content || parsed.text || ''
                if (txt) onChunk(txt)
              } else if (parsed.text) {
                onChunk(parsed.text)
              } else {
                onChunk(JSON.stringify(parsed))
              }
            } catch (_) {
              onChunk(payload)
            }
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
