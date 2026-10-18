import { useState } from 'react'
import { Link, useParams } from 'react-router'
import { ArrowRight } from 'lucide-react'
import { useI18n } from '@/shared/i18n/i18n'
import { formatDateTime } from '@/shared/lib/format'
import { Button } from '@/shared/ui/Button'
import { Chip, ErrorState, InlineError, Skeleton, useToast } from '@/shared/ui/Feedback'
import { SelectField } from '@/shared/ui/Field'
import { Card, PageHeader } from '@/shared/ui/Layout'
import { ConfirmDialog, Modal } from '@/shared/ui/Modal'
import { allUnits, allowedUnits } from '@/features/auth/permissions'
import { useSession } from '@/features/auth/session'
import { useMemberNames } from '@/features/members/directory'
import { useMoveTask, useSetStatus, useTask, useUpdateTask } from './api'
import { AssigneesCard } from './AssigneesCard'
import { CommentsCard } from './CommentsCard'
import { HistoryCard } from './HistoryCard'
import { SubtasksCard } from './SubtasksCard'
import { DueText, PriorityText, StatusChip } from './TaskBits'
import { useViewer } from './useViewer'
import { TaskFormModal } from './TaskForm'
import { allowedTransitions, canAdminister, changedFields } from './rules'
import type { Task, TaskStatus } from './types'
import styles from './tasks.module.css'

export function TaskDetailPage() {
  const { taskId = '' } = useParams()
  const query = useTask(taskId)
  if (query.isPending) return <Skeleton lines={6} />
  if (query.isError) return <ErrorState error={query.error} onRetry={() => void query.refetch()} />
  return <TaskView task={query.data} />
}

function TaskView({ task }: { task: Task }) {
  const { t, locale } = useI18n()
  const toast = useToast()
  const { access } = useSession()
  const viewer = useViewer()
  const names = useMemberNames()
  const update = useUpdateTask(task.id)
  const setStatus = useSetStatus(task.id)
  const move = useMoveTask(task.id)

  const [editing, setEditing] = useState(false)
  const [moving, setMoving] = useState(false)
  const [destination, setDestination] = useState('')
  const [confirm, setConfirm] = useState<TaskStatus | null>(null)

  const unitName = (id: string) => allUnits(access).find((u) => u.unit_id === id)?.name ?? id
  const admin = canAdminister(task, viewer)
  const transitions = allowedTransitions(task, viewer)
  const moveOptions = allowedUnits(access, 'task.create').filter((u) => u.unit_id !== task.scope_unit_id)

  const run = (status: TaskStatus) => {
    setStatus.reset()
    setStatus.mutate(status, { onSuccess: () => { setConfirm(null); toast(t('tasks.statusChanged')) } })
  }

  return (
    <>
      <Link className={styles.back} to={task.parent_id ? `/tasks/${task.parent_id}` : '/tasks'}>
        <ArrowRight size={16} aria-hidden="true" className={styles.backIcon} /> {task.parent_id ? t('tasks.detail.parentLink') : t('tasks.back')}
      </Link>
      <PageHeader
        title={task.title}
        description={task.parent_id ? t('tasks.detail.parent') : undefined}
        actions={
          <div className={styles.actions}>
            {transitions.map((s) => (
              <Button
                key={s}
                variant={s === 'cancelled' ? 'danger' : s === 'new' ? 'secondary' : 'primary'}
                onClick={() => (s === 'cancelled' || s === 'new' ? (setStatus.reset(), setConfirm(s)) : run(s))}
                loading={setStatus.isPending && setStatus.variables === s && confirm === null}
              >
                {t(`tasks.action.${s}`)}
              </Button>
            ))}
            {admin && <Button variant="secondary" onClick={() => { update.reset(); setEditing(true) }}>{t('tasks.edit')}</Button>}
            {admin && !task.parent_id && moveOptions.length > 0 && (
              <Button variant="secondary" onClick={() => { move.reset(); setDestination(''); setMoving(true) }}>{t('tasks.move')}</Button>
            )}
          </div>
        }
      />
      {setStatus.error && confirm === null && <InlineError error={setStatus.error} />}

      <div className={styles.sections}>
        <Card>
          <dl className={styles.facts}>
            <dt>{t('tasks.col.status')}</dt>
            <dd><StatusChip status={task.status} /> {task.from_outside && <Chip tone="info">{t('tasks.fromOutside')}</Chip>} {task.series_id && <Link to={`/task-series/${task.series_id}`}><Chip>{t('series.open')}</Chip></Link>}</dd>
            <dt>{t('tasks.col.priority')}</dt>
            <dd><PriorityText priority={task.priority} /></dd>
            <dt>{t('tasks.col.due')}</dt>
            <dd><DueText task={task} /></dd>
            <dt>{t('tasks.detail.scope')}</dt>
            <dd>{unitName(task.scope_unit_id)}</dd>
            <dt>{t('tasks.detail.createdBy')}</dt>
            <dd>{names.nameOf(task.created_by_member_id)}</dd>
            <dt>{t('tasks.detail.created')}</dt>
            <dd>{formatDateTime(task.created_at, locale)}</dd>
            <dt>{t('tasks.detail.updated')}</dt>
            <dd>{formatDateTime(task.updated_at, locale)}</dd>
            {task.started_at && (
              <>
                <dt>{t('tasks.detail.started')}</dt>
                <dd>{formatDateTime(task.started_at, locale)}</dd>
              </>
            )}
          </dl>
          {task.description && <p className={styles.description}>{task.description}</p>}
        </Card>

        <AssigneesCard task={task} viewer={viewer} />
        {!task.parent_id && <SubtasksCard task={task} viewer={viewer} />}
        <CommentsCard task={task} viewer={viewer} />
        <HistoryCard task={task} />
      </div>

      {editing && (
        <TaskFormModal
          title={t('tasks.edit.title')}
          submitLabel={t('common.save')}
          initial={task}
          loading={update.isPending}
          error={update.error}
          onClose={() => setEditing(false)}
          onSubmit={(v) => {
            const diff = changedFields(task, v)
            if (Object.keys(diff).length === 0) {
              setEditing(false)
              return toast(t('tasks.noChanges'), 'info')
            }
            update.mutate(diff, { onSuccess: () => { setEditing(false); toast(t('tasks.updated')) } })
          }}
        />
      )}

      <Modal
        open={moving}
        title={t('tasks.move.title')}
        onClose={() => setMoving(false)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setMoving(false)}>{t('common.cancel')}</Button>
            <Button
              disabled={!destination}
              loading={move.isPending}
              onClick={() => move.mutate(destination, { onSuccess: () => { setMoving(false); toast(t('tasks.moved')) } })}
            >
              {t('tasks.move')}
            </Button>
          </>
        }
      >
        <div className={styles.form}>
          <p>{t('tasks.move.body')}</p>
          <SelectField label={t('tasks.field.scope')} value={destination} onChange={(e) => setDestination(e.target.value)}>
            <option value="">{t('tasks.pickUnit')}</option>
            {moveOptions.map((u) => <option key={u.unit_id} value={u.unit_id}>{u.name}</option>)}
          </SelectField>
          <InlineError error={move.error} />
        </div>
      </Modal>

      <ConfirmDialog
        open={confirm !== null}
        title={confirm === 'cancelled' ? t('tasks.cancel.title') : t('tasks.reopen.title')}
        body={
          <div className={styles.form}>
            <p>{confirm === 'cancelled' ? t('tasks.cancel.body') : t('tasks.reopen.body')}</p>
            <InlineError error={setStatus.error} />
          </div>
        }
        confirmLabel={confirm ? t(`tasks.action.${confirm}`) : undefined}
        danger={confirm === 'cancelled'}
        loading={setStatus.isPending}
        onConfirm={() => confirm && run(confirm)}
        onClose={() => setConfirm(null)}
      />
    </>
  )
}
