import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { Providers } from '@/app/Providers'
import { routes } from '@/app/router'
import { setApiHandlers } from '@/shared/api/http'
import type { EffectiveAccess } from '@/features/auth/types'
import { account as baseAccount, accessFor, installFakeApi, type FakeApi } from '@/test/fakeApi'
import { describeEvent } from './history'
import { allowedTransitions, changedFields, summarize, type Viewer } from './rules'
import type { Task, TaskEvent } from './types'

const ME = 'm-sara'
const sara = { ...baseAccount, id: 'a-sara', username: 'sara', member_id: ME }
const directory = [
  { id: ME, full_name: 'Sara Khalid', team_id: 'u-team', role_key: 'team_leader' },
  { id: 'm-omar', full_name: 'Omar Ali', team_id: 'u-team', role_key: 'member' },
]
const access = accessFor(['task.view@u-team', 'task.create@u-team', 'task.manage@u-team'])

const task = (over: Partial<Task> = {}): Task => ({
  id: 't1', title: 'Prepare match report', description: 'Details here', priority: 'high', due_at: '2099-01-01T10:00:00Z',
  status: 'new', scope_unit_id: 'u-team', parent_id: null, series_id: null, created_by_account_id: 'a-sara',
  created_by_member_id: ME, created_at: '2026-10-10T08:00:00Z', updated_at: '2026-10-10T08:00:00Z', started_at: null,
  assignee_member_ids: ['m-omar'], external_assignees: [], from_outside: false, ...over,
})

const viewer = (over: Partial<Viewer> = {}): Viewer => ({ memberId: ME, accountId: 'a-sara', access: access as unknown as EffectiveAccess, ...over })
const noAccess = accessFor() as unknown as EffectiveAccess

describe('task rules', () => {
  it('lets an assignee start/complete but not cancel', () => {
    const omar = viewer({ memberId: 'm-omar', accountId: 'a-omar', access: noAccess })
    expect(allowedTransitions(task(), omar)).toEqual(['in_progress', 'completed'])
    expect(allowedTransitions(task({ status: 'in_progress' }), omar)).toEqual(['completed'])
    expect(allowedTransitions(task({ status: 'completed' }), omar)).toEqual([])
  })
  it('lets the creator or a scoped manager cancel and reopen', () => {
    const creatorOnly = viewer({ access: noAccess }) // creator, no manage
    expect(allowedTransitions(task(), creatorOnly)).toEqual(['cancelled'])
    expect(allowedTransitions(task({ status: 'cancelled' }), creatorOnly)).toEqual(['new'])
    expect(allowedTransitions(task(), viewer())).toEqual(['in_progress', 'completed', 'cancelled'])
  })
  it('offers nothing to an unrelated viewer', () => {
    expect(allowedTransitions(task(), viewer({ memberId: 'm-x', accountId: 'a-x', access: noAccess }))).toEqual([])
  })
  it('sends only changed fields, and nothing when the instant is unchanged', () => {
    const t = task()
    expect(changedFields(t, { title: t.title, description: t.description, priority: 'low', due_at: '2099-01-01T10:00:00.000Z' })).toEqual({ priority: 'low' })
    expect(changedFields(t, { title: t.title, description: null, priority: t.priority, due_at: null })).toEqual({ description: null, due_at: null })
  })
  it('summarizes visible tasks into counts and a due-soon list', () => {
    const now = new Date('2026-10-15T00:00:00Z')
    const tasks = [
      task({ id: 'a', due_at: '2026-10-16T00:00:00Z' }),
      task({ id: 'b', due_at: '2026-10-01T00:00:00Z', assignee_member_ids: [] }),
      task({ id: 'c', status: 'completed', due_at: '2026-10-01T00:00:00Z' }),
    ]
    const s = summarize(tasks, (x) => x.assignee_member_ids.includes('m-omar'), now)
    expect(s).toMatchObject({ open: 2, mine: 1, overdue: 1 })
    expect(s.dueSoon.map((x) => x.id)).toEqual(['a'])
  })
})

describe('history descriptions', () => {
  const d = { t: (k: string, p?: Record<string, string | number>) => `${k}${p ? JSON.stringify(p) : ''}`, memberName: (id: string | null | undefined) => `name:${id}`, unitName: (id: string) => `unit:${id}` }
  const ev = (kind: TaskEvent['kind'], data: TaskEvent['data']): TaskEvent => ({ kind, actor_account_id: null, data, created_at: '2026-10-10T08:00:00Z' })

  it('describes status, assignee and scope events', () => {
    expect(describeEvent(ev('status_changed', { previous: 'new', status: 'completed' }), d as never)).toContain('"previous":"tasks.status.new"'.replace('tasks.status', 'task.status'))
    expect(describeEvent(ev('assignee_removed', { member_id: 'm1', reason: 'out_of_scope' }), d as never)).toContain('name:m1')
    expect(describeEvent(ev('scope_changed', { previous: 'a', scope_unit_id: 'b' }), d as never)).toContain('unit:b')
  })
  it('marks removed comment text and never prints previous_body', () => {
    const line = describeEvent(ev('comment_edited', { comment_id: 'c', content_removed: true, previous_body: 'SECRET' }), d as never)
    expect(line).toContain('tasks.event.textRemoved')
    expect(line).not.toContain('SECRET')
  })
})

function renderApp(path: string) {
  render(
    <Providers>
      <RouterProvider router={createMemoryRouter(routes, { initialEntries: [path] })} />
    </Providers>,
  )
}

describe('Tasks UI', () => {
  let api: FakeApi
  beforeEach(() => {
    localStorage.clear()
    setApiHandlers({})
    api = installFakeApi({
      'GET /auth/me': { body: sara },
      'GET /access/me': { body: access },
      'GET /organization/members': { body: directory },
      'GET /tasks': { body: [task(), task({ id: 't2', title: 'Book the pitch', status: 'completed', series_id: 's1', assignee_member_ids: [ME] })] },
      'GET /tasks/t1': { body: task() },
      'GET /tasks/t1/subtasks': { body: [] },
      'GET /tasks/t1/history': { body: [{ kind: 'created', actor_account_id: 'a-sara', data: {}, created_at: '2026-10-10T08:00:00Z' }] },
      'GET /tasks/t1/comments': { body: [
        { id: 'c1', task_id: 't1', author_account_id: 'a-sara', body: 'On it', created_at: '2026-10-10T09:00:00Z', edited_at: null, deleted_at: null },
        { id: 'c2', task_id: 't1', author_account_id: 'a-omar', body: null, created_at: '2026-10-10T10:00:00Z', edited_at: null, deleted_at: '2026-10-10T11:00:00Z' },
      ] },
    })
  })
  afterEach(() => vi.unstubAllGlobals())

  it('lists visible tasks with Member names from the lookup, and filters to mine', async () => {
    renderApp('/tasks')
    expect(await screen.findByRole('link', { name: 'Prepare match report' })).toHaveAttribute('href', '/tasks/t1')
    expect(screen.getAllByText(/Omar Ali/).length).toBeGreaterThan(0)
    expect(screen.getByText('سلسلة أسبوعية')).toBeInTheDocument()
    await userEvent.click(screen.getByLabelText(/أنشأتها أو أُسندت إليّ/))
    // both tasks were created by Sara, so both stay; narrow with the search box
    await userEvent.type(screen.getByLabelText('ابحث في العناوين'), 'pitch')
    expect(screen.queryByRole('link', { name: 'Prepare match report' })).toBeNull()
    expect(screen.getByRole('link', { name: 'Book the pitch' })).toBeInTheDocument()
  })

  it('creates a task with the chosen unit and assignees', async () => {
    api.on('POST /tasks', (b) => ({ status: 201, body: task({ id: 't9', ...(b as object) }) }))
    renderApp('/tasks')
    await userEvent.click(await screen.findByRole('button', { name: /مهمة جديدة/ }))
    const dialog = await screen.findByRole('dialog')
    await userEvent.click(within(dialog).getByRole('button', { name: 'إنشاء المهمة' }))
    expect(await within(dialog).findByText('أدخل عنوانًا.')).toBeInTheDocument()
    expect(within(dialog).getByText('اختر وحدة.')).toBeInTheDocument()
    expect(within(dialog).getByText('اختر مكلّفًا واحدًا على الأقل.')).toBeInTheDocument()

    await userEvent.type(within(dialog).getByLabelText(/^العنوان/), 'Order kits')
    await userEvent.selectOptions(within(dialog).getByLabelText(/^الوحدة/), 'u-team')
    await userEvent.click(within(dialog).getByLabelText('Omar Ali'))
    await userEvent.click(within(dialog).getByRole('button', { name: 'إنشاء المهمة' }))
    await waitFor(() => expect(api.calls.find((c) => c.key === 'POST /tasks')?.body).toEqual({
      title: 'Order kits', description: null, priority: null, due_at: null, scope_unit_id: 'u-team', assignee_member_ids: ['m-omar'], external_assignee_member_ids: [],
    }))
  })

  it('hides create for an account that is not a Member', async () => {
    api.on('GET /auth/me', { body: { ...sara, member_id: null } })
    renderApp('/tasks')
    await screen.findByRole('link', { name: 'Prepare match report' })
    expect(screen.queryByRole('button', { name: /مهمة جديدة/ })).toBeNull()
    expect(screen.getByText(/غير مرتبط بعضو/)).toBeInTheDocument()
  })

  it('shows detail with deleted-comment placeholder and only legal actions', async () => {
    renderApp('/tasks/t1')
    expect(await screen.findByRole('heading', { name: 'Prepare match report' })).toBeInTheDocument()
    expect(await screen.findByText('تم حذف هذا التعليق.')).toBeInTheDocument()
    expect(screen.getByText('On it')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'بدء' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'إلغاء المهمة' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'إعادة فتح' })).toBeNull()
  })

  it('confirms before cancelling and then posts the status', async () => {
    api.on('POST /tasks/t1/status', { body: task({ status: 'cancelled' }) })
    renderApp('/tasks/t1')
    await userEvent.click(await screen.findByRole('button', { name: 'إلغاء المهمة' }))
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByText(/ويمكن لمنشئها أو لمدير إعادة فتحها/)).toBeInTheDocument()
    expect(api.calls.some((c) => c.key === 'POST /tasks/t1/status')).toBe(false)
    await userEvent.click(within(dialog).getByRole('button', { name: 'إلغاء المهمة' }))
    await waitFor(() => expect(api.calls.find((c) => c.key === 'POST /tasks/t1/status')?.body).toEqual({ status: 'cancelled' }))
  })

  it('starts a task immediately without a dialog', async () => {
    api.on('POST /tasks/t1/status', { body: task({ status: 'in_progress' }) })
    renderApp('/tasks/t1')
    await userEvent.click(await screen.findByRole('button', { name: 'بدء' }))
    await waitFor(() => expect(api.calls.find((c) => c.key === 'POST /tasks/t1/status')?.body).toEqual({ status: 'in_progress' }))
  })

  it('shows Home counts labelled as derived from visible tasks', async () => {
    renderApp('/')
    expect(await screen.findByText('تُحسب من المهام التي يمكنك رؤيتها، وليست رقمًا على مستوى المنظمة.')).toBeInTheDocument()
    expect(screen.getByText('المهام المفتوحة')).toBeInTheDocument()
  })
})
