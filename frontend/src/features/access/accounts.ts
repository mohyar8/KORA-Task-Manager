import { useMemo } from 'react'
import { useSession } from '@/features/auth/session'
import { useMembers } from '@/features/members/api'
import { useSystemAdmins } from './api'

export interface AccountOption {
  accountId: string
  label: string
  isSelf: boolean
}

/**
 * Accounts an Admin can act on: their own, every Member's account, and System Admin accounts.
 * (There is no account-list endpoint; the first admin has an account but is not a Member.)
 */
export function useAccountOptions(): { options: AccountOption[]; isLoading: boolean; error: unknown } {
  const { account } = useSession()
  const members = useMembers()
  const admins = useSystemAdmins()

  const options = useMemo(() => {
    const byId = new Map<string, AccountOption>()
    for (const a of admins.data ?? []) byId.set(a.account_id, { accountId: a.account_id, label: a.username, isSelf: false })
    for (const m of members.data ?? []) byId.set(m.account_id, { accountId: m.account_id, label: `${m.full_name} (${m.username})`, isSelf: false })
    if (account) byId.set(account.id, { accountId: account.id, label: byId.get(account.id)?.label ?? account.username, isSelf: true })
    return [...byId.values()].sort((a, b) => a.label.localeCompare(b.label))
  }, [account, members.data, admins.data])

  return { options, isLoading: members.isPending || admins.isPending, error: members.error ?? admins.error }
}
