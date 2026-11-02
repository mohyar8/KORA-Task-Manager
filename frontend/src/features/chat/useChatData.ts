import { useCallback, useEffect, useMemo } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { http } from '@/shared/api/http'
import { isMock } from '@/shared/config'
import { useI18n } from '@/shared/i18n/i18n'
import { canAt } from '@/features/auth/permissions'
import { useSession } from '@/features/auth/session'
import { flatten, useOrgTree, type OrgNode } from '@/features/structure/useOrgTree'
import { summaryKey } from '@/features/summary/useBadges'
import { chatActions, dmChannelId, type ChannelKind } from '@/mock/chatStore'
import { useChatPeople } from './people'
import { useChannels, type Channel } from './useChannels'

export interface ChatMessageView {
  id: string
  authorId: string
  text: string
  at: string
  deleted: boolean
  /** The signed-in person may delete it (their own, or as a moderator of the channel). */
  canDelete: boolean
}

// Contract §9d.
interface ApiMessage {
  id: number
  conversation_id: string
  author_member_id: string
  body: string
  created_at: string
  edited_at: string | null
  deleted: boolean
}
interface ApiConversation {
  id: string
  kind: 'direct' | 'unit' | 'organization'
  unit_id: string | null
  other_member_id: string | null
  last_message: ApiMessage | null
  unread: number
}

const chatKey = ['chat'] as const
const THREAD_POLL_MS = 5_000
const LIST_POLL_MS = 15_000
const isConversationId = (id: string) => /^[0-9a-f]{8}-/i.test(id)

function unitIndex(tree: OrgNode | null) {
  const units = new Map<string, OrgNode>()
  const walk = (n: OrgNode) => { units.set(n.id, n); n.children.forEach(walk) }
  if (tree) walk(tree)
  return units
}

/**
 * Everything the chat screen needs, from the server (default) or from the browser-only mock. The real
 * thread keeps what it has and asks only for what is newer (`after=<last id>`), every few seconds.
 */
export function useChatData(channelId: string) {
  const { t } = useI18n()
  const { access, account } = useSession()
  const qc = useQueryClient()
  const { tree } = useOrgTree()
  const mockMode = isMock()
  const me = account?.member_id ?? ''
  const extraPeer = channelId.startsWith('dm:') ? channelId.slice(3) : null

  // Mock side (all of it is inert in real mode).
  const mockPeople = useChatPeople()
  const mock = useChannels(mockMode ? extraPeer : null)

  // Real side.
  const conversations = useQuery({
    queryKey: [...chatKey, 'conversations'],
    queryFn: () => http.get<ApiConversation[]>('/chat/conversations'),
    enabled: !mockMode,
    refetchInterval: LIST_POLL_MS,
  })
  const threadId = !mockMode && isConversationId(channelId) ? channelId : ''
  const thread = useQuery({
    queryKey: [...chatKey, 'thread', threadId],
    queryFn: async () => {
      const known = qc.getQueryData<ApiMessage[]>([...chatKey, 'thread', threadId]) ?? []
      const last = known.at(-1)?.id
      const fresh = await http.get<ApiMessage[]>(`/chat/conversations/${threadId}/messages`, last ? { after: last } : { limit: 50 })
      return fresh.length ? [...known, ...fresh] : known
    },
    enabled: !!threadId,
    refetchInterval: THREAD_POLL_MS,
  })

  const units = useMemo(() => unitIndex(tree), [tree])
  const people = useMemo(() => {
    if (mockMode) return mockPeople.people
    const byId = new Map<string, string>()
    if (tree) for (const { person } of flatten(tree)) byId.set(person.id, person.name)
    return [...byId].filter(([id]) => id !== me).map(([id, name]) => ({ id, name })).sort((a, b) => a.name.localeCompare(b.name))
  }, [mockMode, mockPeople.people, tree, me])
  const nameMap = useMemo(() => new Map(people.map((p) => [p.id, p.name])), [people])
  const nameOf = (id: string) => (mockMode ? mockPeople.nameOf(id) : nameMap.get(id) ?? '')

  const channels: Channel[] = useMemo(() => {
    if (mockMode) return mock.channels
    return (conversations.data ?? []).map((c) => {
      if (c.kind === 'organization') return { id: c.id, kind: 'organization' as ChannelKind, title: t('chat.org.name'), unread: c.unread }
      if (c.kind === 'unit') {
        const node = c.unit_id ? units.get(c.unit_id) : undefined
        return { id: c.id, kind: (node?.kind === 'team' ? 'team' : 'administration') as ChannelKind, title: node?.name ?? '', unread: c.unread }
      }
      return { id: c.id, kind: 'direct' as ChannelKind, title: nameMap.get(c.other_member_id ?? '') ?? '', unread: c.unread }
    })
  }, [mockMode, mock.channels, conversations.data, units, nameMap, t])

  const activeUnit = (conversations.data ?? []).find((c) => c.id === channelId)?.unit_id ?? null
  const moderator = !!activeUnit && canAt(access, 'chat.moderate', activeUnit)

  const messages: ChatMessageView[] = useMemo(() => {
    if (mockMode) return mock.messages.filter((m) => m.channelId === channelId).map((m) => ({ id: m.id, authorId: m.authorId, text: m.text, at: m.at, deleted: false, canDelete: false }))
    return (thread.data ?? []).map((m) => ({ id: String(m.id), authorId: m.author_member_id, text: m.body, at: m.created_at, deleted: m.deleted, canDelete: !m.deleted && (m.author_member_id === me || moderator) }))
  }, [mockMode, mock.messages, thread.data, channelId, me, moderator])

  const refreshLists = () => {
    void qc.invalidateQueries({ queryKey: [...chatKey, 'conversations'] })
    void qc.invalidateQueries({ queryKey: summaryKey })
  }
  const send = useMutation({
    mutationFn: (text: string) => http.post<ApiMessage>(`/chat/conversations/${threadId}/messages`, { body: text }),
    onSuccess: (message) => {
      qc.setQueryData<ApiMessage[]>([...chatKey, 'thread', threadId], (old = []) => (old.some((m) => m.id === message.id) ? old : [...old, message]))
      refreshLists()
    },
  })
  const remove = useMutation({
    mutationFn: (id: string) => http.delete<ApiMessage>(`/chat/messages/${id}`),
    onSuccess: (message) => qc.setQueryData<ApiMessage[]>([...chatKey, 'thread', threadId], (old = []) => old.map((m) => (m.id === message.id ? message : m))),
  })
  const read = useMutation({ mutationFn: () => http.post(`/chat/conversations/${threadId}/read`, {}), onSuccess: refreshLists })
  const open = useMutation({
    mutationFn: (memberId: string) => http.post<ApiConversation>('/chat/conversations/direct', { member_id: memberId }),
    onSuccess: refreshLists,
  })

  const latest = messages.at(-1)?.id
  const unreadHere = channels.find((c) => c.id === channelId)?.unread ?? 0
  const markReadNow = read.mutate
  useEffect(() => {
    // Mock: the existing store marks and seeds. Real: tell the server once there is something unread.
    if (mockMode) return
    if (threadId && unreadHere > 0) markReadNow()
  }, [mockMode, threadId, latest, unreadHere, markReadNow])

  const openMutate = open.mutateAsync
  const openDm = useCallback(
    async (memberId: string): Promise<string> => {
      if (mockMode) {
        chatActions.openDm(memberId)
        return dmChannelId(memberId)
      }
      return (await openMutate(memberId)).id
    },
    [mockMode, openMutate],
  )
  const markRead = useCallback(() => { if (mockMode && channelId) chatActions.markRead(channelId) }, [mockMode, channelId])

  return {
    me,
    people,
    nameOf,
    channels,
    messages,
    isLoading: !mockMode && (conversations.isPending || (!!threadId && thread.isPending)),
    error: (conversations.error ?? thread.error) as unknown,
    send: async (text: string) => {
      if (mockMode) return chatActions.send(channelId, me, text)
      await send.mutateAsync(text)
    },
    remove: mockMode ? undefined : (id: string) => remove.mutateAsync(id).then(() => undefined),
    /** Open (or create) the private chat with someone; resolves to the channel to show. */
    openDm,
    markRead,
  }
}
