import { useMemo, useState } from 'react'
import { Link } from 'react-router'
import { useI18n } from '@/shared/i18n/i18n'
import { Chip, ErrorState, Skeleton } from '@/shared/ui/Feedback'
import { SelectField } from '@/shared/ui/Field'
import { useMemberDirectory } from '@/features/members/directory'
import { useSession } from '@/features/auth/session'
import { TASK_STATUSES } from '@/features/tasks/types'
import { useBroadCalendar, type BroadScope } from './api'
import styles from './calendar.module.css'

// One colour per team; the viewer's own team is always navy so "mine" stands out.
const PALETTE = ['#944399', '#F26557', '#4EA649', '#2A7FA8', '#B8860B', '#7A4E2D', '#6C5CE7', '#C2185B']
const OWN = '#2D3B70'

const dayOf = (iso: string) => {
  const d = new Date(iso)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

/**
 * Month grid of task due dates for the Administration or every Administration. Each team has its own colour.
 * The all-Administrations view can be filtered by status and Administration.
 */
export function BroadCalendar({ scope, month, from, to }: { scope: BroadScope; month: string; from: string; to: string }) {
  const { t, locale } = useI18n()
  const { account } = useSession()
  const query = useBroadCalendar(scope, from, to)
  const directory = useMemberDirectory()
  const myTeam = directory.data?.find((m) => m.id === account?.member_id)?.team_id ?? null
  const [status, setStatus] = useState('')
  const [admin, setAdmin] = useState('')
  const [picked, setPicked] = useState<string | null>(null)

  const all = useMemo(() => query.data?.tasks ?? [], [query.data])
  const administrations = useMemo(() => {
    const seen = new Map<string, string>()
    for (const x of all) if (x.administration_id && x.administration_name) seen.set(x.administration_id, x.administration_name)
    return [...seen.entries()]
  }, [all])
  const colourOf = useMemo(() => {
    const units = [...new Set(all.map((x) => x.scope_unit_id))].sort()
    const map = new Map(units.map((u, i) => [u, PALETTE[i % PALETTE.length]]))
    return (unit: string) => (unit === myTeam ? OWN : (map.get(unit) ?? PALETTE[0]))
  }, [all, myTeam])
  const tasks = all.filter((x) => (!status || x.status === status) && (!admin || x.administration_id === admin))
  const legend = useMemo(() => {
    const seen = new Map<string, string>()
    for (const x of tasks) seen.set(x.scope_unit_id, x.unit_name)
    return [...seen.entries()]
  }, [tasks])

  const tag = locale === 'ar' ? 'ar-u-nu-latn' : 'en-GB'
  const [y, m] = month.split('-').map(Number)
  const first = new Date(y, m - 1, 1)
  const daysInMonth = new Date(y, m, 0).getDate()
  const weekdays = Array.from({ length: 7 }, (_, i) => new Intl.DateTimeFormat(tag, { weekday: 'short' }).format(new Date(2026, 0, 4 + i)))
  const longDay = (key: string) => {
    const [yy, mm, dd] = key.split('-').map(Number)
    return new Intl.DateTimeFormat(tag, { weekday: 'long', day: 'numeric', month: 'long', calendar: 'gregory' }).format(new Date(yy, mm - 1, dd))
  }
  const time = (iso: string) => new Intl.DateTimeFormat(tag, { hour: '2-digit', minute: '2-digit' }).format(new Date(iso))

  const byDay = useMemo(() => {
    const map = new Map<string, typeof tasks>()
    for (const x of tasks) map.set(dayOf(x.due_at), [...(map.get(dayOf(x.due_at)) ?? []), x])
    return map
  }, [tasks])
  const todayKey = dayOf(new Date().toISOString())
  const firstWithItems = [...byDay.keys()].sort()[0]
  const selected = picked && picked.startsWith(month) ? picked : todayKey.startsWith(month) ? todayKey : (firstWithItems ?? `${month}-01`)
  const cells = [
    ...Array.from({ length: first.getDay() }, (): null => null),
    ...Array.from({ length: daysInMonth }, (_, i) => `${month}-${String(i + 1).padStart(2, '0')}`),
  ]

  if (query.isPending) return <Skeleton lines={8} />
  if (query.isError) return <ErrorState error={query.error} onRetry={() => void query.refetch()} />

  return (
    <>
      {scope === 'all' && (
        <div className={styles.filters}>
          <SelectField label={t('cal.filter.administration')} value={admin} onChange={(e) => setAdmin(e.target.value)}>
            <option value="">{t('cal.filter.allAdministrations')}</option>
            {administrations.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
          </SelectField>
          <SelectField label={t('cal.filter.status')} value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">{t('cal.filter.allStatuses')}</option>
            {TASK_STATUSES.map((s) => <option key={s} value={s}>{t(`task.status.${s}`)}</option>)}
          </SelectField>
        </div>
      )}
      <div className={styles.layout}>
        <div className={styles.gridWrap} role="group" aria-label={t(scope === 'all' ? 'cal.view.all' : 'cal.view.administration')}>
          <div className={styles.weekdays} aria-hidden="true">{weekdays.map((w, i) => <span key={i}>{w}</span>)}</div>
          <div className={styles.grid}>
            {cells.map((key, i) => {
              if (!key) return <span key={`pad-${i}`} className={styles.pad} aria-hidden="true" />
              const items = byDay.get(key) ?? []
              return (
                <button
                  key={key}
                  type="button"
                  className={`${styles.day} ${key === todayKey ? styles.today : ''} ${key === selected ? styles.selected : ''}`}
                  aria-pressed={key === selected}
                  aria-label={`${longDay(key)}${items.length ? ` — ${items.length}` : ''}`}
                  onClick={() => setPicked(key)}
                >
                  <span className={styles.num}>{Number(key.slice(8))}</span>
                  <span className={styles.chips}>
                    {items.slice(0, 2).map((it) => (
                      <span
                        key={it.task_id}
                        dir="auto"
                        className={`${styles.chip} ${it.status === 'completed' || it.status === 'cancelled' ? styles.chipDone : ''}`}
                        style={{ background: `color-mix(in srgb, ${colourOf(it.scope_unit_id)} 15%, white)`, color: colourOf(it.scope_unit_id), borderInlineStartColor: colourOf(it.scope_unit_id) }}
                      >
                        {it.title}
                      </span>
                    ))}
                    {items.length > 2 && <span className={styles.more}>+{items.length - 2}</span>}
                  </span>
                </button>
              )
            })}
          </div>
          <p className={styles.legend}>
            {legend.map(([id, name]) => (
              <span key={id}><i className={styles.swatch} style={{ background: colourOf(id) }} /> {name}{id === myTeam ? ` (${t('cal.myTeam')})` : ''}</span>
            ))}
          </p>
        </div>

        <aside className={styles.panel} aria-label={longDay(selected)}>
          <h2 className={styles.panelTitle}>{longDay(selected)}</h2>
          {(byDay.get(selected) ?? []).length === 0 ? (
            <p className={styles.hint}>{t('cal.empty')}</p>
          ) : (
            <ul className={styles.list}>
              {(byDay.get(selected) ?? []).map((it) => (
                <li key={it.task_id} className={styles.item} style={{ borderInlineStartColor: colourOf(it.scope_unit_id) }}>
                  <span className={styles.time}>{time(it.due_at)}</span>
                  <Link className={styles.link} to={`/tasks/${it.task_id}`}>{it.title}</Link>
                  <Chip>{it.unit_name}</Chip>
                  <Chip tone={it.status === 'completed' ? 'success' : it.status === 'cancelled' ? 'danger' : 'info'}>{t(`task.status.${it.status}`)}</Chip>
                  {it.from_outside && <Chip tone="info">{t('tasks.fromOutside')}</Chip>}
                </li>
              ))}
            </ul>
          )}
        </aside>
      </div>
    </>
  )
}
