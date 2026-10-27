import { useMemo, useState } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useI18n } from '@/shared/i18n/i18n'
import { isOpen } from './rules'
import { TaskLine } from './TaskLine'
import type { Viewer } from './rules'
import type { Task } from './types'
import styles from './miniCalendar.module.css'

type View = 'month' | 'week'

const key = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
const addDays = (d: Date, n: number) => new Date(d.getFullYear(), d.getMonth(), d.getDate() + n)
const startOfWeek = (d: Date) => addDays(d, -d.getDay()) // Sunday first, like the main calendar

/** The days to draw: whole weeks covering the month, or just the anchor's week. */
function daysFor(view: View, anchor: Date): Date[] {
  const first = view === 'week' ? startOfWeek(anchor) : startOfWeek(new Date(anchor.getFullYear(), anchor.getMonth(), 1))
  const count = view === 'week' ? 7 : Math.ceil((new Date(anchor.getFullYear(), anchor.getMonth() + 1, 0).getDate() + new Date(anchor.getFullYear(), anchor.getMonth(), 1).getDay()) / 7) * 7
  return Array.from({ length: count }, (_, i) => addDays(first, i))
}

interface Props {
  tasks: Task[]
  viewer: Viewer
  unitName?: (id: string) => string
}

/** A small month/week calendar: a dot on every day with a task due; click a day to list its tasks underneath. */
export function MiniCalendar({ tasks, viewer, unitName }: Props) {
  const { t, locale } = useI18n()
  const [view, setView] = useState<View>('month')
  const [anchor, setAnchor] = useState(() => new Date())
  const [picked, setPicked] = useState<string | null>(null)
  const today = key(new Date())

  const byDay = useMemo(() => {
    const map = new Map<string, Task[]>()
    for (const task of tasks) {
      if (!task.due_at) continue
      const k = key(new Date(task.due_at))
      map.set(k, [...(map.get(k) ?? []), task])
    }
    return map
  }, [tasks])

  const tag = locale === 'ar' ? 'ar-u-nu-latn' : 'en-GB'
  const weekdays = Array.from({ length: 7 }, (_, i) => new Intl.DateTimeFormat(tag, { weekday: 'narrow' }).format(addDays(new Date(2026, 0, 4), i))) // 4 Jan 2026 is a Sunday
  const title = new Intl.DateTimeFormat(tag, view === 'month' ? { month: 'long', year: 'numeric' } : { day: 'numeric', month: 'long' }).format(anchor)
  const step = (dir: 1 | -1) => setAnchor(view === 'month' ? new Date(anchor.getFullYear(), anchor.getMonth() + dir, 1) : addDays(anchor, 7 * dir))
  const days = daysFor(view, anchor)
  const shown = picked ? (byDay.get(picked) ?? []) : []
  const Prev = locale === 'ar' ? ChevronRight : ChevronLeft
  const Next = locale === 'ar' ? ChevronLeft : ChevronRight

  return (
    <section className={styles.box} aria-label={t('miniCal.title')}>
      <div className={styles.head}>
        <h2 className={styles.title}>{title}</h2>
        <div className={styles.controls}>
          <button type="button" className={styles.nav} onClick={() => step(-1)} aria-label={t('miniCal.prev')}><Prev size={18} aria-hidden="true" /></button>
          <button type="button" className={styles.nav} onClick={() => step(1)} aria-label={t('miniCal.next')}><Next size={18} aria-hidden="true" /></button>
        </div>
      </div>
      <div className={styles.switch} role="group" aria-label={t('miniCal.view')}>
        <button type="button" aria-pressed={view === 'month'} onClick={() => setView('month')}>{t('miniCal.month')}</button>
        <button type="button" aria-pressed={view === 'week'} onClick={() => setView('week')}>{t('miniCal.week')}</button>
        <button type="button" className={styles.todayBtn} onClick={() => { setAnchor(new Date()); setPicked(today) }}>{t('miniCal.today')}</button>
      </div>
      <div className={styles.grid} role="grid" aria-label={title}>
        {weekdays.map((w, i) => <span key={i} className={styles.dow} aria-hidden="true">{w}</span>)}
        {days.map((d) => {
          const k = key(d)
          const list = byDay.get(k) ?? []
          const open = list.some(isOpen)
          const late = open && k < today
          const outside = view === 'month' && d.getMonth() !== anchor.getMonth()
          return (
            <button
              key={k}
              type="button"
              role="gridcell"
              className={`${styles.day} ${k === today ? styles.today : ''} ${k === picked ? styles.picked : ''} ${outside ? styles.outside : ''}`}
              aria-selected={k === picked}
              aria-label={t('miniCal.dayLabel', { date: new Intl.DateTimeFormat(tag, { dateStyle: 'full' }).format(d), n: list.length })}
              onClick={() => setPicked(k === picked ? null : k)}
            >
              <span>{d.getDate()}</span>
              {list.length > 0 && <i className={`${styles.dot} ${late ? styles.dotLate : open ? '' : styles.dotDone}`} aria-hidden="true" />}
            </button>
          )
        })}
      </div>
      {picked && (
        <div className={styles.dayList}>
          {shown.length === 0 ? (
            <p className={styles.none}>{t('miniCal.none')}</p>
          ) : (
            <ul className={styles.tasks}>{shown.map((task) => <TaskLine key={task.id} task={task} viewer={viewer} unitName={unitName?.(task.scope_unit_id)} />)}</ul>
          )}
        </div>
      )}
    </section>
  )
}
