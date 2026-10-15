import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { Providers } from '@/app/Providers'
import { routes } from '@/app/router'
import { setApiHandlers } from '@/shared/api/http'
import { account as baseAccount, accessFor, installFakeApi, type FakeApi } from '@/test/fakeApi'
import type { Task } from './types'

const sara = { ...baseAccount, id: 'a-sara', username: 'sara', member_id: 'm-sara' }
const access = accessFor(['task.view@u-team', 'task.create@u-team', 'task.manage@u-team'])
const task = (over: Partial<Task>): Task => ({
  id: 't1', title: 'Order kits', description: null, priority: 'high', due_at: null, status: 'new', scope_unit_id: 'u-team', parent_id: null,
  series_id: null, created_by_account_id: 'a-sara', created_by_member_id: 'm-sara', created_at: '2026-10-10T08:00:00Z',
  updated_at: '2026-10-10T08:00:00Z', started_at: null, assignee_member_ids: ['m-sara'], ...over,
})

describe('Task board', () => {
  let api: FakeApi
  beforeEach(() => {
    localStorage.clear()
    setApiHandlers({})
    api = installFakeApi({
      'GET /auth/me': { body: sara },
      'GET /access/me': { body: access },
      'GET /organization/members': { body: [{ id: 'm-sara', full_name: 'Sara Khalid', team_id: 'u-team', role_key: 'team_leader' }] },
      'GET /tasks': { body: [task({}), task({ id: 't2', title: 'Book pitch', status: 'in_progress' })] },
    })
  })
  afterEach(() => vi.unstubAllGlobals())

  const open = async () => {
    render(<Providers><RouterProvider router={createMemoryRouter(routes, { initialEntries: ['/tasks?view=board'] })} /></Providers>)
    return screen.findByRole('region', { name: 'جديدة' })
  }

  it('puts each task in its status column', async () => {
    const col = await open()
    expect(within(col).getByRole('link', { name: 'Order kits' })).toBeInTheDocument()
    expect(within(screen.getByRole('region', { name: 'قيد التنفيذ' })).getByRole('link', { name: 'Book pitch' })).toBeInTheDocument()
  })

  it('moves a card to an allowed column by drag and drop', async () => {
    api.on('POST /tasks/t1/status', { body: task({ status: 'in_progress' }) })
    const col = await open()
    const card = within(col).getByRole('link', { name: 'Order kits' }).closest('li')!
    const target = screen.getByRole('region', { name: 'قيد التنفيذ' })
    const data = { effectAllowed: '', setData: vi.fn() }
    fireEvent.dragStart(card, { dataTransfer: data })
    fireEvent.dragOver(target, { dataTransfer: data })
    fireEvent.drop(target, { dataTransfer: data })
    await waitFor(() => expect(api.calls.find((c) => c.key === 'POST /tasks/t1/status')?.body).toEqual({ status: 'in_progress' }))
  })

  it('asks for confirmation before cancelling via the keyboard-friendly select', async () => {
    api.on('POST /tasks/t1/status', { body: task({ status: 'cancelled' }) })
    const col = await open()
    await userEvent.selectOptions(within(col).getByLabelText(/Order kits/), 'cancelled')
    const dialog = await screen.findByRole('dialog')
    expect(api.calls.some((c) => c.key === 'POST /tasks/t1/status')).toBe(false)
    await userEvent.click(within(dialog).getByRole('button', { name: 'إلغاء المهمة' }))
    await waitFor(() => expect(api.calls.find((c) => c.key === 'POST /tasks/t1/status')?.body).toEqual({ status: 'cancelled' }))
  })

  it('ignores a drop on the own column', async () => {
    const col = await open()
    const card = within(col).getByRole('link', { name: 'Order kits' }).closest('li')!
    const data = { effectAllowed: '', setData: vi.fn() }
    fireEvent.dragStart(card, { dataTransfer: data })
    fireEvent.drop(col, { dataTransfer: data })
    expect(api.calls.some((c) => c.key === 'POST /tasks/t1/status')).toBe(false)
  })
})
