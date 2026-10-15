import { useState } from 'react'
import { useSearchParams } from 'react-router'
import { useI18n } from '@/shared/i18n/i18n'
import { formatDateTime, localInputToIso } from '@/shared/lib/format'
import { Button } from '@/shared/ui/Button'
import { EmptyState, ErrorState, Skeleton } from '@/shared/ui/Feedback'
import { SelectField, TextField } from '@/shared/ui/Field'
import { PageHeader, TableWrap } from '@/shared/ui/Layout'
import { Modal } from '@/shared/ui/Modal'
import { allUnits } from '@/features/auth/permissions'
import { useSession } from '@/features/auth/session'
import { useAccountOptions } from '@/features/access/accounts'
import { isUuid, KNOWN_ACTIONS, RESOURCE_TYPES, useAuditRecord, useAuditRecords, type AuditFilters, type AuditRecord } from './api'
import styles from './audit.module.css'

type FilterKey = 'from' | 'to' | 'action' | 'type' | 'actor' | 'resource' | 'unit'

/** /admin/audit — filters live in the URL; records load newest first with "load older". */
export function AuditPage() {
  const { t, locale } = useI18n()
  const { access } = useSession()
  const { options } = useAccountOptions()
  const [params, setParams] = useSearchParams()
  const get = (k: FilterKey) => params.get(k) ?? ''
  const [pickedRow, setPickedRow] = useState<AuditRecord | null>(null)
  const fresh = useAuditRecord(pickedRow?.id ?? null)
  const selected = fresh.data ?? pickedRow

  const actorInvalid = !!get('actor') && !isUuid(get('actor'))
  const resourceInvalid = !!get('resource') && !isUuid(get('resource'))
  const filters: AuditFilters = {
    occurred_from: localInputToIso(get('from')) ?? undefined,
    occurred_to: localInputToIso(get('to')) ?? undefined,
    action: get('action') || undefined,
    resource_type: get('type') || undefined,
    actor_account_id: get('actor') && !actorInvalid ? get('actor').trim() : undefined,
    resource_id: get('resource') && !resourceInvalid ? get('resource').trim() : undefined,
    scope_unit_id: get('unit') || undefined,
  }
  const query = useAuditRecords(filters)

  const set = (key: FilterKey, value: string) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    setParams(next, { replace: true })
  }
  const units = allUnits(access)
  const unitName = (id: string | null) => (id ? (units.find((u) => u.unit_id === id)?.name ?? id) : '—')
  const actorName = (id: string | null) => (id ? (options.find((o) => o.accountId === id)?.label ?? id.slice(0, 8)) : t('audit.detail.system'))
  const records = query.data?.pages.flatMap((p) => p.items) ?? []

  return (
    <>
      <PageHeader title={t('audit.title')} description={t('audit.description')} />
      <div className={styles.filters}>
        <TextField label={t('audit.filter.from')} type="datetime-local" value={get('from')} onChange={(e) => set('from', e.target.value)} dir="ltr" />
        <TextField label={t('audit.filter.to')} type="datetime-local" value={get('to')} onChange={(e) => set('to', e.target.value)} dir="ltr" />
        <SelectField label={t('audit.filter.action')} value={get('action')} onChange={(e) => set('action', e.target.value)}>
          <option value="">{t('audit.all')}</option>
          {KNOWN_ACTIONS.map((a) => <option key={a} value={a}>{a}</option>)}
        </SelectField>
        <SelectField label={t('audit.filter.resourceType')} value={get('type')} onChange={(e) => set('type', e.target.value)}>
          <option value="">{t('audit.all')}</option>
          {RESOURCE_TYPES.map((r) => <option key={r} value={r}>{r}</option>)}
        </SelectField>
        <SelectField label={t('audit.filter.actor')} value={get('actor')} onChange={(e) => set('actor', e.target.value)}>
          <option value="">{t('audit.all')}</option>
          {options.map((o) => <option key={o.accountId} value={o.accountId}>{o.label}</option>)}
        </SelectField>
        <SelectField label={t('audit.filter.unit')} value={get('unit')} onChange={(e) => set('unit', e.target.value)}>
          <option value="">{t('audit.all')}</option>
          {units.map((u) => <option key={u.unit_id} value={u.unit_id}>{u.name}</option>)}
        </SelectField>
        <TextField label={t('audit.filter.resourceId')} value={get('resource')} onChange={(e) => set('resource', e.target.value)} error={resourceInvalid ? t('audit.invalidId') : undefined} dir="ltr" />
        <div className={styles.clear}><Button variant="ghost" onClick={() => setParams({}, { replace: true })}>{t('audit.filter.clear')}</Button></div>
      </div>

      {query.isPending && <Skeleton lines={6} />}
      {query.isError && <ErrorState error={query.error} onRetry={() => void query.refetch()} />}
      {query.data && records.length === 0 && <EmptyState title={t('audit.empty')} />}
      {records.length > 0 && (
        <>
          <TableWrap label={t('audit.title')}>
            <table>
              <thead>
                <tr>
                  <th>{t('audit.col.time')}</th>
                  <th>{t('audit.col.action')}</th>
                  <th>{t('audit.col.resource')}</th>
                  <th>{t('audit.col.actor')}</th>
                  <th>{t('audit.col.unit')}</th>
                  <th><span className="visually-hidden">{t('audit.view')}</span></th>
                </tr>
              </thead>
              <tbody>
                {records.map((r) => (
                  <tr key={r.id}>
                    <td>{formatDateTime(r.occurred_at, locale)}</td>
                    <td className={styles.mono}>{r.action}</td>
                    <td><span className={styles.mono}>{r.resource_type}</span> <span className={styles.sub}>{r.resource_id.slice(0, 8)}</span></td>
                    <td>{actorName(r.actor_account_id)}</td>
                    <td>{unitName(r.scope_unit_id)}</td>
                    <td><Button variant="ghost" onClick={() => setPickedRow(r)}>{t('audit.view')}</Button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableWrap>
          <div className={styles.more}>
            {query.hasNextPage ? (
              <Button variant="secondary" loading={query.isFetchingNextPage} onClick={() => void query.fetchNextPage()}>{t('audit.loadMore')}</Button>
            ) : (
              <p className={styles.sub}>{t('audit.end')}</p>
            )}
          </div>
        </>
      )}

      <Modal open={!!selected} title={t('audit.detail.title')} onClose={() => setPickedRow(null)}>
        {selected && (
          <div className={styles.detail}>
            <dl className={styles.facts}>
              <dt>{t('audit.col.time')}</dt><dd>{formatDateTime(selected.occurred_at, locale)}</dd>
              <dt>{t('audit.detail.sequence')}</dt><dd>{selected.sequence}</dd>
              <dt>{t('audit.col.action')}</dt><dd className={styles.mono}>{selected.action}</dd>
              <dt>{t('audit.col.resource')}</dt><dd className={styles.mono}>{selected.resource_type}</dd>
              <dt>{t('audit.detail.resourceId')}</dt><dd className={styles.mono}>{selected.resource_id}</dd>
              <dt>{t('audit.detail.actor')}</dt><dd>{actorName(selected.actor_account_id)}</dd>
              <dt>{t('audit.col.unit')}</dt><dd>{unitName(selected.scope_unit_id)}</dd>
            </dl>
            <h3>{t('audit.detail.before')}</h3>
            <pre className={styles.json}>{selected.before ? JSON.stringify(selected.before, null, 2) : t('audit.detail.none')}</pre>
            <h3>{t('audit.detail.after')}</h3>
            <pre className={styles.json}>{selected.after ? JSON.stringify(selected.after, null, 2) : t('audit.detail.none')}</pre>
          </div>
        )}
      </Modal>
    </>
  )
}
