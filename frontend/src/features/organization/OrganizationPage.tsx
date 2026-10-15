import { useState, type ReactNode } from 'react'
import { Archive, ArrowRightLeft, Plus } from 'lucide-react'
import { useI18n } from '@/shared/i18n/i18n'
import { formatDateTime } from '@/shared/lib/format'
import { Button } from '@/shared/ui/Button'
import { Chip, EmptyState, ErrorState, InlineError, Skeleton, useToast } from '@/shared/ui/Feedback'
import { SelectField, TextField } from '@/shared/ui/Field'
import { PageHeader } from '@/shared/ui/Layout'
import { ConfirmDialog, Modal } from '@/shared/ui/Modal'
import { unitKindLabel } from '@/features/access/labels'
import { useSession } from '@/features/auth/session'
import { useMembers } from '@/features/members/api'
import { useArchiveUnit, useCreateUnit, useMoveTeam, useUnit, useUnits, type Unit } from './api'
import styles from './organization.module.css'

type Dialog =
  | { type: 'create'; kind: 'administration' | 'team'; parent: Unit }
  | { type: 'move'; team: Unit }
  | { type: 'archive'; unit: Unit }
  | { type: 'details'; unit: Unit }
  | null

/** Tree of the units the caller manages. KORA and the PMO cannot be archived (contract §8.1). */
export function OrganizationPage() {
  const { t, locale } = useI18n()
  const toast = useToast()
  const { account } = useSession()
  const units = useUnits(true)
  // Active Member counts per team are available only to System Admins (the only Member listing, roadmap G1).
  const members = useMembers(!!account?.is_system_admin)
  const create = useCreateUnit()
  const move = useMoveTeam()
  const archive = useArchiveUnit()

  const [dialog, setDialog] = useState<Dialog>(null)
  const detail = useUnit(dialog?.type === 'details' ? dialog.unit.id : null)
  const [name, setName] = useState('')
  const [nameMissing, setNameMissing] = useState(false)
  const [destination, setDestination] = useState('')

  const open = (d: Dialog) => {
    create.reset()
    move.reset()
    archive.reset()
    setName('')
    setNameMissing(false)
    setDestination('')
    setDialog(d)
  }
  const close = () => setDialog(null)

  if (units.isPending) return <Skeleton lines={6} />
  if (units.isError) return <ErrorState error={units.error} onRetry={() => void units.refetch()} />

  const all = units.data
  const ids = new Set(all.map((u) => u.id))
  const childrenOf = (id: string) => all.filter((u) => u.parent_id === id).sort((a, b) => a.name.localeCompare(b.name))
  // A unit whose parent the caller does not manage is shown as a root of its own subtree.
  const roots = all.filter((u) => !u.parent_id || !ids.has(u.parent_id)).sort((a, b) => a.kind.localeCompare(b.kind) || a.name.localeCompare(b.name))
  const countFor = (teamId: string) => members.data?.filter((m) => m.status === 'active' && m.team_id === teamId).length

  const activeAdministrations = all.filter((u) => u.kind === 'administration' && u.status === 'active')

  const submitCreate = () => {
    if (dialog?.type !== 'create') return
    const trimmed = name.trim()
    if (!trimmed) return setNameMissing(true)
    create.mutate(
      { kind: dialog.kind, name: trimmed, parent_id: dialog.parent.id },
      { onSuccess: () => { close(); toast(t('org.created')) } },
    )
  }

  const renderUnit = (u: Unit): ReactNode => {
    const archived = u.status === 'archived'
    const count = u.kind === 'team' ? countFor(u.id) : undefined
    return (
      <li key={u.id} className={styles.node}>
        <div className={`${styles.row} ${archived ? styles.archived : ''}`}>
          <div className={styles.info}>
            <span className={styles.name}>{u.name}</span>
            <span className={styles.meta}>{unitKindLabel(t, u.kind)}</span>
            <Chip tone={archived ? 'neutral' : 'success'}>{archived ? t('org.status.archived') : t('org.status.active')}</Chip>
            {count !== undefined && <span className={styles.meta}>{t('org.members.count', { n: count })}</span>}
          </div>
          <div className={styles.actions}>
            <Button variant="ghost" onClick={() => open({ type: 'details', unit: u })}>{t('org.details')}</Button>
            {!archived && (<>
              {(u.kind === 'organization' || u.kind === 'administration') && (
                <Button
                  variant="secondary"
                  onClick={() => open({ type: 'create', kind: u.kind === 'organization' ? 'administration' : 'team', parent: u })}
                >
                  <Plus size={16} aria-hidden="true" /> {u.kind === 'organization' ? t('org.addAdministration') : t('org.addTeam')}
                </Button>
              )}
              {u.kind === 'team' && (
                <Button variant="ghost" onClick={() => open({ type: 'move', team: u })}>
                  <ArrowRightLeft size={16} aria-hidden="true" /> {t('org.move')}
                </Button>
              )}
              {(u.kind === 'administration' || u.kind === 'team') && (
                <Button variant="ghost" onClick={() => open({ type: 'archive', unit: u })}>
                  <Archive size={16} aria-hidden="true" /> {t('org.archive')}
                </Button>
              )}
            </>)}
          </div>
        </div>
        {childrenOf(u.id).length > 0 && <ul className={styles.tree}>{childrenOf(u.id).map(renderUnit)}</ul>}
      </li>
    )
  }

  const detailUnit = detail.data ?? (dialog?.type === 'details' ? dialog.unit : null)
  const parentName = dialog?.type === 'create' ? dialog.parent.name : ''

  return (
    <>
      <PageHeader title={t('org.title')} description={t('org.description')} />
      {roots.length === 0 ? <EmptyState title={t('org.empty')} /> : <ul className={`${styles.tree} ${styles.root}`}>{roots.map(renderUnit)}</ul>}

      <Modal
        open={dialog?.type === 'create'}
        title={dialog?.type === 'create' ? (dialog.kind === 'administration' ? t('org.create.administration.title') : t('org.create.team.title', { parent: parentName })) : ''}
        onClose={close}
        footer={
          <>
            <Button variant="ghost" onClick={close}>{t('common.cancel')}</Button>
            <Button loading={create.isPending} onClick={submitCreate}>{t('common.add')}</Button>
          </>
        }
      >
        <div className={styles.form}>
          <TextField
            label={t('org.name')}
            value={name}
            maxLength={200}
            hint={t('org.nameHint')}
            error={nameMissing && !name.trim() ? t('org.nameRequired') : undefined}
            onChange={(e) => setName(e.target.value)}
            required
          />
          <InlineError error={create.error} />
        </div>
      </Modal>

      <Modal
        open={dialog?.type === 'move'}
        title={dialog?.type === 'move' ? t('org.move.title', { team: dialog.team.name }) : ''}
        onClose={close}
        footer={
          <>
            <Button variant="ghost" onClick={close}>{t('common.cancel')}</Button>
            <Button
              loading={move.isPending}
              disabled={!destination}
              onClick={() =>
                dialog?.type === 'move' &&
                move.mutate({ unitId: dialog.team.id, administrationId: destination }, { onSuccess: () => { close(); toast(t('org.moved')) } })
              }
            >
              {t('org.move')}
            </Button>
          </>
        }
      >
        <div className={styles.form}>
          <p>{t('org.move.body')}</p>
          {dialog?.type === 'move' && (() => {
            const options = activeAdministrations.filter((a) => a.id !== dialog.team.parent_id)
            return options.length === 0 ? (
              <p>{t('org.move.noDestinations')}</p>
            ) : (
              <SelectField label={t('org.move.destination')} value={destination} onChange={(e) => setDestination(e.target.value)}>
                <option value="">{t('members.pickAdministration')}</option>
                {options.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
              </SelectField>
            )
          })()}
          <InlineError error={move.error} />
        </div>
      </Modal>

      <Modal open={dialog?.type === 'details'} title={t('org.detail.title')} onClose={close}>
        {detailUnit && (
          <dl className={styles.facts}>
            <dt>{t('org.name')}</dt><dd>{detailUnit.name}</dd>
            <dt>{t('org.detail.kind')}</dt><dd>{unitKindLabel(t, detailUnit.kind)}</dd>
            <dt>{t('org.detail.status')}</dt><dd>{detailUnit.status === 'archived' ? t('org.status.archived') : t('org.status.active')}</dd>
            <dt>{t('org.detail.parent')}</dt><dd>{all.find((x) => x.id === detailUnit.parent_id)?.name ?? '—'}</dd>
            {detailUnit.archived_at && (<><dt>{t('org.detail.archivedAt')}</dt><dd>{formatDateTime(detailUnit.archived_at, locale)}</dd></>)}
          </dl>
        )}
      </Modal>

      <ConfirmDialog
        open={dialog?.type === 'archive'}
        title={dialog?.type === 'archive' ? t('org.archive.title', { unit: dialog.unit.name }) : ''}
        body={
          <div className={styles.form}>
            <p>{t('org.archive.body')}</p>
            <InlineError error={archive.error} />
          </div>
        }
        confirmLabel={t('org.archive')}
        danger
        loading={archive.isPending}
        onConfirm={() => dialog?.type === 'archive' && archive.mutate(dialog.unit.id, { onSuccess: () => { close(); toast(t('org.archivedToast')) } })}
        onClose={close}
      />
    </>
  )
}
