import { useState } from 'react'
import { useSearchParams } from 'react-router'
import { useI18n } from '@/shared/i18n/i18n'
import { formatDateTime } from '@/shared/lib/format'
import { Button } from '@/shared/ui/Button'
import { Chip, EmptyState, ErrorState, InlineError, Skeleton, useToast } from '@/shared/ui/Feedback'
import { SelectField, TextAreaField } from '@/shared/ui/Field'
import { TableWrap } from '@/shared/ui/Layout'
import { ConfirmDialog, Modal } from '@/shared/ui/Modal'
import { allUnits } from '@/features/auth/permissions'
import { useSession } from '@/features/auth/session'
import type { Permission } from '@/features/auth/types'
import { useAccountOptions } from './accounts'
import { useCreateOverride, useEndOverride, useOverrides } from './api'
import { EffectiveAccessView } from './EffectiveAccessView'
import { permissionLabel } from './labels'
import { KORA_UNIT_ID, PERMISSIONS, type Override, type OverrideEffect } from './types'
import styles from './access.module.css'

interface Draft {
  permission: Permission
  unitId: string
  effect: OverrideEffect
  reason: string
}
const blankDraft: Draft = { permission: PERMISSIONS[0], unitId: '', effect: 'grant', reason: '' }

export function AccountAccessTab() {
  const { t, locale } = useI18n()
  const toast = useToast()
  const { access } = useSession()
  const [params, setParams] = useSearchParams()
  const accountId = params.get('account')
  const { options, isLoading, error } = useAccountOptions()
  const overrides = useOverrides(accountId)
  const create = useCreateOverride(accountId ?? '')
  const end = useEndOverride()

  const [draft, setDraft] = useState<Draft | null>(null)
  const [reasonMissing, setReasonMissing] = useState(false)
  const [ending, setEnding] = useState<Override | null>(null)

  const units = allUnits(access)
  const unitName = (id: string) => units.find((u) => u.unit_id === id)?.name ?? id
  const selected = options.find((o) => o.accountId === accountId)
  const isSelf = !!selected?.isSelf

  const pick = (id: string) => {
    const next = new URLSearchParams(params)
    if (id) next.set('account', id)
    else next.delete('account')
    setParams(next, { replace: true })
  }
  const openDraft = (d: Draft) => {
    create.reset()
    setReasonMissing(false)
    setDraft(d)
  }
  const closeEnd = () => {
    end.reset()
    setEnding(null)
  }
  const submit = () => {
    if (!draft) return
    const reason = draft.reason.trim()
    if (!reason) return setReasonMissing(true)
    create.mutate(
      { permission: draft.permission, unit_id: draft.unitId, effect: draft.effect, reason },
      { onSuccess: () => { setDraft(null); toast(t('admin.overrides.created')) } },
    )
  }

  if (isLoading) return <Skeleton lines={3} />
  if (error) return <ErrorState error={error} />

  return (
    <div className={styles.stack}>
      <div className={styles.pick}>
        <SelectField label={t('admin.accounts.pick')} value={accountId ?? ''} onChange={(e) => pick(e.target.value)}>
          <option value="">{t('admin.accounts.pickPlaceholder')}</option>
          {options.map((o) => (
            <option key={o.accountId} value={o.accountId}>{o.isSelf ? `${o.label} — ${t('common.you')}` : o.label}</option>
          ))}
        </SelectField>
      </div>

      {!accountId && <EmptyState title={t('admin.accounts.empty')} />}

      {accountId && (
        <>
          {isSelf && (
            <div className={styles.banner}>
              <h3>{t('admin.bootstrap.title')}</h3>
              <p>{t('admin.bootstrap.body')}</p>
              <Button
                variant="secondary"
                onClick={() => openDraft({ ...blankDraft, permission: 'organization.manage', unitId: KORA_UNIT_ID })}
              >
                {t('admin.bootstrap.action')}
              </Button>
            </div>
          )}

          <div className={styles.stack}>
            <div className={styles.sectionHead}>
              <h2 className={styles.sectionTitle}>{t('admin.overrides.title')}</h2>
              <Button onClick={() => openDraft(blankDraft)}>{t('admin.overrides.add')}</Button>
            </div>

            {overrides.isPending && <Skeleton lines={3} />}
            {overrides.isError && <ErrorState error={overrides.error} onRetry={() => void overrides.refetch()} />}
            {overrides.data && overrides.data.length === 0 && <EmptyState title={t('admin.overrides.empty')} />}
            {overrides.data && overrides.data.length > 0 && (
              <TableWrap label={t('admin.overrides.title')}>
                <table>
                  <thead>
                    <tr>
                      <th>{t('admin.roles.permission')}</th>
                      <th>{t('admin.overrides.unit')}</th>
                      <th>{t('admin.overrides.effect')}</th>
                      <th>{t('common.reason')}</th>
                      <th>{t('admin.roles.from')}</th>
                      <th>{t('common.actions')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {overrides.data.map((o) => (
                      <tr key={o.id}>
                        <td>{permissionLabel(t, o.permission)}</td>
                        <td>{unitName(o.unit_id)}</td>
                        <td><Chip tone={o.effect === 'grant' ? 'success' : 'danger'}>{t(`effect.${o.effect}`)}</Chip></td>
                        <td className={styles.reasonCell}>{o.reason}</td>
                        <td>{formatDateTime(o.valid_from, locale)}</td>
                        <td>
                          {o.valid_to ? (
                            <Chip>{t('common.ended')}</Chip>
                          ) : (
                            <Button variant="secondary" onClick={() => setEnding(o)}>{t('common.end')}</Button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </TableWrap>
            )}
          </div>

          <EffectiveAccessView accountId={accountId} />
        </>
      )}

      <Modal
        open={!!draft}
        title={t('admin.overrides.add.title')}
        onClose={() => setDraft(null)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setDraft(null)}>{t('common.cancel')}</Button>
            <Button loading={create.isPending} disabled={!draft?.unitId} onClick={submit}>{t('common.add')}</Button>
          </>
        }
      >
        {draft && (
          <div className={styles.formGrid}>
            <SelectField label={t('admin.roles.permission')} value={draft.permission} onChange={(e) => setDraft({ ...draft, permission: e.target.value as Permission })}>
              {PERMISSIONS.map((p) => <option key={p} value={p}>{permissionLabel(t, p)}</option>)}
            </SelectField>
            <SelectField label={t('admin.overrides.unit')} value={draft.unitId} onChange={(e) => setDraft({ ...draft, unitId: e.target.value })}>
              <option value="">{t('admin.overrides.pickUnit')}</option>
              {units.map((u) => <option key={u.unit_id} value={u.unit_id}>{u.name}</option>)}
            </SelectField>
            <SelectField label={t('admin.overrides.effect')} value={draft.effect} onChange={(e) => setDraft({ ...draft, effect: e.target.value as OverrideEffect })}>
              <option value="grant">{t('effect.grant')}</option>
              <option value="deny">{t('effect.deny')}</option>
            </SelectField>
            <TextAreaField
              label={t('common.reason')}
              required
              maxLength={1000}
              hint={t('admin.overrides.reasonHint')}
              error={reasonMissing && !draft.reason.trim() ? t('admin.overrides.reasonRequired') : undefined}
              value={draft.reason}
              onChange={(e) => setDraft({ ...draft, reason: e.target.value })}
            />
            <InlineError error={create.error} />
          </div>
        )}
      </Modal>

      <ConfirmDialog
        open={!!ending}
        title={t('admin.overrides.end.title')}
        body={
          <div className={styles.formGrid}>
            <p>{t('admin.overrides.end.body')}</p>
            <InlineError error={end.error} />
          </div>
        }
        confirmLabel={t('common.end')}
        danger
        loading={end.isPending}
        onConfirm={() => ending && end.mutate(ending.id, { onSuccess: () => { closeEnd(); toast(t('admin.overrides.endedToast')) } })}
        onClose={closeEnd}
      />
    </div>
  )
}
