import type { MessageKey } from '@/shared/i18n/messages.en'
import { en } from '@/shared/i18n/messages.en'
import type { TaskEvent } from './types'

interface Describe {
  t: (key: MessageKey, params?: Record<string, string | number>) => string
  memberName: (id: string | null | undefined) => string
  unitName: (id: string) => string
}

const label = (t: Describe['t'], prefix: string, value: unknown) => {
  const key = `${prefix}.${String(value)}`
  return key in en ? t(key as MessageKey) : String(value)
}

/** One readable line per history event (contract §9.3 `data` shapes). Never reconstructs deleted comment text. */
export function describeEvent(event: TaskEvent, d: Describe): string {
  const { t } = d
  const data = event.data
  switch (event.kind) {
    case 'updated': {
      const changes = (data.changes ?? {}) as Record<string, unknown>
      const fields = Object.keys(changes).map((f) => label(t, 'tasks.field.name', f)).join(', ')
      return t('tasks.event.updated', { fields })
    }
    case 'status_changed':
      return t('tasks.event.status_changed', {
        previous: label(t, 'task.status', data.previous),
        status: label(t, 'task.status', data.status),
      })
    case 'assignee_added':
      return t('tasks.event.assignee_added', { name: d.memberName(data.member_id as string) })
    case 'assignee_removed':
      return t('tasks.event.assignee_removed', {
        name: d.memberName(data.member_id as string),
        reason: label(t, 'tasks.reason', data.reason),
      })
    case 'assignee_not_added':
      return t('tasks.event.assignee_not_added', { name: d.memberName(data.member_id as string) })
    case 'scope_changed':
      return t('tasks.event.scope_changed', { previous: d.unitName(String(data.previous)), unit: d.unitName(String(data.scope_unit_id)) })
    case 'comment_added':
    case 'comment_edited':
    case 'comment_deleted': {
      const base = t(`tasks.event.${event.kind}`)
      return data.content_removed ? `${base} (${t('tasks.event.textRemoved')})` : base
    }
    default:
      return t(`tasks.event.${event.kind}`)
  }
}
