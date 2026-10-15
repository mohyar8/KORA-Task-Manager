import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { Providers } from '@/app/Providers'
import { routes } from '@/app/router'
import { setApiHandlers } from '@/shared/api/http'
import { account as baseAccount, accessFor, installFakeApi, type FakeApi } from '@/test/fakeApi'
import { isUuid, type AuditRecord } from './api'

const admin = { ...baseAccount, id: 'adm1', username: 'root', is_system_admin: true }
const rec = (n: number, over: Partial<AuditRecord> = {}): AuditRecord => ({
  id: `r${n}`, sequence: n, occurred_at: '2026-10-15T10:00:00Z', action: 'task.created', actor_account_id: 'adm1', resource_type: 'task',
  resource_id: `0000000${n}-0000-0000-0000-000000000000`, scope_unit_id: 'u-team', before: null, after: { title: `Task ${n}` }, ...over,
})

function renderApp(path: string) {
  render(
    <Providers>
      <RouterProvider router={createMemoryRouter(routes, { initialEntries: [path] })} />
    </Providers>,
  )
}

describe('Audit log', () => {
  let api: FakeApi
  beforeEach(() => {
    localStorage.clear()
    setApiHandlers({})
    api = installFakeApi({
      'GET /auth/me': { body: admin },
      'GET /access/me': { body: accessFor() },
      'GET /admin/members': { body: [] },
      'GET /admin/system-admins': { body: [{ account_id: 'adm1', username: 'root', granted_at: '2026-10-10T08:00:00Z', granted_by_account_id: null }] },
      'GET /admin/audit-records': { body: { items: [rec(2), rec(1, { action: 'member.provisioned', resource_type: 'member' })], next_cursor: null } },
    })
  })
  afterEach(() => vi.unstubAllGlobals())

  it('recognises UUIDs', () => {
    expect(isUuid('6b0a0000-0000-4000-8000-000000000001')).toBe(true)
    expect(isUuid('abc')).toBe(false)
  })

  it('is closed to non-admins and open to System Admins', async () => {
    api.on('GET /auth/me', { body: baseAccount })
    renderApp('/admin/audit')
    expect(await screen.findByRole('heading', { name: 'لا تملك صلاحية الوصول' })).toBeInTheDocument()
  })

  it('lists records newest first with the actor resolved and shows the log end', async () => {
    renderApp('/admin/audit')
    const table = await screen.findByRole('region', { name: 'سجل التدقيق' })
    const rows = within(table).getAllByRole('row').slice(1)
    expect(rows).toHaveLength(2)
    expect(within(rows[0]).getByText('task.created')).toBeInTheDocument()
    expect(within(rows[0]).getByText('root')).toBeInTheDocument()
    expect(screen.getByText('هذه نهاية السجل.')).toBeInTheDocument()
  })

  it('opens a record with before/after metadata', async () => {
    renderApp('/admin/audit')
    const table = await screen.findByRole('region', { name: 'سجل التدقيق' })
    await userEvent.click(within(table).getAllByRole('button', { name: 'التفاصيل' })[0])
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByText(/"title": "Task 2"/)).toBeInTheDocument()
    expect(within(dialog).getByText('لا شيء مسجّل')).toBeInTheDocument() // before = null
  })

  it('follows the cursor when loading older records', async () => {
    let call = 0
    api.on('GET /admin/audit-records', () => (++call === 1 ? { body: { items: [rec(3)], next_cursor: 3 } } : { body: { items: [rec(2)], next_cursor: null } }))
    renderApp('/admin/audit')
    await userEvent.click(await screen.findByRole('button', { name: 'تحميل سجلات أقدم' }))
    await waitFor(() => expect(screen.getByText('هذه نهاية السجل.')).toBeInTheDocument())
    expect(api.calls.filter((c) => c.key === 'GET /admin/audit-records')).toHaveLength(2)
  })

  it('flags a malformed id filter instead of sending it', async () => {
    renderApp('/admin/audit?resource=not-a-uuid')
    expect(await screen.findByText('أدخل المعرّف كاملًا (UUID) أو اتركه فارغًا.')).toBeInTheDocument()
    await screen.findByRole('region', { name: 'سجل التدقيق' })
    expect(api.calls.length).toBeGreaterThan(0)
  })
})
