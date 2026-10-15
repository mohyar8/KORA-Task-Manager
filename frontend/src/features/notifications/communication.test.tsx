import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { Providers } from '@/app/Providers'
import { routes } from '@/app/router'
import { setApiHandlers } from '@/shared/api/http'
import { announcementActions, type Announcement } from '@/features/announcements/api'
import { account as baseAccount, accessFor, installFakeApi, type FakeApi } from '@/test/fakeApi'
import { sourceLink, type AppNotification } from './api'

const sara = { ...baseAccount, id: 'a-sara', username: 'sara', member_id: 'm-sara' }
const directory = [
  { id: 'm-sara', full_name: 'Sara Khalid', team_id: 'u-team', role_key: 'team_leader' },
  { id: 'm-omar', full_name: 'Omar Ali', team_id: 'u-team', role_key: 'member' },
]
const access = accessFor(['task.view@u-team', 'announcement.publish@u-team', 'announcement.manage@u-team'])

const ann = (over: Partial<Announcement> = {}): Announcement => ({
  id: 'n1', scope_unit_id: 'u-team', state: 'draft', current_version: 1, created_by_account_id: 'a-sara', created_at: '2026-10-10T08:00:00Z',
  updated_at: '2026-10-10T08:00:00Z', published_at: null, published_by_account_id: null, withdrawn_at: null, withdrawn_by_account_id: null,
  title: 'Kit day', body: 'Bring your kit.', content_hidden: false, my_read_version: null, my_read_current: null, ...over,
})
const notif = (over: Partial<AppNotification> = {}): AppNotification => ({
  id: 'x1', category: 'task_assignment', kind: 'assigned', source_type: 'task', source_id: 't1', summary: 'You were assigned: Order kits',
  redacted: false, actor_account_id: 'a-omar', created_at: '2026-10-10T08:00:00Z', read_at: null, ...over,
})

describe('announcement actions', () => {
  const v = { accountId: 'a-sara', canManage: false, canPublish: true }
  it('lets a draft creator edit and publish but not withdraw', () => {
    expect(announcementActions(ann(), v)).toEqual({ edit: true, publish: true, withdraw: false, versions: true, recipients: false })
  })
  it('lets only the publisher or a manager act on a published one; nobody edits a withdrawn one', () => {
    const pub = ann({ state: 'published', published_by_account_id: 'a-other' })
    expect(announcementActions(pub, v)).toMatchObject({ edit: false, withdraw: false, versions: false })
    expect(announcementActions(pub, { ...v, canManage: true })).toMatchObject({ edit: true, withdraw: true, recipients: true })
    expect(announcementActions(ann({ state: 'withdrawn' }), { ...v, canManage: true }).edit).toBe(false)
  })
})

describe('notification links', () => {
  it('maps every source type to a page', () => {
    expect(sourceLink({ source_type: 'task', source_id: 'a' })).toBe('/tasks/a')
    expect(sourceLink({ source_type: 'task_series', source_id: 'a' })).toBe('/task-series/a')
    expect(sourceLink({ source_type: 'announcement', source_id: 'a' })).toBe('/announcements/a')
    expect(sourceLink({ source_type: 'calendar_event', source_id: 'a' })).toBe('/calendar/a')
    expect(sourceLink({ source_type: 'other', source_id: 'a' })).toBeNull()
  })
})

function renderApp(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] })
  render(
    <Providers>
      <RouterProvider router={router} />
    </Providers>,
  )
  return router
}

describe('Announcements UI', () => {
  let api: FakeApi
  beforeEach(() => {
    localStorage.clear()
    setApiHandlers({})
    api = installFakeApi({
      'GET /auth/me': { body: sara },
      'GET /access/me': { body: access },
      'GET /organization/members': { body: directory },
      'GET /notifications': { body: [] },
      'GET /announcements': { body: [ann(), ann({ id: 'n2', title: null, body: null, state: 'withdrawn', content_hidden: true, my_read_current: false })] },
      'GET /announcements/n1': { body: ann() },
    })
  })
  afterEach(() => vi.unstubAllGlobals())

  it('lists announcements and hides withdrawn content', async () => {
    renderApp('/announcements')
    expect(await screen.findByRole('link', { name: 'Kit day' })).toHaveAttribute('href', '/announcements/n1')
    expect(screen.getByRole('link', { name: 'إعلان مسحوب' })).toBeInTheDocument()
  })

  it('requires recipients before publishing, then sends them', async () => {
    api.on('POST /announcements/n1/publish', { body: ann({ state: 'published', published_by_account_id: 'a-sara' }) })
    renderApp('/announcements/n1')
    await userEvent.click(await screen.findByRole('button', { name: 'نشر' }))
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByText(/لا يمكن تغييرهم بعد ذلك/)).toBeInTheDocument()
    await userEvent.click(within(dialog).getByRole('button', { name: 'نشر' }))
    expect(await within(dialog).findByText('اختر مستلمًا واحدًا على الأقل.')).toBeInTheDocument()
    expect(api.calls.some((c) => c.key === 'POST /announcements/n1/publish')).toBe(false)
    await userEvent.click(within(dialog).getByLabelText('Omar Ali'))
    await userEvent.click(within(dialog).getByRole('button', { name: 'نشر' }))
    await waitFor(() => expect(api.calls.find((c) => c.key === 'POST /announcements/n1/publish')?.body).toEqual({ recipient_member_ids: ['m-omar'] }))
  })

  it('sends only changed fields when editing', async () => {
    api.on('PATCH /announcements/n1', { body: ann({ title: 'Kit day!' }) })
    renderApp('/announcements/n1')
    await userEvent.click(await screen.findByRole('button', { name: 'تعديل' }))
    const dialog = await screen.findByRole('dialog')
    const title = within(dialog).getByLabelText(/^العنوان/)
    await userEvent.clear(title)
    await userEvent.type(title, 'Kit day!')
    await userEvent.click(within(dialog).getByRole('button', { name: 'حفظ' }))
    await waitFor(() => expect(api.calls.find((c) => c.key === 'PATCH /announcements/n1')?.body).toEqual({ title: 'Kit day!' }))
  })

  it('loads versions only on request', async () => {
    api.on('GET /announcements/n1', { body: ann({ state: 'published', published_by_account_id: 'a-sara', current_version: 2 }) })
    api.on('GET /announcements/n1/versions', { body: [{ version: 1, title: 'Old', body: 'Old text', created_by_account_id: 'a-sara', created_at: '2026-10-10T08:00:00Z' }] })
    renderApp('/announcements/n1')
    await userEvent.click(await screen.findByRole('button', { name: 'عرض الإصدارات' }))
    expect(await screen.findByText(/Old text/)).toBeInTheDocument()
  })

  it('shows the withdrawn placeholder to a recipient', async () => {
    api.on('GET /announcements/n1', { body: ann({ state: 'withdrawn', title: null, body: null, content_hidden: true, my_read_current: false }) })
    renderApp('/announcements/n1')
    expect(await screen.findByText('تم سحب هذا الإعلان ولم يعد محتواه ظاهرًا.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'تعديل' })).toBeNull()
  })
})

describe('Notifications UI', () => {
  let api: FakeApi
  beforeEach(() => {
    localStorage.clear()
    setApiHandlers({})
    api = installFakeApi({
      'GET /auth/me': { body: sara },
      'GET /access/me': { body: access },
      'GET /organization/members': { body: directory },
      'GET /tasks': { body: [] },
      'GET /notifications': { body: [notif(), notif({ id: 'x2', redacted: true, summary: null, source_id: 't9', read_at: '2026-10-10T09:00:00Z' })] },
    })
  })
  afterEach(() => vi.unstubAllGlobals())

  it('shows the unread count in the bell’s accessible name', async () => {
    renderApp('/')
    expect(await screen.findByRole('link', { name: 'الإشعارات (2 غير مقروء)' })).toBeInTheDocument()
  })

  it('opens a notification: marks it read and navigates to its source; redacted ones have no link', async () => {
    api.on('GET /notifications/x1', { body: notif() })
    api.on('POST /notifications/x1/read', { body: notif({ read_at: '2026-10-15T10:00:00Z' }) })
    api.on('GET /tasks/t1', { status: 404, body: { detail: 'Not found.' } })
    const router = renderApp('/notifications')
    expect(await screen.findByText('You were assigned: Order kits')).toBeInTheDocument()
    expect(screen.getByText('لم يعد بإمكانك عرض العنصر الذي يشير إليه هذا الإشعار.')).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: 'فتح' })).toHaveLength(1)
    await userEvent.click(screen.getByRole('button', { name: 'فتح' }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/tasks/t1'))
    expect(api.calls.some((c) => c.key === 'POST /notifications/x1/read')).toBe(true)
  })

  it('confirms before deleting everything', async () => {
    api.on('POST /notifications/delete-all', { status: 204 })
    renderApp('/notifications')
    await userEvent.click(await screen.findByRole('button', { name: 'حذف الكل' }))
    const dialog = await screen.findByRole('dialog')
    expect(api.calls.some((c) => c.key === 'POST /notifications/delete-all')).toBe(false)
    await userEvent.click(within(dialog).getByRole('button', { name: 'حذف الكل' }))
    await waitFor(() => expect(api.calls.some((c) => c.key === 'POST /notifications/delete-all')).toBe(true))
  })

  it('saves a single preference as a partial map', async () => {
    api.on('GET /notifications/preferences', { body: { task_assignment: true, task_update: true, task_comment: true, announcement_new: true, announcement_change: true, calendar_event: true } })
    api.on('PUT /notifications/preferences', (b) => ({ body: { task_assignment: true, task_update: true, task_comment: true, announcement_new: true, announcement_change: true, calendar_event: true, ...(b as object) } }))
    renderApp('/notifications?tab=preferences')
    await userEvent.click(await screen.findByLabelText('تعليقات المهام'))
    await waitFor(() => expect(api.calls.find((c) => c.key === 'PUT /notifications/preferences')?.body).toEqual({ task_comment: false }))
  })
})
