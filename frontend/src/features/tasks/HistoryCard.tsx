import { useI18n } from '@/shared/i18n/i18n'
import { formatDateTime } from '@/shared/lib/format'
import { ErrorState, Skeleton } from '@/shared/ui/Feedback'
import { Card } from '@/shared/ui/Layout'
import { allUnits } from '@/features/auth/permissions'
import { useSession } from '@/features/auth/session'
import { useMemberNames } from '@/features/members/directory'
import { useTaskHistory } from './api'
import { describeEvent } from './history'
import type { Task } from './types'
import styles from './tasks.module.css'

export function HistoryCard({ task }: { task: Task }) {
  const { t, locale } = useI18n()
  const { access } = useSession()
  const names = useMemberNames()
  const query = useTaskHistory(task.id)
  const unitName = (id: string) => allUnits(access).find((u) => u.unit_id === id)?.name ?? id

  return (
    <Card>
      <h2 className={styles.cardTitle}>{t('tasks.history.title')}</h2>
      {query.isPending && <Skeleton lines={3} />}
      {query.isError && <ErrorState error={query.error} onRetry={() => void query.refetch()} />}
      {query.data && query.data.length === 0 && <p className={styles.hint}>{t('tasks.history.none')}</p>}
      {query.data && query.data.length > 0 && (
        <ol className={styles.timeline}>
          {[...query.data].reverse().map((e, i) => (
            <li key={`${e.created_at}-${i}`}>
              <span>{describeEvent(e, { t, memberName: names.nameOf, unitName })}</span>
              <span className={styles.when}>{formatDateTime(e.created_at, locale)}</span>
            </li>
          ))}
        </ol>
      )}
    </Card>
  )
}
