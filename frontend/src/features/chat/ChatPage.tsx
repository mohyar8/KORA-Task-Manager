import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { ArrowRight, Building2, Globe2, MessageSquare, Send, UserRound, Users } from 'lucide-react'
import { useI18n } from '@/shared/i18n/i18n'
import type { MessageKey } from '@/shared/i18n/messages.en'
import { useSession } from '@/features/auth/session'
import { useChatPeople } from './people'
import { chatActions, dmChannelId, type ChannelKind } from '@/mock/chatStore'
import { useChannels } from './useChannels'
import styles from './chat.module.css'

const ORDER: ChannelKind[] = ['direct', 'team', 'administration', 'organization']
const SECTION: Record<ChannelKind, MessageKey> = { direct: 'chat.section.direct', team: 'chat.section.team', administration: 'chat.section.administration', organization: 'chat.section.organization' }
const ICON = { direct: UserRound, team: Users, administration: Building2, organization: Globe2 }
const SEED = ['chat.seed.1', 'chat.seed.2'] as const

/** Conversations: private, team, administration and the whole organization, in one place. */
export function ChatPage() {
  const { t, locale } = useI18n()
  const { account } = useSession()
  const { people, nameOf } = useChatPeople()
  const navigate = useNavigate()
  const { channelId = '' } = useParams()
  const me = account?.member_id ?? ''
  const extraPeer = channelId.startsWith('dm:') ? channelId.slice(3) : null
  const { channels, messages } = useChannels(extraPeer)
  const active = channels.find((c) => c.id === channelId)
  const thread = messages.filter((m) => m.channelId === channelId)
  const [text, setText] = useState('')
  const bottom = useRef<HTMLDivElement>(null)
  const others = people.filter((m) => m.id !== me)

  useEffect(() => {
    if (!active || active.kind === 'direct') return
    chatActions.seed(active.id, others.slice(0, 2).map((m) => m.id), SEED.map((k) => t(k)))
  }, [active, others, t])
  useEffect(() => {
    if (channelId) chatActions.markRead(channelId)
    bottom.current?.scrollIntoView?.({ block: 'end' })
  }, [channelId, thread.length])

  const send = (e: FormEvent) => {
    e.preventDefault()
    if (!active || !text.trim() || !me) return
    chatActions.send(active.id, me, text)
    setText('')
  }
  const time = (iso: string) => new Intl.DateTimeFormat(locale === 'ar' ? 'ar-u-nu-latn' : 'en-GB', { hour: '2-digit', minute: '2-digit', hour12: false }).format(new Date(iso))

  return (
    <div className={`${styles.chat} ${channelId ? styles.threadOpen : ''}`}>
      <aside className={styles.list} aria-label={t('chat.title')}>
        <h1 className={styles.heading}>{t('chat.title')}</h1>
        <label className={styles.newDm}>
          <span className="visually-hidden">{t('chat.new')}</span>
          <select value="" onChange={(e) => { if (e.target.value) { chatActions.openDm(e.target.value); void navigate(`/chat/${dmChannelId(e.target.value)}`) } }}>
            <option value="">{t('chat.new')}</option>
            {others.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
          </select>
        </label>
        <div className={styles.groups}>
          {ORDER.map((kind) => {
            const rows = channels.filter((c) => c.kind === kind)
            if (rows.length === 0) return null
            const Icon = ICON[kind]
            return (
              <section key={kind}>
                <h2 className={styles.groupTitle}>{t(SECTION[kind])}</h2>
                <ul>
                  {rows.map((c) => (
                    <li key={c.id}>
                      <Link to={`/chat/${c.id}`} className={`${styles.row} ${c.id === channelId ? styles.on : ''}`}>
                        <Icon size={18} aria-hidden="true" />
                        <span className={styles.rowName}>{c.title}</span>
                        {c.unread > 0 && <span className={styles.badge}>{c.unread}</span>}
                      </Link>
                    </li>
                  ))}
                </ul>
              </section>
            )
          })}
        </div>
      </aside>

      <section className={styles.thread} aria-label={active?.title ?? t('chat.title')}>
        {!active ? (
          <div className={styles.placeholder}><MessageSquare size={36} aria-hidden="true" /><p>{t('chat.pick')}</p></div>
        ) : (
          <>
            <header className={styles.threadHead}>
              <Link to="/chat" className={styles.back} aria-label={t('chat.back')}><ArrowRight size={20} aria-hidden="true" /></Link>
              <h2>{active.title}</h2>
              <small>{t(SECTION[active.kind])}</small>
            </header>
            <ol className={styles.messages}>
              {thread.length === 0 && <li className={styles.empty}>{t('chat.empty')}</li>}
              {thread.map((m) => (
                <li key={m.id} className={`${styles.msg} ${m.authorId === me ? styles.mine : ''}`}>
                  {m.authorId !== me && <b className={styles.author}>{nameOf(m.authorId)}</b>}
                  <p>{m.text}</p>
                  <time dateTime={m.at}>{time(m.at)}</time>
                </li>
              ))}
              <div ref={bottom} />
            </ol>
            <form className={styles.composer} onSubmit={send}>
              <input value={text} onChange={(e) => setText(e.target.value)} placeholder={t('chat.placeholder')} aria-label={t('chat.placeholder')} maxLength={2000} />
              <button type="submit" disabled={!text.trim()} aria-label={t('chat.send')}><Send size={18} aria-hidden="true" /></button>
            </form>
          </>
        )}
      </section>
    </div>
  )
}
