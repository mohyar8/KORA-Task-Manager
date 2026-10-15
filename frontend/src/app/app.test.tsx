import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { RequireAdmin, RequirePermission } from '@/features/auth/guards'
import { setApiHandlers } from '@/shared/api/http'
import { account, accessFor, installFakeApi } from '@/test/fakeApi'
import { Providers } from './Providers'
import { routes } from './router'

function renderRoutes(r: Parameters<typeof createMemoryRouter>[0], path: string) {
  render(
    <Providers>
      <RouterProvider router={createMemoryRouter(r, { initialEntries: [path] })} />
    </Providers>,
  )
}

describe('app shell (signed in)', () => {
  beforeEach(() => {
    localStorage.clear()
    setApiHandlers({})
    installFakeApi({
      'GET /auth/me': { body: account },
      'GET /access/me': { body: accessFor(['task.view@u-team']) },
    })
  })
  afterEach(() => vi.unstubAllGlobals())

  it('renders Home inside the shell, in Arabic RTL by default, with the account link', async () => {
    renderRoutes(routes, '/')
    expect(await screen.findByRole('heading', { level: 1, name: 'الرئيسية' })).toBeInTheDocument()
    expect(screen.getAllByRole('navigation').length).toBeGreaterThan(0)
    expect(screen.getByRole('link', { name: 'حسابي' })).toHaveAttribute('href', '/account')
    expect(document.documentElement.dir).toBe('rtl')
  })

  it('shows the not-found state for unknown routes', async () => {
    renderRoutes(routes, '/nope')
    expect(await screen.findByRole('heading', { name: 'الصفحة غير موجودة' })).toBeInTheDocument()
  })

  it('guards pages by effective permission and by System Admin grant', async () => {
    const guarded = [
      {
        element: routes[2].element,
        children: [
          { path: 'org', element: <RequirePermission permission="organization.manage"><p>org page</p></RequirePermission> },
          { path: 'tasks', element: <RequirePermission permission="task.view"><p>tasks page</p></RequirePermission> },
          { path: 'admin', element: <RequireAdmin><p>admin page</p></RequireAdmin> },
        ],
      },
    ]
    renderRoutes(guarded, '/org')
    expect(await screen.findByRole('heading', { name: 'لا تملك صلاحية الوصول' })).toBeInTheDocument()
  })

  it('lets a permitted user through a permission guard', async () => {
    const guarded = [
      {
        element: routes[2].element,
        children: [{ path: 'tasks', element: <RequirePermission permission="task.view"><p>tasks page</p></RequirePermission> }],
      },
    ]
    renderRoutes(guarded, '/tasks')
    expect(await screen.findByText('tasks page')).toBeInTheDocument()
  })
})
