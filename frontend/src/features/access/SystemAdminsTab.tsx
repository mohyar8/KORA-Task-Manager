import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { meKey } from '@/features/auth/api'
import { useI18n } from '@/shared/i18n/i18n'
import { formatDateTime } from '@/shared/lib/format'
import { Button } from '@/shared/ui/Button'
import { Chip, ErrorState, InlineError, Skeleton, useToast } from '@/shared/ui/Feedback'
import { SelectField } from '@/shared/ui/Field'
import { TableWrap } from '@/shared/ui/Layout'
import { ConfirmDialog, Modal } from '@/shared/ui/Modal'
import { useSession } from '@/features/auth/session'
import { useAccountOptions } from './accounts'
import { useGrantSystemAdmin, useRevokeSystemAdmin, useSystemAdmins } from './api'
import type { SystemAdmin } from './types'
import styles from './access.module.css'

export function SystemAdminsTab() {
  const { t, locale } = useI18n()
  const toast = useToast()
  const { account } = useSession()
  const query = useSystemAdmins()
  const { options } = useAccountOptions()
  const grant = useGrantSystemAdmin()
  const revoke = useRevokeSystemAdmin()
  const queryClient = useQueryClient()
  const [granting, setGranting] = useState(false)
  const [target, setTarget] = useState('')
  const [revoking, setRevoking] = useState<SystemAdmin | null>(null)

  if (query.isPending) return <Skeleton lines={4} />
  if (query.isError) return <ErrorState error={query.error} onRetry={() => void query.refetch()} />

  const adminIds = new Set(query.data.map((a) => a.account_id))
  const usernameOf = (id: string | null) => (id ? (query.data.find((a) => a.account_id === id)?.username ?? options.find((o) => o.accountId === id)?.label ?? t('common.unknown')) : t('admin.admins.bootstrap'))
  const candidates = options.filter((o) => !adminIds.has(o.accountId))

  const closeGrant = () => {
    grant.reset()
    setGranting(false)
    setTarget('')
  }
  const closeRevoke = () => {
    revoke.reset()
    setRevoking(null)
  }

  return (
    <div className={styles.stack}>
      <div className={styles.sectionHead}>
        <p>{t('admin.admins.description')}</p>
        <Button onClick={() => setGranting(true)}>{t('admin.admins.grant')}</Button>
      </div>

      <TableWrap label={t('admin.tab.admins')}>
        <table>
          <thead>
            <tr>
              <th>{t('admin.admins.username')}</th>
              <th>{t('admin.admins.grantedAt')}</th>
              <th>{t('admin.admins.grantedBy')}</th>
              <th>{t('common.actions')}</th>
            </tr>
          </thead>
          <tbody>
            {query.data.map((a) => (
              <tr key={a.account_id}>
                <td>
                  <span className={styles.mono}>{a.username}</span> {a.account_id === account?.id && <Chip tone="info">{t('common.you')}</Chip>}
                </td>
                <td>{formatDateTime(a.granted_at, locale)}</td>
                <td>{usernameOf(a.granted_by_account_id)}</td>
                <td>
                  <Button variant="secondary" onClick={() => setRevoking(a)}>{t('common.revoke')}</Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </TableWrap>

      <Modal
        open={granting}
        title={t('admin.admins.grant.title')}
        onClose={closeGrant}
        footer={
          <>
            <Button variant="ghost" onClick={closeGrant}>{t('common.cancel')}</Button>
            <Button
              disabled={!target}
              loading={grant.isPending}
              onClick={() => grant.mutate(target, { onSuccess: () => { closeGrant(); toast(t('admin.admins.granted')) } })}
            >
              {t('admin.admins.grant')}
            </Button>
          </>
        }
      >
        <div className={styles.formGrid}>
          <p>{t('admin.admins.grant.body')}</p>
          {candidates.length === 0 ? (
            <p>{t('admin.admins.noCandidates')}</p>
          ) : (
            <SelectField label={t('admin.accounts.pick')} value={target} onChange={(e) => setTarget(e.target.value)}>
              <option value="">{t('admin.accounts.pickPlaceholder')}</option>
              {candidates.map((o) => <option key={o.accountId} value={o.accountId}>{o.label}</option>)}
            </SelectField>
          )}
          <InlineError error={grant.error} />
        </div>
      </Modal>

      <ConfirmDialog
        open={!!revoking}
        title={t('admin.admins.revoke.title', { name: revoking?.username ?? '' })}
        body={
          <div className={styles.formGrid}>
            <p>{t('admin.admins.revoke.body')}</p>
            <InlineError error={revoke.error} />
          </div>
        }
        confirmLabel={t('common.revoke')}
        danger
        loading={revoke.isPending}
        onConfirm={() => revoking && revoke.mutate(revoking.account_id, {
            onSuccess: () => {
              // Revoking yourself changes what /auth/me says about you.
              if (revoking.account_id === account?.id) void queryClient.invalidateQueries({ queryKey: meKey })
              closeRevoke()
              toast(t('admin.admins.revoked'))
            },
          })}
        onClose={closeRevoke}
      />
    </div>
  )
}
