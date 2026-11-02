import { useState } from 'react'
import { Link } from 'react-router'
import { Circle, CircleCheck, Hourglass, Paperclip } from 'lucide-react'
import { useI18n } from '@/shared/i18n/i18n'
import { Chip } from '@/shared/ui/Feedback'
import { useMemberNames } from '@/features/members/directory'
import { isMock } from '@/shared/config'
import { useTaskFiles } from '@/mock/fileStore'
import { CompleteDialog } from './CompleteDialog'
import { useSetProgress, useSetStatus } from './api'
import { formatDate } from '@/shared/lib/format'
import { allowedTransitions, canFinish, isAssignee, isOpen, isOverdue, type Viewer } from './rules'
import type { Task } from './types'
import styles from './taskLists.module.css'

interface Props {
  task: Task
  viewer: Viewer
  /** Show the unit the task belongs to (Home, where tasks of several teams mix). */
  unitName?: string
}

/** One task as a single line: tick it off, open it, see who owns it and when it is due. */
export function TaskLine({ task, viewer, unitName }: Props) {
  const { t, locale } = useI18n()
  const names = useMemberNames()
  const setStatus = useSetStatus(task.id)
  const allowed = allowedTransitions(task, viewer)
  const done = task.status === 'completed'
  const target = done ? 'new' : 'completed'
  const progress = useSetProgress(task.id)
  const [confirming, setConfirming] = useState(false)
  // Only the mock layer counts files per task; the real list has no per-task count (open the task to see them).
  const mockFiles = useTaskFiles()
  const fileCount = isMock() ? mockFiles.filter((f) => f.taskId === (task.review_of_task_id ?? task.id)).length : 0
  // A review item is the leader's own task: "review X's work on Y". Ticking it closes the review.
  const review = task.kind === 'review'
  const title = review ? t('review.title', { name: names.nameOf(task.review_member_id), task: task.title }) : task.title
  // Members cannot close: ticking flags their own part for the leader, who then closes the task.
  const flagging = !review && !done && isOpen(task) && isAssignee(task, viewer) && !canFinish(task, viewer)
  const myPart = !!viewer.memberId && task.finished_member_ids.includes(viewer.memberId)
  const readyCount = task.finished_member_ids.length
  const canToggle = flagging || allowed.includes(target)
  const owners = [...task.assignee_member_ids.map((id) => names.nameOf(id)), ...task.external_assignees.map((a) => a.full_name)]

  return (
    <li className={`${styles.line} ${done ? styles.done : ''}`}>
      <button
        type="button"
        className={styles.check}
        disabled={!canToggle || setStatus.isPending || progress.isPending}
        aria-label={review ? t('review.mark', { title }) : done ? t('taskLine.reopen', { title }) : flagging ? t(myPart ? 'taskLine.unflag' : 'taskLine.flag', { title }) : t('taskLine.complete', { title })}
        title={canToggle ? undefined : t('taskLine.noRight')}
        onClick={() => {
          if (flagging && myPart) progress.mutate(false)
          else if (flagging || (!review && target === 'completed')) setConfirming(true)
          else setStatus.mutate(target)
        }}
      >
        {done ? <CircleCheck size={24} aria-hidden="true" /> : myPart ? <Hourglass size={22} aria-hidden="true" className={styles.flagged} /> : <Circle size={24} aria-hidden="true" />}
      </button>
      <div className={styles.main}>
        <Link className={styles.title} to={`/tasks/${task.review_of_task_id ?? task.id}`}>{title}</Link>
        <div className={styles.meta}>
          {fileCount > 0 && <span className={styles.clip}><Paperclip size={13} aria-hidden="true" /> {fileCount}</span>}
          {review && <Chip tone="info">{t('review.chip')}</Chip>}
          {unitName && <span className={styles.unit}>{unitName}</span>}
          {owners.length > 0 && <span className={styles.owners}>{owners.join('، ')}</span>}
          {task.priority === 'urgent' && <Chip tone="danger">{t('task.priority.urgent')}</Chip>}
          {task.priority === 'high' && <Chip tone="warning">{t('task.priority.high')}</Chip>}
          {!done && readyCount > 0 && <Chip tone="success">{flagging ? t('taskLine.waiting') : t('taskLine.ready', { n: readyCount, total: task.assignee_member_ids.length })}</Chip>}
          {task.status === 'in_progress' && <Chip tone="info">{t('task.status.in_progress')}</Chip>}
        </div>
      </div>
      {confirming && (
        <CompleteDialog
          taskId={task.id}
          title={title}
          mode={flagging ? 'flag' : 'close'}
          loading={setStatus.isPending || progress.isPending}
          onClose={() => setConfirming(false)}
          onConfirm={() => {
            if (flagging) progress.mutate(true)
            else setStatus.mutate('completed')
            setConfirming(false)
          }}
        />
      )}
      <span className={`${styles.due} ${isOverdue(task, new Date()) ? styles.late : ''}`}>{task.due_at ? formatDate(task.due_at, locale) : ''}</span>
    </li>
  )
}
