// Types copied from API_CONTRACT.md §3.1, §4, §6, §7.4.

export type Permission =
  | 'organization.manage'
  | 'task.view'
  | 'task.create'
  | 'task.manage'
  | 'announcement.publish'
  | 'announcement.manage'
  | 'calendar.create'
  | 'calendar.manage'
  | 'calendar.view_administration'
  | 'calendar.view_all'

export type UnitKind = 'organization' | 'pmo' | 'administration' | 'team'
export type DecisionSource = 'override_deny' | 'override_grant' | 'role_default' | 'none'

export interface Account {
  id: string
  username: string
  must_change_password: boolean
  is_system_admin: boolean
  /** The Member record linked to this account; null for accounts that are not Members (e.g. the bootstrap admin). */
  member_id: string | null
}

export interface SessionResponse {
  account: Account
  csrf_token: string
}

export interface UnitDecision {
  unit_id: string
  name: string
  kind: UnitKind
  allowed: boolean
  source: DecisionSource
  decided_at_unit_id: string | null
}

export interface PermissionAccess {
  permission: Permission
  units: UnitDecision[]
}

export interface EffectiveAccess {
  account_id: string
  at: string
  permissions: PermissionAccess[]
}
