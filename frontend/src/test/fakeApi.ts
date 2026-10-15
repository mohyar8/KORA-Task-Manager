import { vi } from 'vitest'

export interface FakeReply {
  status?: number
  body?: unknown
  headers?: Record<string, string>
}
type Handler = FakeReply | ((body: unknown) => FakeReply)

export interface FakeApi {
  /** Replace/add a handler. Keys look like "POST /auth/sign-in" (path without /api/v1 and without query). */
  on: (key: string, handler: Handler) => void
  calls: { key: string; body: unknown; headers: Record<string, string> }[]
}

/** Stubs global fetch with a route table; unknown routes answer 404 so missing mocks fail loudly. */
export function installFakeApi(initial: Record<string, Handler> = {}): FakeApi {
  const table = new Map<string, Handler>(Object.entries(initial))
  const calls: FakeApi['calls'] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      const path = url.replace(/^\/api\/v1/, '').split('?')[0]
      const key = `${init?.method ?? 'GET'} ${path}`
      const body = init?.body ? JSON.parse(init.body as string) : undefined
      calls.push({ key, body, headers: (init?.headers ?? {}) as Record<string, string> })
      const handler = table.get(key)
      if (!handler) return new Response(JSON.stringify({ detail: `No fake for ${key}` }), { status: 404 })
      const reply = typeof handler === 'function' ? handler(body) : handler
      const status = reply.status ?? 200
      return new Response(status === 204 || reply.body === undefined ? null : JSON.stringify(reply.body), {
        status,
        headers: reply.headers,
      })
    }),
  )
  return { on: (k, h) => void table.set(k, h), calls }
}

export const account = { id: 'a1', username: 'sara', must_change_password: false, is_system_admin: false, member_id: null as string | null }

/** An access response where `allowed` lists "permission@unitId" pairs; units are KORA + one Team. */
export function accessFor(allowed: string[] = []) {
  const units = [
    { unit_id: 'u-kora', name: 'KORA', kind: 'organization' },
    { unit_id: 'u-team', name: 'Team A', kind: 'team' },
  ]
  const perms = [
    'organization.manage', 'task.view', 'task.create', 'task.manage',
    'announcement.publish', 'announcement.manage', 'calendar.create', 'calendar.manage',
  ]
  return {
    account_id: 'a1',
    at: '2026-10-15T10:00:00Z',
    permissions: perms.map((permission) => ({
      permission,
      units: units.map((u) => ({
        ...u,
        allowed: allowed.includes(`${permission}@${u.unit_id}`),
        source: 'none',
        decided_at_unit_id: null,
      })),
    })),
  }
}
