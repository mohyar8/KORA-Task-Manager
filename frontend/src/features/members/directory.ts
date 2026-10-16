import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { http } from '@/shared/api/http'
import { useT } from '@/shared/i18n/i18n'
import { useSession } from '@/features/auth/session'
import type { RoleKey } from '@/features/access/types'
import { useMembers } from './api'

// Contract §8.1a: names and placement of the Members the caller works with (no contact data).
export interface DirectoryMember {
  id: string
  full_name: string
  team_id: string | null
  role_key: RoleKey | null
}

const isTop = (role: RoleKey | null) => role === 'event_project_leader' || role === 'deputy_leader'
// Roles that may give the Event Leader or Deputy a task (the server enforces the same rule).
const canAssignTop = (role: RoleKey | null) =>
  role === 'team_leader' || role === 'administration_manager' || role === 'pmo_leader' || isTop(role)

export const directoryKey = ['members', 'directory'] as const

export const useMemberDirectory = () =>
  useQuery({ queryKey: directoryKey, queryFn: () => http.get<DirectoryMember[]>('/organization/members'), staleTime: 60_000 })

/** The signed-in person's own name (their Member record); accounts without a Member fall back to the username. */
export function useDisplayName(): string {
  const { account } = useSession()
  const directory = useMemberDirectory()
  const own = account?.member_id ? directory.data?.find((m) => m.id === account.member_id) : undefined
  return own?.full_name ?? account?.username ?? ''
}

/**
 * Member names and the assignable list. Everyone gets the scoped lookup; System Admins additionally know every
 * Member through /admin/members (so even deactivated people keep their names in history).
 */
export function useMemberNames() {
  const t = useT()
  const { account } = useSession()
  const directory = useMemberDirectory()
  const isAdmin = !!account?.is_system_admin
  const admin = useMembers(isAdmin)

  return useMemo(() => {
    const byId = new Map<string, DirectoryMember>()
    for (const m of directory.data ?? []) byId.set(m.id, m)
    const adminNames = new Map<string, string>()
    for (const m of admin.data ?? []) {
      adminNames.set(m.id, m.full_name)
      if (m.status === 'active' && !byId.has(m.id)) {
        byId.set(m.id, { id: m.id, full_name: m.full_name, team_id: m.team_id, role_key: m.role_key })
      }
    }
    const me = account?.member_id ? byId.get(account.member_id) : undefined
    const all = [...byId.values()].sort((a, b) => a.full_name.localeCompare(b.full_name))
    return {
      isLoading: directory.isPending || (isAdmin && admin.isPending),
      error: directory.error,
      /** Active Members the caller may pick. */
      members: me && isTop(me.role_key) ? all : all.filter((m) => !isTop(m.role_key)),
      /** Event Leader / Deputy: assignable to any task, but only by leaders and managers. */
      leadership: canAssignTop(me?.role_key ?? null) ? all.filter((m) => isTop(m.role_key)) : [],
      /** Never fails: Members outside the caller's view get a neutral label (contract §8.1a). */
      nameOf: (id: string | null | undefined) =>
        (id && (byId.get(id)?.full_name ?? adminNames.get(id))) || t('members.unavailable'),
    }
  }, [directory.data, directory.error, directory.isPending, admin.data, admin.isPending, isAdmin, account, t])
}
