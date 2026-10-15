import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { Providers } from '@/app/Providers'
import { routes } from '@/app/router'
import { setApiHandlers } from '@/shared/api/http'
import { account as baseAccount, accessFor, installFakeApi, type FakeApi } from '@/test/fakeApi'
import { currentMonth, eventChanges, groupByDay, isHttpUrl, isMonth, monthRange, shiftMonth, type CalendarEvent, type MyCalendar } from './api'

const sara = { ...baseAccount, id: 'a-sara', username: 'sara', member_id: 'm-sara' }
const directory = [
  { id: 'm-sara', full_name: 'Sara Khalid', team_id: 'u-team', role_key: 'team_leader' },
  { id: 'm-omar', full_name: 'Omar Ali', team_id: 'u-team', role_key: 'member' },
]
const access = accessFor(['task.view@u-team', 'calendar.create@u-team', 'calendar.manage@u-team'])

const event = (over: Partial<CalendarEvent> = {}): CalendarEvent => ({
  id: 'e1', type: 'meeting', title: 'Kickoff', description: null, starts_at: '2026-10-20T09:00:00Z', ends_at: '2026-10-20T10:00:00Z',
  location_text: 'Room 4', online_url: null, scope_unit_id: 'u-team', organizer_account_id: 'a-sara', organizer_member_id: 'm-sara',
  state: 'scheduled', created_at: '2026-10-10T08:00:00Z', updated_at: '2026-10-10T08:00:00Z', cancelled_at: null,
  invitee_member_ids: ['m-omar'], my_invitation: null, ...over,
})

describe('calendar helpers', () => {
  it('builds month ranges with an offset and shifts across years', () => {
    const r = monthRange('2026-10')
    expect(r.from).toMatch(/Z$/)
    expect(r.to).toMatch(/Z$/)
    expect(Date.parse(r.to)).toBeGreaterThan(Date.parse(r.from) + 27 * 86400000)
    expect(shiftMonth('2026-12', 1)).toBe('2027-01')
    expect(shiftMonth('2026-01', -1)).toBe('2025-12')
    expect(currentMonth(new Date(2026, 2, 5))).toBe('2026-03')
    expect(isMonth('2026-13')).toBe(false)
    expect(isMonth('2026-02')).toBe(true)
  })
  it('groups events and task due dates by local day in time order, clamping into the range', () => {
    const cal: MyCalendar = {
      starts_at: new Date(2026, 9, 1).toISOString(), ends_at: new Date(2026, 10, 1).toISOString(),
      events: [{ ...event({ id: 'a', starts_at: new Date(2026, 8, 30, 20).toISOString() }), item_type: 'event' }, { ...event({ id: 'b', starts_at: new Date(2026, 9, 5, 9).toISOString() }), item_type: 'event' }],
      task_due_dates: [{ item_type: 'task_due', task_id: 't', title: 'T', due_at: new Date(2026, 9, 5, 8).toISOString(), status: 'new', scope_unit_id: 'u' }],
    }
    const days = groupByDay(cal)
    expect(days.map(([k]) => k)).toEqual(['2026-10-01', '2026-10-05'])
    expect(days[1][1].map((i) => i.kind)).toEqual(['task', 'event'])
  })
  it('validates links and diffs only changed fields (including mutually exclusive place)', () => {
    expect(isHttpUrl('https://meet.example/x')).toBe(true)
    expect(isHttpUrl('javascript:alert(1)')).toBe(false)
    const e = event()
    const same = { type: e.type, title: e.title, description: e.description, starts_at: '2026-10-20T09:00:00.000Z', ends_at: e.ends_at, location_text: e.location_text, online_url: e.online_url }
    expect(eventChanges(e, same)).toEqual({})
    expect(eventChanges(e, { ...same, location_text: null, online_url: 'https://meet.example/x' })).toEqual({ location_text: null, online_url: 'https://meet.example/x' })
  })
})

function renderApp(path: string) {
  render(
    <Providers>
      <RouterProvider router={createMemoryRouter(routes, { initialEntries: [path] })} />
    </Providers>,
  )
}

describe('Calendar UI', () => {
  let api: FakeApi
  beforeEach(() => {
    localStorage.clear()
    setApiHandlers({})
    api = installFakeApi({
      'GET /auth/me': { body: sara },
      'GET /access/me': { body: access },
      'GET /organization/members': { body: directory },
      'GET /notifications': { body: [] },
      'GET /calendar': { body: {
        starts_at: '2026-10-01T00:00:00Z', ends_at: '2026-11-01T00:00:00Z',
        events: [{ ...event(), item_type: 'event' }],
        task_due_dates: [{ item_type: 'task_due', task_id: 't1', title: 'Order kits', due_at: '2026-10-20T07:00:00Z', status: 'new', scope_unit_id: 'u-team' }],
      } },
      'GET /calendar/events/e1': { body: event() },
    })
  })
  afterEach(() => vi.unstubAllGlobals())

  it('shows the month agenda with events and own task due dates, and requests offset-aware ranges', async () => {
    renderApp('/calendar?m=2026-10')
    // the grid shows squares per day; picking a day opens its list
    await userEvent.click(await screen.findByRole('button', { name: /20/ }))
    expect(await screen.findByRole('link', { name: 'Kickoff' })).toHaveAttribute('href', '/calendar/e1')
    expect(screen.getByRole('link', { name: 'Order kits' })).toHaveAttribute('href', '/tasks/t1')
    expect(screen.getByText('مواعيد استحقاق المهام هنا تخص المهام التي أنشأتها أو أُسندت إليك فقط.')).toBeInTheDocument()
    const call = api.calls.find((c) => c.key === 'GET /calendar')
    expect(call).toBeDefined()
  })

  it('moves between months', async () => {
    const router = createMemoryRouter(routes, { initialEntries: ['/calendar?m=2026-10'] })
    render(<Providers><RouterProvider router={router} /></Providers>)
    await userEvent.click(await screen.findByRole('button', { name: 'الشهر التالي' }))
    await waitFor(() => expect(router.state.location.search).toBe('?m=2026-11'))
  })

  it('creates an event with an online link, offsets and the chosen invitee', async () => {
    api.on('POST /calendar/events', (b) => ({ status: 201, body: event({ ...(b as object) } as Partial<CalendarEvent>) }))
    renderApp('/calendar?m=2026-10')
    await userEvent.click(await screen.findByRole('button', { name: /حدث جديد/ }))
    const dialog = await screen.findByRole('dialog')
    await userEvent.type(within(dialog).getByLabelText(/^العنوان/), 'Team call')
    await userEvent.type(within(dialog).getByLabelText(/^يبدأ/), '2026-10-22T18:00')
    await userEvent.type(within(dialog).getByLabelText(/^ينتهي/), '2026-10-22T17:00')
    await userEvent.selectOptions(within(dialog).getByLabelText(/^المكان/), 'online')
    await userEvent.type(within(dialog).getByLabelText(/^الرابط/), 'ftp://nope')
    await userEvent.selectOptions(within(dialog).getByLabelText(/^الوحدة/), 'u-team')
    await userEvent.click(within(dialog).getByLabelText('Omar Ali'))
    await userEvent.click(within(dialog).getByRole('button', { name: 'إنشاء' }))
    expect(await within(dialog).findByText('يجب أن يكون الانتهاء بعد البدء.')).toBeInTheDocument()
    expect(within(dialog).getByText('أدخل رابطًا يبدأ بـ http أو https.')).toBeInTheDocument()

    const ends = within(dialog).getByLabelText(/^ينتهي/)
    await userEvent.clear(ends)
    await userEvent.type(ends, '2026-10-22T19:00')
    const url = within(dialog).getByLabelText(/^الرابط/)
    await userEvent.clear(url)
    await userEvent.type(url, 'https://meet.example/abc')
    await userEvent.click(within(dialog).getByRole('button', { name: 'إنشاء' }))
    await waitFor(() => expect(api.calls.some((c) => c.key === 'POST /calendar/events')).toBe(true))
    const body = api.calls.find((c) => c.key === 'POST /calendar/events')?.body as Record<string, unknown>
    expect(body).toMatchObject({ type: 'event', title: 'Team call', online_url: 'https://meet.example/abc', location_text: null, scope_unit_id: 'u-team', invitee_member_ids: ['m-omar'] })
    expect(String(body.starts_at)).toMatch(/Z$/)
    expect(body).not.toHaveProperty('state')
  })

  it('lets the organizer cancel only after confirming', async () => {
    api.on('POST /calendar/events/e1/cancel', { body: event({ state: 'cancelled' }) })
    renderApp('/calendar/e1')
    await userEvent.click(await screen.findByRole('button', { name: 'إلغاء الحدث' }))
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByText(/لا يمكن التراجع عن ذلك/)).toBeInTheDocument()
    expect(api.calls.some((c) => c.key === 'POST /calendar/events/e1/cancel')).toBe(false)
    await userEvent.click(within(dialog).getByRole('button', { name: 'إلغاء الحدث' }))
    await waitFor(() => expect(api.calls.some((c) => c.key === 'POST /calendar/events/e1/cancel')).toBe(true))
  })

  it('is read-only when cancelled, and hides the invitee list from an invitee', async () => {
    api.on('GET /calendar/events/e1', { body: event({ state: 'cancelled', organizer_account_id: 'a-other', invitee_member_ids: null, my_invitation: { member_id: 'm-sara', invited_at: '2026-10-10T08:00:00Z' } }) })
    api.on('GET /access/me', { body: accessFor(['task.view@u-team']) })
    renderApp('/calendar/e1')
    expect(await screen.findByText('هذا الحدث ملغى ولم يعد قابلًا للتغيير.')).toBeInTheDocument()
    expect(screen.getByText('أنت مدعو. قائمة المدعوين الكاملة ظاهرة للمنظّم والمديرين فقط.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'تعديل' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'إضافة مدعو' })).toBeNull()
  })
})
