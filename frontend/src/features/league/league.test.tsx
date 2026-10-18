import { beforeEach, describe, expect, it } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { Providers } from '@/app/Providers'
import { routes } from '@/app/router'
import { setApiHandlers } from '@/shared/api/http'
import { account, accessFor, installFakeApi, type FakeApi } from '@/test/fakeApi'

const league = {
  round_title: 'الجولة الأولى',
  updated_at: '2026-10-19T10:00:00Z',
  standings: [
    { rank: 1, team_id: 't-a', team_name: 'تصميم المعرض', administration_name: 'إدارة تصميم الحدث', points: 6 },
    { rank: 2, team_id: 't-b', team_name: 'التقنية', administration_name: 'إدارة التقنية', points: 5 },
  ],
}

function renderApp(allowed: string[]) {
  const api: FakeApi = installFakeApi({
    'GET /auth/me': { body: { ...account, member_id: 'm1' } },
    'GET /access/me': { body: accessFor(allowed) },
    'GET /organization/members': { body: [] },
    'GET /league': { body: league },
    'GET /notifications': { body: [] },
  })
  render(
    <Providers>
      <RouterProvider router={createMemoryRouter(routes, { initialEntries: ['/league'] })} />
    </Providers>,
  )
  return api
}

describe('League', () => {
  beforeEach(() => {
    localStorage.clear()
    setApiHandlers({})
  })

  it('shows the table to everyone, without an edit button', async () => {
    renderApp([])
    const table = await screen.findByRole('list', { name: 'دوري كورة' })
    expect(within(table).getAllByRole('listitem')).toHaveLength(2)
    expect(screen.getAllByText('الجولة الأولى').length).toBeGreaterThan(0)
    expect(screen.queryByRole('button', { name: /تعديل النتائج/ })).toBeNull()
  })

  it('lets the PMO Leader change points and the round title', async () => {
    const api = renderApp(['league.manage@u-kora'])
    api.on('PUT /league', (b) => ({ body: { ...league, round_title: (b as { round_title: string }).round_title } }))
    await userEvent.click(await screen.findByRole('button', { name: /تعديل النتائج/ }))
    await userEvent.click(screen.getByRole('button', { name: 'زيادة نقاط التقنية' }))
    await userEvent.click(screen.getByRole('button', { name: 'حفظ' }))
    await waitFor(() => expect(api.calls.find((c) => c.key === 'PUT /league')?.body).toEqual({
      round_title: 'الجولة الأولى',
      points: [{ team_id: 't-a', points: 6 }, { team_id: 't-b', points: 6 }],
    }))
  })
})
