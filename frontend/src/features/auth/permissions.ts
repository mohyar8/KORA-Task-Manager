import type { EffectiveAccess, Permission, UnitDecision } from './types'

// Decisions come only from GET /access/me (the server's evaluation). Roles/titles are never consulted.

/** Units where the permission is allowed. */
export function allowedUnits(access: EffectiveAccess | null, permission: Permission): UnitDecision[] {
  const entry = access?.permissions.find((p) => p.permission === permission)
  return entry ? entry.units.filter((u) => u.allowed) : []
}

/** True if the permission is allowed at the given unit. */
export function canAt(access: EffectiveAccess | null, permission: Permission, unitId: string): boolean {
  return allowedUnits(access, permission).some((u) => u.unit_id === unitId)
}

/** True if the permission is allowed at any unit (used for navigation visibility). */
export function canAnywhere(access: EffectiveAccess | null, permission: Permission): boolean {
  return allowedUnits(access, permission).length > 0
}

/** Every unit the caller can name (id, name, kind), from the access response. */
export function allUnits(access: EffectiveAccess | null): UnitDecision[] {
  const seen = new Map<string, UnitDecision>()
  for (const p of access?.permissions ?? []) for (const u of p.units) if (!seen.has(u.unit_id)) seen.set(u.unit_id, u)
  return [...seen.values()]
}

/** Manages at least one Administration (not just a team): the people who see the organisation-wide task list. */
export function isAdministrationManager(access: EffectiveAccess | null): boolean {
  return allowedUnits(access, 'task.manage').some((u) => u.kind === 'administration')
}

