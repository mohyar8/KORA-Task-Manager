import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { http } from '@/shared/api/http'
import type { TaskStatus } from '@/features/tasks/types'

// Contract §12.
export type EventType = 'event' | 'meeting'

export interface CalendarEvent {
  id: string
  type: EventType
  title: string
  description: string | null
  starts_at: string
  ends_at: string
  location_text: string | null
  online_url: string | null
  scope_unit_id: string
  organizer_account_id: string
  organizer_member_id: string
  state: 'scheduled' | 'cancelled'
  created_at: string
  updated_at: string
  cancelled_at: string | null
  /** only for the organizer and scoped managers; otherwise null */
  invitee_member_ids: string[] | null
  my_invitation: { member_id: string; invited_at: string } | null
}

export interface TaskDueItem {
  item_type: 'task_due'
  task_id: string
  title: string
  due_at: string
  status: TaskStatus
  scope_unit_id: string
}

export interface MyCalendar {
  starts_at: string
  ends_at: string
  events: (CalendarEvent & { item_type: 'event' })[]
  task_due_dates: TaskDueItem[]
}

export interface Invitation {
  member_id: string
  valid_from: string
  valid_to: string | null
  created_by_account_id: string
  ended_by_account_id: string | null
}

export interface CalendarHistory {
  kind: 'created' | 'updated' | 'cancelled' | 'invitee_added' | 'invitee_removed'
  actor_account_id: string | null
  data: Record<string, unknown>
  created_at: string
}

export interface EventFields {
  type: EventType
  title: string
  description: string | null
  starts_at: string
  ends_at: string
  location_text: string | null
  online_url: string | null
}

export const calKey = ['calendar'] as const

/** `from`/`to` must carry an offset and span ≤ 366 days (contract §12); ISO strings from Date do. */
export const useMyCalendar = (from: string, to: string) =>
  useQuery({ queryKey: [...calKey, 'range', from, to], queryFn: () => http.get<MyCalendar>('/calendar', { from, to }) })

export interface BroadTask {
  task_id: string
  title: string
  due_at: string
  status: TaskStatus
  scope_unit_id: string
  unit_name: string
  administration_id: string | null
  administration_name: string | null
  from_outside: boolean
}

export type BroadScope = 'administration' | 'all'

/** Task due dates of the caller's Administration, or of every Administration (contract §12). */
export const useBroadCalendar = (scope: BroadScope, from: string, to: string) =>
  useQuery({
    queryKey: [...calKey, 'broad', scope, from, to],
    queryFn: () => http.get<{ tasks: BroadTask[] }>(`/calendar/${scope}`, { from, to }),
  })

/** All events the caller may see (no range filter exists on this route, contract §15.4). */
export const useVisibleEvents = () =>
  useQuery({ queryKey: [...calKey, 'visible'], queryFn: () => http.get<CalendarEvent[]>('/calendar/events') })

export const useEvent = (id: string) =>
  useQuery({ queryKey: [...calKey, 'event', id], queryFn: () => http.get<CalendarEvent>(`/calendar/events/${id}`) })

export const useInvitations = (id: string, enabled: boolean) =>
  useQuery({ queryKey: [...calKey, 'event', id, 'invitations'], queryFn: () => http.get<Invitation[]>(`/calendar/events/${id}/invitations`), enabled, retry: false })

export const useEventHistory = (id: string, enabled: boolean) =>
  useQuery({ queryKey: [...calKey, 'event', id, 'history'], queryFn: () => http.get<CalendarHistory[]>(`/calendar/events/${id}/history`), enabled, retry: false })

function useRefresh() {
  const qc = useQueryClient()
  return () => {
    void qc.invalidateQueries({ queryKey: calKey })
    void qc.invalidateQueries({ queryKey: ['notifications'] })
  }
}

export function useCreateEvent() {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: (body: EventFields & { scope_unit_id: string; invitee_member_ids: string[] }) => http.post<CalendarEvent>('/calendar/events', body),
    onSuccess: refresh,
  })
}

/** Partial update. Never send `scope_unit_id` (422). */
export function useUpdateEvent(id: string) {
  const refresh = useRefresh()
  return useMutation({ mutationFn: (body: Partial<EventFields>) => http.patch<CalendarEvent>(`/calendar/events/${id}`, body), onSuccess: refresh })
}

export function useCancelEvent(id: string) {
  const refresh = useRefresh()
  return useMutation({ mutationFn: () => http.post<CalendarEvent>(`/calendar/events/${id}/cancel`), onSuccess: refresh })
}

export function useAddInvitee(id: string) {
  const refresh = useRefresh()
  return useMutation({ mutationFn: (member_id: string) => http.post<CalendarEvent>(`/calendar/events/${id}/invitees`, { member_id }), onSuccess: refresh })
}

export function useRemoveInvitee(id: string) {
  const refresh = useRefresh()
  return useMutation({ mutationFn: (memberId: string) => http.post<CalendarEvent>(`/calendar/events/${id}/invitees/${memberId}/remove`), onSuccess: refresh })
}

// ---- pure helpers -------------------------------------------------------------------------

/** [start of month, start of next month) as ISO strings with an offset; `month` is "YYYY-MM" (local time). */
export function monthRange(month: string): { from: string; to: string } {
  const [y, m] = month.split('-').map(Number)
  return { from: new Date(y, m - 1, 1).toISOString(), to: new Date(y, m, 1).toISOString() }
}

export const currentMonth = (now = new Date()) => `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`

export function shiftMonth(month: string, delta: number): string {
  const [y, m] = month.split('-').map(Number)
  return currentMonth(new Date(y, m - 1 + delta, 1))
}

export const isMonth = (v: string | null): v is string => !!v && /^\d{4}-(0[1-9]|1[0-2])$/.test(v)

export type AgendaItem =
  | { kind: 'event'; at: string; event: MyCalendar['events'][number] }
  | { kind: 'task'; at: string; task: TaskDueItem }

/** Items grouped by local day (YYYY-MM-DD), events clamped into the range, each day sorted by time. */
export function groupByDay(cal: MyCalendar): [string, AgendaItem[]][] {
  const rangeStart = Date.parse(cal.starts_at)
  const dayKey = (iso: string) => {
    const d = new Date(Math.max(Date.parse(iso), rangeStart))
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  }
  const items: AgendaItem[] = [
    ...cal.events.map((event): AgendaItem => ({ kind: 'event', at: event.starts_at, event })),
    ...cal.task_due_dates.map((task): AgendaItem => ({ kind: 'task', at: task.due_at, task })),
  ].sort((a, b) => Date.parse(a.at) - Date.parse(b.at))
  const days = new Map<string, AgendaItem[]>()
  for (const item of items) {
    const key = dayKey(item.at)
    days.set(key, [...(days.get(key) ?? []), item])
  }
  return [...days.entries()].sort(([a], [b]) => a.localeCompare(b))
}

export const isHttpUrl = (v: string) => /^https?:\/\/\S+$/i.test(v.trim())

/** Only the changed fields. location_text and online_url are mutually exclusive: setting one clears the other. */
export function eventChanges(event: CalendarEvent, next: EventFields): Partial<EventFields> {
  const diff: Partial<EventFields> = {}
  if (next.type !== event.type) diff.type = next.type
  if (next.title !== event.title) diff.title = next.title
  if (next.description !== event.description) diff.description = next.description
  if (Date.parse(next.starts_at) !== Date.parse(event.starts_at)) diff.starts_at = next.starts_at
  if (Date.parse(next.ends_at) !== Date.parse(event.ends_at)) diff.ends_at = next.ends_at
  if (next.location_text !== event.location_text) diff.location_text = next.location_text
  if (next.online_url !== event.online_url) diff.online_url = next.online_url
  return diff
}
