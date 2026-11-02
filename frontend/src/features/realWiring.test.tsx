import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { Providers } from '@/app/Providers'
import { routes } from '@/app/router'
import { setApiHandlers } from '@/shared/api/http'
import { account as baseAccount, accessFor, installFakeApi, type FakeApi } from '@/test/fakeApi'
import { uploadTaskFile } from '@/features/tasks/filesApi'
import { PrivateNote } from '@/features/notes/PrivateNote'

// The app talks to the real backend unless VITE_MOCK=true; the rest of the suite runs in mock mode.
const sara = { ...baseAccount, id: 'a-sara', username: 'sara', member_id: 'm-sara' }
const directory = [
  { id: 'm-sara', full_name: 'Sara Khalid', team_id: 'u-team', role_key: 'administration_manager' },
  { id: 'm-omar', full_name: 'Omar Ali', team_id: 'u-team', role_key: 'member' },
]
const structure = {
  unit_id: 'u-kora', name: 'KORA', kind: 'organization', leader_ids: ['m-boss'],
  members: [{ member_id: 'm-boss', full_name: 'Boss Leader', role_key: 'event_project_leader' }],
  children: [
    {
      unit_id: 'u-admin', name: 'Admin B', kind: 'administration', leader_ids: ['m-sara'],
      members: [{ member_id: 'm-sara', full_name: 'Sara Khalid', role_key: 'administration_manager' }],
      children: [{ unit_id: 'u-team', name: 'Team A', kind: 'team', leader_ids: [], members: [{ member_id: 'm-omar', full_name: 'Omar Ali', role_key: 'member' }], children: [] }],
    },
    { unit_id: 'u-other', name: 'Admin C', kind: 'administration', leader_ids: [], members: [], children: [] },
  ],
}
const access = accessFor(['task.view@u-admin', 'task_request.create@u-admin', 'task_request.respond@u-admin', 'chat.moderate@u-admin'], true)

function renderApp(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] })
  render(<Providers><RouterProvider router={router} /></Providers>)
  return router
}

describe('real backend wiring', () => {
  let api: FakeApi
  beforeEach(() => {
    vi.stubEnv('VITE_MOCK', 'false')
    localStorage.clear()
    setApiHandlers({})
    api = installFakeApi({
      'GET /auth/me': { body: sara },
      'GET /access/me': { body: access },
      'GET /organization/members': { body: directory },
      'GET /organization/structure': { body: structure },
      'GET /notifications': { body: [] },
      'GET /announcements': { body: [] },
      'GET /me/summary': { body: { notifications_unread: 0, chat_unread: 7, requests_pending: 3, announcements_unread: 0, reviews_open: 0 } },
    })
  })
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.unstubAllEnvs()
  })

  it('draws the structure the server sends and highlights your own unit', async () => {
    renderApp('/structure')
    expect(await screen.findByRole('group', { name: 'Admin B' })).toBeInTheDocument()
    expect(screen.getByRole('group', { name: 'Team A' })).toBeInTheDocument()
    expect(screen.getByRole('group', { name: 'Admin C' })).toBeInTheDocument()
    expect(within(screen.getByRole('group', { name: 'Team A' })).getByText('Omar Ali')).toBeInTheDocument()
  })

  it('shows the badge counts from /me/summary', async () => {
    api.on('GET /tasks', { body: [] })
    renderApp('/')
    await waitFor(() => expect(api.calls.some((c) => c.key === 'GET /me/summary')).toBe(true))
    expect((await screen.findAllByLabelText(/7/)).length).toBeGreaterThan(0)
  })

  it('answers a request with the people of the target Administration', async () => {
    const request = {
      id: 'r1', title: 'Banner', description: 'Two metres', priority: 'high', due_at: null, from_unit_id: 'u-other', to_unit_id: 'u-admin',
      requested_by_member_id: 'm-boss', status: 'pending', decided_by_member_id: null, decided_at: null, rejection_reason: null, resulting_task_id: null, created_at: '2026-10-28T10:00:00Z',
    }
    api.on('GET /task-requests', { body: [request] })
    api.on('POST /task-requests/r1/accept', { body: { ...request, status: 'accepted', resulting_task_id: 't9' } })
    renderApp('/requests')
    expect(await screen.findByRole('heading', { name: 'Banner' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'الرد على الطلب' }))
    await userEvent.click(await screen.findByLabelText('Omar Ali'))
    await userEvent.click(screen.getByRole('button', { name: 'قبول' }))
    await waitFor(() => expect(api.calls.find((c) => c.key === 'POST /task-requests/r1/accept')?.body).toEqual({ assignee_member_ids: ['m-omar'] }))
  })

  it('sends a chat message to the conversation and shows it', async () => {
    const message = (id: number, body: string, author: string) => ({ id, conversation_id: 'c1aaaaaa-0000', author_member_id: author, body, created_at: '2026-10-28T10:00:00Z', edited_at: null, deleted: false })
    api.on('GET /chat/conversations', { body: [{ id: 'c1aaaaaa-0000', kind: 'direct', unit_id: null, other_member_id: 'm-omar', last_message: null, unread: 0 }] })
    api.on('GET /chat/conversations/c1aaaaaa-0000/messages', { body: [message(1, 'Hello Sara', 'm-omar')] })
    api.on('POST /chat/conversations/c1aaaaaa-0000/messages', (body) => ({ status: 201, body: message(2, (body as { body: string }).body, 'm-sara') }))
    renderApp('/chat/c1aaaaaa-0000')
    expect(await screen.findByText('Hello Sara')).toBeInTheDocument()
    await userEvent.type(screen.getByPlaceholderText('اكتب رسالة'), 'On my way{Enter}')
    await waitFor(() => expect(api.calls.find((c) => c.key === 'POST /chat/conversations/c1aaaaaa-0000/messages')?.body).toEqual({ body: 'On my way' }))
    expect(await screen.findByText('On my way')).toBeInTheDocument()
  })

  it('opens a private chat from the structure link before showing it', async () => {
    api.on('POST /chat/conversations/direct', { body: { id: 'c2aaaaaa-0000', kind: 'direct', unit_id: null, other_member_id: 'm-omar', last_message: null, unread: 0 } })
    api.on('GET /chat/conversations', { body: [] })
    const router = renderApp('/chat/dm:m-omar')
    await waitFor(() => expect(router.state.location.pathname).toBe('/chat/c2aaaaaa-0000'))
    expect(api.calls.find((c) => c.key === 'POST /chat/conversations/direct')?.body).toEqual({ member_id: 'm-omar' })
  })

  it('uploads a file straight to the bucket in three steps', async () => {
    const file = { id: 'f1', task_id: 't1', kind: 'brief', name: 'plan.pdf', size: 3, content_type: null, uploaded_by_member_id: 'm-sara', created_at: '2026-10-28T10:00:00Z' }
    const seen: string[] = []
    // The shared fake parses bodies as JSON; this one carries raw bytes to the bucket.
    vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
      seen.push(`${init?.method ?? 'GET'} ${url.split('?')[0]}`)
      if (url.startsWith('https://bucket.test')) return new Response(null, { status: 200 })
      if (url.endsWith('/complete')) return new Response(JSON.stringify(file), { status: 200 })
      return new Response(JSON.stringify({ file, upload_url: 'https://bucket.test/tasks/t1/f1?sig=1', expires_in: 600 }), { status: 201 })
    }))
    await uploadTaskFile('t1', 'brief', new File(['abc'], 'plan.pdf'))
    expect(seen).toEqual(['POST /api/v1/tasks/t1/files', 'PUT https://bucket.test/tasks/t1/f1', 'POST /api/v1/tasks/t1/files/f1/complete'])
  })

  it('keeps the private note on the server and moves a browser copy there once', async () => {
    localStorage.setItem('kora.mock.note.a-sara', '• from the browser')
    api.on('GET /me/note', { body: { body: '', version: 0, updated_at: null } })
    api.on('PUT /me/note', (body) => ({ body: { body: (body as { body: string }).body, version: 1, updated_at: '2026-10-28T10:00:00Z' } }))
    render(<Providers><PrivateNote /></Providers>)
    const box = await screen.findByRole('textbox')
    await waitFor(() => expect(box).toHaveValue('• from the browser'))
    await waitFor(() => expect(api.calls.find((c) => c.key === 'PUT /me/note')?.body).toEqual({ body: '• from the browser', version: 0 }))
    await waitFor(() => expect(localStorage.getItem('kora.mock.note.a-sara')).toBeNull())
  })
})
