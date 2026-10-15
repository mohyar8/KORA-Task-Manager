import { useState, type DragEvent } from 'react'
import { Link } from 'react-router'
import { CalendarClock, GripVertical } from 'lucide-react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { http } from '@/shared/api/http'
import { useI18n } from '@/shared/i18n/i18n'
import { Chip, InlineError, useToast } from '@/shared/ui/Feedback'
import { ConfirmDialog } from '@/shared/ui/Modal'
import { useMemberNames } from '@/features/members/directory'
import { tasksKey } from './api'
import { DueText } from './TaskBits'
import { allowedTransitions, type Viewer } from './rules'
import { TASK_STATUSES, type Task, type TaskStatus } from './types'
import styles from './board.module.css'

const COLUMN_TONE: Record<TaskStatus, string> = { new: 'colNew', in_progress: 'colProgress', completed: 'colDone', cancelled: 'colCancelled' }

/** Kanban view: drag a card to another column to change its status (only moves the API allows are offered). */
export function TaskBoard({ tasks, viewer }: { tasks: Task[]; viewer: Viewer }) {
  const { t } = useI18n()
  const toast = useToast()
  const qc = useQueryClient()
  const names = useMemberNames()
  const [dragging, setDragging] = useState<Task | null>(null)
  const [over, setOver] = useState<TaskStatus | null>(null)
  const [pending, setPending] = useState<{ task: Task; status: TaskStatus } | null>(null)

  const move = useMutation({
    mutationFn: (v: { id: string; status: TaskStatus }) => http.post<Task>(`/tasks/${v.id}/status`, { status: v.status }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: tasksKey })
      toast(t('tasks.statusChanged'))
    },
  })

  const canDrop = (task: Task | null, status: TaskStatus) => !!task && allowedTransitions(task, viewer).includes(status)

  const request = (task: Task, status: TaskStatus) => {
    if (!canDrop(task, status)) return toast(t('tasks.board.noMove'), 'info')
    // Cancelling and reopening are consequential: explain first, like on the detail page.
    if (status === 'cancelled' || status === 'new') {
      move.reset()
      return setPending({ task, status })
    }
    move.mutate({ id: task.id, status })
  }

  const onDrop = (e: DragEvent, status: TaskStatus) => {
    e.preventDefault()
    const task = dragging
    setDragging(null)
    setOver(null)
    if (task && task.status !== status) request(task, status)
  }

  return (
    <>
      <p className={styles.hint}>{t('tasks.board.dropHint')}</p>
      <div className={styles.board}>
        {TASK_STATUSES.map((status) => {
          const items = tasks.filter((x) => x.status === status)
          const droppable = dragging ? canDrop(dragging, status) || dragging.status === status : false
          return (
            <section
              key={status}
              className={`${styles.column} ${styles[COLUMN_TONE[status]]} ${over === status && droppable ? styles.over : ''} ${dragging && !droppable ? styles.dim : ''}`}
              aria-label={t(`task.status.${status}`)}
              onDragOver={(e) => {
                if (droppable) {
                  e.preventDefault()
                  setOver(status)
                }
              }}
              onDragLeave={() => setOver((cur) => (cur === status ? null : cur))}
              onDrop={(e) => onDrop(e, status)}
            >
              <h2 className={styles.colHead}>
                <span>{t(`task.status.${status}`)}</span>
                <span className={styles.count}>{items.length}</span>
              </h2>
              <ul className={styles.cards}>
                {items.length === 0 && <li className={styles.empty}>{t('tasks.board.empty')}</li>}
                {items.map((task) => {
                  const options = allowedTransitions(task, viewer)
                  return (
                    <li
                      key={task.id}
                      className={`${styles.card} ${dragging?.id === task.id ? styles.lifted : ''}`}
                      draggable={options.length > 0}
                      onDragStart={(e) => {
                        e.dataTransfer.effectAllowed = 'move'
                        e.dataTransfer.setData('text/plain', task.id)
                        setDragging(task)
                      }}
                      onDragEnd={() => {
                        setDragging(null)
                        setOver(null)
                      }}
                    >
                      <div className={styles.cardTop}>
                        {options.length > 0 && <GripVertical size={16} className={styles.grip} aria-hidden="true" />}
                        <Link className={styles.cardTitle} to={`/tasks/${task.id}`}>{task.title}</Link>
                      </div>
                      <div className={styles.cardMeta}>
                        {task.priority && <Chip tone={task.priority === 'urgent' ? 'danger' : task.priority === 'high' ? 'warning' : 'neutral'}>{t(`task.priority.${task.priority}`)}</Chip>}
                        {task.due_at && (
                          <span className={styles.due}><CalendarClock size={14} aria-hidden="true" /> <DueText task={task} /></span>
                        )}
                      </div>
                      {task.assignee_member_ids.length > 0 && (
                        <ul className={styles.people} aria-label={t('tasks.col.assignees')}>
                          {task.assignee_member_ids.slice(0, 4).map((id) => (
                            <li key={id} className={styles.person} title={names.nameOf(id)}>{names.nameOf(id).charAt(0).toUpperCase()}</li>
                          ))}
                          {task.assignee_member_ids.length > 4 && <li className={styles.person}>+{task.assignee_member_ids.length - 4}</li>}
                        </ul>
                      )}
                      {options.length > 0 && (
                        <select
                          className={styles.moveSelect}
                          aria-label={`${task.title}: ${t('tasks.col.status')}`}
                          value=""
                          onChange={(e) => e.target.value && request(task, e.target.value as TaskStatus)}
                        >
                          <option value="">{t('tasks.col.status')}…</option>
                          {options.map((s) => <option key={s} value={s}>{t(`task.status.${s}`)}</option>)}
                        </select>
                      )}
                    </li>
                  )
                })}
              </ul>
            </section>
          )
        })}
      </div>
      {move.error && !pending && <InlineError error={move.error} />}

      <ConfirmDialog
        open={!!pending}
        title={pending?.status === 'cancelled' ? t('tasks.cancel.title') : t('tasks.reopen.title')}
        body={
          <div className={styles.confirm}>
            <p>{pending?.status === 'cancelled' ? t('tasks.cancel.body') : t('tasks.reopen.body')}</p>
            <InlineError error={move.error} />
          </div>
        }
        confirmLabel={pending ? t(`tasks.action.${pending.status}`) : undefined}
        danger={pending?.status === 'cancelled'}
        loading={move.isPending}
        onConfirm={() => pending && move.mutate({ id: pending.task.id, status: pending.status }, { onSuccess: () => setPending(null) })}
        onClose={() => setPending(null)}
      />
    </>
  )
}
