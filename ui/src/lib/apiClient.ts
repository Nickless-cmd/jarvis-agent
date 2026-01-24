class ApiError extends Error {
  status: number
  body: any
  constructor(message: string, status = 0, body: any = null) {
    super(message)
    this.status = status
    this.body = body
  }
}

class AuthError extends ApiError {}

function readCookie(name: string) {
  if (typeof document === 'undefined') return null
  const m = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'))
  return m ? decodeURIComponent(m[2]) : null
}

function defaultHeaders(hasBody = false) {
  const headers: Record<string,string> = {}
  // Always send devkey as requested
  headers['Authorization'] = 'Bearer devkey'
  if (hasBody) headers['Content-Type'] = 'application/json'
  const jarvis = readCookie('jarvis_token')
  if (jarvis) headers['X-User-Token'] = jarvis
  return headers
}

async function apiFetch(path: string, init: RequestInit = {}) {
  const hasBody = !!(init.body)
  const headers = { ...(init.headers || {}), ...defaultHeaders(hasBody) }
  const res = await fetch(path, { credentials: 'include', ...init, headers })
  if (res.status === 401 || res.status === 403) {
    // Centralized handling: redirect to login and throw typed error
    try {
      window.location.href = '/login'
    } catch {}
    throw new AuthError('Unauthorized', res.status, null)
  }
  const text = await res.text()
  let data = null
  try { data = text ? JSON.parse(text) : null } catch (e) { data = text }
  if (!res.ok) throw new ApiError('API error', res.status, data)
  return { status: res.status, data }
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
  return r.data?.session_id || r.data?.sessionId || null
}

export async function getSessionMessages(sessionId: string) {
  const r = await apiFetch(`/share/${sessionId}`)
  return r.data?.messages || []
}

export async function sendChatMessage(opts: { sessionId?: string; prompt: string }) {
  const { sessionId, prompt } = opts
  const headers: Record<string,string> = {}
  if (sessionId) headers['X-Session-Id'] = sessionId
  const r = await apiFetch('/v1/chat/completions', { method: 'POST', headers, body: JSON.stringify({ prompt, stream: false }) })
  // Parse non-stream response
  if (r.data && r.data.choices && r.data.choices[0]) {
    const m = r.data.choices[0].message || r.data.choices[0]
    return { text: m?.content || r.data.text || '' , raw: r.data }
  }
  return { text: '', raw: r.data }
}

export async function sendChatMessageStream(opts: { sessionId?: string; prompt: string }, onChunk: (s: string) => void) {
  const { sessionId, prompt } = opts
  const headers: Record<string,string> = { 'Content-Type': 'application/json' }
  if (sessionId) headers['X-Session-Id'] = sessionId
  // include auth headers via apiFetch approach but use fetch directly for streaming
  const jarvis = readCookie('jarvis_token')
  const authHeaders = { ...defaultHeaders(true), ...headers }
  const ac = new AbortController()
  const res = await fetch('/v1/chat/completions', {
    method: 'POST',
    headers: authHeaders,
    body: JSON.stringify({ prompt, stream: true }),
    credentials: 'include',
    signal: ac.signal,
  })
  if (res.status === 401 || res.status === 403) {
    try { window.location.href = '/login' } catch {}
    throw new AuthError('Unauthorized', res.status, null)
  }
  if (!res.ok) throw new ApiError('Network error', res.status, null)

  const reader = res.body?.getReader()
  if (!reader) return { abort: () => ac.abort() }
  const dec = new TextDecoder()
  let buffer = ''
  let closed = false

  async function pump() {
    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += dec.decode(value, { stream: true })
        // split into lines
        const parts = buffer.split(/\n/) // handle newline-separated or SSE lines
        // keep last partial
        buffer = parts.pop() || ''
        for (const raw of parts) {
          const line = raw.trim()
          if (!line) continue
          const data = line.startsWith('data:') ? line.replace(/^data:\s*/, '') : line
          if (data === '[DONE]') {
            closed = true
            return
          }
          // try parse json
          try {
            const parsed = JSON.parse(data)
            // openai-ish delta
            if (parsed.choices && parsed.choices[0]) {
              const delta = parsed.choices[0].delta || parsed.choices[0]
              const txt = delta?.content || parsed.text || ''
              if (txt) onChunk(txt)
            } else if (parsed.text) {
              onChunk(parsed.text)
            } else {
              onChunk(JSON.stringify(parsed))
            }
          } catch (e) {
            // plain text
            onChunk(data)
          }
        }
      }
    } catch (err) {
      if ((err as any)?.name !== 'AbortError') throw err
    }
  }

  pump().catch(() => {})

  return {
    abort: () => ac.abort(),
    closed: () => closed,
  }
}

export async function logout() {
  // try backend endpoints, ignore failures
  try {
    await fetch('/auth/logout', { method: 'POST', credentials: 'include' })
  } catch {}
  try {
    await fetch('/logout', { method: 'POST', credentials: 'include' })
  } catch {}
  // remove jarvis_token cookie client-side
  try {
    document.cookie = 'jarvis_token=;path=/;expires=Thu, 01 Jan 1970 00:00:00 GMT'
  } catch {}
  try { window.location.href = '/login' } catch {}
}

export default {
  apiFetch,
  getProfile,
  listSessions,
  createSession,
  getSessionMessages,
  sendChatMessage,
  sendChatMessageStream,
  logout,
}
