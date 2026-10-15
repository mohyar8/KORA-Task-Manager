import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { http } from '@/shared/api/http'

// Contract §11.
export type NotificationCategory =
  | 'task_assignment' | 'task_update' | 'task_comment' | 'announcement_new' | 'announcement_change' | 'calendar_event'

export const CATEGORIES: NotificationCategory[] = [
  'task_assignment', 'task_update', 'task_comment', 'announcement_new', 'announcement_change', 'calendar_event',
]

export interface AppNotification {
  id: string
  category: NotificationCategory
  kind: string
  source_type: string
  source_id: string
  summary: string | null
  /** true when the reader can no longer see the source: summary is null */
  redacted: boolean
  actor_account_id: string | null
  created_at: string
  read_at: string | null
}

export type Preferences = Record<NotificationCategory, boolean>

export const notifKey = ['notifications'] as const
export const POLL_MS = 60_000

export const useNotifications = (unreadOnly: boolean) =>
  useQuery({
    queryKey: [...notifKey, 'list', unreadOnly],
    queryFn: () => http.get<AppNotification[]>('/notifications', { unread_only: unreadOnly }),
    refetchInterval: POLL_MS,
  })

/** The bell's count; polled (no push channel exists). */
export function useUnreadCount() {
  const q = useQuery({
    queryKey: [...notifKey, 'unread'],
    queryFn: () => http.get<AppNotification[]>('/notifications', { unread_only: true }),
    refetchInterval: POLL_MS,
    select: (list) => list.length,
  })
  return q.data ?? 0
}

export const usePreferences = () =>
  useQuery({ queryKey: [...notifKey, 'preferences'], queryFn: () => http.get<Preferences>('/notifications/preferences') })

function useRefresh() {
  const qc = useQueryClient()
  return () => void qc.invalidateQueries({ queryKey: notifKey })
}

/** Re-reads one notification: access to its source is re-checked on every read (redaction), contract §11. */
export function useOpenNotification() {
  const refresh = useRefresh()
  return useMutation({ mutationFn: (id: string) => http.get<AppNotification>(`/notifications/${id}`), onSettled: refresh })
}

export function useMarkRead() {
  const refresh = useRefresh()
  return useMutation({ mutationFn: (id: string) => http.post<AppNotification>(`/notifications/${id}/read`), onSuccess: refresh })
}
export function useReadAll() {
  const refresh = useRefresh()
  return useMutation({ mutationFn: () => http.post<void>('/notifications/read-all'), onSuccess: refresh })
}
export function useDeleteNotification() {
  const refresh = useRefresh()
  return useMutation({ mutationFn: (id: string) => http.post<void>(`/notifications/${id}/delete`), onSuccess: refresh })
}
export function useDeleteAll() {
  const refresh = useRefresh()
  return useMutation({ mutationFn: () => http.post<void>('/notifications/delete-all'), onSuccess: refresh })
}
export function useSavePreferences() {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: (patch: Partial<Preferences>) => http.put<Preferences>('/notifications/preferences', patch),
    onSuccess: refresh,
  })
}

/** Where a notification's source lives in the app; null when there is no page for it. */
export function sourceLink(n: Pick<AppNotification, 'source_type' | 'source_id'>): string | null {
  switch (n.source_type) {
    case 'task': return `/tasks/${n.source_id}`
    case 'task_series': return `/task-series/${n.source_id}`
    case 'announcement': return `/announcements/${n.source_id}`
    case 'calendar_event': return `/calendar/${n.source_id}`
    default: return null
  }
}
