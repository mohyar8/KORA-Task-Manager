import { useState } from 'react'
import { useI18n } from '@/shared/i18n/i18n'
import { localInputToIso } from '@/shared/lib/format'
import { Button } from '@/shared/ui/Button'
import { InlineError } from '@/shared/ui/Feedback'
import { SelectField, TextAreaField, TextField } from '@/shared/ui/Field'
import { Modal } from '@/shared/ui/Modal'
import { isoToLocalInput } from '@/features/tasks/rules'
import { AssigneePicker } from '@/features/tasks/AssigneePicker'
import { isHttpUrl, type CalendarEvent, type EventFields, type EventType } from './api'
import styles from './calendar.module.css'

export interface EventFormValues extends EventFields {
  scope_unit_id: string
  invitee_member_ids: string[]
}

interface Props {
  title: string
  submitLabel: string
  initial?: CalendarEvent
  /** Create: the unit select. Edit omits it (the scope never changes). */
  scopeOptions?: { id: string; name: string }[]
  loading: boolean
  error: unknown
  onSubmit: (v: EventFormValues) => void
  onClose: () => void
}

type Place = 'none' | 'location' | 'online'

export function EventFormModal({ title, submitLabel, initial, scopeOptions, loading, error, onSubmit, onClose }: Props) {
  const { t } = useI18n()
  const [type, setType] = useState<EventType>(initial?.type ?? 'event')
  const [name, setName] = useState(initial?.title ?? '')
  const [description, setDescription] = useState(initial?.description ?? '')
  const [starts, setStarts] = useState(isoToLocalInput(initial?.starts_at ?? null))
  const [ends, setEnds] = useState(isoToLocalInput(initial?.ends_at ?? null))
  const [place, setPlace] = useState<Place>(initial?.location_text ? 'location' : initial?.online_url ? 'online' : 'none')
  const [location, setLocation] = useState(initial?.location_text ?? '')
  const [url, setUrl] = useState(initial?.online_url ?? '')
  const [scope, setScope] = useState('')
  const [invitees, setInvitees] = useState<string[]>([])
  const [submitted, setSubmitted] = useState(false)

  const startIso = localInputToIso(starts)
  const endIso = localInputToIso(ends)
  const problems = {
    title: !name.trim() ? t('tasks.titleRequired') : undefined,
    starts: !startIso ? t('cal.startRequired') : undefined,
    ends: !endIso ? t('cal.endRequired') : startIso && Date.parse(endIso) <= Date.parse(startIso) ? t('cal.endsAfter') : undefined,
    place: place === 'location' && !location.trim() ? t('cal.placeRequired') : place === 'online' && !isHttpUrl(url) ? t('cal.urlInvalid') : undefined,
    scope: scopeOptions && !scope ? t('tasks.scopeRequired') : undefined,
    invitees: scopeOptions && invitees.length === 0 ? t('tasks.assigneesRequired') : undefined,
  }

  const submit = () => {
    setSubmitted(true)
    if (Object.values(problems).some(Boolean) || !startIso || !endIso) return
    onSubmit({
      type,
      title: name.trim(),
      description: description === '' ? null : description,
      starts_at: startIso,
      ends_at: endIso,
      location_text: place === 'location' ? location.trim() : null,
      online_url: place === 'online' ? url.trim() : null,
      scope_unit_id: scope,
      invitee_member_ids: invitees,
    })
  }
  const show = (p?: string) => (submitted ? p : undefined)

  return (
    <Modal
      open
      title={title}
      onClose={onClose}
      footer={<><Button variant="ghost" onClick={onClose}>{t('common.cancel')}</Button><Button loading={loading} onClick={submit}>{submitLabel}</Button></>}
    >
      <div className={styles.form}>
        <SelectField label={t('cal.field.type')} value={type} onChange={(e) => setType(e.target.value as EventType)}>
          <option value="event">{t('cal.type.event')}</option>
          <option value="meeting">{t('cal.type.meeting')}</option>
        </SelectField>
        <TextField label={t('cal.field.title')} value={name} maxLength={300} onChange={(e) => setName(e.target.value)} error={show(problems.title)} required />
        <TextAreaField label={t('cal.field.description')} value={description} maxLength={10000} onChange={(e) => setDescription(e.target.value)} />
        <div className={styles.twoCol}>
          <TextField label={t('cal.field.starts')} type="datetime-local" value={starts} onChange={(e) => setStarts(e.target.value)} error={show(problems.starts)} dir="ltr" required />
          <TextField label={t('cal.field.ends')} type="datetime-local" value={ends} onChange={(e) => setEnds(e.target.value)} error={show(problems.ends)} dir="ltr" required />
        </div>
        <SelectField label={t('cal.field.place')} value={place} onChange={(e) => setPlace(e.target.value as Place)}>
          <option value="none">{t('cal.place.none')}</option>
          <option value="location">{t('cal.place.location')}</option>
          <option value="online">{t('cal.place.online')}</option>
        </SelectField>
        {place === 'location' && <TextField label={t('cal.field.location')} value={location} maxLength={500} onChange={(e) => setLocation(e.target.value)} error={show(problems.place)} />}
        {place === 'online' && <TextField label={t('cal.field.url')} type="url" value={url} maxLength={2000} onChange={(e) => setUrl(e.target.value)} error={show(problems.place)} dir="ltr" />}
        {scopeOptions && (
          <SelectField label={t('cal.field.scope')} value={scope} onChange={(e) => setScope(e.target.value)} error={show(problems.scope)} required>
            <option value="">{t('tasks.pickUnit')}</option>
            {scopeOptions.map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
          </SelectField>
        )}
        {scopeOptions && <AssigneePicker legend={t('cal.field.invitees')} selected={invitees} onChange={setInvitees} error={show(problems.invitees)} />}
        <InlineError error={error} />
      </div>
    </Modal>
  )
}
