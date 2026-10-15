import { CircleCheck, CircleDashed, CircleX, Loader } from 'lucide-react'
import { useI18n } from '@/shared/i18n/i18n'
import { formatDateTime } from '@/shared/lib/format'
import { Chip, type Tone } from '@/shared/ui/Feedback'
import { isOverdue } from './rules'
import type { Task, TaskStatus } from './types'
import styles from './tasks.module.css'

const statusTone: Record<TaskStatus, Tone> = { new: 'info', in_progress: 'warning', completed: 'success', cancelled: 'neutral' }

export function StatusChip({ status }: { status: TaskStatus }) {
  const { t } = useI18n()
  return <Chip tone={statusTone[status]}>{t(`task.status.${status}`)}</Chip>
}

export function PriorityText({ priority }: { priority: Task['priority'] }) {
  const { t } = useI18n()
  return <>{priority ? t(`task.priority.${priority}`) : t('tasks.noPriority')}</>
}

export function DueText({ task }: { task: Task }) {
  const { t, locale } = useI18n()
  if (!task.due_at) return <span>{t('tasks.noDue')}</span>
  const late = isOverdue(task, new Date())
  return (
    <span className={late ? styles.overdue : undefined}>
      {formatDateTime(task.due_at, locale)}
      {late && ` — ${t('tasks.overdue')}`}
    </span>
  )
}

export function StatusIcon({ status }: { status: TaskStatus }) {
  const Icon = { new: CircleDashed, in_progress: Loader, completed: CircleCheck, cancelled: CircleX }[status]
  return <Icon size={22} aria-hidden="true" />
}
