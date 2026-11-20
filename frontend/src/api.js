// Thin fetch wrapper around the SkyShield API.
const TOKEN_KEY = 'skyshield_token'
// Empty in development (Vite forwards /api). In production, the backend's address, e.g. https://skyshield-api.onrender.com
const API_BASE = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')

export const tokenStore = {
  get: () => {
    try { return localStorage.getItem(TOKEN_KEY) } catch { return null }
  },
  set: (t) => {
    try { localStorage.setItem(TOKEN_KEY, t) } catch { /* storage unavailable */ }
  },
  clear: () => {
    try { localStorage.removeItem(TOKEN_KEY) } catch { /* storage unavailable */ }
  },
}

let onUnauthorized = () => {}
export const setUnauthorizedHandler = (fn) => { onUnauthorized = fn }

export class ApiError extends Error {
  constructor(status, message, fields = {}) {
    super(message)
    this.status = status
    this.fields = fields // field name -> message, for 422 validation errors
  }
}

function parseError(status, body) {
  const detail = body?.detail
  if (Array.isArray(detail)) {
    const fields = {}
    for (const d of detail) {
      const field = d.loc?.[d.loc.length - 1]
      const msg = (d.msg || 'Invalid value').replace(/^Value error, /, '')
      if (field && field !== 'body') fields[field] = msg
    }
    const first = Object.values(fields)[0] || detail[0]?.msg || 'Please check the form.'
    return new ApiError(status, first, fields)
  }
  return new ApiError(status, typeof detail === 'string' ? detail : `Request failed (${status})`)
}

export async function api(path, { method = 'GET', body, query } = {}) {
  let url = `${API_BASE}/api${path}`
  if (query) {
    const params = new URLSearchParams()
    Object.entries(query).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') params.set(k, v)
    })
    const qs = params.toString()
    if (qs) url += `?${qs}`
  }
  const headers = { Accept: 'application/json' }
  const token = tokenStore.get()
  if (token) headers.Authorization = `Bearer ${token}`
  if (body !== undefined) headers['Content-Type'] = 'application/json'

  let res
  try {
    res = await fetch(url, { method, headers, body: body !== undefined ? JSON.stringify(body) : undefined })
  } catch {
    throw new ApiError(0, API_BASE
      ? 'Cannot reach the server. If it was idle it may be waking up; try again in a minute.'
      : 'Cannot reach the server. Is the API running?')
  }
  const text = await res.text()
  const data = text ? JSON.parse(text) : null
  if (res.status === 401 && path !== '/auth/login') {
    onUnauthorized()
  }
  if (!res.ok) throw parseError(res.status, data)
  return data
}
