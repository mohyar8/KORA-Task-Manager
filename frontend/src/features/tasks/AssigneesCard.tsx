import { useState } from 'react'
import { useI18n } from '@/shared/i18n/i18n'
import { Button } from '@/shared/ui/Button'
import { Chip, InlineError, useToast } from '@/shared/ui/Feedback'
import { SelectField } from '@/shared/ui/Field'
import { Card } from '@/shared/ui/Layout'
import { initialOf } from '@/shared/lib/initial'
import { Avatar, Row, RowList } from '@/shared/ui/RowList'
import { ConfirmDialog, Modal } from '@/shared/ui/Modal'
import { isTopRole, useAllMembers, useMemberNames } from '@/features/members/directory'
import { useAddAssignee, useRemoveAssignee } from './api'
import { canAdminister, isOpen, type Viewer } from './rules'
import type { Task } from './types'
import styles from './tasks.module.css'

export function AssigneesCard({ task, viewer }: { task: Task; viewer: Viewer }) {
  const { t } = useI18n()
  const toast = useToast()
  const names = useMemberNames()
  const add = useAddAssignee(task.id)
  const remove = useRemoveAssignee(task.id)
  const [adding, setAdding] = useState(false)
  const [pick, setPick] = useState('')
  const [other, setOther] = useState(false)
  const all = useAllMembers(other)
  const [removing, setRemoving] = useState<string | null>(null)

  const admin = canAdminister(task, viewer) && isOpen(task)
  const pool = other ? (all.data ?? []) : names.members.filter((m) => !isTopRole(m.role_key))
  const candidates = pool.filter((m) => !task.assignee_member_ids.includes(m.id))
  const externalIds = new Set(task.external_assignees.map((e) => e.id))
  const nameOf = (id: string) => task.external_assignees.find((e) => e.id === id)?.full_name || names.nameOf(id)

  return (
    <Card>
      <div className={styles.cardHead}>
        <h2 className={styles.cardTitle}>{t('tasks.assignees.title')}</h2>
        {admin && (
          <Button variant="secondary" onClick={() => { add.reset(); setPick(''); setOther(false); setAdding(true) }}>{t('tasks.assignees.add')}</Button>
        )}
      </div>
      {task.assignee_member_ids.length === 0 ? (
        <p className={styles.hint}>{t('tasks.assignees.none')}</p>
      ) : (
        <RowList label={t('tasks.assignees.title')}>
          {task.assignee_member_ids.map((id, i) => (
            <Row
              key={id}
              index={i}
              title={<>{nameOf(id)}{externalIds.has(id) && <> <Chip tone="info">{t('tasks.assignees.externalChip')}</Chip></>}</>}
              leading={<Avatar tone="fuchsia" size={40}>{initialOf(nameOf(id))}</Avatar>}
              trailing={admin && <Button variant="ghost" onClick={() => { remove.reset(); setRemoving(id) }}>{t('tasks.assignees.remove')}</Button>}
            />
          ))}
        </RowList>
      )}

      <Modal
        open={adding}
        title={t('tasks.assignees.add')}
        onClose={() => setAdding(false)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setAdding(false)}>{t('common.cancel')}</Button>
            <Button disabled={!pick} loading={add.isPending} onClick={() => add.mutate({ member_id: pick, external: other }, { onSuccess: () => { setAdding(false); toast(t('tasks.assignees.added')) } })}>
              {t('common.add')}
            </Button>
          </>
        }
      >
        <div className={styles.form}>
          <label className={styles.pick}>
            <input type="checkbox" checked={other} onChange={(e) => { setOther(e.target.checked); setPick('') }} /> {t('tasks.assignees.other')}
          </label>
          <SelectField label={t('tasks.field.assignees')} value={pick} onChange={(e) => setPick(e.target.value)}>
            <option value="">{t('tasks.assignees.pick')}</option>
            {candidates.map((m) => <option key={m.id} value={m.id}>{m.full_name}</option>)}
          </SelectField>
          <InlineError error={add.error} />
        </div>
      </Modal>

      <ConfirmDialog
        open={removing !== null}
        title={t('tasks.assignees.removeTitle', { name: removing ? nameOf(removing) : '' })}
        body={
          <div className={styles.form}>
            <p>{t('tasks.assignees.removeBody')}</p>
            <InlineError error={remove.error} />
          </div>
        }
        confirmLabel={t('tasks.assignees.remove')}
        danger
        loading={remove.isPending}
        onConfirm={() => removing && remove.mutate(removing, { onSuccess: () => { setRemoving(null); toast(t('tasks.assignees.removed')) } })}
        onClose={() => setRemoving(null)}
      />
    </Card>
  )
}
