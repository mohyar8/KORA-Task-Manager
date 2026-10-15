import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError, fieldErrors, http, setApiHandlers } from './http'

function mockFetch(status: number, body?: unknown, headers: Record<string, string> = {}) {
  const fn = vi.fn(
    async (_url: string, _init?: RequestInit) =>
      new Response(body === undefined ? null : JSON.stringify(body), { status, headers }),
  )
  vi.stubGlobal('fetch', fn)
  return fn
}

describe('http', () => {
  beforeEach(() => {
    document.cookie = 'kora_csrf=tok123'
    setApiHandlers({})
  })
  afterEach(() => {
    document.cookie = 'kora_csrf=; max-age=0'
    vi.unstubAllGlobals()
  })

  it('does not send a CSRF header on GET, and builds the query string', async () => {
    const fn = mockFetch(200, [])
    await http.get('/tasks', { status: 'new', scope_unit_id: undefined })
    const [url, init] = fn.mock.calls[0]
    expect(url).toBe('/api/v1/tasks?status=new')
    expect((init?.headers as Record<string, string>)['X-CSRF-Token']).toBeUndefined()
    expect(init?.credentials).toBe('same-origin')
  })

  it('sends X-CSRF-Token and JSON on unsafe methods', async () => {
    const fn = mockFetch(200, { ok: 1 })
    await http.post('/tasks', { title: 'x' })
    const init = fn.mock.calls[0][1]
    const h = init?.headers as Record<string, string>
    expect(h['X-CSRF-Token']).toBe('tok123')
    expect(h['Content-Type']).toBe('application/json')
    expect(init?.body).toBe('{"title":"x"}')
  })

  it('returns undefined for 204', async () => {
    mockFetch(204)
    await expect(http.post('/auth/sign-out')).resolves.toBeUndefined()
  })

  it('normalizes string and list details and Retry-After', async () => {
    mockFetch(429, { detail: 'Too many failed sign-in attempts. Try again later.' }, { 'Retry-After': '900' })
    const err = (await http.post('/auth/sign-in', {}, { expectUnauthorized: true }).catch((e) => e)) as ApiError
    expect(err.status).toBe(429)
    expect(err.retryAfter).toBe(900)
    expect(err.message).toContain('Too many')

    mockFetch(422, { detail: [{ type: 'missing', loc: ['body', 'title'], msg: 'Field required' }] })
    const v = (await http.post('/tasks', {}).catch((e) => e)) as ApiError
    expect(fieldErrors(v)).toEqual({ title: 'Field required' })
    expect(v.message).toBe('title: Field required')
  })

  it('calls onUnauthorized for 401 except during sign-in', async () => {
    const onUnauthorized = vi.fn()
    setApiHandlers({ onUnauthorized })
    mockFetch(401, { detail: 'Not authenticated.' })
    await http.get('/auth/me').catch(() => {})
    expect(onUnauthorized).toHaveBeenCalledTimes(1)
    await http.post('/auth/sign-in', {}, { expectUnauthorized: true }).catch(() => {})
    expect(onUnauthorized).toHaveBeenCalledTimes(1)
  })

  it('calls onPasswordChangeRequired for the temporary-password gate', async () => {
    const onPasswordChangeRequired = vi.fn()
    setApiHandlers({ onPasswordChangeRequired })
    mockFetch(403, { detail: 'Password change required.' })
    await http.get('/tasks').catch(() => {})
    expect(onPasswordChangeRequired).toHaveBeenCalled()
  })

  it('maps network failure to status 0', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        throw new TypeError('fail')
      }),
    )
    const err = (await http.get('/health').catch((e) => e)) as ApiError
    expect(err.status).toBe(0)
  })
})
