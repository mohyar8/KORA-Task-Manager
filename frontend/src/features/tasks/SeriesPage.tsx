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
import { allUnits, allowedUnits, canAt } from '@/features/auth/permissions'
import { useSession } from '@/features/auth/session'
import { useMemberNames } from '@/features/members/directory'
import { useTasks } from './api'
import { seriesChanges, useMoveSeries, useSeries, useStopSeries, useUpdateSeries, type Series } from './seriesApi'
import { SeriesFormModal } from './SeriesForm'
import { DueText, PriorityText, StatusChip } from './TaskBits'
import { useViewer } from './useViewer'
import styles from './tasks.module.css'

export function SeriesPage() {
  const { seriesId = '' } = useParams()
  const query = useSeries(seriesId)
  if (query.isPending) return <Skeleton lines={6} />
  if (query.isError) return <ErrorState error={query.error} onRetry={() => void query.refetch()} />
  return <SeriesView series={query.data} />
}

function SeriesView({ series }: { series: Series }) {
  const { t, locale } = useI18n()
  const toast = useToast()
  const { access } = useSession()
  const viewer = useViewer()
  const names = useMemberNames()
  const tasks = useTasks({})
  const update = useUpdateSeries(series.id)
  const move = useMoveSeries(series.id)
  const stop = useStopSeries(series.id)
  const [dialog, setDialog] = useState<'edit' | 'move' | 'stop' | null>(null)
  const [destination, setDestination] = useState('')

  const unitName = (id: string) => allUnits(access).find((u) => u.unit_id === id)?.name ?? id
  const active = series.status === 'active'
  // The creator or a scoped manager may change or stop a series (contract §9.4).
  const mayManage = active && (series.created_by_account_id === viewer.accountId || canAt(access, 'task.manage', series.scope_unit_id))
  const moveOptions = allowedUnits(access, 'task.create').filter((u) => u.unit_id !== series.scope_unit_id)
  // Occurrences are ordinary tasks; the series response lists their ids, the task list gives their details.
  const known = new Map((tasks.data ?? []).map((x) => [x.id, x]))
  const occurrences = series.occurrence_ids.map((id) => known.get(id)).filter((x) => !!x)

  const close = () => setDialog(null)
  const open = (d: 'edit' | 'move' | 'stop') => {
    update.reset(); move.reset(); stop.reset(); setDestination(''); setDialog(d)
  }

  return (
    <>
      <Link className={styles.back} to="/tasks"><ArrowRight size={16} aria-hidden="true" className={styles.backIcon} /> {t('series.backList')}</Link>
      <PageHeader
        title={series.title}
        description={t('series.title')}
        actions={
          mayManage && (
            <div className={styles.actions}>
              <Button variant="secondary" onClick={() => open('edit')}>{t('series.edit')}</Button>
              {moveOptions.length > 0 && <Button variant="secondary" onClick={() => open('move')}>{t('series.move')}</Button>}
              <Button variant="danger" onClick={() => open('stop')}>{t('series.stop')}</Button>
            </div>
          )
        }
      />
      <div className={styles.sections}>
        <Card>
          <dl className={styles.facts}>
            <dt>{t('tasks.col.status')}</dt>
            <dd><Chip tone={active ? 'success' : 'neutral'}>{t(`series.status.${series.status}`)}</Chip></dd>
            <dt>{t('tasks.col.priority')}</dt>
            <dd><PriorityText priority={series.priority} /></dd>
            <dt>{t('tasks.detail.scope')}</dt>
            <dd>{unitName(series.scope_unit_id)}</dd>
            <dt>{t('series.firstDue')}</dt>
            <dd>{formatDateTime(series.first_due_at, locale)}</dd>
            <dt>{t('series.endsAt')}</dt>
            <dd>{formatDateTime(series.ends_at, locale)}</dd>
            <dt>{t('tasks.assignees.title')}</dt>
            <dd>{series.assignee_member_ids.map((id) => names.nameOf(id)).join('، ') || '—'}</dd>
            {series.stopped_at && (
              <>
                <dt>{t('series.stoppedOn')}</dt>
                <dd>{formatDateTime(series.stopped_at, locale)}</dd>
              </>
            )}
          </dl>
          {series.description && <p className={styles.description}>{series.description}</p>}
        </Card>

        <Card>
          <h2 className={styles.cardTitle}>{t('series.templates')}</h2>
          {series.subtask_templates.length === 0 ? (
            <p className={styles.hint}>{t('series.templates.none')}</p>
          ) : (
            <ul className={styles.list}>
              {series.subtask_templates.map((tpl) => (
                <li key={tpl.key} className={styles.item}>
                  <span>{tpl.title}</span>
                  <span className={styles.hint}>{tpl.assignee_member_ids.map((id) => names.nameOf(id)).join('، ')}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card>
          <h2 className={styles.cardTitle}>{t('series.occurrences')} ({series.occurrence_ids.length})</h2>
          <p className={styles.note}>{t('series.occurrences.note')}</p>
          {tasks.isPending && <Skeleton lines={3} />}
          {occurrences.length === 0 && !tasks.isPending && <p className={styles.hint}>{t('series.occurrences.none')}</p>}
          {occurrences.length > 0 && (
            <ul className={styles.list}>
              {occurrences.map((o) => (
                <li key={o.id} className={styles.item}>
                  <Link className={styles.titleLink} to={`/tasks/${o.id}`}>{o.title}</Link>
                  <span className={styles.meta}><DueText task={o} /> <StatusChip status={o.status} /></span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      {dialog === 'edit' && (
        <SeriesFormModal
          title={t('series.edit.title')}
          submitLabel={t('common.save')}
          initial={series}
          loading={update.isPending}
          error={update.error}
          onClose={close}
          onSubmit={(v) => {
            const diff = seriesChanges(series, v)
            if (Object.keys(diff).length === 0) return close()
            update.mutate(diff, { onSuccess: () => { close(); toast(t('series.updated')) } })
          }}
        />
      )}

      <Modal
        open={dialog === 'move'}
        title={t('series.move.title')}
        onClose={close}
        footer={
          <>
            <Button variant="ghost" onClick={close}>{t('common.cancel')}</Button>
            <Button disabled={!destination} loading={move.isPending} onClick={() => move.mutate(destination, { onSuccess: () => { close(); toast(t('series.moved')) } })}>
              {t('series.move')}
            </Button>
          </>
        }
      >
        <div className={styles.form}>
          <p>{t('series.move.body')}</p>
          <SelectField label={t('tasks.field.scope')} value={destination} onChange={(e) => setDestination(e.target.value)}>
            <option value="">{t('tasks.pickUnit')}</option>
            {moveOptions.map((u) => <option key={u.unit_id} value={u.unit_id}>{u.name}</option>)}
          </SelectField>
          <InlineError error={move.error} />
        </div>
      </Modal>

      <ConfirmDialog
        open={dialog === 'stop'}
        title={t('series.stop.title')}
        body={<div className={styles.form}><p>{t('series.stop.body')}</p><InlineError error={stop.error} /></div>}
        confirmLabel={t('series.stop')}
        danger
        loading={stop.isPending}
        onConfirm={() => stop.mutate(undefined, { onSuccess: () => { close(); toast(t('series.stopped')) } })}
        onClose={close}
      />
    </>
  )
}
