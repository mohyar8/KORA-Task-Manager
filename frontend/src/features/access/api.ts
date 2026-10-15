import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { http } from '@/shared/api/http'
import { accessKey } from '@/features/auth/api'
import type { EffectiveAccess, Permission } from '@/features/auth/types'
import type { Override, OverrideRequest, PermissionResponse, RoleDefault, SystemAdmin } from './types'

// Contract §7 — every route here is System Admin only.

export const keys = {
  permissions: ['admin', 'permissions'] as const,
  roleDefaults: ['admin', 'role-defaults'] as const,
  overrides: (accountId: string) => ['admin', 'overrides', accountId] as const,
  effective: (accountId: string, asOf: string | null) => ['admin', 'effective', accountId, asOf] as const,
  admins: ['admin', 'system-admins'] as const,
}

export const usePermissions = () =>
  useQuery({ queryKey: keys.permissions, queryFn: () => http.get<PermissionResponse[]>('/admin/permissions') })

export const useRoleDefaults = () =>
  useQuery({ queryKey: keys.roleDefaults, queryFn: () => http.get<RoleDefault[]>('/admin/role-defaults') })

export function useAddRoleDefault() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { role_key: string; permission: Permission }) => http.post<RoleDefault>('/admin/role-defaults', body),
    onSuccess: () => invalidateAccess(qc),
  })
}

export function useEndRoleDefault() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => http.post<RoleDefault>(`/admin/role-defaults/${id}/end`),
    onSuccess: () => invalidateAccess(qc),
  })
}

export const useOverrides = (accountId: string | null) =>
  useQuery({
    queryKey: keys.overrides(accountId ?? ''),
    queryFn: () => http.get<Override[]>(`/admin/accounts/${accountId}/overrides`),
    enabled: !!accountId,
  })

export function useCreateOverride(accountId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: OverrideRequest) => http.post<Override>(`/admin/accounts/${accountId}/overrides`, body),
    onSuccess: () => invalidateAccess(qc),
  })
}

export function useEndOverride() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => http.post<Override>(`/admin/overrides/${id}/end`),
    onSuccess: () => invalidateAccess(qc),
  })
}

/** `asOf` must be an ISO string with an offset (or null for "now"). */
export const useEffectiveAccess = (accountId: string | null, asOf: string | null) =>
  useQuery({
    queryKey: keys.effective(accountId ?? '', asOf),
    queryFn: () => http.get<EffectiveAccess>(`/admin/accounts/${accountId}/effective-access`, { as_of: asOf }),
    enabled: !!accountId,
  })

export const useSystemAdmins = () =>
  useQuery({ queryKey: keys.admins, queryFn: () => http.get<SystemAdmin[]>('/admin/system-admins') })

export function useGrantSystemAdmin() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (accountId: string) => http.post<SystemAdmin>(`/admin/accounts/${accountId}/system-admin`),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.admins }),
  })
}

export function useRevokeSystemAdmin() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (accountId: string) => http.post<void>(`/admin/accounts/${accountId}/system-admin/revoke`),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.admins }),
  })
}

/**
 * Role defaults and overrides change what people (possibly the admin themself) may do, so refresh every admin view
 * AND the caller's own /access/me so navigation reflects it immediately.
 */
function invalidateAccess(qc: ReturnType<typeof useQueryClient>) {
  void qc.invalidateQueries({ queryKey: ['admin'] })
  void qc.invalidateQueries({ queryKey: accessKey })
}
