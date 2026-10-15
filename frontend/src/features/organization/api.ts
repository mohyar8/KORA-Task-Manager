import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { http } from '@/shared/api/http'
import { accessKey } from '@/features/auth/api'
import type { UnitKind } from '@/features/auth/types'

// Contract §8.1. Units are listed only where the caller holds organization.manage.

export type UnitStatus = 'active' | 'archived'

export interface Unit {
  id: string
  kind: UnitKind
  name: string
  status: UnitStatus
  parent_id: string | null
  archived_at: string | null
}

export const unitsKey = ['org', 'units'] as const

export const useUnits = (enabled: boolean) =>
  useQuery({ queryKey: unitsKey, queryFn: () => http.get<Unit[]>('/organization/units'), enabled })

/** Structure changes alter unit lists, access decisions (new units appear in /access/me) and member placement. */
function useRefresh() {
  const qc = useQueryClient()
  return () => {
    void qc.invalidateQueries({ queryKey: unitsKey })
    void qc.invalidateQueries({ queryKey: accessKey })
    void qc.invalidateQueries({ queryKey: ['admin', 'members'] })
  }
}

export const useUnit = (id: string | null) =>
  useQuery({ queryKey: [...unitsKey, id], queryFn: () => http.get<Unit>(`/organization/units/${id}`), enabled: !!id })

export function useCreateUnit() {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: (body: { kind: UnitKind; name: string; parent_id: string }) => http.post<Unit>('/organization/units', body),
    onSuccess: refresh,
  })
}

export function useMoveTeam() {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: (v: { unitId: string; administrationId: string }) =>
      http.post<Unit>(`/organization/units/${v.unitId}/move`, { administration_id: v.administrationId }),
    onSuccess: refresh,
  })
}

export function useArchiveUnit() {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: (unitId: string) => http.post<Unit>(`/organization/units/${unitId}/archive`),
    onSuccess: refresh,
  })
}
