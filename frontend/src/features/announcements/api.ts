import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { http } from '@/shared/api/http'

// Contract §10.
export type AnnouncementState = 'draft' | 'published' | 'withdrawn'
export const ANNOUNCEMENT_STATES: AnnouncementState[] = ['draft', 'published', 'withdrawn']

export interface Announcement {
  id: string
  scope_unit_id: string
  state: AnnouncementState
  current_version: number
  created_by_account_id: string
  created_at: string
  updated_at: string
  published_at: string | null
  published_by_account_id: string | null
  withdrawn_at: string | null
  withdrawn_by_account_id: string | null
  title: string | null
  body: string | null
  /** true (with null content) when a recipient views a withdrawn announcement */
  content_hidden: boolean
  /** set only for recipients */
  my_read_version: number | null
  my_read_current: boolean | null
}

export interface AnnouncementVersion {
  version: number
  title: string
  body: string
  created_by_account_id: string
  created_at: string
}

export interface RecipientStatus {
  member_id: string
  account_id: string
  read_version: number | null
  read_current: boolean
}

export const annKey = ['announcements'] as const

export const useAnnouncements = (state?: string) =>
  useQuery({ queryKey: [...annKey, 'list', state ?? ''], queryFn: () => http.get<Announcement[]>('/announcements', { state }) })

/** Opening a published announcement as a recipient marks its current version read (server side effect). */
export const useAnnouncement = (id: string) =>
  useQuery({ queryKey: [...annKey, id], queryFn: () => http.get<Announcement>(`/announcements/${id}`) })

/** Lazy: only the publisher and managers may read these (403 otherwise), so they load on request. */
export const useVersions = (id: string, enabled: boolean) =>
  useQuery({ queryKey: [...annKey, id, 'versions'], queryFn: () => http.get<AnnouncementVersion[]>(`/announcements/${id}/versions`), enabled, retry: false })

export const useRecipients = (id: string, enabled: boolean) =>
  useQuery({ queryKey: [...annKey, id, 'recipients'], queryFn: () => http.get<RecipientStatus[]>(`/announcements/${id}/recipients`), enabled, retry: false })

function useRefresh() {
  const qc = useQueryClient()
  return () => {
    void qc.invalidateQueries({ queryKey: annKey })
    // reading/publishing changes what the notification list and bell show
    void qc.invalidateQueries({ queryKey: ['notifications'] })
  }
}

export function useCreateAnnouncement() {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: (body: { scope_unit_id: string; title: string; body: string }) => http.post<Announcement>('/announcements', body),
    onSuccess: refresh,
  })
}

export function useUpdateAnnouncement(id: string) {
  const refresh = useRefresh()
  return useMutation({ mutationFn: (body: { title?: string; body?: string }) => http.patch<Announcement>(`/announcements/${id}`, body), onSuccess: refresh })
}

export function usePublishAnnouncement(id: string) {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: (recipient_member_ids: string[]) => http.post<Announcement>(`/announcements/${id}/publish`, { recipient_member_ids }),
    onSuccess: refresh,
  })
}

export function useWithdrawAnnouncement(id: string) {
  const refresh = useRefresh()
  return useMutation({ mutationFn: () => http.post<Announcement>(`/announcements/${id}/withdraw`), onSuccess: refresh })
}

/** Which of this caller's actions are worth offering (the server decides; contract §10). */
export function announcementActions(
  a: Announcement,
  v: { accountId: string; canManage: boolean; canPublish: boolean },
) {
  const creator = a.created_by_account_id === v.accountId
  const publisher = a.published_by_account_id === v.accountId
  const privileged = a.state === 'draft' ? creator || v.canManage : publisher || v.canManage
  return {
    edit: a.state !== 'withdrawn' && privileged,
    publish: a.state === 'draft' && v.canPublish && (creator || v.canManage),
    withdraw: a.state === 'published' && privileged,
    versions: privileged,
    recipients: a.state !== 'draft' && privileged,
  }
}
