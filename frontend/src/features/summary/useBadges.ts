import { useQuery } from '@tanstack/react-query'
import { http } from '@/shared/api/http'
import { isMock } from '@/shared/config'
import { useChannels } from '@/features/chat/useChannels'
import { usePendingIncoming } from '@/features/requests/useIncoming'
import { useAnnouncements } from '@/features/announcements/api'

// Contract §9e: counts only.
export interface Summary {
  notifications_unread: number
  chat_unread: number
  requests_pending: number
  announcements_unread: number
  reviews_open: number
}

export const summaryKey = ['me', 'summary'] as const
const POLL_MS = 30_000

/** One call for the sidebar numbers. Mock mode counts them from the browser-only data instead. */
export function useBadges() {
  const summary = useQuery({
    queryKey: summaryKey,
    queryFn: () => http.get<Summary>('/me/summary'),
    enabled: !isMock(),
    refetchInterval: POLL_MS,
  })
  const mockChat = useChannels().totalUnread
  const mockRequests = usePendingIncoming()
  const announcements = (useAnnouncements('published').data ?? []).filter((a) => !a.content_hidden && a.my_read_current === false).length
  if (isMock()) return { chat: mockChat, requests: mockRequests, announcements }
  return {
    chat: summary.data?.chat_unread ?? 0,
    requests: summary.data?.requests_pending ?? 0,
    announcements: summary.data?.announcements_unread ?? 0,
  }
}
