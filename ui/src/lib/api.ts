export type FetchInit = RequestInit

export class UnauthorizedError extends Error {
  status: number
  body: any
  constructor(message = 'Unauthorized', status = 401, body: any = null) {
    super(message)
    this.status = status
    this.body = body
  }
}

function getAuthHeaders(): Record<string, string> {
  const headers: Record<string, string> = {}
  // Prefer persisted token from localStorage (cookie may be httpOnly and unreadable)
  try {
    const ls = typeof window !== 'undefined' ? window.localStorage.getItem('jarvis_token') : null
    if (ls) headers['Authorization'] = `Bearer ${ls}`
  } catch {}
  // Fallback devkey for development if no user token
  if (!headers['Authorization']) headers['Authorization'] = 'Bearer devkey'
  // Optionally include X-User-Token from cookie if accessible (non-httpOnly)
  try {
    const m = typeof document !== 'undefined' ? document.cookie.match(/jarvis_token=([^;]*)/) : null
    const cookie = m && m[1] ? decodeURIComponent(m[1]) : null
    if (cookie) headers['X-User-Token'] = cookie
  } catch {}
  return headers
}

async function apiFetch(path: string, init: FetchInit = {}) {
  const authHeaders = getAuthHeaders()
  const res = await fetch(path, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...authHeaders, ...(init.headers || {}) },
    ...init,
  })
  const contentType = res.headers.get('content-type') || ''
  const isJson = contentType.includes('application/json')

  let data: any = null
  if (isJson) {
    try {
      data = await res.json()
    } catch (err) {
      console.warn('[api] failed to parse JSON', { status: res.status, path, contentType, err })
      data = null
    }
  } else {
    const text = await res.text()
    data = text
    // Log once for non-JSON for debugging
    console.warn('[api] non-JSON response', { status: res.status, path, contentType, sample: text?.slice(0, 200) })
  }

  if (res.status === 401 || res.status === 403) {
    try {
      window.localStorage.removeItem('jarvis_token')
    } catch {}
    try {
      window.sessionStorage.removeItem('jarvis_auth_redirected')
    } catch {}
    try {
      document.cookie = 'jarvis_token=;path=/;expires=Thu, 01 Jan 1970 00:00:00 GMT'
    } catch {}
    // Avoid redirect loops: only redirect once per session
    try {
      const key = 'jarvis_auth_redirected'
      const already = typeof sessionStorage !== 'undefined' ? sessionStorage.getItem(key) : null
      if (!already) {
        sessionStorage.setItem(key, '1')
        window.location.href = '/login'
      }
    } catch {}
    throw new UnauthorizedError('Unauthorized', res.status, data)
  }
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
// Deprecated: use streamChat in src/lib/stream.ts for streaming

export default apiFetch
