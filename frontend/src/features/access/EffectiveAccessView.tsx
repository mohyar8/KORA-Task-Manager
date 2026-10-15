import { useState } from 'react'
import { Check, Minus, X } from 'lucide-react'
import { useI18n } from '@/shared/i18n/i18n'
import { localInputToIso } from '@/shared/lib/format'
import { ErrorState, Skeleton } from '@/shared/ui/Feedback'
import { TextField } from '@/shared/ui/Field'
import { TableWrap } from '@/shared/ui/Layout'
import type { UnitDecision } from '@/features/auth/types'
import { useEffectiveAccess } from './api'
import { decisionLabel, permissionLabel, unitKindLabel } from './labels'
import styles from './access.module.css'

/** Matrix of unit × permission with the deciding source — the server's own evaluation (contract §7.4). */
export function EffectiveAccessView({ accountId }: { accountId: string }) {
  const { t } = useI18n()
  const [asOfInput, setAsOfInput] = useState('')
  const asOf = localInputToIso(asOfInput)
  const query = useEffectiveAccess(accountId, asOf)

  // Units come from the first permission's list; the response orders them by depth then name.
  const permissions = query.data?.permissions ?? []
  const units = permissions[0]?.units ?? []
  const decisionAt = (permissionIndex: number, unitId: string): UnitDecision | undefined =>
    permissions[permissionIndex].units.find((u) => u.unit_id === unitId)
  const nameOf = (id: string | null) => units.find((u) => u.unit_id === id)?.name

  return (
    <div className={styles.stack}>
      <div className={styles.toolbar}>
        <h2 className={styles.sectionTitle}>{t('admin.effective.title')}</h2>
        <TextField
          label={t('admin.effective.asOf')}
          type="datetime-local"
          hint={t('admin.effective.asOfHint')}
          value={asOfInput}
          onChange={(e) => setAsOfInput(e.target.value)}
        />
      </div>

      {query.isPending && <Skeleton lines={5} />}
      {query.isError && <ErrorState error={query.error} onRetry={() => void query.refetch()} />}
      {query.data && (
        <TableWrap label={t('admin.effective.title')}>
          <table className={styles.matrix}>
            <thead>
              <tr>
                <th>{t('admin.effective.unit')}</th>
                {permissions.map((p) => <th key={p.permission}>{permissionLabel(t, p.permission)}</th>)}
              </tr>
            </thead>
            <tbody>
              {units.map((u) => (
                <tr key={u.unit_id}>
                  <td>
                    {u.name} <span className={styles.sub}>({unitKindLabel(t, u.kind)})</span>
                  </td>
                  {permissions.map((p, i) => {
                    const d = decisionAt(i, u.unit_id)
                    if (!d) return <td key={p.permission}>—</td>
                    const Icon = d.allowed ? Check : d.source === 'override_deny' ? X : Minus
                    const cls = d.allowed ? styles.allowed : d.source === 'override_deny' ? styles.denied : styles.none
                    const at = d.decided_at_unit_id && d.decided_at_unit_id !== u.unit_id ? nameOf(d.decided_at_unit_id) : null
                    return (
                      <td key={p.permission}>
                        <span className={styles.cell}>
                          <Icon size={18} className={cls} aria-hidden="true" />
                          <span>{decisionLabel(t, d.source)}</span>
                          {at && <span className={styles.sub}>{t('admin.effective.decidedAt', { unit: at })}</span>}
                        </span>
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </TableWrap>
      )}
    </div>
  )
}
