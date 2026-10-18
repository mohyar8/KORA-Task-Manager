// Contract §3.3, §4, §7.
import type { Permission } from '@/features/auth/types'

export type RoleKey =
  | 'event_project_leader'
  | 'deputy_leader'
  | 'pmo_leader'
  | 'pmo_member'
  | 'administration_manager'
  | 'team_leader'
  | 'member'

export const ROLE_KEYS: RoleKey[] = [
  'event_project_leader',
  'deputy_leader',
  'pmo_leader',
  'pmo_member',
  'administration_manager',
  'team_leader',
  'member',
]

export const PERMISSIONS: Permission[] = [
  'organization.manage',
  'task.view',
  'task.create',
  'task.manage',
  'announcement.publish',
  'announcement.manage',
  'calendar.create',
  'calendar.manage',
  'calendar.view_administration',
  'calendar.view_all',
]

export type OverrideEffect = 'grant' | 'deny'

export interface PermissionResponse {
  key: Permission
  description: string
}

export interface RoleDefault {
  id: string
  role_key: string
  permission: string
  valid_from: string
  valid_to: string | null
  created_by_account_id: string | null
  ended_by_account_id: string | null
}

export interface Override {
  id: string
  account_id: string
  permission: Permission
  unit_id: string
  effect: OverrideEffect
  reason: string
  valid_from: string
  valid_to: string | null
  created_by_account_id: string
  ended_by_account_id: string | null
}

export interface OverrideRequest {
  permission: Permission
  unit_id: string
  effect: OverrideEffect
  reason: string
}

export interface SystemAdmin {
  account_id: string
  username: string
  granted_at: string
  granted_by_account_id: string | null
}

/** Fixed ID of the KORA root unit (contract §4). */
export const KORA_UNIT_ID = '6b0a0000-0000-4000-8000-000000000001'
