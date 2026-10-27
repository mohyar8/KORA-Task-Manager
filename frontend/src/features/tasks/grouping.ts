import { isOpen, isOverdue } from './rules'
import type { Task } from './types'

const WEEK_MS = 7 * 24 * 60 * 60 * 1000

export interface TaskGroups {
  overdue: Task[]
  /** Due within the next 7 days. */
  week: Task[]
  /** Due later than a week away. */
  later: Task[]
  noDue: Task[]
  done: Task[]
}

const byDue = (a: Task, b: Task) => Date.parse(a.due_at ?? '') - Date.parse(b.due_at ?? '')

/** Splits tasks into the groups people scan for: what is late, what is coming, what has no date, what is done. */
export function groupTasks(tasks: Task[], now: Date): TaskGroups {
  const open = tasks.filter(isOpen)
  const overdue = open.filter((t) => isOverdue(t, now)).sort(byDue)
  const dated = open.filter((t) => t.due_at && !isOverdue(t, now)).sort(byDue)
  return {
    overdue,
    week: dated.filter((t) => Date.parse(t.due_at!) - now.getTime() <= WEEK_MS),
    later: dated.filter((t) => Date.parse(t.due_at!) - now.getTime() > WEEK_MS),
    noDue: open.filter((t) => !t.due_at),
    done: tasks.filter((t) => t.status === 'completed').sort((a, b) => Date.parse(b.updated_at) - Date.parse(a.updated_at)),
  }
}
