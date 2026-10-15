import { useState } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import { useI18n } from '@/shared/i18n/i18n'
import { localInputToIso } from '@/shared/lib/format'
import { Button } from '@/shared/ui/Button'
import { InlineError } from '@/shared/ui/Feedback'
import { SelectField, TextAreaField, TextField } from '@/shared/ui/Field'
import { Modal } from '@/shared/ui/Modal'
import { AssigneePicker } from './AssigneePicker'
import { MAX_OCCURRENCES, occurrenceCount, type CreateSeries, type Series, type TemplateInput } from './seriesApi'
import { TASK_PRIORITIES, type TaskPriority } from './types'
import styles from './tasks.module.css'

interface Props {
  title: string
  submitLabel: string
  /** Edit mode: prefill, and hide the fields a series cannot change (unit, dates). */
  initial?: Series
  scopeOptions?: { id: string; name: string }[]
  loading: boolean
  error: unknown
  onSubmit: (values: CreateSeries) => void
  onClose: () => void
}

interface TemplateDraft extends TemplateInput {
  uid: number
}

/** Create / edit a weekly series. Mounted only while open so each open starts from `initial`. */
export function SeriesFormModal({ title, submitLabel, initial, scopeOptions, loading, error, onSubmit, onClose }: Props) {
  const { t } = useI18n()
  const editing = !!initial
  const [name, setName] = useState(initial?.title ?? '')
  const [description, setDescription] = useState(initial?.description ?? '')
  const [priority, setPriority] = useState<TaskPriority | ''>(initial?.priority ?? '')
  const [scope, setScope] = useState('')
  const [first, setFirst] = useState('')
  const [ends, setEnds] = useState('')
  const [assignees, setAssignees] = useState<string[]>(initial?.assignee_member_ids ?? [])
  const [templates, setTemplates] = useState<TemplateDraft[]>(
    (initial?.subtask_templates ?? []).map((tpl, i) => ({ ...tpl, uid: i })),
  )
  const [nextUid, setNextUid] = useState(templates.length)
  const [submitted, setSubmitted] = useState(false)

  const firstIso = localInputToIso(first)
  const endsIso = localInputToIso(ends)
  const count = firstIso && endsIso ? occurrenceCount(firstIso, endsIso) : 0

  const problems = {
    title: !name.trim() ? t('tasks.titleRequired') : undefined,
    scope: !editing && !scope ? t('tasks.scopeRequired') : undefined,
    first: !editing && !firstIso ? t('series.firstRequired') : undefined,
    ends: editing ? undefined : (!endsIso ? t('series.endsRequired') : firstIso && endsIso && Date.parse(endsIso) < Date.parse(firstIso) ? t('series.endsAfterFirst') : count > MAX_OCCURRENCES ? t('series.tooMany', { n: count, max: MAX_OCCURRENCES }) : undefined),
    assignees: assignees.length === 0 ? t('tasks.assigneesRequired') : undefined,
    templates: templates.some((tpl) => !tpl.title.trim() || tpl.assignee_member_ids.length === 0) ? t('series.templates.titleRequired') : undefined,
  }

  const patchTemplate = (uid: number, patch: Partial<TemplateInput>) =>
    setTemplates((cur) => cur.map((x) => (x.uid === uid ? { ...x, ...patch } : x)))

  const submit = () => {
    setSubmitted(true)
    if (Object.values(problems).some(Boolean)) return
    onSubmit({
      scope_unit_id: scope,
      title: name.trim(),
      description: description === '' ? null : description,
      priority: priority === '' ? null : priority,
      first_due_at: firstIso ?? initial?.first_due_at ?? '',
      ends_at: endsIso ?? initial?.ends_at ?? '',
      assignee_member_ids: assignees,
      subtasks: templates.map(({ uid: _uid, ...tpl }) => ({ ...tpl, title: tpl.title.trim() })),
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
        <SelectField label={t('tasks.field.priority')} value={priority} onChange={(e) => setPriority(e.target.value as TaskPriority | '')}>
          <option value="">{t('tasks.noPriority')}</option>
          {TASK_PRIORITIES.map((p) => <option key={p} value={p}>{t(`task.priority.${p}`)}</option>)}
        </SelectField>
        {!editing && scopeOptions && (
          <SelectField label={t('tasks.field.scope')} value={scope} onChange={(e) => setScope(e.target.value)} error={submitted ? problems.scope : undefined} required>
            <option value="">{t('tasks.pickUnit')}</option>
            {scopeOptions.map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
          </SelectField>
        )}
        {!editing && (
          <div className={styles.twoCol}>
            <TextField label={t('series.firstDue')} type="datetime-local" value={first} onChange={(e) => setFirst(e.target.value)} error={submitted ? problems.first : undefined} dir="ltr" required />
            <TextField
              label={t('series.endsAt')}
              type="datetime-local"
              value={ends}
              onChange={(e) => setEnds(e.target.value)}
              error={submitted || count > MAX_OCCURRENCES ? problems.ends : undefined}
              hint={count > 0 && count <= MAX_OCCURRENCES ? t('series.count', { n: count }) : undefined}
              dir="ltr"
              required
            />
          </div>
        )}
        <AssigneePicker selected={assignees} onChange={setAssignees} error={submitted ? problems.assignees : undefined} />

        <fieldset className={styles.assigneeBox}>
          <legend>{t('series.templates')}</legend>
          <p className={styles.hint}>{t('series.templates.note')}</p>
          {templates.length === 0 && <p className={styles.hint}>{t('series.templates.none')}</p>}
          {templates.map((tpl) => (
            <div key={tpl.uid} className={styles.template}>
              <TextField label={t('series.templates.title')} value={tpl.title} maxLength={300} onChange={(e) => patchTemplate(tpl.uid, { title: e.target.value })} />
              <AssigneePicker selected={tpl.assignee_member_ids} onChange={(ids) => patchTemplate(tpl.uid, { assignee_member_ids: ids })} />
              <Button variant="ghost" onClick={() => setTemplates((cur) => cur.filter((x) => x.uid !== tpl.uid))}>
                <Trash2 size={16} aria-hidden="true" /> {t('series.templates.remove')}
              </Button>
            </div>
          ))}
          {submitted && problems.templates && <p className={styles.fieldError} role="alert">{problems.templates}</p>}
          <div>
            <Button
              variant="secondary"
              onClick={() => {
                setTemplates((cur) => [...cur, { uid: nextUid, title: '', description: null, priority: null, assignee_member_ids: [] }])
                setNextUid((n) => n + 1)
              }}
            >
              <Plus size={16} aria-hidden="true" /> {t('series.templates.add')}
            </Button>
          </div>
        </fieldset>
        <InlineError error={error} />
      </div>
    </Modal>
  )
}
