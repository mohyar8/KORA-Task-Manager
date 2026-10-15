import { useState } from 'react'
import { Link, useParams } from 'react-router'
import { ArrowRight } from 'lucide-react'
import { useI18n } from '@/shared/i18n/i18n'
import { formatDateTime } from '@/shared/lib/format'
import { Button } from '@/shared/ui/Button'
import { Chip, ErrorState, InlineError, Skeleton, useToast } from '@/shared/ui/Feedback'
import { SelectField } from '@/shared/ui/Field'
import { Card, PageHeader } from '@/shared/ui/Layout'
import { ConfirmDialog, Modal } from '@/shared/ui/Modal'
import { allUnits, canAt } from '@/features/auth/permissions'
import { useSession } from '@/features/auth/session'
import { useMemberNames } from '@/features/members/directory'
import {
  eventChanges, useAddInvitee, useCancelEvent, useEvent, useEventHistory, useInvitations, useRemoveInvitee, useUpdateEvent, type CalendarEvent,
} from './api'
import { EventFormModal } from './EventForm'
import styles from './calendar.module.css'

export function EventDetailPage() {
  const { eventId = '' } = useParams()
  const query = useEvent(eventId)
  if (query.isPending) return <Skeleton lines={6} />
  if (query.isError) return <ErrorState error={query.error} onRetry={() => void query.refetch()} />
  return <EventView event={query.data} />
}

function EventView({ event }: { event: CalendarEvent }) {
  const { t, locale } = useI18n()
  const toast = useToast()
  const { account, access } = useSession()
  const names = useMemberNames()
  const update = useUpdateEvent(event.id)
  const cancel = useCancelEvent(event.id)
  const add = useAddInvitee(event.id)
  const remove = useRemoveInvitee(event.id)
  const [dialog, setDialog] = useState<'edit' | 'cancel' | 'invite' | null>(null)
  const [pick, setPick] = useState('')
  const [removing, setRemoving] = useState<string | null>(null)
  const [showInvitations, setShowInvitations] = useState(false)
  const [showHistory, setShowHistory] = useState(false)

  // Administer = the organizer or a scoped manager; a cancelled event is read-only (contract §12).
  const administer = event.organizer_account_id === account?.id || canAt(access, 'calendar.manage', event.scope_unit_id)
  const editable = administer && event.state === 'scheduled'
  const invitations = useInvitations(event.id, showInvitations && administer)
  const history = useEventHistory(event.id, showHistory)
  const unitName = allUnits(access).find((u) => u.unit_id === event.scope_unit_id)?.name ?? event.scope_unit_id
  const candidates = names.members.filter((m) => !(event.invitee_member_ids ?? []).includes(m.id))
  const close = () => setDialog(null)

  const describe = (h: { kind: string; data: Record<string, unknown> }) => {
    const base = t(`cal.event.${h.kind}` as 'cal.event.created', { name: names.nameOf(h.data.member_id as string | undefined) })
    return base
  }

  return (
    <>
      <Link className={styles.back} to="/calendar"><ArrowRight size={16} aria-hidden="true" className={styles.backIcon} /> {t('cal.back')}</Link>
      <PageHeader
        title={event.title}
        actions={
          editable && (
            <div className={styles.actions}>
              <Button variant="secondary" onClick={() => { update.reset(); setDialog('edit') }}>{t('cal.edit')}</Button>
              <Button variant="danger" onClick={() => { cancel.reset(); setDialog('cancel') }}>{t('cal.cancel')}</Button>
            </div>
          )
        }
      />
      {event.state === 'cancelled' && <p className={styles.notice}>{t('cal.readOnly')}</p>}
      <div className={styles.sections}>
        <Card>
          <dl className={styles.facts}>
            <dt>{t('cal.field.type')}</dt>
            <dd><Chip tone="info">{t(`cal.type.${event.type}`)}</Chip> {event.state === 'cancelled' && <Chip tone="danger">{t('cal.cancelledChip')}</Chip>}</dd>
            <dt>{t('cal.detail.when')}</dt>
            <dd>{formatDateTime(event.starts_at, locale)} → {formatDateTime(event.ends_at, locale)}</dd>
            {event.location_text && (<><dt>{t('cal.detail.where')}</dt><dd>{event.location_text}</dd></>)}
            {event.online_url && (
              <>
                <dt>{t('cal.detail.link')}</dt>
                <dd><a href={event.online_url} target="_blank" rel="noopener noreferrer" dir="ltr">{event.online_url}</a></dd>
              </>
            )}
            <dt>{t('cal.detail.organizer')}</dt>
            <dd>{names.nameOf(event.organizer_member_id)}</dd>
            <dt>{t('cal.detail.unit')}</dt>
            <dd>{unitName}</dd>
          </dl>
          {event.description && <p className={styles.description}>{event.description}</p>}
        </Card>

        <Card>
          <div className={styles.cardHead}>
            <h2 className={styles.cardTitle}>{t('cal.invitees')}</h2>
            {editable && <Button variant="secondary" onClick={() => { add.reset(); setPick(''); setDialog('invite') }}>{t('cal.invitees.add')}</Button>}
          </div>
          {event.invitee_member_ids === null ? (
            <p className={styles.hint}>{t('cal.invitees.hidden')}</p>
          ) : (
            <ul className={styles.rows}>
              {event.invitee_member_ids.map((id) => (
                <li key={id} className={styles.row}>
                  <span>{names.nameOf(id)}</span>
                  {editable && <Button variant="ghost" onClick={() => { remove.reset(); setRemoving(id) }}>{t('cal.invitees.remove')}</Button>}
                </li>
              ))}
            </ul>
          )}
        </Card>

        {administer && (
          <Card>
            <div className={styles.cardHead}>
              <h2 className={styles.cardTitle}>{t('cal.invitations')}</h2>
              {!showInvitations && <Button variant="secondary" onClick={() => setShowInvitations(true)}>{t('cal.invitations.show')}</Button>}
            </div>
            {invitations.isPending && showInvitations && <Skeleton lines={2} />}
            {invitations.isError && <ErrorState error={invitations.error} />}
            {invitations.data && (
              <ul className={styles.rows}>
                {invitations.data.map((i, n) => (
                  <li key={`${i.member_id}-${n}`} className={styles.row}>
                    <span>{names.nameOf(i.member_id)}</span>
                    <span className={styles.when}>{formatDateTime(i.valid_from, locale)}{i.valid_to && ` — ${t('cal.invitations.removedOn')} ${formatDateTime(i.valid_to, locale)}`}</span>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        )}

        <Card>
          <div className={styles.cardHead}>
            <h2 className={styles.cardTitle}>{t('cal.history')}</h2>
            {!showHistory && <Button variant="secondary" onClick={() => setShowHistory(true)}>{t('cal.history.show')}</Button>}
          </div>
          {history.isPending && showHistory && <Skeleton lines={2} />}
          {history.isError && <ErrorState error={history.error} />}
          {history.data && (
            <ul className={styles.rows}>
              {history.data.map((h, n) => (
                <li key={`${h.created_at}-${n}`} className={styles.row}>
                  <span>{describe(h)}</span>
                  <span className={styles.when}>{formatDateTime(h.created_at, locale)}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      {dialog === 'edit' && (
        <EventFormModal
          title={t('cal.edit.title')}
          submitLabel={t('common.save')}
          initial={event}
          loading={update.isPending}
          error={update.error}
          onClose={close}
          onSubmit={(v) => {
            const diff = eventChanges(event, v)
            if (Object.keys(diff).length === 0) return close()
            update.mutate(diff, { onSuccess: () => { close(); toast(t('cal.updated')) } })
          }}
        />
      )}

      <ConfirmDialog
        open={dialog === 'cancel'}
        title={t('cal.cancel.title')}
        body={<div className={styles.form}><p>{t('cal.cancel.body')}</p><InlineError error={cancel.error} /></div>}
        confirmLabel={t('cal.cancel')}
        danger
        loading={cancel.isPending}
        onConfirm={() => cancel.mutate(undefined, { onSuccess: () => { close(); toast(t('cal.cancelledToast')) } })}
        onClose={close}
      />

      <Modal
        open={dialog === 'invite'}
        title={t('cal.invitees.add')}
        onClose={close}
        footer={
          <>
            <Button variant="ghost" onClick={close}>{t('common.cancel')}</Button>
            <Button disabled={!pick} loading={add.isPending} onClick={() => add.mutate(pick, { onSuccess: () => { close(); toast(t('cal.invitees.added')) } })}>{t('common.add')}</Button>
          </>
        }
      >
        <div className={styles.form}>
          <SelectField label={t('cal.field.invitees')} value={pick} onChange={(e) => setPick(e.target.value)}>
            <option value="">{t('cal.invitees.pick')}</option>
            {candidates.map((m) => <option key={m.id} value={m.id}>{m.full_name}</option>)}
          </SelectField>
          <InlineError error={add.error} />
        </div>
      </Modal>

      <ConfirmDialog
        open={removing !== null}
        title={t('cal.invitees.removeTitle', { name: removing ? names.nameOf(removing) : '' })}
        body={<div className={styles.form}><p>{t('cal.invitees.removeBody')}</p><InlineError error={remove.error} /></div>}
        confirmLabel={t('cal.invitees.remove')}
        danger
        loading={remove.isPending}
        onConfirm={() => removing && remove.mutate(removing, { onSuccess: () => { setRemoving(null); toast(t('cal.invitees.removed')) } })}
        onClose={() => setRemoving(null)}
      />
    </>
  )
}
