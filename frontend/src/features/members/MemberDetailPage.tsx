import { useState } from 'react'
import { Link, useParams } from 'react-router'
import { ArrowRight } from 'lucide-react'
import { ApiError } from '@/shared/api/http'
import { useI18n } from '@/shared/i18n/i18n'
import { Button } from '@/shared/ui/Button'
import { Chip, ErrorState, InlineError, Skeleton, useToast } from '@/shared/ui/Feedback'
import { Card, PageHeader } from '@/shared/ui/Layout'
import { ConfirmDialog, Modal } from '@/shared/ui/Modal'
import { roleLabel } from '@/features/access/labels'
import { useUnitDirectory } from '@/features/organization/directory'
import {
  useChangeRole, useChangeTeam, useDeactivateMember, useMember, useReactivateMember, useReplaceProfile, useResetPassword,
} from './api'
import { ProfileFields, RoleFieldsInput, TeamSelect } from './fields'
import { TemporaryPasswordDialog } from './TemporaryPasswordDialog'
import {
  blankRoleDraft, draftToProfile, profileToDraft, roleFieldsFor, roleNeedsTeam, validateProfile, type Member, type ProfileDraft, type RoleDraft,
} from './types'
import styles from './members.module.css'

export function MemberDetailPage() {
  const { memberId = '' } = useParams()
  const { t } = useI18n()
  const query = useMember(memberId)

  if (query.isPending) return <Skeleton lines={6} />
  if (query.isError) {
    return <ErrorState error={query.error instanceof ApiError && query.error.status === 404 ? new ApiError(404, 'Not found.') : query.error} onRetry={() => void query.refetch()} />
  }
  const m = query.data
  return (
    <>
      <Link className={styles.back} to="/admin/members"><ArrowRight size={16} aria-hidden="true" className={styles.backIcon} /> {t('members.back')}</Link>
      <PageHeader
        title={m.full_name}
        description={m.username}
        actions={<Chip tone={m.status === 'active' ? 'success' : 'neutral'}>{t(`members.status.${m.status}`)}</Chip>}
      />
      {/* key resets form state whenever the server copy changes */}
      <div className={styles.sections}>
        <ProfileCard key={`p-${m.id}-${JSON.stringify([m.full_name, m.university_id, m.phone, m.email, m.major, m.academic_year])}`} member={m} />
        <PlacementCard member={m} />
        <AccountCard member={m} />
      </div>
    </>
  )
}

function ProfileCard({ member }: { member: Member }) {
  const { t } = useI18n()
  const toast = useToast()
  const save = useReplaceProfile(member.id)
  const [draft, setDraft] = useState<ProfileDraft>(profileToDraft(member))
  const [submitted, setSubmitted] = useState(false)
  const errors = validateProfile(draft, t)

  return (
    <Card>
      <h2 className={styles.cardTitle}>{t('members.profile.title')}</h2>
      <form
        className={styles.form}
        noValidate
        onSubmit={(e) => {
          e.preventDefault()
          setSubmitted(true)
          if (Object.keys(errors).length) return
          save.mutate(draftToProfile(draft), { onSuccess: () => toast(t('members.profile.saved')) })
        }}
      >
        <p className={styles.note}>{t('members.profile.note')}</p>
        <div className={styles.twoCol}>
          <ProfileFields draft={draft} onChange={setDraft} errors={submitted ? errors : {}} />
        </div>
        <InlineError error={save.error} />
        <div><Button type="submit" loading={save.isPending}>{t('members.profile.save')}</Button></div>
      </form>
    </Card>
  )
}

function PlacementCard({ member }: { member: Member }) {
  const { t } = useI18n()
  const toast = useToast()
  const { nameOf } = useUnitDirectory()
  const changeTeam = useChangeTeam(member.id)
  const changeRole = useChangeRole(member.id)
  const [mode, setMode] = useState<'team' | 'role' | null>(null)
  const [teamId, setTeamId] = useState('')
  const [roleDraft, setRoleDraft] = useState<RoleDraft>(blankRoleDraft)
  const [submitted, setSubmitted] = useState(false)
  const active = member.status === 'active'

  const openTeam = () => { changeTeam.reset(); setTeamId(''); setSubmitted(false); setMode('team') }
  const openRole = () => {
    changeRole.reset()
    setRoleDraft({ roleKey: member.role_key ?? 'member', administrationId: '' })
    setSubmitted(false)
    setMode('role')
  }
  const needsAdmin = roleDraft.roleKey === 'administration_manager' && !roleDraft.administrationId

  return (
    <Card>
      <h2 className={styles.cardTitle}>{t('members.placement.title')}</h2>
      <dl className={styles.facts}>
        <dt>{t('members.placement.team')}</dt>
        <dd>{nameOf(member.team_id) ?? t('members.placement.none')}</dd>
        <dt>{t('members.placement.role')}</dt>
        <dd>{member.role_key ? roleLabel(t, member.role_key) : t('members.placement.none')}</dd>
      </dl>
      {active ? (
        <div className={styles.actions}>
          <Button variant="secondary" onClick={openTeam}>{t('members.placement.changeTeam')}</Button>
          <Button variant="secondary" onClick={openRole}>{t('members.placement.changeRole')}</Button>
        </div>
      ) : (
        <p className={styles.note}>{t('members.account.deactivatedNote')}</p>
      )}

      <Modal
        open={mode === 'team'}
        title={t('members.placement.changeTeam')}
        onClose={() => setMode(null)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setMode(null)}>{t('common.cancel')}</Button>
            <Button
              loading={changeTeam.isPending}
              onClick={() => {
                setSubmitted(true)
                if (teamId) changeTeam.mutate(teamId, { onSuccess: () => { setMode(null); toast(t('members.placement.teamChanged')) } })
              }}
            >
              {t('common.save')}
            </Button>
          </>
        }
      >
        <div className={styles.form}>
          <TeamSelect value={teamId} onChange={setTeamId} error={submitted && !teamId ? t('members.teamRequired') : undefined} />
          <InlineError error={changeTeam.error} />
        </div>
      </Modal>

      <Modal
        open={mode === 'role'}
        title={t('members.placement.changeRole')}
        onClose={() => setMode(null)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setMode(null)}>{t('common.cancel')}</Button>
            <Button
              loading={changeRole.isPending}
              onClick={() => {
                setSubmitted(true)
                if (needsAdmin) return
                changeRole.mutate(roleFieldsFor(roleDraft.roleKey, roleDraft.administrationId), { onSuccess: () => { setMode(null); toast(t('members.placement.roleChanged')) } })
              }}
            >
              {t('common.save')}
            </Button>
          </>
        }
      >
        <div className={styles.form}>
          <RoleFieldsInput value={roleDraft} onChange={setRoleDraft} errors={submitted && needsAdmin ? { administration: t('members.administrationRequired') } : {}} />
          <InlineError error={changeRole.error} />
        </div>
      </Modal>
    </Card>
  )
}

function AccountCard({ member }: { member: Member }) {
  const { t } = useI18n()
  const toast = useToast()
  const reset = useResetPassword(member.id)
  const deactivate = useDeactivateMember(member.id)
  const reactivate = useReactivateMember(member.id)
  const [dialog, setDialog] = useState<'reset' | 'deactivate' | 'reactivate' | null>(null)
  const [secret, setSecret] = useState<{ name: string; username: string; password: string } | null>(null)
  const [teamId, setTeamId] = useState('')
  const [roleDraft, setRoleDraft] = useState<RoleDraft>(blankRoleDraft)
  const [submitted, setSubmitted] = useState(false)
  const active = member.status === 'active'

  const open = (d: typeof dialog) => {
    reset.reset(); deactivate.reset(); reactivate.reset()
    setTeamId(''); setRoleDraft(blankRoleDraft); setSubmitted(false)
    setDialog(d)
  }
  const needsAdmin = roleDraft.roleKey === 'administration_manager' && !roleDraft.administrationId

  return (
    <Card>
      <h2 className={styles.cardTitle}>{t('members.account.title')}</h2>
      <div className={styles.actions}>
        {active ? (
          <>
            <Button variant="secondary" onClick={() => open('reset')}>{t('members.account.reset')}</Button>
            <Button variant="danger" onClick={() => open('deactivate')}>{t('members.account.deactivate')}</Button>
          </>
        ) : (
          <Button onClick={() => open('reactivate')}>{t('members.account.reactivate')}</Button>
        )}
      </div>

      <ConfirmDialog
        open={dialog === 'reset'}
        title={t('members.account.reset.title', { name: member.full_name })}
        body={<div className={styles.form}><p>{t('members.account.reset.body')}</p><InlineError error={reset.error} /></div>}
        confirmLabel={t('members.account.reset')}
        loading={reset.isPending}
        onConfirm={() =>
          reset.mutate(undefined, {
            onSuccess: (res) => {
              setDialog(null)
              setSecret({ name: member.full_name, username: member.username, password: res.temporary_password })
            },
          })
        }
        onClose={() => setDialog(null)}
      />

      <ConfirmDialog
        open={dialog === 'deactivate'}
        title={t('members.account.deactivate.title', { name: member.full_name })}
        body={<div className={styles.form}><p>{t('members.account.deactivate.body')}</p><InlineError error={deactivate.error} /></div>}
        confirmLabel={t('members.account.deactivate')}
        danger
        loading={deactivate.isPending}
        onConfirm={() => deactivate.mutate(undefined, { onSuccess: () => { setDialog(null); toast(t('members.account.deactivated')) } })}
        onClose={() => setDialog(null)}
      />

      <Modal
        open={dialog === 'reactivate'}
        title={t('members.account.reactivate.title', { name: member.full_name })}
        onClose={() => setDialog(null)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setDialog(null)}>{t('common.cancel')}</Button>
            <Button
              loading={reactivate.isPending}
              onClick={() => {
                setSubmitted(true)
                if ((roleNeedsTeam(roleDraft.roleKey) && !teamId) || needsAdmin) return
                reactivate.mutate(
                  { ...roleFieldsFor(roleDraft.roleKey, roleDraft.administrationId), team_id: teamId || null },
                  { onSuccess: () => { setDialog(null); toast(t('members.account.reactivated')) } },
                )
              }}
            >
              {t('members.account.reactivate')}
            </Button>
          </>
        }
      >
        <div className={styles.form}>
          <p>{t('members.account.reactivate.body')}</p>
          <TeamSelect value={teamId} onChange={setTeamId} required={roleNeedsTeam(roleDraft.roleKey)} error={submitted && roleNeedsTeam(roleDraft.roleKey) && !teamId ? t('members.teamRequired') : undefined} />
          <RoleFieldsInput value={roleDraft} onChange={setRoleDraft} errors={submitted && needsAdmin ? { administration: t('members.administrationRequired') } : {}} />
          <InlineError error={reactivate.error} />
        </div>
      </Modal>

      <TemporaryPasswordDialog secret={secret} onDone={() => setSecret(null)} />
    </Card>
  )
}
