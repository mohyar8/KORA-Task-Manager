import { useMemo } from 'react'
import { useI18n } from '@/shared/i18n/i18n'
import { useSession } from '@/features/auth/session'
import { useChatPeople } from './people'
import { workUnits } from '@/features/teams/units'
import { dmChannelId, orgChannelId, unitChannelId, useChatState, type ChannelKind } from '@/mock/chatStore'

export interface Channel {
  id: string
  kind: ChannelKind
  title: string
  unread: number
}

/** Every conversation the signed-in person can see: private, their teams, their administrations, the whole organization. */
export function useChannels(extraDmPeer?: string | null) {
  const { t } = useI18n()
  const { access, account } = useSession()
  const people = useChatPeople()
  const chat = useChatState()
  const me = account?.member_id ?? ''

  return useMemo(() => {
    const unread = (id: string) => {
      const seen = chat.read[id] ?? ''
      return chat.messages.filter((m) => m.channelId === id && m.authorId !== me && m.at > seen).length
    }
    const list: Channel[] = [{ id: orgChannelId, kind: 'organization', title: t('chat.org.name'), unread: unread(orgChannelId) }]
    for (const u of workUnits(access)) {
      const id = unitChannelId(u.unit_id)
      list.push({ id, kind: u.kind === 'team' ? 'team' : 'administration', title: u.name, unread: unread(id) })
    }
    const peers = new Set(chat.dms)
    if (extraDmPeer) peers.add(extraDmPeer)
    for (const peer of peers) {
      const id = dmChannelId(peer)
      list.push({ id, kind: 'direct', title: people.nameOf(peer), unread: unread(id) })
    }
    return { channels: list, totalUnread: list.reduce((n, c) => n + c.unread, 0), messages: chat.messages }
  }, [access, chat, extraDmPeer, me, people, t])
}
