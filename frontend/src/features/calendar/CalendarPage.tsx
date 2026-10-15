import { useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { ChevronLeft, ChevronRight, Plus } from 'lucide-react'
import { useI18n } from '@/shared/i18n/i18n'
import { Button } from '@/shared/ui/Button'
import { Chip, ErrorState, Skeleton, useToast } from '@/shared/ui/Feedback'
import { PageHeader } from '@/shared/ui/Layout'
import { allowedUnits } from '@/features/auth/permissions'
import { useSession } from '@/features/auth/session'
import { currentMonth, groupByDay, isMonth, monthRange, shiftMonth, useCreateEvent, useMyCalendar, type AgendaItem } from './api'
import { EventFormModal } from './EventForm'
import styles from './calendar.module.css'

const dayKey = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`

/** /calendar?m=YYYY-MM — a month grid of day squares (events + the caller's own task due dates); click a day for its list. */
export function CalendarPage() {
  const { t, locale } = useI18n()
  const toast = useToast()
  const { account, access } = useSession()
  const [params, setParams] = useSearchParams()
  const requested = params.get('m')
  const month = isMonth(requested) ? requested : currentMonth()
  const { from, to } = monthRange(month)
  const query = useMyCalendar(from, to)
  const create = useCreateEvent()
  const [creating, setCreating] = useState(false)
  const [picked, setPicked] = useState<string | null>(null)

  const tag = locale === 'ar' ? 'ar-u-nu-latn' : 'en-GB'
  const [y, m] = month.split('-').map(Number)
  const first = new Date(y, m - 1, 1)
  const daysInMonth = new Date(y, m, 0).getDate()
  const monthLabel = new Intl.DateTimeFormat(tag, { month: 'long', year: 'numeric', calendar: 'gregory' }).format(first)
  const weekdays = Array.from({ length: 7 }, (_, i) => new Intl.DateTimeFormat(tag, { weekday: 'short' }).format(new Date(2026, 0, 4 + i))) // Sunday first
  const longDay = (key: string) => {
    const [yy, mm, dd] = key.split('-').map(Number)
    return new Intl.DateTimeFormat(tag, { weekday: 'long', day: 'numeric', month: 'long', calendar: 'gregory' }).format(new Date(yy, mm - 1, dd))
  }
  const time = (iso: string) => new Intl.DateTimeFormat(tag, { hour: '2-digit', minute: '2-digit' }).format(new Date(iso))

  const byDay = useMemo(() => new Map(query.data ? groupByDay(query.data) : []), [query.data])
  const todayKey = dayKey(new Date())
  const firstWithItems = [...byDay.keys()].sort()[0]
  const selected = picked && picked.startsWith(month) ? picked : todayKey.startsWith(month) ? todayKey : (firstWithItems ?? `${month}-01`)
  const selectedItems = byDay.get(selected) ?? []

  const go = (next: string) => {
    setPicked(null)
    setParams({ m: next }, { replace: true })
  }
  const creatable = allowedUnits(access, 'calendar.create').map((u) => ({ id: u.unit_id, name: u.name }))
  const canCreate = !!account?.member_id && creatable.length > 0

  const cells = [
    ...Array.from({ length: first.getDay() }, (): null => null),
    ...Array.from({ length: daysInMonth }, (_, i) => `${month}-${String(i + 1).padStart(2, '0')}`),
  ]

  const label = (it: AgendaItem) => (it.kind === 'event' ? it.event.title : it.task.title)

  return (
    <>
      <PageHeader
        title={t('cal.title')}
        description={t('cal.description')}
        actions={canCreate && <Button onClick={() => { create.reset(); setCreating(true) }}><Plus size={18} aria-hidden="true" /> {t('cal.new')}</Button>}
      />

      <div className={styles.monthBar}>
        <div className={styles.nav}>
          <Button variant="secondary" onClick={() => go(shiftMonth(month, -1))} aria-label={t('cal.prev')}><ChevronLeft size={18} className={styles.flip} aria-hidden="true" /></Button>
          <span className={styles.monthName} aria-live="polite">{monthLabel}</span>
          <Button variant="secondary" onClick={() => go(shiftMonth(month, 1))} aria-label={t('cal.next')}><ChevronRight size={18} className={styles.flip} aria-hidden="true" /></Button>
        </div>
        <Button variant="ghost" onClick={() => go(currentMonth())}>{t('cal.today')}</Button>
      </div>

      {query.isPending && <Skeleton lines={8} />}
      {query.isError && <ErrorState error={query.error} onRetry={() => void query.refetch()} />}
      {query.data && (
        <div className={styles.layout}>
          <div className={styles.gridWrap} role="group" aria-label={monthLabel}>
            <div className={styles.weekdays} aria-hidden="true">
              {weekdays.map((w, i) => <span key={i}>{w}</span>)}
            </div>
            <div className={styles.grid}>
              {cells.map((key, i) => {
                if (!key) return <span key={`pad-${i}`} className={styles.pad} aria-hidden="true" />
                const items = byDay.get(key) ?? []
                const events = items.filter((x) => x.kind === 'event').length
                const tasks = items.length - events
                const day = Number(key.slice(8))
                return (
                  <button
                    key={key}
                    type="button"
                    className={`${styles.day} ${key === todayKey ? styles.today : ''} ${key === selected ? styles.selected : ''}`}
                    aria-pressed={key === selected}
                    aria-label={`${longDay(key)}${items.length ? ` — ${items.length}` : ''}`}
                    onClick={() => setPicked(key)}
                  >
                    <span className={styles.num}>{day}</span>
                    <span className={styles.chips}>
                      {items.slice(0, 2).map((it, n) => (
                        <span key={n} dir="auto" className={`${styles.chip} ${it.kind === 'event' ? styles.chipEvent : styles.chipTask}`}>{label(it)}</span>
                      ))}
                      {items.length > 2 && <span className={styles.more}>+{items.length - 2}</span>}
                    </span>
                    <span className={styles.dots} aria-hidden="true">
                      {events > 0 && <i className={styles.dotEvent} />}
                      {tasks > 0 && <i className={styles.dotTask} />}
                    </span>
                  </button>
                )
              })}
            </div>
            <p className={styles.legend}>
              <span><i className={styles.dotEvent} /> {t('cal.type.event')} / {t('cal.type.meeting')}</span>
              <span><i className={styles.dotTask} /> {t('cal.taskDue')}</span>
            </p>
          </div>

          <aside className={styles.panel} aria-label={longDay(selected)}>
            <h2 className={styles.panelTitle}>{longDay(selected)}</h2>
            {selectedItems.length === 0 ? (
              <p className={styles.hint}>{t('cal.empty')}</p>
            ) : (
              <ul className={styles.list}>
                {selectedItems.map((item) =>
                  item.kind === 'event' ? (
                    <li key={`e-${item.event.id}`} className={`${styles.item} ${styles.event} ${item.event.state === 'cancelled' ? styles.cancelled : ''}`}>
                      <span className={styles.time}>{time(item.event.starts_at)} – {time(item.event.ends_at)}</span>
                      <Link className={styles.link} to={`/calendar/${item.event.id}`}>{item.event.title}</Link>
                      <Chip tone="info">{t(`cal.type.${item.event.type}`)}</Chip>
                      {item.event.state === 'cancelled' && <Chip tone="danger">{t('cal.cancelledChip')}</Chip>}
                    </li>
                  ) : (
                    <li key={`t-${item.task.task_id}`} className={`${styles.item} ${styles.task}`}>
                      <span className={styles.time}>{time(item.task.due_at)}</span>
                      <Link className={styles.link} to={`/tasks/${item.task.task_id}`}>{item.task.title}</Link>
                      <Chip tone="danger">{t('cal.taskDue')}</Chip>
                    </li>
                  ),
                )}
              </ul>
            )}
            <p className={styles.note}>{t('cal.taskDueNote')}</p>
          </aside>
        </div>
      )}

      {creating && (
        <EventFormModal
          title={t('cal.create.title')}
          submitLabel={t('cal.create.submit')}
          scopeOptions={creatable}
          loading={create.isPending}
          error={create.error}
          onClose={() => setCreating(false)}
          onSubmit={(v) => create.mutate(v, { onSuccess: () => { setCreating(false); toast(t('cal.created')) } })}
        />
      )}
    </>
  )
}
