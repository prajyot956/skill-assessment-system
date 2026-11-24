import type { AppNotification, Dashboard, Profile, User } from '../types'

export class ApiError extends Error {
  code: string
  status: number
  fields: Record<string, string>
  constructor(code: string, message: string, status: number, fields: Record<string, string> = {}) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
    this.fields = fields
  }
}

interface Envelope<T> {
  success: boolean
  data?: T
  meta?: Record<string, number>
  error?: { code: string; message: string; details?: { fields?: Record<string, string> } }
}

let csrfToken: string | null = null
let onUnauthorized: (() => void) | null = null
export const setUnauthorizedHandler = (fn: (() => void) | null) => { onUnauthorized = fn }
export const resetCsrf = () => { csrfToken = null }

async function getCsrf(): Promise<string> {
  if (!csrfToken) {
    const res = await fetch('/api/auth/csrf', { credentials: 'same-origin' })
    const body = (await res.json()) as Envelope<{ csrf_token: string }>
    csrfToken = body.data?.csrf_token ?? ''
  }
  return csrfToken
}

export async function request<T>(method: string, path: string, body?: unknown, retried = false): Promise<{ data: T; meta?: Record<string, number> }> {
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (method !== 'GET') headers['X-CSRFToken'] = await getCsrf()

  let res: Response
  try {
    res = await fetch(path, {
      method, headers, credentials: 'same-origin',
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new ApiError('network', 'Cannot reach the server. Check your connection and try again.', 0)
  }

  let payload: Envelope<T> | null = null
  try { payload = (await res.json()) as Envelope<T> } catch { /* non-JSON response */ }

  if (res.ok && payload?.success) return { data: payload.data as T, meta: payload.meta }

  const err = payload?.error
  if (err?.code === 'csrf_failed' && !retried) {
    resetCsrf()
    return request<T>(method, path, body, true)
  }
  if (res.status === 401 && err?.code === 'unauthorized') onUnauthorized?.()
  throw new ApiError(err?.code ?? 'server_error', err?.message ?? 'Something went wrong. Please try again.',
    res.status, err?.details?.fields ?? {})
}

const get = <T,>(p: string) => request<T>('GET', p)
const send = <T,>(m: string, p: string, b?: unknown) => request<T>(m, p, b ?? {})

export const api = {
  auth: {
    me: () => get<User>('/api/auth/me').then((r) => r.data),
    login: (b: { email: string; password: string; remember: boolean }) => send<User>('POST', '/api/auth/login', b).then((r) => r.data),
    register: (b: { full_name: string; email: string; password: string; confirm_password: string }) =>
      send<User>('POST', '/api/auth/register', b).then((r) => r.data),
    logout: () => send<unknown>('POST', '/api/auth/logout').then((r) => r.data),
    forgot: (email: string) => send<{ message: string }>('POST', '/api/auth/forgot-password', { email }).then((r) => r.data),
    reset: (b: { token: string; password: string; confirm_password: string }) =>
      send<{ message: string }>('POST', '/api/auth/reset-password', b).then((r) => r.data),
    changePassword: (b: { current_password: string; new_password: string; confirm_password: string }) =>
      send<{ message: string }>('POST', '/api/auth/change-password', b).then((r) => r.data),
  },
  profile: {
    get: () => get<Profile>('/api/profile').then((r) => r.data),
    update: (b: Partial<Omit<Profile, 'completion' | 'education' | 'experience' | 'projects' | 'certifications' | 'email'>>) =>
      send<Profile>('PUT', '/api/profile', b).then((r) => r.data),
  },
  dashboard: { get: () => get<Dashboard>('/api/dashboard').then((r) => r.data) },
  notifications: {
    list: () => get<AppNotification[]>('/api/notifications').then((r) => ({ items: r.data, unread: r.meta?.unread ?? 0 })),
    read: (id: number) => send<AppNotification>('POST', `/api/notifications/${id}/read`).then((r) => r.data),
    readAll: () => send<unknown>('POST', '/api/notifications/read-all').then((r) => r.data),
  },
}

export const http = {
  get: <T,>(p: string) => request<T>('GET', p),
  post: <T,>(p: string, b?: unknown) => request<T>('POST', p, b ?? {}),
  put: <T,>(p: string, b?: unknown) => request<T>('PUT', p, b ?? {}),
  patch: <T,>(p: string, b?: unknown) => request<T>('PATCH', p, b ?? {}),
  del: <T,>(p: string) => request<T>('DELETE', p, {}),
}

/** Multipart upload with real progress events (fetch cannot report upload progress). */
export async function uploadResume(file: File, onProgress: (pct: number) => void): Promise<import('../types').ResumeInfo> {
  const token = await getCsrf()
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', '/api/resumes')
    xhr.setRequestHeader('X-CSRFToken', token)
    xhr.setRequestHeader('Accept', 'application/json')
    xhr.upload.onprogress = (e) => { if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100)) }
    xhr.onerror = () => reject(new ApiError('network', 'Cannot reach the server. Check your connection and try again.', 0))
    xhr.onload = () => {
      let payload: Envelope<import('../types').ResumeInfo> | null = null
      try { payload = JSON.parse(xhr.responseText) as Envelope<import('../types').ResumeInfo> } catch { /* ignore */ }
      if (xhr.status >= 200 && xhr.status < 300 && payload?.success) return resolve(payload.data as import('../types').ResumeInfo)
      if (xhr.status === 401) onUnauthorized?.()
      reject(new ApiError(payload?.error?.code ?? 'server_error', payload?.error?.message ?? 'Upload failed. Please try again.', xhr.status))
    }
    const fd = new FormData()
    fd.append('file', file)
    xhr.send(fd)
  })
}
