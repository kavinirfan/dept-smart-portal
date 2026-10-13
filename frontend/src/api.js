const TOKEN_KEY = 'portal_token'

export const getToken = () => localStorage.getItem(TOKEN_KEY)
export const setToken = (t) => (t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY))

export class ApiError extends Error {
  constructor(status, message) {
    super(message)
    this.status = status
  }
}

// Small fetch wrapper: adds the JWT, parses JSON, turns FastAPI errors into readable messages.
export async function api(path, { method = 'GET', body, form } = {}) {
  const headers = {}
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  let payload
  if (form) {
    payload = new URLSearchParams(form)
  } else if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
    payload = JSON.stringify(body)
  }
  const res = await fetch(`/api${path}`, { method, headers, body: payload })
  if (res.status === 401 && token) {
    setToken(null)
    window.location.href = '/login'
  }
  if (!res.ok) {
    let msg = res.statusText
    try {
      const data = await res.json()
      msg = Array.isArray(data.detail) ? data.detail.map((d) => d.msg).join('; ') : data.detail || msg
    } catch {
      /* non-JSON error */
    }
    throw new ApiError(res.status, msg)
  }
  return res.status === 204 ? null : res.json()
}

// Download a file from an authenticated endpoint (e.g. Excel exports).
export async function download(path, fallbackName) {
  const res = await fetch(`/api${path}`, { headers: { Authorization: `Bearer ${getToken()}` } })
  if (!res.ok) throw new ApiError(res.status, 'Download failed')
  const name = res.headers.get('Content-Disposition')?.match(/filename="(.+)"/)?.[1] ?? fallbackName
  const url = URL.createObjectURL(await res.blob())
  const a = Object.assign(document.createElement('a'), { href: url, download: name })
  a.click()
  URL.revokeObjectURL(url)
}

// Format helpers shared by pages.
export const fmtTime = (iso) => new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
export const fmtDate = (iso) => new Date(iso).toLocaleDateString([], { day: 'numeric', month: 'short', year: 'numeric' })
export const ago = (iso) => {
  const mins = Math.round((Date.now() - new Date(iso)) / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins} min ago`
  if (mins < 1440) return `${Math.round(mins / 60)} h ago`
  return fmtDate(iso)
}
export const todayISO = () => {
  const d = new Date()
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10)
}

// Fetch an authenticated image (e.g. an ID card) and return an object URL for <img src>.
export async function blobUrl(path) {
  const res = await fetch(`/api${path}`, { headers: { Authorization: `Bearer ${getToken()}` } })
  if (!res.ok) throw new ApiError(res.status, 'Could not load image')
  return URL.createObjectURL(await res.blob())
}

// Multipart upload (FormData) with the JWT.
export async function upload(path, formData) {
  const res = await fetch(`/api${path}`, { method: 'POST', headers: { Authorization: `Bearer ${getToken()}` }, body: formData })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const msg = Array.isArray(data.detail) ? data.detail.map((d) => d.msg).join('; ') : data.detail || res.statusText
    throw new ApiError(res.status, msg)
  }
  return data
}
