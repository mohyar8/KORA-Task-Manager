import { createContext, useContext } from 'react'
import type { Account, EffectiveAccess, SessionResponse } from './types'

export type SessionStatus =
  | 'loading' // first "who am I" in flight
  | 'anonymous' // not signed in (or session ended)
  | 'passwordChange' // signed in with a temporary password: only change-password / sign-out work
  | 'ready' // signed in; access loaded
  | 'error' // could not reach the platform / unexpected failure

export interface SessionValue {
  status: SessionStatus
  account: Account | null
  access: EffectiveAccess | null
  /** True when a signed-in session ended underneath the user (vs. never having signed in). */
  expired: boolean
  /** The user signed out on purpose: the next sign-in should start at Home, not at the page they left. */
  signedOut: boolean
  error: unknown
  retry: () => void
  /** Adopt the session returned by sign-in or change-password. */
  applySession: (s: SessionResponse) => void
  /** Drop all session-bound state after sign-out / sign-out-all. */
  endSession: () => void
}

export const SessionContext = createContext<SessionValue | null>(null)

export function useSession(): SessionValue {
  const ctx = useContext(SessionContext)
  if (!ctx) throw new Error('useSession must be used inside <SessionProvider>')
  return ctx
}
