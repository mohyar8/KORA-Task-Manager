import { useEffect, useRef, useState, type KeyboardEvent } from 'react'
import { Lock, StickyNote } from 'lucide-react'
import { useI18n } from '@/shared/i18n/i18n'
import { useSession } from '@/features/auth/session'
import styles from './notes.module.css'

/** MOCK: a private scratch note kept in this browser, per account. The backend will store it as a row only its owner can read. */
const storageKey = (accountId: string) => `kora.mock.note.${accountId}`
const BULLET = '• '

function read(accountId: string): string {
  try {
    return localStorage.getItem(storageKey(accountId)) ?? ''
  } catch {
    return ''
  }
}

export function PrivateNote() {
  const { t } = useI18n()
  const { account } = useSession()
  const id = account?.id ?? ''
  const [text, setText] = useState(() => read(id))
  const area = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    const handle = window.setTimeout(() => {
      try {
        localStorage.setItem(storageKey(id), text)
      } catch {
        // storage unavailable: the note simply is not kept
      }
    }, 400)
    return () => window.clearTimeout(handle)
  }, [id, text])

  const edit = (next: string, caret: number) => {
    setText(next)
    window.requestAnimationFrame(() => area.current?.setSelectionRange(caret, caret))
  }

  // Every Enter starts a new bullet; Enter on an empty bullet ends the list.
  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key !== 'Enter' || e.shiftKey || e.nativeEvent.isComposing) return
    e.preventDefault()
    const { selectionStart: start, selectionEnd: end } = e.currentTarget
    const lineStart = text.lastIndexOf('\n', start - 1) + 1
    if (text.slice(lineStart, start) === BULLET) edit(text.slice(0, lineStart) + text.slice(end), lineStart)
    else edit(`${text.slice(0, start)}\n${BULLET}${text.slice(end)}`, start + 1 + BULLET.length)
  }

  return (
    <section className={styles.note} aria-label={t('notes.title')}>
      <header>
        <StickyNote size={16} aria-hidden="true" />
        <h2>{t('notes.title')}</h2>
        <span className={styles.lock}><Lock size={12} aria-hidden="true" /> {t('notes.private')}</span>
      </header>
      <textarea
        ref={area}
        value={text}
        rows={3}
        maxLength={5000}
        placeholder={t('notes.placeholder')}
        aria-label={t('notes.title')}
        onChange={(e) => setText(e.target.value)}
        onFocus={() => { if (!text) edit(BULLET, BULLET.length) }}
        onBlur={() => { if (text.trim() === BULLET.trim()) setText('') }}
        onKeyDown={onKeyDown}
      />
    </section>
  )
}
