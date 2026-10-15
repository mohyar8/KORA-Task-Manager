import { useMemo } from 'react'
import { allUnits, canAnywhere } from '@/features/auth/permissions'
import { useSession } from '@/features/auth/session'
import type { UnitKind } from '@/features/auth/types'
import { useUnits, type UnitStatus } from './api'

export interface UnitInfo {
  id: string
  name: string
  kind: UnitKind
  /** Known only for units the caller manages (GET /organization/units). */
  status?: UnitStatus
  parentId?: string | null
}

/**
 * Unit lookup for pickers and labels. Names/kinds of every unit come from GET /access/me (available to everyone,
 * roadmap G2); status and parent are added for units the caller can manage.
 */
export function useUnitDirectory() {
  const { access } = useSession()
  const manages = canAnywhere(access, 'organization.manage')
  const managed = useUnits(manages)

  return useMemo(() => {
    const byId = new Map<string, UnitInfo>()
    for (const u of allUnits(access)) byId.set(u.unit_id, { id: u.unit_id, name: u.name, kind: u.kind })
    for (const u of managed.data ?? []) byId.set(u.id, { id: u.id, name: u.name, kind: u.kind, status: u.status, parentId: u.parent_id })
    const list = [...byId.values()]
    const ofKind = (kind: UnitKind) => list.filter((u) => u.kind === kind && u.status !== 'archived').sort((a, b) => a.name.localeCompare(b.name))
    return {
      byId,
      nameOf: (id: string | null | undefined) => (id ? (byId.get(id)?.name ?? id) : null),
      teams: ofKind('team'),
      administrations: ofKind('administration'),
    }
  }, [access, managed.data])
}
