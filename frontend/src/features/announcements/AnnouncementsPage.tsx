import { useState } from 'react'
import { useSearchParams } from 'react-router'
import { Megaphone, Plus } from 'lucide-react'
import { useI18n } from '@/shared/i18n/i18n'
import { formatDateTime } from '@/shared/lib/format'
import { Button } from '@/shared/ui/Button'
import { Chip, EmptyState, ErrorState, InlineError, Skeleton, useToast, type Tone } from '@/shared/ui/Feedback'
import { SelectField, TextAreaField, TextField } from '@/shared/ui/Field'
import { PageHeader } from '@/shared/ui/Layout'
import { Avatar, Row, RowList } from '@/shared/ui/RowList'
import { Modal } from '@/shared/ui/Modal'
import { allUnits, allowedUnits } from '@/features/auth/permissions'
import { useSession } from '@/features/auth/session'
import { ANNOUNCEMENT_STATES, useAnnouncements, useCreateAnnouncement, type Announcement } from './api'
import styles from './announcements.module.css'

const stateTone: Record<Announcement['state'], Tone> = { draft: 'neutral', published: 'success', withdrawn: 'warning' }

export function ReadChip({ a }: { a: Announcement }) {
  const { t } = useI18n()
  if (a.my_read_current === null) return <>—</>
  if (a.my_read_current) return <Chip tone="success">{t('ann.read.read')}</Chip>
  return <Chip tone="warning">{a.my_read_version ? t('ann.read.updated') : t('ann.read.unread')}</Chip>
}

export function AnnouncementsPage() {
  const { t, locale } = useI18n()
  const toast = useToast()
  const { access } = useSession()
  const [params, setParams] = useSearchParams()
  const state = params.get('state') ?? ''
  const query = useAnnouncements(state || undefined)
  const create = useCreateAnnouncement()
  const [creating, setCreating] = useState(false)
  const [title, setTitle] = useState('')
  const [body, setBody] = useState('')
  const [scope, setScope] = useState('')
  const [submitted, setSubmitted] = useState(false)

  const publishUnits = allowedUnits(access, 'announcement.publish')
  const unitName = (id: string) => allUnits(access).find((u) => u.unit_id === id)?.name ?? id

  const open = () => {
    create.reset(); setTitle(''); setBody(''); setScope(''); setSubmitted(false); setCreating(true)
  }
  const submit = () => {
    setSubmitted(true)
    if (!title.trim() || !body.trim() || !scope) return
    create.mutate({ scope_unit_id: scope, title: title.trim(), body: body.trim() }, { onSuccess: () => { setCreating(false); toast(t('ann.created')) } })
  }

  return (
    <>
      <PageHeader
        title={t('ann.title')}
        description={t('ann.description')}
        actions={publishUnits.length > 0 && <Button onClick={open}><Plus size={18} aria-hidden="true" /> {t('ann.new')}</Button>}
      />
      <div className={styles.filter}>
        <SelectField
          label={t('ann.filter.state')}
          value={state}
          onChange={(e) => {
            const next = new URLSearchParams(params)
            if (e.target.value) next.set('state', e.target.value)
            else next.delete('state')
            setParams(next, { replace: true })
          }}
        >
          <option value="">{t('tasks.all')}</option>
          {ANNOUNCEMENT_STATES.map((s) => <option key={s} value={s}>{t(`ann.state.${s}`)}</option>)}
        </SelectField>
      </div>

      {query.isPending && <Skeleton lines={5} />}
      {query.isError && <ErrorState error={query.error} onRetry={() => void query.refetch()} />}
      {query.data && query.data.length === 0 && <EmptyState title={state ? t('ann.empty') : t('ann.emptyNone')} />}
      {query.data && query.data.length > 0 && (
        <RowList label={t('ann.title')}>
          {query.data.map((a, i) => (
            <Row
              key={a.id}
              index={i}
              to={`/announcements/${a.id}`}
              title={a.title ?? t('ann.untitled')}
              accent={a.state === 'published' ? (a.my_read_current === false ? 'coral' : 'green') : a.state === 'withdrawn' ? 'fuchsia' : 'gray'}
              leading={<Avatar tone={a.state === 'published' ? 'fuchsia' : a.state === 'withdrawn' ? 'gray' : 'navy'}><Megaphone size={22} aria-hidden="true" /></Avatar>}
              meta={<><span>{unitName(a.scope_unit_id)}</span><span>{formatDateTime(a.updated_at, locale)}</span></>}
              trailing={<><ReadChip a={a} /><Chip tone={stateTone[a.state]}>{t(`ann.state.${a.state}`)}</Chip></>}
            />
          ))}
        </RowList>
      )}

      <Modal
        open={creating}
        title={t('ann.create.title')}
        onClose={() => setCreating(false)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setCreating(false)}>{t('common.cancel')}</Button>
            <Button loading={create.isPending} onClick={submit}>{t('ann.create.submit')}</Button>
          </>
        }
      >
        <div className={styles.form}>
          <TextField label={t('ann.field.title')} value={title} maxLength={300} onChange={(e) => setTitle(e.target.value)} error={submitted && !title.trim() ? t('tasks.titleRequired') : undefined} required />
          <TextAreaField label={t('ann.field.body')} value={body} maxLength={20000} onChange={(e) => setBody(e.target.value)} error={submitted && !body.trim() ? t('ann.bodyRequired') : undefined} required />
          <SelectField label={t('ann.field.scope')} value={scope} onChange={(e) => setScope(e.target.value)} error={submitted && !scope ? t('tasks.scopeRequired') : undefined} required>
            <option value="">{t('tasks.pickUnit')}</option>
            {publishUnits.map((u) => <option key={u.unit_id} value={u.unit_id}>{u.name}</option>)}
          </SelectField>
          <InlineError error={create.error} />
        </div>
      </Modal>
    </>
  )
}
