import { useState } from 'react'
import { Link } from 'react-router'
import { Circle, CircleCheck, Hourglass, Paperclip } from 'lucide-react'
import { useI18n } from '@/shared/i18n/i18n'
import { Chip } from '@/shared/ui/Feedback'
import { useMemberNames } from '@/features/members/directory'
import { useTaskParts, taskParts, partKey } from '@/mock/taskParts'
import { useTaskFiles } from '@/mock/fileStore'
import { parseReview } from './reviewTasks'
import { CompleteDialog } from './CompleteDialog'
import { useSetStatus } from './api'
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
  const parts = useTaskParts()
  const [confirming, setConfirming] = useState(false)
  const fileCount = useTaskFiles().filter((f) => f.taskId === (parseReview(task.id)?.taskId ?? task.id)).length
  // A review item is the leader's own task: "review X's work on Y". Ticking it records that the work was reviewed.
  const review = parseReview(task.id)
  // Members cannot close: ticking flags their own part for the leader, who then closes the task.
  const flagging = !done && isOpen(task) && isAssignee(task, viewer) && !canFinish(task, viewer)
  const myPart = !!viewer.memberId && !!parts[partKey(task.id, viewer.memberId)]
  const readyCount = task.assignee_member_ids.filter((id) => parts[partKey(task.id, id)]).length
  const canToggle = !!review || flagging || allowed.includes(target)
  const owners = [...task.assignee_member_ids.map((id) => names.nameOf(id)), ...task.external_assignees.map((a) => a.full_name)]

  return (
    <li className={`${styles.line} ${done ? styles.done : ''}`}>
      <button
        type="button"
        className={styles.check}
        disabled={!canToggle || setStatus.isPending}
        aria-label={review ? t('review.mark', { title: task.title }) : done ? t('taskLine.reopen', { title: task.title }) : flagging ? t(myPart ? 'taskLine.unflag' : 'taskLine.flag', { title: task.title }) : t('taskLine.complete', { title: task.title })}
        title={canToggle ? undefined : t('taskLine.noRight')}
        onClick={() => {
          if (review) taskParts.setReviewed(review.key, !done)
          else if (flagging && viewer.memberId && myPart) taskParts.toggle(task.id, viewer.memberId)
          else if (flagging || target === 'completed') setConfirming(true)
          else setStatus.mutate(target)
        }}
      >
        {done ? <CircleCheck size={24} aria-hidden="true" /> : myPart ? <Hourglass size={22} aria-hidden="true" className={styles.flagged} /> : <Circle size={24} aria-hidden="true" />}
      </button>
      <div className={styles.main}>
        <Link className={styles.title} to={`/tasks/${review?.taskId ?? task.id}`}>{task.title}</Link>
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
          title={task.title}
          mode={flagging ? 'flag' : 'close'}
          loading={setStatus.isPending}
          onClose={() => setConfirming(false)}
          onConfirm={() => {
            if (flagging && viewer.memberId) taskParts.toggle(task.id, viewer.memberId)
            else setStatus.mutate('completed')
            setConfirming(false)
          }}
        />
      )}
      <span className={`${styles.due} ${isOverdue(task, new Date()) ? styles.late : ''}`}>{task.due_at ? formatDate(task.due_at, locale) : ''}</span>
    </li>
  )
}
