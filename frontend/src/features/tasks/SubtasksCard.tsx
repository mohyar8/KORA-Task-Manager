import { useState } from 'react'
import { useI18n } from '@/shared/i18n/i18n'
import { Button } from '@/shared/ui/Button'
import { ErrorState, Skeleton, useToast } from '@/shared/ui/Feedback'
import { Card } from '@/shared/ui/Layout'
import { Avatar, Row, RowList } from '@/shared/ui/RowList'
import { useCreateSubtask, useSubtasks } from './api'
import { StatusChip, StatusIcon } from './TaskBits'
import { TaskFormModal } from './TaskForm'
import { canCreateSubtask, statusAccent, type Viewer } from './rules'
import type { Task } from './types'
import styles from './tasks.module.css'

export function SubtasksCard({ task, viewer }: { task: Task; viewer: Viewer }) {
  const { t } = useI18n()
  const toast = useToast()
  const query = useSubtasks(task.id)
  const create = useCreateSubtask(task.id)
  const [adding, setAdding] = useState(false)

  return (
    <Card>
      <div className={styles.cardHead}>
        <h2 className={styles.cardTitle}>{t('tasks.subtasks.title')}</h2>
        {canCreateSubtask(task, viewer) && (
          <Button variant="secondary" onClick={() => { create.reset(); setAdding(true) }}>{t('tasks.subtasks.add')}</Button>
        )}
      </div>
      {query.isPending && <Skeleton lines={2} />}
      {query.isError && <ErrorState error={query.error} onRetry={() => void query.refetch()} />}
      {query.data && query.data.length === 0 && <p className={styles.hint}>{t('tasks.subtasks.none')}</p>}
      {query.data && query.data.length > 0 && (
        <RowList label={t('tasks.subtasks.title')}>
          {query.data.map((sub, i) => (
            <Row
              key={sub.id}
              index={i}
              to={`/tasks/${sub.id}`}
              title={sub.title}
              accent={statusAccent[sub.status]}
              leading={<Avatar tone={statusAccent[sub.status]} size={40}><StatusIcon status={sub.status} /></Avatar>}
              trailing={<StatusChip status={sub.status} />}
            />
          ))}
        </RowList>
      )}

      {adding && (
        <TaskFormModal
          title={t('tasks.subtasks.new')}
          submitLabel={t('tasks.create.submit')}
          withAssignees
          loading={create.isPending}
          error={create.error}
          onClose={() => setAdding(false)}
          onSubmit={(v) =>
            create.mutate(
              { title: v.title, description: v.description, priority: v.priority, due_at: v.due_at, assignee_member_ids: v.assignee_member_ids },
              { onSuccess: () => { setAdding(false); toast(t('tasks.subtasks.created')) } },
            )
          }
        />
      )}
    </Card>
  )
}
