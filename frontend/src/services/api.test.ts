import { afterEach, beforeEach, vi } from 'vitest'
import { api, ApiError, resetCsrf } from './api'

const json = (body: unknown, status = 200) => Promise.resolve(new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }))

describe('api client', () => {
  beforeEach(() => resetCsrf())
  afterEach(() => vi.restoreAllMocks())

  it('sends the CSRF token on writes and not on reads', async () => {
    const spy = vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      if (String(url).endsWith('/csrf')) return json({ success: true, data: { csrf_token: 'tok123' } })
      return json({ success: true, data: { ok: 1 } })
    })
    await api.auth.logout()
    const write = spy.mock.calls.find(([u]) => String(u).endsWith('/logout'))!
    expect((write[1]!.headers as Record<string, string>)['X-CSRFToken']).toBe('tok123')
    await api.auth.me()
    const read = spy.mock.calls.find(([u]) => String(u).endsWith('/me'))!
    expect((read[1]!.headers as Record<string, string>)['X-CSRFToken']).toBeUndefined()
  })

  it('refreshes the token once when the server rejects it', async () => {
    let n = 0
    vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      if (String(url).endsWith('/csrf')) return json({ success: true, data: { csrf_token: `t${++n}` } })
      return n < 2
        ? json({ success: false, error: { code: 'csrf_failed', message: 'bad' } }, 400)
        : json({ success: true, data: { message: 'done' } })
    })
    await expect(api.auth.forgot('a@b.com')).resolves.toEqual({ message: 'done' })
  })

  it('exposes field errors from validation failures', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((url) =>
      String(url).endsWith('/csrf') ? json({ success: true, data: { csrf_token: 't' } })
        : json({ success: false, error: { code: 'validation_error', message: 'Fix', details: { fields: { email: 'Taken' } } } }, 422))
    const err = await api.auth.register({ full_name: 'A', email: 'a@b.com', password: 'x', confirm_password: 'x' }).catch((e) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect(err.fields).toEqual({ email: 'Taken' })
  })

  it('reports an unreachable server in plain language', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('failed'))
    await expect(api.auth.me()).rejects.toMatchObject({ code: 'network' })
  })
})
