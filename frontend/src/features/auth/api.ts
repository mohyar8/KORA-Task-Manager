import { ApiError, http } from '@/shared/api/http'
import type { Account, EffectiveAccess, SessionResponse } from './types'

// Contract §6. All HTTP for auth lives here.

export const meKey = ['session', 'me'] as const
export const accessKey = ['session', 'access'] as const

/** The boot-time "who am I" probe: a 401 just means "not signed in" (null), not an expired session. */
export async function fetchMe(): Promise<Account | null> {
  try {
    return await http.get<Account>('/auth/me', undefined, { expectUnauthorized: true })
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) return null
    throw e
  }
}

export const fetchAccess = () => http.get<EffectiveAccess>('/access/me')

export const signIn = (username: string, password: string) =>
  http.post<SessionResponse>('/auth/sign-in', { username, password }, { expectUnauthorized: true })

export const signOut = () => http.post<void>('/auth/sign-out')

export const changePassword = (current_password: string, new_password: string) =>
  http.post<SessionResponse>('/auth/change-password', { current_password, new_password })
