import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { Providers } from '@/app/Providers'
import { routes } from '@/app/router'
import { setApiHandlers } from '@/shared/api/http'
import { account, accessFor, installFakeApi, type FakeApi } from '@/test/fakeApi'

const units = [
  { id: 'u-kora', kind: 'organization', name: 'KORA', status: 'active', parent_id: null, archived_at: null },
  { id: 'u-adm', kind: 'administration', name: 'Operations', status: 'active', parent_id: 'u-kora', archived_at: null },
  { id: 'u-adm2', kind: 'administration', name: 'Media', status: 'active', parent_id: 'u-kora', archived_at: null },
  { id: 'u-team', kind: 'team', name: 'Team A', status: 'active', parent_id: 'u-adm', archived_at: null },
]

function renderApp(path: string) {
  render(
    <Providers>
      <RouterProvider router={createMemoryRouter(routes, { initialEntries: [path] })} />
    </Providers>,
  )
}

describe('Organization page', () => {
  let api: FakeApi
  beforeEach(() => {
    localStorage.clear()
    setApiHandlers({})
    api = installFakeApi({
      'GET /auth/me': { body: account },
      'GET /access/me': { body: accessFor(['organization.manage@u-kora']) },
      'GET /organization/units': { body: units },
    })
  })
  afterEach(() => vi.unstubAllGlobals())

  it('shows the hierarchy with only the legal actions per unit kind', async () => {
    renderApp('/organization')
    await screen.findByText('Operations')
    expect(screen.getByRole('button', { name: /إضافة إدارة/ })).toBeInTheDocument() // on KORA
    expect(screen.getAllByRole('button', { name: /إضافة فريق/ })).toHaveLength(2) // on each administration
    expect(screen.getAllByRole('button', { name: /^.*حذف$/ })).toHaveLength(3) // 2 administrations + 1 team, never KORA
    expect(screen.getAllByRole('button', { name: /نقل/ })).toHaveLength(1) // only the team
  })

  it('creates an administration under KORA and requires a name', async () => {
    api.on('POST /organization/units', (b) => ({ status: 201, body: { id: 'new', status: 'active', archived_at: null, ...(b as object) } }))
    renderApp('/organization')
    await userEvent.click(await screen.findByRole('button', { name: /إضافة إدارة/ }))
    const dialog = await screen.findByRole('dialog')
    await userEvent.click(within(dialog).getByRole('button', { name: 'إضافة' }))
    expect(await within(dialog).findByText('أدخل اسمًا.')).toBeInTheDocument()
    await userEvent.type(within(dialog).getByLabelText(/الاسم/), '  Finance ')
    await userEvent.click(within(dialog).getByRole('button', { name: 'إضافة' }))
    await waitFor(() => expect(api.calls.find((c) => c.key === 'POST /organization/units')?.body).toEqual({ kind: 'administration', name: 'Finance', parent_id: 'u-kora' }))
  })

  it('moves a team to another active administration only', async () => {
    api.on('POST /organization/units/u-team/move', { body: { ...units[3], parent_id: 'u-adm2' } })
    renderApp('/organization')
    await userEvent.click(await screen.findByRole('button', { name: /نقل/ }))
    const dialog = await screen.findByRole('dialog')
    const select = within(dialog).getByLabelText(/الإدارة الجديدة/)
    // the team's current administration (Operations) is not offered
    expect(within(select).queryByRole('option', { name: 'Operations' })).toBeNull()
    await userEvent.selectOptions(select, 'u-adm2')
    await userEvent.click(within(dialog).getByRole('button', { name: 'نقل' }))
    await waitFor(() => expect(api.calls.find((c) => c.key === 'POST /organization/units/u-team/move')?.body).toEqual({ administration_id: 'u-adm2' }))
  })

  it('explains the effect before archiving and shows the server conflict', async () => {
    api.on('POST /organization/units/u-adm/archive', { status: 409, body: { detail: 'Cannot archive: the unit still has active sub-units.' } })
    renderApp('/organization')
    const row = (await screen.findByText('Operations')).closest('div')!.parentElement!
    await userEvent.click(within(row).getByRole('button', { name: /حذف/ }))
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByText(/يبقى سجلها محفوظًا/)).toBeInTheDocument()
    await userEvent.click(within(dialog).getByRole('button', { name: 'حذف' }))
    expect(await within(dialog).findByRole('alert')).toHaveTextContent('Cannot archive: the unit still has active sub-units.')
  })

  it('denies the page without organization.manage', async () => {
    api.on('GET /access/me', { body: accessFor() })
    renderApp('/organization')
    expect(await screen.findByRole('heading', { name: 'لا تملك صلاحية الوصول' })).toBeInTheDocument()
  })
})
