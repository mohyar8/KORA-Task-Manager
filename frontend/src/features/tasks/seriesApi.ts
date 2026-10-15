import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { http } from '@/shared/api/http'
import { tasksKey } from './api'
import type { TaskPriority } from './types'

// Contract §9.4. Series changes touch many occurrence tasks, so they refresh every ['tasks'] query too.

export const MAX_OCCURRENCES = 104

export interface SubtaskTemplate {
  key: string
  title: string
  description: string | null
  priority: TaskPriority | null
  assignee_member_ids: string[]
}

export interface Series {
  id: string
  scope_unit_id: string
  title: string
  description: string | null
  priority: TaskPriority | null
  assignee_member_ids: string[]
  first_due_at: string
  ends_at: string
  status: 'active' | 'stopped'
  created_by_account_id: string
  stopped_at: string | null
  subtask_templates: SubtaskTemplate[]
  occurrence_ids: string[]
}

/** A template as sent: existing templates carry their `key`; new ones omit it. */
export interface TemplateInput {
  key?: string
  title: string
  description: string | null
  priority: TaskPriority | null
  assignee_member_ids: string[]
}

export interface CreateSeries {
  scope_unit_id: string
  title: string
  description: string | null
  priority: TaskPriority | null
  first_due_at: string
  ends_at: string
  assignee_member_ids: string[]
  subtasks: TemplateInput[]
}

export type UpdateSeries = Partial<{
  title: string
  description: string | null
  priority: TaskPriority | null
  assignee_member_ids: string[]
  /** The complete new template list. */
  subtasks: TemplateInput[]
}>

export const seriesKey = (id: string) => ['tasks', 'series', id] as const

export const useSeries = (id: string) =>
  useQuery({ queryKey: seriesKey(id), queryFn: () => http.get<Series>(`/task-series/${id}`) })

function useRefresh() {
  const qc = useQueryClient()
  return () => void qc.invalidateQueries({ queryKey: tasksKey })
}

export function useCreateSeries() {
  const refresh = useRefresh()
  return useMutation({ mutationFn: (body: CreateSeries) => http.post<Series>('/task-series', body), onSuccess: refresh })
}

export function useUpdateSeries(id: string) {
  const refresh = useRefresh()
  return useMutation({ mutationFn: (body: UpdateSeries) => http.patch<Series>(`/task-series/${id}`, body), onSuccess: refresh })
}

export function useMoveSeries(id: string) {
  const refresh = useRefresh()
  return useMutation({ mutationFn: (scope_unit_id: string) => http.post<Series>(`/task-series/${id}/move`, { scope_unit_id }), onSuccess: refresh })
}

export function useStopSeries(id: string) {
  const refresh = useRefresh()
  return useMutation({ mutationFn: () => http.post<Series>(`/task-series/${id}/stop`), onSuccess: refresh })
}

/** Weekly occurrences from first_due_at up to and including ends_at (same weekday/time). */
export function occurrenceCount(firstDueIso: string, endsIso: string): number {
  const span = Date.parse(endsIso) - Date.parse(firstDueIso)
  return span < 0 ? 0 : Math.floor(span / (7 * 24 * 60 * 60 * 1000)) + 1
}

/** Only changed fields; templates are sent as the complete list when anything about them changed. */
export function seriesChanges(series: Series, next: CreateSeries): UpdateSeries {
  const diff: UpdateSeries = {}
  if (next.title !== series.title) diff.title = next.title
  if (next.description !== series.description) diff.description = next.description
  if (next.priority !== series.priority) diff.priority = next.priority
  const sameIds = (a: string[], b: string[]) => a.length === b.length && [...a].sort().join() === [...b].sort().join()
  if (!sameIds(next.assignee_member_ids, series.assignee_member_ids)) diff.assignee_member_ids = next.assignee_member_ids
  const strip = (t: TemplateInput) => ({ k: t.key ?? null, t: t.title, d: t.description, p: t.priority, a: [...t.assignee_member_ids].sort() })
  if (JSON.stringify(next.subtasks.map(strip)) !== JSON.stringify(series.subtask_templates.map(strip))) diff.subtasks = next.subtasks
  return diff
}
