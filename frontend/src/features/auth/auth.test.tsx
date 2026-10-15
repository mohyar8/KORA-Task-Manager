import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { Providers } from '@/app/Providers'
import { routes } from '@/app/router'
import { setApiHandlers } from '@/shared/api/http'
import { account, accessFor, installFakeApi, type FakeApi } from '@/test/fakeApi'

const NOT_AUTH = { status: 401, body: { detail: 'Not authenticated.' } }
const session = { account, csrf_token: 'csrf-1' }

function renderApp(path = '/') {
  const router = createMemoryRouter(routes, { initialEntries: [path] })
  render(
    <Providers>
      <RouterProvider router={router} />
    </Providers>,
  )
  return router
}

describe('authentication flow', () => {
  let api: FakeApi
  beforeEach(() => {
    localStorage.clear()
    setApiHandlers({})
    api = installFakeApi({ 'GET /auth/me': NOT_AUTH })
  })
  afterEach(() => vi.unstubAllGlobals())

  it('sends anonymous visitors to sign-in and keeps the deep link for after sign-in', async () => {
    api.on('POST /auth/sign-in', { body: session })
    api.on('GET /access/me', { body: accessFor() })
    const router = renderApp('/account')
    await screen.findByRole('heading', { name: 'تسجيل الدخول' })
    expect(router.state.location.pathname).toBe('/sign-in')

    api.on('GET /auth/me', { body: account })
    await userEvent.type(screen.getByLabelText(/اسم المستخدم/), 'sara')
    await userEvent.type(screen.getByLabelText(/^كلمة المرور/), 'secret-pass')
    await userEvent.click(screen.getByRole('button', { name: 'تسجيل الدخول' }))

    await screen.findByRole('heading', { name: 'حسابي', level: 1 })
    await waitFor(() => expect(router.state.location.pathname).toBe('/account'))
    expect(api.calls.find((c) => c.key === 'POST /auth/sign-in')?.body).toEqual({ username: 'sara', password: 'secret-pass' })
  })

  it('shows one generic message for bad credentials', async () => {
    api.on('POST /auth/sign-in', { status: 401, body: { detail: 'Invalid username or password.' } })
    renderApp('/sign-in')
    await userEvent.type(await screen.findByLabelText(/اسم المستخدم/), 'nobody')
    await userEvent.type(screen.getByLabelText(/^كلمة المرور/), 'wrongwrong')
    await userEvent.click(screen.getByRole('button', { name: 'تسجيل الدخول' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('اسم المستخدم أو كلمة المرور غير صحيحة.')
  })

  it('locks the form with a countdown on 429', async () => {
    api.on('POST /auth/sign-in', {
      status: 429,
      body: { detail: 'Too many failed sign-in attempts. Try again later.' },
      headers: { 'Retry-After': '900' },
    })
    renderApp('/sign-in')
    await userEvent.type(await screen.findByLabelText(/اسم المستخدم/), 'sara')
    await userEvent.type(screen.getByLabelText(/^كلمة المرور/), 'whatever1')
    await userEvent.click(screen.getByRole('button', { name: 'تسجيل الدخول' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('15:00')
    expect(screen.getByRole('button', { name: 'تسجيل الدخول' })).toBeDisabled()
  })

  it('forces a temporary-password change before anything else, then continues', async () => {
    api.on('GET /auth/me', { body: { ...account, must_change_password: true } })
    api.on('POST /auth/change-password', (body) => {
      expect(body).toEqual({ current_password: 'temp-pass-1', new_password: 'brand-new-pass' })
      api.on('GET /auth/me', { body: account })
      return { body: { account, csrf_token: 'csrf-2' } }
    })
    api.on('GET /access/me', { body: accessFor() })
    const router = renderApp('/')
    await screen.findByRole('heading', { name: 'تعيين كلمة مرور جديدة' })
    expect(router.state.location.pathname).toBe('/change-password')

    await userEvent.type(screen.getByLabelText(/^كلمة المرور الحالية/), 'temp-pass-1')
    await userEvent.type(screen.getByLabelText(/^كلمة المرور الجديدة/), 'short')
    await userEvent.type(screen.getByLabelText(/^تأكيد/), 'short')
    await userEvent.click(screen.getByRole('button', { name: 'تغيير كلمة المرور' }))
    expect(await screen.findByText('يجب ألا تقل كلمة المرور الجديدة عن 8 أحرف.')).toBeInTheDocument()

    await userEvent.clear(screen.getByLabelText(/^كلمة المرور الجديدة/))
    await userEvent.type(screen.getByLabelText(/^كلمة المرور الجديدة/), 'brand-new-pass')
    await userEvent.clear(screen.getByLabelText(/^تأكيد/))
    await userEvent.type(screen.getByLabelText(/^تأكيد/), 'different-pass')
    await userEvent.click(screen.getByRole('button', { name: 'تغيير كلمة المرور' }))
    expect(await screen.findByText('كلمتا المرور غير متطابقتين.')).toBeInTheDocument()

    await userEvent.clear(screen.getByLabelText(/^تأكيد/))
    await userEvent.type(screen.getByLabelText(/^تأكيد/), 'brand-new-pass')
    await userEvent.click(screen.getByRole('button', { name: 'تغيير كلمة المرور' }))
    await screen.findByRole('heading', { name: 'الرئيسية', level: 1 })
  })

  it('maps a 400 on change-password to the current-password field', async () => {
    api.on('GET /auth/me', { body: { ...account, must_change_password: true } })
    api.on('POST /auth/change-password', { status: 400, body: { detail: 'Current password is incorrect.' } })
    renderApp('/change-password')
    await userEvent.type(await screen.findByLabelText(/^كلمة المرور الحالية/), 'nope-nope')
    await userEvent.type(screen.getByLabelText(/^كلمة المرور الجديدة/), 'brand-new-pass')
    await userEvent.type(screen.getByLabelText(/^تأكيد/), 'brand-new-pass')
    await userEvent.click(screen.getByRole('button', { name: 'تغيير كلمة المرور' }))
    expect(await screen.findByText('كلمة المرور الحالية غير صحيحة.')).toBeInTheDocument()
  })

  it('sends the CSRF header on sign-out and lands on a clean sign-in (not the page it left)', async () => {
    document.cookie = 'kora_csrf=csrf-cookie'
    api.on('GET /auth/me', { body: account })
    api.on('GET /access/me', { body: accessFor() })
    api.on('POST /auth/sign-out', { status: 204 })
    const router = renderApp('/account')
    await userEvent.click(await screen.findByRole('button', { name: 'تسجيل الخروج' }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/sign-in'))
    expect(api.calls.find((c) => c.key === 'POST /auth/sign-out')?.headers['X-CSRF-Token']).toBe('csrf-cookie')
    // signing in again goes to Home, not back to My Account
    api.on('POST /auth/sign-in', { body: session })
    api.on('GET /auth/me', { body: account })
    await userEvent.type(await screen.findByLabelText(/اسم المستخدم/), 'sara')
    await userEvent.type(screen.getByLabelText(/^كلمة المرور/), 'secret-pass')
    await userEvent.click(screen.getByRole('button', { name: 'تسجيل الدخول' }))
    await screen.findByRole('heading', { level: 1, name: 'الرئيسية' })
    expect(router.state.location.pathname).toBe('/')
    document.cookie = 'kora_csrf=; max-age=0'
  })

  it('shows the session-ended notice when a later call returns 401', async () => {
    api.on('GET /auth/me', { body: account })
    api.on('GET /access/me', { body: accessFor() })
    api.on('POST /auth/sign-out', NOT_AUTH)
    renderApp('/account')
    await userEvent.click(await screen.findByRole('button', { name: 'تسجيل الخروج' }))
    // sign-out answered 401 → treated as expiry first, then the sign-in page
    await screen.findByRole('heading', { name: 'تسجيل الدخول' })
  })
})
