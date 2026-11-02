import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { ArrowRight, Building2, Globe2, MessageSquare, Send, Trash2, UserRound, Users } from 'lucide-react'
import { useI18n } from '@/shared/i18n/i18n'
import type { MessageKey } from '@/shared/i18n/messages.en'
import { isMock } from '@/shared/config'
import { ErrorState, InlineError, Skeleton } from '@/shared/ui/Feedback'
import { ApiError } from '@/shared/api/http'
import { chatActions, type ChannelKind } from '@/mock/chatStore'
import { useChatData } from './useChatData'
import styles from './chat.module.css'

const ORDER: ChannelKind[] = ['direct', 'team', 'administration', 'organization']
const SECTION: Record<ChannelKind, MessageKey> = { direct: 'chat.section.direct', team: 'chat.section.team', administration: 'chat.section.administration', organization: 'chat.section.organization' }
const ICON = { direct: UserRound, team: Users, administration: Building2, organization: Globe2 }
const SEED = ['chat.seed.1', 'chat.seed.2'] as const

/** Conversations: private, team, administration and the whole organization, in one place. */
export function ChatPage() {
  const { t, locale } = useI18n()
  const navigate = useNavigate()
  const { channelId = '' } = useParams()
  const chat = useChatData(channelId)
  const { me, people, nameOf, channels, messages: thread } = chat
  const active = channels.find((c) => c.id === channelId)
  const [text, setText] = useState('')
  const [failure, setFailure] = useState<unknown>(null)
  const bottom = useRef<HTMLDivElement>(null)
  const others = people.filter((m) => m.id !== me)
  const { openDm, markRead } = chat

  // `/chat/dm:<member>` (from the structure chart): the real app opens the private chat first, then shows it.
  useEffect(() => {
    if (isMock() || !channelId.startsWith('dm:')) return
    openDm(channelId.slice(3)).then((id) => void navigate(`/chat/${id}`, { replace: true }), (error: unknown) => setFailure(error))
  }, [channelId, openDm, navigate])
  useEffect(() => {
    if (!isMock() || !active || active.kind === 'direct') return
    chatActions.seed(active.id, others.slice(0, 2).map((m) => m.id), SEED.map((k) => t(k)))
  }, [active, others, t])
  useEffect(() => {
    if (channelId) markRead()
    bottom.current?.scrollIntoView?.({ block: 'end' })
  }, [channelId, thread.length, markRead])

  const send = (e: FormEvent) => {
    e.preventDefault()
    if (!active || !text.trim() || !me) return
    const message = text
    setText('')
    setFailure(null)
    chat.send(message).catch((error: unknown) => { setText(message); setFailure(error) })
  }
  const start = (memberId: string) => {
    setFailure(null)
    openDm(memberId).then((id) => void navigate(`/chat/${id}`), (error: unknown) => setFailure(error))
  }
  const time = (iso: string) => new Intl.DateTimeFormat(locale === 'ar' ? 'ar-u-nu-latn' : 'en-GB', { hour: '2-digit', minute: '2-digit', hour12: false }).format(new Date(iso))

  if (chat.isLoading) return <div className={styles.chat}><Skeleton lines={6} /></div>
  if (chat.error && channels.length === 0) return <div className={styles.chat}><ErrorState error={chat.error} /></div>

  return (
    <div className={`${styles.chat} ${channelId ? styles.threadOpen : ''}`}>
      <aside className={styles.list} aria-label={t('chat.title')}>
        <h1 className={styles.heading}>{t('chat.title')}</h1>
        <label className={styles.newDm}>
          <span className="visually-hidden">{t('chat.new')}</span>
          <select value="" onChange={(e) => { if (e.target.value) start(e.target.value) }}>
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
                  <p>{m.deleted ? <i>{t('chat.deleted')}</i> : m.text}</p>
                  <time dateTime={m.at}>{time(m.at)}</time>
                  {m.canDelete && chat.remove && (
                    <button type="button" className={styles.del} aria-label={t('chat.delete')} onClick={() => void chat.remove!(m.id)}><Trash2 size={14} aria-hidden="true" /></button>
                  )}
                </li>
              ))}
              <div ref={bottom} />
            </ol>
            {failure != null && <InlineError error={failure instanceof ApiError && failure.status === 429 ? new Error(t('chat.rateLimited')) : failure} />}
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
