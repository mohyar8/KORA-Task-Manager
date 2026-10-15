import { useState } from 'react'
import { Link, useParams } from 'react-router'
import { ArrowRight } from 'lucide-react'
import { useI18n } from '@/shared/i18n/i18n'
import { formatDateTime } from '@/shared/lib/format'
import { Button } from '@/shared/ui/Button'
import { Chip, ErrorState, InlineError, Skeleton, useToast } from '@/shared/ui/Feedback'
import { TextAreaField, TextField } from '@/shared/ui/Field'
import { Card, PageHeader } from '@/shared/ui/Layout'
import { ConfirmDialog, Modal } from '@/shared/ui/Modal'
import { allUnits, canAt } from '@/features/auth/permissions'
import { useSession } from '@/features/auth/session'
import { useMemberNames } from '@/features/members/directory'
import {
  announcementActions, useAnnouncement, usePublishAnnouncement, useRecipients, useUpdateAnnouncement, useVersions, useWithdrawAnnouncement,
  type Announcement,
} from './api'
import { ReadChip } from './AnnouncementsPage'
import styles from './announcements.module.css'

export function AnnouncementDetailPage() {
  const { announcementId = '' } = useParams()
  const query = useAnnouncement(announcementId)
  if (query.isPending) return <Skeleton lines={6} />
  if (query.isError) return <ErrorState error={query.error} onRetry={() => void query.refetch()} />
  return <AnnouncementView a={query.data} />
}

function AnnouncementView({ a }: { a: Announcement }) {
  const { t, locale } = useI18n()
  const toast = useToast()
  const { account, access } = useSession()
  const names = useMemberNames()
  const update = useUpdateAnnouncement(a.id)
  const publish = usePublishAnnouncement(a.id)
  const withdraw = useWithdrawAnnouncement(a.id)

  const [dialog, setDialog] = useState<'edit' | 'publish' | 'withdraw' | null>(null)
  const [title, setTitle] = useState('')
  const [body, setBody] = useState('')
  const [recipients, setRecipients] = useState<string[]>([])
  const [submitted, setSubmitted] = useState(false)
  const [showVersions, setShowVersions] = useState(false)
  const [showRecipients, setShowRecipients] = useState(false)

  const actions = announcementActions(a, {
    accountId: account?.id ?? '',
    canManage: canAt(access, 'announcement.manage', a.scope_unit_id),
    canPublish: canAt(access, 'announcement.publish', a.scope_unit_id),
  })
  const versions = useVersions(a.id, showVersions)
  const status = useRecipients(a.id, showRecipients)
  const unitName = allUnits(access).find((u) => u.unit_id === a.scope_unit_id)?.name ?? a.scope_unit_id

  const open = (d: 'edit' | 'publish' | 'withdraw') => {
    update.reset(); publish.reset(); withdraw.reset(); setSubmitted(false); setRecipients([])
    setTitle(a.title ?? ''); setBody(a.body ?? '')
    setDialog(d)
  }
  const close = () => setDialog(null)
  const toggle = (id: string) => setRecipients((cur) => (cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]))

  const saveEdit = () => {
    setSubmitted(true)
    if (!title.trim() || !body.trim()) return
    const diff: { title?: string; body?: string } = {}
    if (title.trim() !== a.title) diff.title = title.trim()
    if (body.trim() !== a.body) diff.body = body.trim()
    if (Object.keys(diff).length === 0) return close()
    update.mutate(diff, { onSuccess: () => { close(); toast(t('ann.updated')) } })
  }

  return (
    <>
      <Link className={styles.back} to="/announcements"><ArrowRight size={16} aria-hidden="true" className={styles.backIcon} /> {t('ann.back')}</Link>
      <PageHeader
        title={a.title ?? t('ann.untitled')}
        actions={
          <div className={styles.actions}>
            {actions.publish && <Button onClick={() => open('publish')}>{t('ann.publish')}</Button>}
            {actions.edit && <Button variant="secondary" onClick={() => open('edit')}>{t('ann.edit')}</Button>}
            {actions.withdraw && <Button variant="danger" onClick={() => open('withdraw')}>{t('ann.withdraw')}</Button>}
          </div>
        }
      />
      <div className={styles.sections}>
        <Card>
          <dl className={styles.facts}>
            <dt>{t('ann.col.state')}</dt>
            <dd><Chip tone={a.state === 'published' ? 'success' : a.state === 'withdrawn' ? 'warning' : 'neutral'}>{t(`ann.state.${a.state}`)}</Chip></dd>
            <dt>{t('ann.col.unit')}</dt>
            <dd>{unitName}</dd>
            <dt>{t('ann.version')}</dt>
            <dd>{a.current_version}</dd>
            {a.published_at && (
              <>
                <dt>{t('ann.publishedAt')}</dt>
                <dd>{formatDateTime(a.published_at, locale)}</dd>
              </>
            )}
            <dt>{t('ann.col.read')}</dt>
            <dd><ReadChip a={a} /></dd>
          </dl>
          {a.content_hidden ? <p className={styles.notice}>{t('ann.contentHidden')}</p> : <p className={styles.body}>{a.body}</p>}
        </Card>

        {actions.versions && (
          <Card>
            <div className={styles.cardHead}>
              <h2 className={styles.cardTitle}>{t('ann.versions')}</h2>
              {!showVersions && <Button variant="secondary" onClick={() => setShowVersions(true)}>{t('ann.versions.show')}</Button>}
            </div>
            {versions.isPending && showVersions && <Skeleton lines={2} />}
            {versions.isError && <ErrorState error={versions.error} />}
            {versions.data && (
              <ul className={styles.list}>
                {[...versions.data].reverse().map((v) => (
                  <li key={v.version} className={styles.item}>
                    <strong>{t('ann.versions.v', { n: v.version })} — {v.title}</strong>
                    <span className={styles.meta}>{formatDateTime(v.created_at, locale)}</span>
                    <span className={styles.body}>{v.body}</span>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        )}

        {actions.recipients && (
          <Card>
            <div className={styles.cardHead}>
              <h2 className={styles.cardTitle}>{t('ann.recipients')}</h2>
              {!showRecipients && <Button variant="secondary" onClick={() => setShowRecipients(true)}>{t('ann.recipients.show')}</Button>}
            </div>
            {status.isPending && showRecipients && <Skeleton lines={2} />}
            {status.isError && <ErrorState error={status.error} />}
            {status.data && (
              <ul className={styles.list}>
                {status.data.map((r) => (
                  <li key={r.member_id} className={styles.item}>
                    <span>{names.nameOf(r.member_id)}</span>
                    {r.read_current ? <Chip tone="success">{t('ann.recipients.read')}</Chip> : r.read_version ? <Chip tone="warning">{t('ann.recipients.older')}</Chip> : <Chip>{t('ann.recipients.notRead')}</Chip>}
                  </li>
                ))}
              </ul>
            )}
          </Card>
        )}
      </div>

      <Modal
        open={dialog === 'edit'}
        title={t('ann.edit.title')}
        onClose={close}
        footer={<><Button variant="ghost" onClick={close}>{t('common.cancel')}</Button><Button loading={update.isPending} onClick={saveEdit}>{t('common.save')}</Button></>}
      >
        <div className={styles.form}>
          {a.state === 'published' && <p className={styles.hint}>{t('ann.edit.publishedNote')}</p>}
          <TextField label={t('ann.field.title')} value={title} maxLength={300} onChange={(e) => setTitle(e.target.value)} error={submitted && !title.trim() ? t('tasks.titleRequired') : undefined} required />
          <TextAreaField label={t('ann.field.body')} value={body} maxLength={20000} onChange={(e) => setBody(e.target.value)} error={submitted && !body.trim() ? t('ann.bodyRequired') : undefined} required />
          <InlineError error={update.error} />
        </div>
      </Modal>

      <Modal
        open={dialog === 'publish'}
        title={t('ann.publish.title')}
        onClose={close}
        footer={
          <>
            <Button variant="ghost" onClick={close}>{t('common.cancel')}</Button>
            <Button
              loading={publish.isPending}
              onClick={() => {
                setSubmitted(true)
                if (recipients.length === 0) return
                publish.mutate(recipients, { onSuccess: () => { close(); toast(t('ann.published')) } })
              }}
            >
              {t('ann.publish')}
            </Button>
          </>
        }
      >
        <div className={styles.form}>
          <p>{t('ann.publish.body')}</p>
          <ul className={styles.pickList}>
            {names.members.map((m) => (
              <li key={m.id}>
                <label className={styles.pick}><input type="checkbox" checked={recipients.includes(m.id)} onChange={() => toggle(m.id)} /> {m.full_name}</label>
              </li>
            ))}
          </ul>
          {submitted && recipients.length === 0 && <p role="alert" className={styles.notice}>{t('ann.recipientsRequired')}</p>}
          <InlineError error={publish.error} />
        </div>
      </Modal>

      <ConfirmDialog
        open={dialog === 'withdraw'}
        title={t('ann.withdraw.title')}
        body={<div className={styles.form}><p>{t('ann.withdraw.body')}</p><InlineError error={withdraw.error} /></div>}
        confirmLabel={t('ann.withdraw')}
        danger
        loading={withdraw.isPending}
        onConfirm={() => withdraw.mutate(undefined, { onSuccess: () => { close(); toast(t('ann.withdrawn')) } })}
        onClose={close}
      />
    </>
  )
}
