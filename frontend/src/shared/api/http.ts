// The only place that calls fetch. Same-origin, cookie session, CSRF header on unsafe methods.
// Contract: API_CONTRACT.md §1.2 (errors), §2 (cookies, CSRF).

const BASE = '/api/v1'
const CSRF_COOKIE = 'kora_csrf'
const PASSWORD_CHANGE_REQUIRED = 'Password change required.'

export interface ValidationIssue {
  type: string
  loc: (string | number)[]
  msg: string
  ctx?: unknown
}

/** 422 `detail` is a list of issues (schema) or a string (business rule); other errors use a string. */
export type ErrorDetail = string | ValidationIssue[] | null

export class ApiError extends Error {
  readonly status: number
  readonly detail: ErrorDetail
  /** Seconds, from the `Retry-After` header on 429. */
  readonly retryAfter: number | null

  constructor(status: number, detail: ErrorDetail, retryAfter: number | null = null) {
    super(formatDetail(detail) || `HTTP ${status}`)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
    this.retryAfter = retryAfter
  }
}

export function formatDetail(detail: ErrorDetail): string {
  if (detail == null) return ''
  if (typeof detail === 'string') return detail
  return detail.map((i) => `${i.loc.filter((p) => p !== 'body').join('.')}: ${i.msg}`).join('; ')
}

/** Field-level messages from a 422 validation list, keyed by the last `loc` segment. */
export function fieldErrors(error: unknown): Record<string, string> {
  const out: Record<string, string> = {}
  if (error instanceof ApiError && Array.isArray(error.detail)) {
    for (const issue of error.detail) {
      const key = String(issue.loc[issue.loc.length - 1] ?? '')
      if (key && !(key in out)) out[key] = issue.msg
    }
  }
  return out
}

interface Handlers {
  /** Any 401 other than a failed sign-in: the session has ended. */
  onUnauthorized?: () => void
  /** 403 "Password change required." */
  onPasswordChangeRequired?: () => void
}
let handlers: Handlers = {}
export function setApiHandlers(next: Handlers) {
  handlers = next
}

let csrfFallback: string | null = null
/** Token returned in the body of sign-in / change-password; used only if the cookie is unreadable. */
export function setCsrfToken(token: string | null) {
  csrfFallback = token
}

function readCsrf(): string | null {
  const match = document.cookie.split('; ').find((c) => c.startsWith(`${CSRF_COOKIE}=`))
  return match ? decodeURIComponent(match.slice(CSRF_COOKIE.length + 1)) : csrfFallback
}

export type Query = Record<string, string | number | boolean | null | undefined>

function buildUrl(path: string, query?: Query): string {
  const params = new URLSearchParams()
  for (const [k, v] of Object.entries(query ?? {})) {
    if (v !== undefined && v !== null && v !== '') params.set(k, String(v))
  }
  const qs = params.toString()
  return `${BASE}${path}${qs ? `?${qs}` : ''}`
}

interface Options {
  query?: Query
  body?: unknown
  /** The caller expects a possible 401 (sign-in failure, or the boot-time "who am I" probe): it is not a session expiry. */
  expectUnauthorized?: boolean
}

async function request<T>(method: string, path: string, opts: Options = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (opts.body !== undefined) headers['Content-Type'] = 'application/json'
  if (method !== 'GET' && method !== 'HEAD') {
    const token = readCsrf()
    if (token) headers['X-CSRF-Token'] = token
  }

  let response: Response
  try {
    response = await fetch(buildUrl(path, opts.query), {
      method,
      headers,
      credentials: 'same-origin',
      body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
    })
  } catch {
    throw new ApiError(0, null) // network failure → ConnectionFailure state
  }

  if (response.ok) {
    if (response.status === 204) return undefined as T
    return (await response.json()) as T
  }

  let detail: ErrorDetail = null
  try {
    detail = ((await response.json()) as { detail?: ErrorDetail }).detail ?? null
  } catch {
    /* non-JSON error body */
  }
  const retry = Number(response.headers.get('Retry-After'))
  const error = new ApiError(response.status, detail, Number.isFinite(retry) && retry > 0 ? retry : null)

  if (response.status === 401 && !opts.expectUnauthorized) handlers.onUnauthorized?.()
  if (response.status === 403 && detail === PASSWORD_CHANGE_REQUIRED) handlers.onPasswordChangeRequired?.()
  throw error
}

export const http = {
  get: <T>(path: string, query?: Query, opts?: Pick<Options, 'expectUnauthorized'>) =>
    request<T>('GET', path, { query, ...opts }),
  post: <T>(path: string, body?: unknown, opts?: Pick<Options, 'expectUnauthorized'>) =>
    request<T>('POST', path, { body, ...opts }),
  put: <T>(path: string, body?: unknown) => request<T>('PUT', path, { body }),
  patch: <T>(path: string, body?: unknown) => request<T>('PATCH', path, { body }),
}
