import { allowedUnits } from '@/features/auth/permissions'
import type { EffectiveAccess, UnitDecision } from '@/features/auth/types'

/**
 * The places a person works in: Teams and Administrations where they may see tasks.
 * Derived only from the server's access decisions (never from titles). Teams come first, then by name.
 */
export function workUnits(access: EffectiveAccess | null): UnitDecision[] {
  const rank = (u: UnitDecision) => (u.kind === 'team' ? 0 : 1)
  return allowedUnits(access, 'task.view')
    .filter((u) => u.kind === 'team' || u.kind === 'administration')
    .sort((a, b) => rank(a) - rank(b) || a.name.localeCompare(b.name))
}
