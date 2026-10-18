import { useInfiniteQuery, useQuery } from '@tanstack/react-query'
import { http } from '@/shared/api/http'

// Contract §13 — System Admin only, read-only, newest first, cursor pagination (no export).
export interface AuditRecord {
  id: string
  sequence: number
  occurred_at: string
  action: string
  actor_account_id: string | null
  resource_type: string
  resource_id: string
  scope_unit_id: string | null
  before: Record<string, unknown> | null
  after: Record<string, unknown> | null
}

interface Page {
  items: AuditRecord[]
  next_cursor: number | null
}

export interface AuditFilters {
  occurred_from?: string
  occurred_to?: string
  action?: string
  resource_type?: string
  actor_account_id?: string
  resource_id?: string
  scope_unit_id?: string
}

export const PAGE_SIZE = 50

export const useAuditRecords = (filters: AuditFilters) =>
  useInfiniteQuery({
    queryKey: ['admin', 'audit', filters],
    initialPageParam: undefined as number | undefined,
    queryFn: ({ pageParam }) => http.get<Page>('/admin/audit-records', { ...filters, limit: PAGE_SIZE, cursor: pageParam }),
    getNextPageParam: (last) => last.next_cursor ?? undefined,
  })

/** Actions recorded by the backend (contract §13), grouped for the filter select. */
export const KNOWN_ACTIONS = [
  'account.bootstrapped', 'account.password_changed', 'account.password_reset', 'account.locked_out', 'system_admin.granted', 'system_admin.revoked',
  'role_default.created', 'role_default.ended', 'permission_override.created', 'permission_override.ended',
  'org_unit.created', 'org_unit.moved', 'org_unit.archived',
  'member.provisioned', 'member.profile_updated', 'member.team_changed', 'member.role_changed', 'member.deactivated', 'member.reactivated',
  'league.updated', 'task.created', 'task.updated', 'task.status_changed', 'task.cancelled', 'task.reopened', 'task.moved', 'task.assignee_added', 'task.assignee_removed',
  'task_comment.created', 'task_comment.edited', 'task_comment.deleted',
  'task_series.created', 'task_series.updated', 'task_series.moved', 'task_series.stopped', 'task_series.assignees_removed',
  'announcement.draft_created', 'announcement.published', 'announcement.edited', 'announcement.withdrawn',
  'notification_preferences.updated',
  'calendar_event.created', 'calendar_event.updated', 'calendar_event.cancelled', 'calendar_event.invitee_added', 'calendar_event.invitee_removed',
] as const

export const RESOURCE_TYPES = [
  'user_account', 'role_permission_default', 'permission_override', 'org_unit', 'member', 'task', 'task_comment', 'task_series',
  'announcement', 'notification_preferences', 'calendar_event',
] as const

export const isUuid = (v: string) => /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(v.trim())

/** Fresh copy of one record (GET /admin/audit-records/{id}); the list already has it, this confirms it on open. */
export const useAuditRecord = (id: string | null) =>
  useQuery({ queryKey: ['admin', 'audit', 'record', id], queryFn: () => http.get<AuditRecord>(`/admin/audit-records/${id}`), enabled: !!id })
