import { Link } from 'react-router'
import { useI18n } from '@/shared/i18n/i18n'
import { ErrorState, Skeleton } from '@/shared/ui/Feedback'
import { allowedUnits, canAnywhere } from '@/features/auth/permissions'
import { useSession } from '@/features/auth/session'
import { roleLabel } from '@/features/access/labels'
import { useDisplayName, useMemberNames } from '@/features/members/directory'
import { useAnnouncements } from '@/features/announcements/api'
import { PrivateNote } from '@/features/notes/PrivateNote'
import { useTasks } from '@/features/tasks/api'
import { MiniCalendar } from '@/features/tasks/MiniCalendar'
import { MyTasksCard } from '@/features/tasks/MyTasksCard'
import { QuickAdd } from '@/features/tasks/QuickAdd'
import { isAssignee } from '@/features/tasks/rules'
import { useReviewTasks } from '@/features/tasks/reviewTasks'
import { useViewer } from '@/features/tasks/useViewer'
import { workUnits } from '@/features/teams/units'
import { PanelArt } from '@/shared/brand/PanelArt'
import styles from './home.module.css'

/** Home answers one question: what is on my plate? Only the essentials: my tasks, my calendar, the latest announcements. */
export function HomePage() {
  const { t, locale } = useI18n()
  const { access, account } = useSession()
  const viewer = useViewer()
  const names = useMemberNames()
  const displayName = useDisplayName()
  const canSee = canAnywhere(access, 'task.view')
  const query = useTasks({})
  const creatable = allowedUnits(access, 'task.create').map((u) => ({ id: u.unit_id, name: u.name, kind: u.kind }))
  const units = workUnits(access)
  const unitName = (id: string) => units.find((u) => u.unit_id === id)?.name ?? ''
  const hour = new Date().getHours()
  const greeting = hour < 12 ? t('home.greeting.morning') : hour < 18 ? t('home.greeting.afternoon') : t('home.greeting.evening')
  const today = new Intl.DateTimeFormat(locale === 'ar' ? 'ar-u-nu-latn' : 'en-GB', { dateStyle: 'full', calendar: 'gregory' }).format(new Date())
  const all = query.data ?? []
  const reviews = useReviewTasks(all, viewer)
  const mine = [...all.filter((task) => isAssignee(task, viewer)), ...reviews]
  const me = names.members.find((m) => m.id === account?.member_id)
  const myTeam = units.find((u) => u.unit_id === me?.team_id)?.name
  const roleLine = me?.role_key ? [roleLabel(t, me.role_key), myTeam].filter(Boolean).join(' · ') : ''

  return (
    <div className={styles.page}>
      <h1 className="visually-hidden">{t('home.title')}</h1>
      <header className={styles.hello}>
        <PanelArt className={styles.art} />
        <p className={styles.date}>{today}</p>
        <p className={styles.name}>{greeting}، {displayName}</p>
        {roleLine && <p className={styles.role}>{roleLine}</p>}
      </header>

      <div className={styles.cols}>
        <div className={styles.main}>
          <QuickAdd units={creatable} />
          {canSee && query.isPending && <Skeleton lines={5} />}
          {canSee && query.isError && <ErrorState error={query.error} onRetry={() => void query.refetch()} />}
          {canSee && query.data && <MyTasksCard tasks={mine} viewer={viewer} unitName={unitName} />}
        </div>
        <aside className={styles.side}>
          {canSee && query.data && <MiniCalendar tasks={mine} viewer={viewer} unitName={unitName} />}
          <PrivateNote />
          <LatestAnnouncements />
        </aside>
      </div>
    </div>
  )
}

function LatestAnnouncements() {
  const { t } = useI18n()
  const query = useAnnouncements('published')
  const list = (query.data ?? []).filter((a) => !a.content_hidden && a.title).slice(0, 8)
  return (
    <section className={`${styles.card} ${styles.fill}`} aria-label={t('home.announcements')}>
      <h2 className={styles.cardTitle}><span className="eyebrow-num">02</span>{t('home.announcements')}</h2>
      {query.isPending && <Skeleton lines={2} />}
      {query.data && list.length === 0 && <p className={styles.muted}>{t('home.announcements.none')}</p>}
      <ul className={`${styles.plain} ${styles.scroll}`}>
        {list.map((a) => (
          <li key={a.id}>
            <Link to={`/announcements/${a.id}`}>{a.title}</Link>
            {a.my_read_current === false && <span className={styles.new}>{t('home.announcements.new')}</span>}
          </li>
        ))}
      </ul>
      <p><Link to="/announcements">{t('home.announcements.all')}</Link></p>
    </section>
  )
}
