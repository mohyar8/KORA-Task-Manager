import { useState } from 'react'
import { useI18n } from '@/shared/i18n/i18n'
import { localInputToIso } from '@/shared/lib/format'
import { Button } from '@/shared/ui/Button'
import { InlineError } from '@/shared/ui/Feedback'
import { SelectField, TextAreaField, TextField } from '@/shared/ui/Field'
import { Modal } from '@/shared/ui/Modal'
import { AssigneePicker } from './AssigneePicker'
import { FilePicker } from './FilePicker'
import { isoToLocalInput } from './rules'
import { TASK_PRIORITIES, type Task, type TaskFields, type TaskPriority } from './types'
import styles from './tasks.module.css'

export interface TaskFormValues extends TaskFields {
  scope_unit_id: string
  assignee_member_ids: string[]
  external_assignee_member_ids: string[]
  /** Files attached while creating; they are saved once the task exists. */
  files?: File[]
}

interface Props {
  title: string
  submitLabel: string
  /** Prefill (edit). */
  initial?: Task
  /** Show the unit select (create). */
  scopeOptions?: { id: string; name: string }[]
  /** Show the assignee picker (create, subtask). */
  withAssignees?: boolean
  loading: boolean
  error: unknown
  onSubmit: (values: TaskFormValues) => void
  onClose: () => void
}

/** Create / edit / subtask form in a modal. Mounted only while open, so every open starts from `initial`. */
export function TaskFormModal(props: Props) {
  const { t } = useI18n()
  const { title, submitLabel, initial, scopeOptions, withAssignees, loading, error, onSubmit, onClose } = props

  const [name, setName] = useState(initial?.title ?? '')
  const [description, setDescription] = useState(initial?.description ?? '')
  const [priority, setPriority] = useState<TaskPriority | ''>(initial?.priority ?? '')
  const [due, setDue] = useState(isoToLocalInput(initial?.due_at ?? null))
  const [scope, setScope] = useState('')
  const [assignees, setAssignees] = useState<string[]>([])
  const [externals, setExternals] = useState<string[]>([])
  const [submitted, setSubmitted] = useState(false)
  const [files, setFiles] = useState<File[]>([])

  const problems = {
    title: !name.trim() ? t('tasks.titleRequired') : undefined,
    scope: scopeOptions && !scope ? t('tasks.scopeRequired') : undefined,
    assignees: withAssignees && assignees.length + externals.length === 0 ? t('tasks.assigneesRequired') : undefined,
  }

  const submit = () => {
    setSubmitted(true)
    if (problems.title || problems.scope || problems.assignees) return
    onSubmit({
      title: name.trim(),
      description: description === '' ? null : description,
      priority: priority === '' ? null : priority,
      due_at: localInputToIso(due),
      scope_unit_id: scope,
      assignee_member_ids: assignees,
      external_assignee_member_ids: externals,
      files,
    })
  }

  return (
    <Modal
      open
      title={title}
      onClose={onClose}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>{t('common.cancel')}</Button>
          <Button loading={loading} onClick={submit}>{submitLabel}</Button>
        </>
      }
    >
      <div className={styles.form}>
        <TextField label={t('tasks.field.title')} value={name} maxLength={300} onChange={(e) => setName(e.target.value)} error={submitted ? problems.title : undefined} required />
        <TextAreaField label={t('tasks.field.description')} value={description} maxLength={10000} onChange={(e) => setDescription(e.target.value)} />
        <div className={styles.twoCol}>
          <SelectField label={t('tasks.field.priority')} value={priority} onChange={(e) => setPriority(e.target.value as TaskPriority | '')}>
            <option value="">{t('tasks.noPriority')}</option>
            {TASK_PRIORITIES.map((p) => <option key={p} value={p}>{t(`task.priority.${p}`)}</option>)}
          </SelectField>
          <TextField label={t('tasks.field.due')} type="datetime-local" value={due} onChange={(e) => setDue(e.target.value)} dir="ltr" />
        </div>
        {scopeOptions && (
          <SelectField label={t('tasks.field.scope')} value={scope} onChange={(e) => setScope(e.target.value)} error={submitted ? problems.scope : undefined} required>
            <option value="">{t('tasks.pickUnit')}</option>
            {scopeOptions.map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
          </SelectField>
        )}
        {withAssignees && <AssigneePicker selected={assignees} onChange={setAssignees} external={externals} onExternalChange={setExternals} error={submitted ? problems.assignees : undefined} />}
        {scopeOptions && <FilePicker files={files} onChange={setFiles} />}
        <InlineError error={error} />
      </div>
    </Modal>
  )
}
