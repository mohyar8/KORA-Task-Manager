import { useState, type FormEvent } from 'react'
import { CalendarDays, Plus, UserRound, Users } from 'lucide-react'
import { useI18n } from '@/shared/i18n/i18n'
import { localInputToIso } from '@/shared/lib/format'
import { Button } from '@/shared/ui/Button'
import { InlineError, useToast } from '@/shared/ui/Feedback'
import { isTopRole, useMemberNames } from '@/features/members/directory'
import { useSession } from '@/features/auth/session'
import { useCreateTask } from './api'
import { TaskFormModal } from './TaskForm'
import { useAttachAfterCreate } from './FilePicker'
import styles from './taskLists.module.css'

export interface QuickUnit {
  id: string
  name: string
  kind: string
}

interface Props {
  /** Units the caller may create tasks in. */
  units: QuickUnit[]
  /** Pin the unit (team page); otherwise the person picks (Home). */
  fixedUnitId?: string
}

/** Create and assign a task in one line: a title, who does it, and when. Enter adds it. */
export function QuickAdd({ units, fixedUnitId }: Props) {
  const { t } = useI18n()
  const toast = useToast()
  const { account } = useSession()
  const names = useMemberNames()
  const create = useCreateTask()
  const attach = useAttachAfterCreate()
  const [title, setTitle] = useState('')
  const [unitPick, setUnitPick] = useState('')
  const [assigneePick, setAssigneePick] = useState('')
  const [due, setDue] = useState('')
  const [more, setMore] = useState(false)

  const unitId = fixedUnitId ?? (unitPick || units[0]?.id || '')
  const unit = units.find((u) => u.id === unitId)
  const options = names.members.filter((m) => !isTopRole(m.role_key) && (unit?.kind !== 'team' || m.team_id === unitId))
  const me = account?.member_id ?? ''
  const assignee = assigneePick && options.some((m) => m.id === assigneePick) ? assigneePick : options.some((m) => m.id === me) ? me : (options[0]?.id ?? '')

  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (!title.trim() || !unitId || !assignee) return
    create.mutate(
      {
        title: title.trim(),
        description: null,
        priority: null,
        due_at: due ? localInputToIso(`${due}T23:59`) : null,
        scope_unit_id: unitId,
        assignee_member_ids: [assignee],
      },
      {
        onSuccess: () => {
          setTitle('')
          setDue('')
          toast(t('tasks.created'))
        },
      },
    )
  }

  if (units.length === 0 || !account?.member_id) return null

  return (
    <>
    <form className={styles.quick} onSubmit={submit} aria-label={t('quickAdd.label')}>
      <input
        className={styles.quickTitle}
        value={title}
        maxLength={300}
        placeholder={t('quickAdd.placeholder')}
        aria-label={t('tasks.field.title')}
        onChange={(e) => setTitle(e.target.value)}
      />
      <div className={styles.quickRow}>
        {!fixedUnitId && units.length > 1 && (
          <label className={styles.quickField}>
            <Users size={16} aria-hidden="true" />
            <select value={unitId} aria-label={t('tasks.field.scope')} onChange={(e) => setUnitPick(e.target.value)}>
              {units.map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
            </select>
          </label>
        )}
        <label className={styles.quickField}>
          <UserRound size={16} aria-hidden="true" /><span className={styles.quickCap}>{t('quickAdd.assignee')}</span>
          <select value={assignee} aria-label={t('quickAdd.assignee')} onChange={(e) => setAssigneePick(e.target.value)}>
            {options.map((m) => <option key={m.id} value={m.id}>{m.id === me ? t('quickAdd.me') : m.full_name}</option>)}
          </select>
        </label>
        <label className={styles.quickField}>
          <CalendarDays size={16} aria-hidden="true" /><span className={styles.quickCap}>{t('quickAdd.due')}</span>
          <input type="date" value={due} aria-label={t('quickAdd.due')} onChange={(e) => setDue(e.target.value)} dir="ltr" />
        </label>
        <button type="button" className={styles.quickMore} onClick={() => { create.reset(); setMore(true) }}>{t('quickAdd.more')}</button>
        <span className={styles.quickSpacer} />
        <Button type="submit" loading={create.isPending} disabled={!title.trim() || !assignee}>
          <Plus size={18} aria-hidden="true" /> {t('quickAdd.add')}
        </Button>
      </div>
      <InlineError error={create.error} />
    </form>

      {more && (
        <TaskFormModal
          title={t('tasks.create.title')}
          submitLabel={t('tasks.create.submit')}
          scopeOptions={fixedUnitId ? units.filter((u) => u.id === fixedUnitId) : units}
          withAssignees
          loading={create.isPending}
          error={create.error}
          onClose={() => setMore(false)}
          onSubmit={(v) =>
            create.mutate(
              { title: v.title, description: v.description, priority: v.priority, due_at: v.due_at, scope_unit_id: v.scope_unit_id, assignee_member_ids: v.assignee_member_ids, external_assignee_member_ids: v.external_assignee_member_ids },
              { onSuccess: (task) => { attach(task.id, v.files ?? []); setMore(false); toast(t('tasks.created')) } },
            )
          }
        />
      )}
    </>
  )
}
