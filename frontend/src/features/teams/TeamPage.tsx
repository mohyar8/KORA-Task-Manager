import { useParams } from 'react-router'
import { useI18n } from '@/shared/i18n/i18n'
import { AccessDenied, ErrorState, Skeleton } from '@/shared/ui/Feedback'
import { allowedUnits } from '@/features/auth/permissions'
import { useSession } from '@/features/auth/session'
import { roleLabel } from '@/features/access/labels'
import { useMemberNames } from '@/features/members/directory'
import { useTasks } from '@/features/tasks/api'
import { MiniCalendar } from '@/features/tasks/MiniCalendar'
import { QuickAdd } from '@/features/tasks/QuickAdd'
import { TaskGroupList } from '@/features/tasks/TaskGroups'
import { isOpen, isOverdue } from '@/features/tasks/rules'
import { useViewer } from '@/features/tasks/useViewer'
import { teamColor } from './teamColor'
import { workUnits } from './units'
import styles from './teams.module.css'

/** One place per team: its numbers, tasks, calendar, people, events and announcements. */
export function TeamPage() {
  const { t } = useI18n()
  const { unitId = '' } = useParams()
  const { access } = useSession()
  const viewer = useViewer()
  const query = useTasks({ scope_unit_id: unitId })
  const unit = workUnits(access).find((u) => u.unit_id === unitId)
  if (!unit) return <AccessDenied />

  const creatable = allowedUnits(access, 'task.create').filter((u) => u.unit_id === unitId).map((u) => ({ id: u.unit_id, name: u.name, kind: u.kind }))
  const tasks = query.data ?? []
  const open = tasks.filter(isOpen)
  const late = open.filter((x) => isOverdue(x, new Date())).length
  const done = tasks.filter((x) => x.status === 'completed').length

  return (
    <div className={styles.page}>
      <header className={styles.head}>
        <span className={styles.swatch} style={{ background: teamColor(unitId) }} aria-hidden="true">{unit.name.charAt(0)}</span>
        <div>
          <h1 className={styles.title}>{unit.name}</h1>
          <p className={styles.sub}>{t(unit.kind === 'team' ? 'team.kind.team' : 'team.kind.administration')}</p>
        </div>
      </header>

      <ul className={styles.stats}>
        <li><b>{open.length}</b><span>{t('team.stat.open')}</span></li>
        <li className={late > 0 ? styles.statLate : undefined}><b>{late}</b><span>{t('team.stat.late')}</span></li>
        <li><b>{done}</b><span>{t('team.stat.done')}</span></li>
      </ul>

      <div className={styles.cols}>
        <div className={styles.main}>
          <QuickAdd units={creatable} fixedUnitId={unitId} />
          {query.isPending && <Skeleton lines={5} />}
          {query.isError && <ErrorState error={query.error} onRetry={() => void query.refetch()} />}
          {query.data && <div className={styles.scroll}><TaskGroupList tasks={tasks} viewer={viewer} showDone empty={t('team.tasks.empty')} /></div>}
        </div>
        <aside className={styles.side}>
          {query.data && <MiniCalendar tasks={tasks} viewer={viewer} />}
          {unit.kind === 'team' && <MembersCard unitId={unitId} tasks={tasks} />}
        </aside>
      </div>
    </div>
  )
}

function MembersCard({ unitId, tasks }: { unitId: string; tasks: { assignee_member_ids: string[]; status: string }[] }) {
  const { t } = useI18n()
  const names = useMemberNames()
  const people = names.members.filter((m) => m.team_id === unitId)
  return (
    <section className={`${styles.card} ${styles.fill}`} aria-label={t('team.tab.members')}>
      <h2 className={styles.cardTitle}>{t('team.tab.members')} <span className={styles.count}>{people.length}</span></h2>
      {names.isLoading && <Skeleton lines={3} />}
      <ul className={`${styles.people} ${styles.scroll}`}>
        {people.map((m) => {
          const n = tasks.filter((x) => (x.status === 'new' || x.status === 'in_progress') && x.assignee_member_ids.includes(m.id)).length
          return (
            <li key={m.id}>
              <span className={styles.avatar} style={{ background: teamColor(m.id) }} aria-hidden="true">{m.full_name.charAt(0)}</span>
              <span className={styles.personText}><span>{m.full_name}</span>{m.role_key && <small>{roleLabel(t, m.role_key)}</small>}</span>
              <span className={styles.load}>{t('home.team.open', { n })}</span>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
