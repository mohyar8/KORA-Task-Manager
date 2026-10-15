import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { http } from '@/shared/api/http'
import type { Member, MemberProfile, RoleFields } from './types'

// Contract §8.2 — System Admin only. Do NOT call for non-admin accounts (roadmap G1).

export const membersKey = ['admin', 'members'] as const

export const useMembers = (enabled = true) =>
  useQuery({ queryKey: membersKey, queryFn: () => http.get<Member[]>('/admin/members'), enabled })

export const useMember = (id: string) =>
  useQuery({ queryKey: [...membersKey, id], queryFn: () => http.get<Member>(`/admin/members/${id}`) })

/** Member changes also affect task eligibility and the team lists, so refresh everything member-shaped. */
function useRefresh() {
  const qc = useQueryClient()
  return () => void qc.invalidateQueries({ queryKey: membersKey })
}

export interface Provisioned {
  member: Member
  temporary_password: string
}

export function useProvisionMember() {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: (body: MemberProfile & RoleFields & { username: string; team_id: string }) =>
      http.post<Provisioned>('/admin/members', body),
    onSuccess: refresh,
  })
}

/** PUT replaces the whole profile: omitted optional fields become null (contract §8.2). */
export function useReplaceProfile(id: string) {
  const refresh = useRefresh()
  return useMutation({ mutationFn: (body: MemberProfile) => http.put<Member>(`/admin/members/${id}`, body), onSuccess: refresh })
}

export function useChangeTeam(id: string) {
  const refresh = useRefresh()
  return useMutation({ mutationFn: (team_id: string) => http.post<Member>(`/admin/members/${id}/team`, { team_id }), onSuccess: refresh })
}

export function useChangeRole(id: string) {
  const refresh = useRefresh()
  return useMutation({ mutationFn: (body: RoleFields) => http.post<Member>(`/admin/members/${id}/role`, body), onSuccess: refresh })
}

export function useDeactivateMember(id: string) {
  const refresh = useRefresh()
  return useMutation({ mutationFn: () => http.post<Member>(`/admin/members/${id}/deactivate`), onSuccess: refresh })
}

export function useReactivateMember(id: string) {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: (body: RoleFields & { team_id: string }) => http.post<Member>(`/admin/members/${id}/reactivate`, body),
    onSuccess: refresh,
  })
}

export function useResetPassword(id: string) {
  return useMutation({ mutationFn: () => http.post<{ temporary_password: string }>(`/admin/members/${id}/reset-password`) })
}
