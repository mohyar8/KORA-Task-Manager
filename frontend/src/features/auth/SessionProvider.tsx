import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query'
import { setApiHandlers, setCsrfToken } from '@/shared/api/http'
import { accessKey, fetchAccess, fetchMe, meKey } from './api'
import { SessionContext, type SessionStatus, type SessionValue } from './session'
import type { Account, SessionResponse } from './types'

/** Forget everything fetched on behalf of the ended session (never keep another user's data in the cache). */
function dropSessionData(queryClient: QueryClient) {
  queryClient.removeQueries({ predicate: (q) => q.queryKey[0] !== 'session' })
  queryClient.removeQueries({ queryKey: accessKey })
  queryClient.setQueryData<Account | null>(meKey, null)
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [expired, setExpired] = useState(false)
  const [signedOut, setSignedOut] = useState(false)

  const me = useQuery({ queryKey: meKey, queryFn: fetchMe, staleTime: 5 * 60_000 })
  const account = me.data ?? null
  const needsPasswordChange = !!account?.must_change_password

  const access = useQuery({
    queryKey: accessKey,
    queryFn: fetchAccess,
    enabled: !!account && !needsPasswordChange,
    staleTime: 60_000,
    refetchOnWindowFocus: true, // an Admin may have changed this user's access
  })

  // A 401 on any call after we knew the user means the session ended; a 403 "Password change required." means the
  // temporary-password gate closed on us.
  useEffect(() => {
    setApiHandlers({
      onUnauthorized: () => {
        if (queryClient.getQueryData(meKey)) {
          setExpired(true)
          dropSessionData(queryClient)
        }
      },
      onPasswordChangeRequired: () => void queryClient.invalidateQueries({ queryKey: meKey }),
    })
  }, [queryClient])

  const applySession = useCallback(
    (s: SessionResponse) => {
      setCsrfToken(s.csrf_token)
      setExpired(false)
      setSignedOut(false)
      queryClient.setQueryData<Account | null>(meKey, s.account)
      void queryClient.invalidateQueries({ queryKey: accessKey })
    },
    [queryClient],
  )

  const endSession = useCallback(() => {
    setCsrfToken(null)
    setExpired(false)
    setSignedOut(true)
    dropSessionData(queryClient)
  }, [queryClient])

  const retry = useCallback(() => {
    void me.refetch()
    void access.refetch()
  }, [me, access])

  let status: SessionStatus
  if (me.isPending) status = 'loading'
  else if (me.isError) status = 'error'
  else if (!account) status = 'anonymous'
  else if (needsPasswordChange) status = 'passwordChange'
  else if (access.isError) status = 'error'
  else if (access.data) status = 'ready'
  else status = 'loading'

  const value = useMemo<SessionValue>(
    () => ({
      status,
      account,
      access: access.data ?? null,
      expired,
      signedOut,
      error: me.error ?? access.error,
      retry,
      applySession,
      endSession,
    }),
    [status, account, access.data, expired, signedOut, me.error, access.error, retry, applySession, endSession],
  )

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
}
