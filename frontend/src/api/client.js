const BASE_URL = import.meta.env.VITE_API_BASE_URL || ''
const TOKEN_KEY = 'tf_token'
const ANON_ID_KEY = 'tf_anon_id'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY)
}

export function isLoggedIn() {
  return Boolean(getToken())
}

// Guest identity (Phase 8) -- generated once, persisted, sent only when
// there's no real token. Signing up doesn't need to clear this; the
// backend simply stops checking it once a real Authorization header shows
// up (verify_identity prefers the JWT unconditionally).
export function getAnonId() {
  let id = localStorage.getItem(ANON_ID_KEY)
  if (!id) {
    id = crypto.randomUUID()
    localStorage.setItem(ANON_ID_KEY, id)
  }
  return id
}

async function request(path, options = {}) {
  const token = getToken()
  const headers = { 'Content-Type': 'application/json', ...options.headers }
  if (token) {
    headers.Authorization = `Bearer ${token}`
  } else {
    headers['X-Anon-Id'] = getAnonId()
  }

  const res = await fetch(`${BASE_URL}${path}`, { ...options, headers })

  if (res.status === 403) {
    const body = await res.json().catch(() => ({}))
    if (body.detail === 'signup_required') {
      const error = new Error('signup_required')
      error.status = 403
      error.code = 'signup_required'
      throw error
    }
  }

  if (res.status === 401) {
    clearToken()
    const error = new Error('Not logged in')
    error.status = 401
    throw error
  }

  if (res.status === 429) {
    const body = await res.json().catch(() => ({}))
    const error = new Error('Rate limit exceeded')
    error.status = 429
    error.retryAfterSeconds = body.retry_after_seconds ?? 60
    throw error
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    const error = new Error(body.detail || `Request failed (${res.status})`)
    error.status = res.status
    throw error
  }

  if (res.status === 204) return null
  return res.json()
}

export async function signup(email, password) {
  const data = await request('/auth/signup', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  })
  setToken(data.token)
  return data
}

export async function login(email, password) {
  const data = await request('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  })
  setToken(data.token)
  return data
}

export function logout() {
  clearToken()
}

export function getMe() {
  return request('/auth/me')
}

export function listSessions() {
  return request('/sessions')
}

export function getSession(sessionId) {
  return request(`/session/${sessionId}`)
}

export function deleteSession(sessionId) {
  return request(`/session/${sessionId}`, { method: 'DELETE' })
}

export function sendChat({ message, sessionId, platform, posts = 5, verbose = false }) {
  return request('/chat', {
    method: 'POST',
    body: JSON.stringify({ message, session_id: sessionId, platform, posts, verbose }),
  })
}

export function getJobStatus(jobId) {
  return request(`/chat/status/${jobId}`)
}

export async function pollJobUntilDone(jobId, { intervalMs = 2000, timeoutMs = 120000 } = {}) {
  const start = Date.now()
  while (true) {
    const status = await getJobStatus(jobId)
    if (status.status === 'done' || status.status === 'error') return status
    if (Date.now() - start > timeoutMs) {
      const error = new Error('Job polling timed out')
      error.status = 'timeout'
      throw error
    }
    await new Promise((r) => setTimeout(r, intervalMs))
  }
}

// Sends a message and resolves once the reply is actually ready --
// inline actions resolve immediately, slow actions are polled underneath.
export async function sendChatAndWait(params, pollOptions) {
  const initial = await sendChat(params)
  if (initial.status === 'done') return initial
  const final = await pollJobUntilDone(initial.job_id, pollOptions)
  return { ...initial, ...final }
}