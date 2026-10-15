import { useMemo } from 'react'
import { useSession } from '@/features/auth/session'
import type { Viewer } from './rules'

/** Who the signed-in user is for task rules: their Member id (null for non-Member accounts) and access. */
export function useViewer(): Viewer {
  const { account, access } = useSession()
  return useMemo(() => ({ memberId: account?.member_id ?? null, accountId: account?.id ?? '', access }), [account, access])
}
