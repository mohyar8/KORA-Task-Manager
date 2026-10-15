import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { Providers } from '@/app/Providers'
import { routes } from '@/app/router'
import { setApiHandlers } from '@/shared/api/http'
import { account, accessFor, installFakeApi, type FakeApi } from '@/test/fakeApi'
import { draftToProfile, emptyProfileDraft, isValidEmail, roleFieldsFor, validateProfile } from './types'
import type { Member } from './types'

const admin = { ...account, id: 'adm1', username: 'root', is_system_admin: true }
const sara: Member = {
  id: 'm1', account_id: 'a-sara', username: 'sara.k', full_name: 'Sara Khalid', university_id: '20211234', phone: '0555', email: 'sara@kfupm.edu.sa',
  major: 'SWE', academic_year: '3', status: 'active', team_id: 'u-team', role_key: 'member', role_unit_id: 'u-team',
}
const omar: Member = { ...sara, id: 'm2', account_id: 'a-omar', username: 'omar', full_name: 'Omar Ali', university_id: null, phone: null, email: null, major: null, academic_year: null, status: 'deactivated', team_id: null, role_key: null, role_unit_id: null }

function renderApp(path: string) {
  render(
    <Providers>
      <RouterProvider router={createMemoryRouter(routes, { initialEntries: [path] })} />
    </Providers>,
  )
}

describe('member helpers', () => {
  it('only administration managers carry an administration id', () => {
    expect(roleFieldsFor('administration_manager', 'adm-1')).toEqual({ role_key: 'administration_manager', administration_id: 'adm-1' })
    expect(roleFieldsFor('team_leader', 'stale')).toEqual({ role_key: 'team_leader', administration_id: null })
  })
  it('blank optional profile fields become null', () => {
    expect(draftToProfile({ ...emptyProfileDraft, full_name: ' Sara ', phone: '  ' })).toEqual({
      full_name: 'Sara', university_id: null, phone: null, email: null, major: null, academic_year: null,
    })
  })
  it('mirrors the contract email rule', () => {
    expect(isValidEmail('a@b.co')).toBe(true)
    expect(isValidEmail('a@b')).toBe(false)
    expect(isValidEmail('a b@c.d')).toBe(false)
    expect(validateProfile({ ...emptyProfileDraft, full_name: '' }, (k) => k)).toEqual({ full_name: 'members.nameRequired' })
  })
})

describe('Members (System Admin)', () => {
  let api: FakeApi
  beforeEach(() => {
    localStorage.clear()
    setApiHandlers({})
    api = installFakeApi({
      'GET /auth/me': { body: admin },
      'GET /access/me': { body: accessFor() },
      'GET /admin/members': { body: [sara, omar] },
      'GET /admin/members/m1': { body: sara },
      'GET /admin/members/m2': { body: omar },
    })
  })
  afterEach(() => vi.unstubAllGlobals())

  it('lists Members and filters by search and status', async () => {
    renderApp('/admin/members')
    expect(await screen.findByRole('link', { name: 'Sara Khalid' })).toHaveAttribute('href', '/admin/members/m1')
    expect(screen.getByText('2 عضوًا')).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText('ابحث بالاسم أو اسم المستخدم أو الرقم الجامعي'), '2021')
    expect(screen.queryByRole('link', { name: 'Omar Ali' })).toBeNull()
    await userEvent.clear(screen.getByLabelText('ابحث بالاسم أو اسم المستخدم أو الرقم الجامعي'))
    await userEvent.selectOptions(screen.getByLabelText('الحالة'), 'deactivated')
    expect(screen.queryByRole('link', { name: 'Sara Khalid' })).toBeNull()
    expect(screen.getByRole('link', { name: 'Omar Ali' })).toBeInTheDocument()
  })

  it('is closed to non-admins', async () => {
    api.on('GET /auth/me', { body: account })
    renderApp('/admin/members')
    expect(await screen.findByRole('heading', { name: 'لا تملك صلاحية الوصول' })).toBeInTheDocument()
  })

  it('provisions a Member and shows the temporary password once', async () => {
    api.on('POST /admin/members', (b) => ({ status: 201, body: { member: { ...sara, id: 'm3', full_name: (b as { full_name: string }).full_name, username: (b as { username: string }).username }, temporary_password: 'Tmp-Secret-123' } }))
    renderApp('/admin/members')
    await userEvent.click((await screen.findAllByRole('button', { name: /إضافة عضو/ }))[0])
    const dialog = await screen.findByRole('dialog')

    await userEvent.click(within(dialog).getByRole('button', { name: 'إنشاء العضو والحساب' }))
    expect(await within(dialog).findByText('أدخل الاسم الكامل.')).toBeInTheDocument()
    expect(within(dialog).getByText('اختر فريقًا.')).toBeInTheDocument()

    await userEvent.type(within(dialog).getByLabelText(/الاسم الكامل/), 'Nora Hassan')
    await userEvent.type(within(dialog).getByLabelText(/^اسم المستخدم/), 'Nora.H')
    await userEvent.selectOptions(within(dialog).getByLabelText(/^الفريق/), 'u-team')
    await userEvent.click(within(dialog).getByRole('button', { name: 'إنشاء العضو والحساب' }))

    const secret = await screen.findByTestId('temporary-password')
    expect(secret).toHaveTextContent('Tmp-Secret-123')
    expect(api.calls.find((c) => c.key === 'POST /admin/members')?.body).toEqual({
      full_name: 'Nora Hassan', university_id: null, phone: null, email: null, major: null, academic_year: null,
      role_key: 'member', administration_id: null, username: 'nora.h', team_id: 'u-team',
    })
    await userEvent.click(screen.getByRole('button', { name: 'حفظتها' }))
    await waitFor(() => expect(screen.queryByTestId('temporary-password')).toBeNull())
    expect(document.body.textContent).not.toContain('Tmp-Secret-123')
  })

  it('asks for an administration only for Administration Managers', async () => {
    renderApp('/admin/members')
    await userEvent.click((await screen.findAllByRole('button', { name: /إضافة عضو/ }))[0])
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).queryByLabelText(/^الإدارة/)).toBeNull()
    await userEvent.selectOptions(within(dialog).getByLabelText(/^الدور/), 'administration_manager')
    expect(within(dialog).getByLabelText(/^الإدارة/)).toBeInTheDocument()
    await userEvent.selectOptions(within(dialog).getByLabelText(/^الدور/), 'team_leader')
    expect(within(dialog).queryByLabelText(/^الإدارة/)).toBeNull()
  })

  it('replaces the whole profile on save, with cleared fields sent as null', async () => {
    api.on('PUT /admin/members/m1', (b) => ({ body: { ...sara, ...(b as object) } }))
    renderApp('/admin/members/m1')
    const phone = await screen.findByLabelText(/الجوال/)
    expect(phone).toHaveValue('0555')
    await userEvent.clear(phone)
    await userEvent.click(screen.getByRole('button', { name: 'حفظ الملف الشخصي' }))
    await waitFor(() => expect(api.calls.find((c) => c.key === 'PUT /admin/members/m1')?.body).toEqual({
      full_name: 'Sara Khalid', university_id: '20211234', phone: null, email: 'sara@kfupm.edu.sa', major: 'SWE', academic_year: '3',
    }))
  })

  it('explains deactivation before doing it', async () => {
    api.on('POST /admin/members/m1/deactivate', { body: { ...omar, id: 'm1' } })
    renderApp('/admin/members/m1')
    await userEvent.click(await screen.findByRole('button', { name: 'تعطيل' }))
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByText(/تُلغى كل جلساته/)).toBeInTheDocument()
    expect(api.calls.some((c) => c.key === 'POST /admin/members/m1/deactivate')).toBe(false)
    await userEvent.click(within(dialog).getByRole('button', { name: 'تعطيل' }))
    await waitFor(() => expect(api.calls.some((c) => c.key === 'POST /admin/members/m1/deactivate')).toBe(true))
  })

  it('offers reactivation (team + role) for a deactivated Member', async () => {
    renderApp('/admin/members/m2')
    expect(await screen.findByText('هذا العضو معطّل: لا فريق ولا دور ولا تسجيل دخول.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'تعطيل' })).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: 'إعادة تفعيل' }))
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByLabelText(/^الفريق/)).toBeInTheDocument()
    expect(within(dialog).getByLabelText(/^الدور/)).toBeInTheDocument()
  })
})
