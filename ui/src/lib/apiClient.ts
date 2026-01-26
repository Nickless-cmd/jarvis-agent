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
  const contentType = res.headers.get('content-type') || ''
  const isJson = contentType.includes('application/json')

  if (res.status === 401 || res.status === 403) {
    try { window.localStorage.removeItem('jarvis_token') } catch {}
    try { document.cookie = 'jarvis_token=;path=/;expires=Thu, 01 Jan 1970 00:00:00 GMT' } catch {}
    try { window.sessionStorage.removeItem('jarvis_auth_redirected') } catch {}
    try { window.location.href = '/login' } catch {}
    throw new AuthError('Unauthorized', res.status, null)
  }

  let data: any = null
  if (isJson) {
    try {
      data = await res.json()
    } catch (e) {
      console.warn('[apiClient] failed to parse JSON', { status: res.status, path, contentType, err: e })
      data = null
    }
  } else {
    const text = await res.text()
    data = text
    console.warn('[apiClient] non-JSON response', { status: res.status, path, contentType, sample: text?.slice(0, 200) })
  }

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

// Deprecated: streaming has moved to src/lib/stream.ts
// Keeping a thin wrapper for compatibility; consider removing once callers migrate.
export async function sendChatMessageStream(opts: { sessionId?: string; prompt: string }, onChunk: (s: string) => void) {
  const { streamChat } = await import('./stream')
  const controller = new AbortController()
  const handle = await streamChat(
    { sessionId: opts.sessionId, prompt: opts.prompt, signal: controller.signal },
    (delta) => onChunk(delta),
    () => {},
    () => {}
  )
  return { abort: () => handle.abort(), closed: () => false }
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
  try { window.location.href = '/ui/login' } catch {}
}

export default {
  apiFetch,
  getProfile,
  listSessions,
  createSession,
  getSessionMessages,
  sendChatMessage,
  logout,
}
