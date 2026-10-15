import { Link } from 'react-router'
import { CircleCheck, Clock3, ListTodo, UserCheck } from 'lucide-react'
import { useCountUp } from '@/shared/lib/useCountUp'
import { useI18n } from '@/shared/i18n/i18n'
import { EmptyState, ErrorState, Skeleton } from '@/shared/ui/Feedback'
import { Card } from '@/shared/ui/Layout'
import { LinkButton } from '@/shared/ui/Button'
import { useTasks } from './api'
import { DueText, StatusChip } from './TaskBits'
import { useViewer } from './useViewer'
import type { ReactNode } from 'react'
import { isAssignee, summarize } from './rules'
import styles from './tasks.module.css'

function Stat({ value, label, tone, icon }: { value: number; label: string; tone: string; icon: ReactNode }) {
  const shown = useCountUp(value)
  return (
    <div className={`${styles.stat} ${styles[tone]}`}>
      <span className={styles.statIcon} aria-hidden="true">{icon}</span>
      <div className={styles.statNumber} aria-label={String(value)}>{shown}</div>
      <div className={styles.statLabel}>{label}</div>
    </div>
  )
}

/** Share of visible tasks that are completed (a derived figure, not an organization-wide metric). */
function tasksTotalDone(tasks: { status: string }[]) {
  return tasks.filter((x) => x.status === 'completed').length
}

/** Home block: labelled as derived from visible tasks, never as organization-wide analytics. */
export function HomeSummary() {
  const { t } = useI18n()
  const viewer = useViewer()
  const query = useTasks({})

  if (query.isPending) return <Skeleton lines={3} />
  if (query.isError) return <ErrorState error={query.error} onRetry={() => void query.refetch()} />

  const s = summarize(query.data, (task) => isAssignee(task, viewer), new Date())
  return (
    <section aria-labelledby="home-summary">
      <h2 id="home-summary" className={styles.cardTitle}>{t('home.summary.title')}</h2>
      <p className={styles.note}>{t('home.summary.note')}</p>
      <div className={styles.summary}>
        <Stat value={s.open} label={t('home.summary.open')} tone="statNavy" icon={<ListTodo size={20} />} />
        <Stat value={s.mine} label={t('home.summary.mine')} tone="statFuchsia" icon={<UserCheck size={20} />} />
        <Stat value={s.overdue} label={t('home.summary.overdue')} tone="statCoral" icon={<Clock3 size={20} />} />
        <Stat value={s.open === 0 ? 0 : Math.round(((tasksTotalDone(query.data)) / Math.max(1, query.data.length)) * 100)} label={t('home.summary.doneRate')} tone="statGreen" icon={<CircleCheck size={20} />} />
      </div>
      <Card>
        <h3 className={styles.cardTitle}>{t('home.dueSoon')}</h3>
        {s.dueSoon.length === 0 ? (
          <EmptyState title={t('home.noDueSoon')} />
        ) : (
          <ul className={styles.list}>
            {s.dueSoon.map((task) => (
              <li key={task.id} className={styles.item}>
                <Link className={styles.titleLink} to={`/tasks/${task.id}`}>{task.title}</Link>
                <span className={styles.meta}><DueText task={task} /> <StatusChip status={task.status} /></span>
              </li>
            ))}
          </ul>
        )}
        <div className={styles.actions}><LinkButton to="/tasks" variant="secondary">{t('home.viewAll')}</LinkButton></div>
      </Card>
    </section>
  )
}
