// Contract §9.2.
export type TaskStatus = 'new' | 'in_progress' | 'completed' | 'cancelled'
export type TaskPriority = 'low' | 'normal' | 'high' | 'urgent'

export const TASK_STATUSES: TaskStatus[] = ['new', 'in_progress', 'completed', 'cancelled']
export const TASK_PRIORITIES: TaskPriority[] = ['low', 'normal', 'high', 'urgent']

export interface Task {
  id: string
  title: string
  description: string | null
  priority: TaskPriority | null
  due_at: string | null
  status: TaskStatus
  scope_unit_id: string
  parent_id: string | null
  series_id: string | null
  created_by_account_id: string
  created_by_member_id: string
  created_at: string
  updated_at: string
  started_at: string | null
  /** Created by someone other than the scope's Team Leader or Administration Manager. */
  from_outside: boolean
  assignee_member_ids: string[]
  /** The assignees given through "Other" (outside the scope), with their names. */
  external_assignees: { id: string; full_name: string }[]
}

export interface TaskFields {
  title: string
  description: string | null
  priority: TaskPriority | null
  due_at: string | null
}

export interface TaskComment {
  id: string
  task_id: string
  author_account_id: string
  /** null once deleted */
  body: string | null
  created_at: string
  edited_at: string | null
  deleted_at: string | null
}

export type TaskEventKind =
  | 'created'
  | 'updated'
  | 'status_changed'
  | 'assignee_added'
  | 'assignee_removed'
  | 'assignee_not_added'
  | 'scope_changed'
  | 'subtask_created'
  | 'comment_added'
  | 'comment_edited'
  | 'comment_deleted'

export interface TaskEvent {
  kind: TaskEventKind
  actor_account_id: string | null
  data: Record<string, unknown>
  created_at: string
}
