import { useState } from 'react'
import { useI18n } from '@/shared/i18n/i18n'
import { formatDate } from '@/shared/lib/format'
import { Button } from '@/shared/ui/Button'
import { Chip, EmptyState, ErrorState, InlineError, Skeleton, useToast } from '@/shared/ui/Feedback'
import { SelectField } from '@/shared/ui/Field'
import { TableWrap } from '@/shared/ui/Layout'
import { ConfirmDialog, Modal } from '@/shared/ui/Modal'
import type { Permission } from '@/features/auth/types'
import { useAddRoleDefault, useEndRoleDefault, useRoleDefaults } from './api'
import { permissionLabel, roleLabel } from './labels'
import { PERMISSIONS, ROLE_KEYS, type RoleDefault } from './types'
import styles from './access.module.css'

export function RoleDefaultsTab() {
  const { t, locale } = useI18n()
  const toast = useToast()
  const query = useRoleDefaults()
  const add = useAddRoleDefault()
  const end = useEndRoleDefault()
  const [adding, setAdding] = useState(false)
  const [role, setRole] = useState<string>(ROLE_KEYS[0])
  const [permission, setPermission] = useState<Permission>(PERMISSIONS[0])
  const [ending, setEnding] = useState<RoleDefault | null>(null)

  const openAdd = () => {
    add.reset()
    setAdding(true)
  }
  const closeEnd = () => {
    end.reset()
    setEnding(null)
  }

  if (query.isPending) return <Skeleton lines={5} />
  if (query.isError) return <ErrorState error={query.error} onRetry={() => void query.refetch()} />

  return (
    <div className={styles.stack}>
      <div className={styles.sectionHead}>
        <p>{t('admin.access.description')}</p>
        <Button onClick={openAdd}>{t('admin.roles.add')}</Button>
      </div>

      {query.data.length === 0 ? (
        <EmptyState title={t('admin.roles.empty')} />
      ) : (
        <TableWrap label={t('admin.tab.roles')}>
          <table>
            <thead>
              <tr>
                <th>{t('admin.roles.role')}</th>
                <th>{t('admin.roles.permission')}</th>
                <th>{t('admin.roles.from')}</th>
                <th>{t('admin.roles.to')}</th>
                <th>{t('common.actions')}</th>
              </tr>
            </thead>
            <tbody>
              {query.data.map((d) => (
                <tr key={d.id}>
                  <td>{roleLabel(t, d.role_key)}</td>
                  <td>{permissionLabel(t, d.permission)}</td>
                  <td>{formatDate(d.valid_from, locale)}</td>
                  <td>
                    {d.valid_to ? (
                      <>
                        <Chip>{t('common.ended')}</Chip> <span className={styles.sub}>{formatDate(d.valid_to, locale)}</span>
                      </>
                    ) : (
                      <Chip tone="success">{t('common.inForce')}</Chip>
                    )}
                  </td>
                  <td>
                    {!d.valid_to && (
                      <Button variant="secondary" onClick={() => setEnding(d)}>{t('common.end')}</Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableWrap>
      )}

      <Modal
        open={adding}
        title={t('admin.roles.add.title')}
        onClose={() => setAdding(false)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setAdding(false)}>{t('common.cancel')}</Button>
            <Button
              loading={add.isPending}
              onClick={() =>
                add.mutate({ role_key: role, permission }, { onSuccess: () => { setAdding(false); toast(t('admin.roles.added')) } })
              }
            >
              {t('common.add')}
            </Button>
          </>
        }
      >
        <div className={styles.formGrid}>
          <SelectField label={t('admin.roles.role')} value={role} onChange={(e) => setRole(e.target.value)}>
            {ROLE_KEYS.map((r) => <option key={r} value={r}>{roleLabel(t, r)}</option>)}
          </SelectField>
          <SelectField label={t('admin.roles.permission')} value={permission} onChange={(e) => setPermission(e.target.value as Permission)}>
            {PERMISSIONS.map((p) => <option key={p} value={p}>{permissionLabel(t, p)}</option>)}
          </SelectField>
          <InlineError error={add.error} />
        </div>
      </Modal>

      <ConfirmDialog
        open={!!ending}
        title={t('admin.roles.end.title')}
        body={
          <div className={styles.formGrid}>
            <p>
              {ending && t('admin.roles.end.body', { role: roleLabel(t, ending.role_key), permission: permissionLabel(t, ending.permission) })}
            </p>
            <InlineError error={end.error} />
          </div>
        }
        confirmLabel={t('common.end')}
        danger
        loading={end.isPending}
        onConfirm={() => ending && end.mutate(ending.id, { onSuccess: () => { closeEnd(); toast(t('admin.roles.endedToast')) } })}
        onClose={closeEnd}
      />
    </div>
  )
}
