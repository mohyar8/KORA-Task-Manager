import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { Providers } from '@/app/Providers'
import { routes } from '@/app/router'
import { setApiHandlers } from '@/shared/api/http'
import { account as baseAccount, accessFor, installFakeApi, type FakeApi } from '@/test/fakeApi'
import { MAX_OCCURRENCES, occurrenceCount, seriesChanges, type CreateSeries, type Series } from './seriesApi'

const sara = { ...baseAccount, id: 'a-sara', username: 'sara', member_id: 'm-sara' }
const directory = [
  { id: 'm-sara', full_name: 'Sara Khalid', team_id: 'u-team', role_key: 'team_leader' },
  { id: 'm-omar', full_name: 'Omar Ali', team_id: 'u-team', role_key: 'member' },
]
const access = accessFor(['task.view@u-team', 'task.create@u-team', 'task.manage@u-team', 'task.manage@u-admin'], true)

const series = (over: Partial<Series> = {}): Series => ({
  id: 's1', scope_unit_id: 'u-team', title: 'Weekly report', description: null, priority: null, assignee_member_ids: ['m-omar'],
  first_due_at: '2099-01-01T10:00:00Z', ends_at: '2099-01-29T10:00:00Z', status: 'active', created_by_account_id: 'a-sara', stopped_at: null,
  subtask_templates: [{ key: 'k1', title: 'Collect stats', description: null, priority: null, assignee_member_ids: ['m-omar'] }],
  occurrence_ids: ['t1', 't2'], ...over,
})
const asInput = (s: Series, over: Partial<CreateSeries> = {}): CreateSeries => ({
  scope_unit_id: s.scope_unit_id, title: s.title, description: s.description, priority: s.priority, first_due_at: s.first_due_at,
  ends_at: s.ends_at, assignee_member_ids: s.assignee_member_ids, subtasks: s.subtask_templates.map((t) => ({ ...t })), ...over,
})

describe('series helpers', () => {
  it('counts weekly occurrences inclusively and against the 104 cap', () => {
    expect(occurrenceCount('2099-01-01T10:00:00Z', '2099-01-29T10:00:00Z')).toBe(5)
    expect(occurrenceCount('2099-01-01T10:00:00Z', '2099-01-01T10:00:00Z')).toBe(1)
    expect(occurrenceCount('2099-01-08T10:00:00Z', '2099-01-01T10:00:00Z')).toBe(0)
    expect(occurrenceCount('2099-01-01T00:00:00Z', '2101-01-01T00:00:00Z')).toBeGreaterThan(MAX_OCCURRENCES)
  })
  it('sends nothing when nothing changed, and only what changed otherwise', () => {
    const s = series()
    expect(seriesChanges(s, asInput(s))).toEqual({})
    expect(seriesChanges(s, asInput(s, { title: 'New' }))).toEqual({ title: 'New' })
    expect(seriesChanges(s, asInput(s, { assignee_member_ids: ['m-omar', 'm-sara'] }))).toEqual({ assignee_member_ids: ['m-omar', 'm-sara'] })
  })
  it('sends the complete template list keeping existing keys and omitting keys of new ones', () => {
    const s = series()
    const next = asInput(s, { subtasks: [...s.subtask_templates, { title: 'Post summary', description: null, priority: null, assignee_member_ids: ['m-sara'] }] })
    const diff = seriesChanges(s, next)
    expect(diff.subtasks).toHaveLength(2)
    expect(diff.subtasks?.[0].key).toBe('k1')
    expect(diff.subtasks?.[1]).not.toHaveProperty('key')
    // removing a template = sending the list without it
    expect(seriesChanges(s, asInput(s, { subtasks: [] })).subtasks).toEqual([])
  })
})

function renderApp(path: string) {
  render(
    <Providers>
      <RouterProvider router={createMemoryRouter(routes, { initialEntries: [path] })} />
    </Providers>,
  )
}

describe('Series UI', () => {
  let api: FakeApi
  beforeEach(() => {
    localStorage.clear()
    setApiHandlers({})
    const occ = (id: string, due: string) => ({
      id, title: 'Weekly report', description: null, priority: null, due_at: due, status: 'new', scope_unit_id: 'u-team', parent_id: null,
      series_id: 's1', created_by_account_id: 'a-sara', created_by_member_id: 'm-sara', created_at: '2026-10-10T08:00:00Z',
      updated_at: '2026-10-10T08:00:00Z', started_at: null, assignee_member_ids: ['m-omar'],
    })
    api = installFakeApi({
      'GET /auth/me': { body: sara },
      'GET /access/me': { body: access },
      'GET /organization/members': { body: directory },
      'GET /tasks': { body: [occ('t1', '2099-01-01T10:00:00Z'), occ('t2', '2099-01-08T10:00:00Z')] },
      'GET /task-series/s1': { body: series() },
    })
  })
  afterEach(() => vi.unstubAllGlobals())

  it('shows the series with its visible occurrences and the scope note', async () => {
    renderApp('/task-series/s1')
    expect(await screen.findByRole('heading', { name: 'Weekly report', level: 1 })).toBeInTheDocument()
    expect(await screen.findAllByRole('link', { name: 'Weekly report' })).toHaveLength(2)
    expect(screen.getByText(/تؤثر فقط في المهام المستقبلية/)).toBeInTheDocument()
    expect(screen.getByText('Collect stats')).toBeInTheDocument()
  })

  it('explains the effect of stopping and then posts it', async () => {
    api.on('POST /task-series/s1/stop', { body: series({ status: 'stopped', stopped_at: '2026-10-15T10:00:00Z' }) })
    renderApp('/task-series/s1')
    await userEvent.click(await screen.findByRole('button', { name: 'إيقاف السلسلة' }))
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByText(/لا يمكن إعادة تشغيل السلسلة/)).toBeInTheDocument()
    expect(api.calls.some((c) => c.key === 'POST /task-series/s1/stop')).toBe(false)
    await userEvent.click(within(dialog).getByRole('button', { name: 'إيقاف السلسلة' }))
    await waitFor(() => expect(api.calls.some((c) => c.key === 'POST /task-series/s1/stop')).toBe(true))
  })

  it('offers no management actions once stopped', async () => {
    api.on('GET /task-series/s1', { body: series({ status: 'stopped' }) })
    renderApp('/task-series/s1')
    await screen.findByRole('heading', { name: 'Weekly report', level: 1 })
    expect(screen.queryByRole('button', { name: 'إيقاف السلسلة' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'تعديل السلسلة' })).toBeNull()
  })

  it('creates a series from the tasks page with offsets, validating the date order', async () => {
    api.on('GET /tasks', { body: [] })
    api.on('POST /task-series', (b) => ({ status: 201, body: series({ ...(b as object) } as Partial<Series>) }))
    renderApp('/tasks')
    await userEvent.click(await screen.findByRole('button', { name: 'سلسلة أسبوعية جديدة' }))
    const dialog = await screen.findByRole('dialog')
    await userEvent.type(within(dialog).getByLabelText(/^العنوان/), 'Weekly report')
    await userEvent.selectOptions(within(dialog).getByLabelText(/^الوحدة/), 'u-team')
    await userEvent.type(within(dialog).getByLabelText(/أول موعد استحقاق/), '2099-01-08T10:00')
    await userEvent.type(within(dialog).getByLabelText(/تنتهي السلسلة في/), '2099-01-01T10:00')
    await userEvent.click(within(dialog).getByLabelText('Omar Ali'))
    await userEvent.click(within(dialog).getByRole('button', { name: 'إنشاء السلسلة' }))
    expect(await within(dialog).findByText('يجب أن يكون الانتهاء بعد أول موعد استحقاق.')).toBeInTheDocument()
    expect(api.calls.some((c) => c.key === 'POST /task-series')).toBe(false)

    const ends = within(dialog).getByLabelText(/تنتهي السلسلة في/)
    await userEvent.clear(ends)
    await userEvent.type(ends, '2099-01-22T10:00')
    expect(await within(dialog).findByText('سيُنشئ هذا 3 مهمة أسبوعية.')).toBeInTheDocument()
    await userEvent.click(within(dialog).getByRole('button', { name: 'إنشاء السلسلة' }))
    await waitFor(() => expect(api.calls.some((c) => c.key === 'POST /task-series')).toBe(true))
    const body = api.calls.find((c) => c.key === 'POST /task-series')?.body as CreateSeries
    expect(body.scope_unit_id).toBe('u-team')
    expect(body.first_due_at).toMatch(/Z$/)
    expect(body.ends_at).toMatch(/Z$/)
    expect(body.assignee_member_ids).toEqual(['m-omar'])
    expect(body.subtasks).toEqual([])
  })
})
