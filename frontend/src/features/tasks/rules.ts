import type { RowTone } from '@/shared/ui/RowList'
import { canAt } from '@/features/auth/permissions'
import type { EffectiveAccess } from '@/features/auth/types'
import type { Task, TaskFields, TaskStatus } from './types'

// Mirrors contract §9.1 and the §9.3 transition table so the UI offers only actions the server can accept.
// The server stays authoritative: it may still answer 403/409 (e.g. the creator is no longer an active Member).

export interface Viewer {
  memberId: string | null
  accountId: string
  access: EffectiveAccess | null
}

export const isCreator = (task: Task, v: Viewer) => task.created_by_account_id === v.accountId
export const isAssignee = (task: Task, v: Viewer) => !!v.memberId && task.assignee_member_ids.includes(v.memberId)
export const isScopedManager = (task: Task, v: Viewer) => canAt(v.access, 'task.manage', task.scope_unit_id)

/** Edit, cancel, reopen, manage assignees, move: the creator (as a Member) or a scoped manager. */
export const canAdminister = (task: Task, v: Viewer) =>
  (!!v.memberId && task.created_by_member_id === v.memberId) || isScopedManager(task, v)

/** Move work forward: an assignee or a scoped manager. */
export const canWork = (task: Task, v: Viewer) => isAssignee(task, v) || isScopedManager(task, v)

export const canComment = (task: Task, v: Viewer) => isCreator(task, v) || isAssignee(task, v) || isScopedManager(task, v)

/** Create a subtask: an active Member with task.create at the parent's scope. */
export const canCreateSubtask = (task: Task, v: Viewer) =>
  !!v.memberId && !task.parent_id && canAt(v.access, 'task.create', task.scope_unit_id)

export function allowedTransitions(task: Task, v: Viewer): TaskStatus[] {
  const work = canWork(task, v)
  const admin = canAdminister(task, v)
  switch (task.status) {
    case 'new':
      return [...(work ? (['in_progress', 'completed'] as const) : []), ...(admin ? (['cancelled'] as const) : [])]
    case 'in_progress':
      return [...(work ? (['completed'] as const) : []), ...(admin ? (['cancelled'] as const) : [])]
    case 'completed':
    case 'cancelled':
      return admin ? ['new'] : []
  }
}

export const isOpen = (task: Task) => task.status === 'new' || task.status === 'in_progress'

export const isOverdue = (task: Task, now: Date) => isOpen(task) && !!task.due_at && new Date(task.due_at) < now

/** Local `datetime-local` value for an ISO instant (inverse of format.localInputToIso). */
export function isoToLocalInput(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

const WEEK_MS = 7 * 24 * 60 * 60 * 1000

/** Pure so it can be tested: counts are derived from the tasks the API returned (there is no analytics API). */
export function summarize(tasks: Task[], isMine: (t: Task) => boolean, now: Date) {
  const open = tasks.filter(isOpen)
  const mine = open.filter(isMine)
  return {
    open: open.length,
    mine: mine.length,
    overdue: open.filter((t) => isOverdue(t, now)).length,
    dueSoon: mine
      .filter((t) => t.due_at && new Date(t.due_at) >= now && new Date(t.due_at).getTime() - now.getTime() <= WEEK_MS)
      .sort((a, b) => Date.parse(a.due_at!) - Date.parse(b.due_at!)),
  }
}


/** Only the fields whose value actually changed (PATCH is partial; no change means no request). */
export function changedFields(task: Task, next: TaskFields): Partial<TaskFields> {
  const diff: Partial<TaskFields> = {}
  if (next.title !== task.title) diff.title = next.title
  if (next.description !== task.description) diff.description = next.description
  if (next.priority !== task.priority) diff.priority = next.priority
  const sameInstant = !!next.due_at && !!task.due_at && Date.parse(next.due_at) === Date.parse(task.due_at)
  if (next.due_at !== task.due_at && !sameInstant) diff.due_at = next.due_at
  return diff
}

export const statusAccent: Record<TaskStatus, RowTone> = { new: 'navy', in_progress: 'fuchsia', completed: 'green', cancelled: 'gray' }

