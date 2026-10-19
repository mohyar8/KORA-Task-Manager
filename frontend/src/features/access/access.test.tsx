import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { Providers } from '@/app/Providers'
import { routes } from '@/app/router'
import { setApiHandlers } from '@/shared/api/http'
import { account, accessFor, installFakeApi, type FakeApi } from '@/test/fakeApi'
import { KORA_UNIT_ID } from './types'

const admin = { ...account, id: 'adm1', username: 'root', is_system_admin: true }
// The KORA unit in the fake access response carries the fixed KORA id, as the real backend does.
const adminAccess = JSON.parse(JSON.stringify(accessFor()).replaceAll('u-kora', KORA_UNIT_ID))

const systemAdmins = [{ account_id: 'adm1', username: 'root', granted_at: '2026-10-10T08:00:00Z', granted_by_account_id: null }]
const roleDefault = {
  id: 'rd1', role_key: 'team_leader', permission: 'task.manage',
  valid_from: '2026-10-01T00:00:00Z', valid_to: null, created_by_account_id: null, ended_by_account_id: null,
}

function renderApp(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] })
  render(
    <Providers>
      <RouterProvider router={router} />
    </Providers>,
  )
  return router
}

describe('System Admin: access control', () => {
  let api: FakeApi
  beforeEach(() => {
    localStorage.clear()
    setApiHandlers({})
    api = installFakeApi({
      'GET /auth/me': { body: admin },
      'GET /access/me': { body: adminAccess },
      'GET /admin/members': { body: [] },
      'GET /admin/system-admins': { body: systemAdmins },
      'GET /admin/role-defaults': { body: [roleDefault] },
      'GET /admin/accounts/adm1/overrides': { body: [] },
      'GET /admin/accounts/adm1/effective-access': { body: adminAccess },
    })
  })
  afterEach(() => vi.unstubAllGlobals())

  it('shows the Administration entry to System Admins and denies everyone else', async () => {
    renderApp('/')
    expect((await screen.findAllByRole('link', { name: 'إدارة النظام' })).length).toBeGreaterThan(0)
  })

  it('denies the page to non-admins', async () => {
    api.on('GET /auth/me', { body: account })
    renderApp('/admin/access')
    expect(await screen.findByRole('heading', { name: 'لا تملك صلاحية الوصول' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'إدارة النظام' })).toBeNull()
  })

  it('lets the admin grant themselves organization.manage at KORA (requires a reason) and refreshes /access/me', async () => {
    api.on('POST /admin/accounts/adm1/overrides', (body) => ({ status: 201, body: { id: 'o1', account_id: 'adm1', valid_from: '2026-10-15T10:00:00Z', valid_to: null, created_by_account_id: 'adm1', ended_by_account_id: null, ...(body as object) } }))
    renderApp('/admin/access?tab=accounts&account=adm1')
    await userEvent.click(await screen.findByRole('button', { name: 'منح نفسي صلاحية إدارة الهيكل التنظيمي' }))

    const dialog = await screen.findByRole('dialog')
    // pre-filled: organization.manage at KORA, grant
    expect(within(dialog).getByLabelText(/الصلاحية/)).toHaveValue('organization.manage')
    expect(within(dialog).getByLabelText(/الوحدة/)).toHaveValue(KORA_UNIT_ID)

    const accessCallsBefore = api.calls.filter((c) => c.key === 'GET /access/me').length
    await userEvent.click(within(dialog).getByRole('button', { name: 'إضافة' }))
    expect(await within(dialog).findByText('السبب مطلوب.')).toBeInTheDocument()
    expect(api.calls.some((c) => c.key === 'POST /admin/accounts/adm1/overrides')).toBe(false)

    await userEvent.type(within(dialog).getByLabelText(/السبب/), '  first setup  ')
    await userEvent.click(within(dialog).getByRole('button', { name: 'إضافة' }))
    await waitFor(() => expect(api.calls.some((c) => c.key === 'POST /admin/accounts/adm1/overrides')).toBe(true))
    expect(api.calls.find((c) => c.key === 'POST /admin/accounts/adm1/overrides')?.body).toEqual({
      permission: 'organization.manage', unit_id: KORA_UNIT_ID, effect: 'grant', reason: 'first setup',
    })
    await waitFor(() => expect(api.calls.filter((c) => c.key === 'GET /access/me').length).toBeGreaterThan(accessCallsBefore))
  })

  it('shows server business-rule errors inside the dialog', async () => {
    api.on('POST /admin/accounts/adm1/overrides', { status: 409, body: { detail: 'An identical override is already in force.' } })
    renderApp('/admin/access?tab=accounts&account=adm1')
    await userEvent.click(await screen.findByRole('button', { name: 'منح نفسي صلاحية إدارة الهيكل التنظيمي' }))
    const dialog = await screen.findByRole('dialog')
    await userEvent.type(within(dialog).getByLabelText(/السبب/), 'again')
    await userEvent.click(within(dialog).getByRole('button', { name: 'إضافة' }))
    expect(await within(dialog).findByRole('alert')).toHaveTextContent('An identical override is already in force.')
  })

  it('asks for confirmation before ending a role default, then ends it', async () => {
    api.on('POST /admin/role-defaults/rd1/end', { body: { ...roleDefault, valid_to: '2026-10-15T10:00:00Z' } })
    renderApp('/admin/access?tab=roles')
    await userEvent.click(await screen.findByRole('button', { name: 'إنهاء' }))
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByText(/يُغلق الافتراضي ولا يُحذف/)).toBeInTheDocument()
    expect(api.calls.some((c) => c.key === 'POST /admin/role-defaults/rd1/end')).toBe(false)
    await userEvent.click(within(dialog).getByRole('button', { name: 'إنهاء' }))
    await waitFor(() => expect(api.calls.some((c) => c.key === 'POST /admin/role-defaults/rd1/end')).toBe(true))
  })

  it('surfaces the final-System-Admin conflict on revoke', async () => {
    api.on('POST /admin/accounts/adm1/system-admin/revoke', { status: 409, body: { detail: 'The final System Admin cannot be revoked.' } })
    renderApp('/admin/access?tab=admins')
    await userEvent.click(await screen.findByRole('button', { name: 'سحب' }))
    const dialog = await screen.findByRole('dialog')
    await userEvent.click(within(dialog).getByRole('button', { name: 'سحب' }))
    expect(await within(dialog).findByRole('alert')).toHaveTextContent('The final System Admin cannot be revoked.')
  })

  it('renders the effective-access matrix from the server evaluation', async () => {
    renderApp('/admin/access?tab=accounts&account=adm1')
    const matrix = await screen.findByRole('region', { name: 'الصلاحيات الفعلية' })
    expect(within(matrix).getByText('Team A')).toBeInTheDocument()
    expect(within(matrix).getAllByText('لا وصول').length).toBe(24) // 2 units × 12 permissions, none granted
  })
})
