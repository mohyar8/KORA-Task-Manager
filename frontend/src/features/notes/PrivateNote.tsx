import { useEffect, useRef, useState, type KeyboardEvent } from 'react'
import { Lock, StickyNote } from 'lucide-react'
import { useI18n } from '@/shared/i18n/i18n'
import { useSession } from '@/features/auth/session'
import { ApiError } from '@/shared/api/http'
import { isMock } from '@/shared/config'
import { saveNote, useNoteQuery } from './api'
import styles from './notes.module.css'

/**
 * A private scratch note only its owner can read. Real: stored by the server (versioned, so a stale tab cannot
 * overwrite a newer save). Mock: kept in this browser. A note left in the browser by the mock moves to the server
 * the first time the account opens the real app.
 */
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
  const mock = isMock()
  const remote = useNoteQuery(!mock && !!id)
  const [text, setText] = useState(() => (mock ? read(id) : ''))
  const version = useRef(0)
  const lastSaved = useRef('')
  const loaded = useRef(mock)
  const area = useRef<HTMLTextAreaElement>(null)

  // Real: take the server's note once it arrives (or the one the mock left behind, when the server has none).
  useEffect(() => {
    if (mock || loaded.current || !remote.data) return
    loaded.current = true
    version.current = remote.data.version
    const legacy = remote.data.version === 0 ? read(id) : ''
    lastSaved.current = remote.data.body
    setText(legacy || remote.data.body)
  }, [mock, remote.data, id])

  useEffect(() => {
    if (!id || (!mock && !loaded.current)) return
    const handle = window.setTimeout(() => {
      if (mock) {
        try {
          localStorage.setItem(storageKey(id), text)
        } catch {
          // storage unavailable: the note simply is not kept
        }
        return
      }
      if (text === lastSaved.current) return
      saveNote(text, version.current)
        .then((saved) => {
          version.current = saved.version
          lastSaved.current = saved.body
          try {
            localStorage.removeItem(storageKey(id)) // the browser copy has moved to the server
          } catch {
            // nothing to clean
          }
        })
        .catch((error: unknown) => {
          // Saved elsewhere meanwhile: show that newer note instead of overwriting it silently.
          if (error instanceof ApiError && error.status === 409) {
            void remote.refetch().then((r) => {
              if (!r.data) return
              version.current = r.data.version
              lastSaved.current = r.data.body
              setText(r.data.body)
            })
          }
        })
    }, 600)
    return () => window.clearTimeout(handle)
  }, [id, text, mock, remote])

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
