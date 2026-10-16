import { useMemo, useState } from 'react'
import { Plus } from 'lucide-react'
import { fieldErrors } from '@/shared/api/http'
import { useI18n } from '@/shared/i18n/i18n'
import { Button } from '@/shared/ui/Button'
import { Chip, EmptyState, ErrorState, InlineError, Skeleton, useToast } from '@/shared/ui/Feedback'
import { SelectField, TextField } from '@/shared/ui/Field'
import { PageHeader } from '@/shared/ui/Layout'
import { initialOf } from '@/shared/lib/initial'
import { Avatar, Row, RowList } from '@/shared/ui/RowList'
import { Modal } from '@/shared/ui/Modal'
import { matchesSearch } from '@/shared/lib/search'
import { roleLabel } from '@/features/access/labels'
import { ROLE_KEYS } from '@/features/access/types'
import { useUnitDirectory } from '@/features/organization/directory'
import { useMembers, useProvisionMember } from './api'
import { ProfileFields, RoleFieldsInput, TeamSelect } from './fields'
import { TemporaryPasswordDialog } from './TemporaryPasswordDialog'
import {
  blankRoleDraft, draftToProfile, emptyProfileDraft, roleFieldsFor, USERNAME_PATTERN, roleNeedsTeam, validateProfile, type ProfileDraft, type RoleDraft,
} from './types'
import styles from './members.module.css'

export function MembersPage() {
  const { t } = useI18n()
  const toast = useToast()
  const members = useMembers()
  const { nameOf, teams } = useUnitDirectory()
  const provision = useProvisionMember()

  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('')
  const [team, setTeam] = useState('')
  const [role, setRole] = useState('')

  const [creating, setCreating] = useState(false)
  const [profile, setProfile] = useState<ProfileDraft>(emptyProfileDraft)
  const [username, setUsername] = useState('')
  const [teamId, setTeamId] = useState('')
  const [roleDraft, setRoleDraft] = useState<RoleDraft>(blankRoleDraft)
  const [submitted, setSubmitted] = useState(false)
  const [secret, setSecret] = useState<{ name: string; username: string; password: string } | null>(null)

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    return (members.data ?? []).filter(
      (m) =>
        (!q || matchesSearch(q, m.full_name, m.username, m.university_id)) &&
        (!status || m.status === status) &&
        (!team || m.team_id === team) &&
        (!role || m.role_key === role),
    )
  }, [members.data, search, status, team, role])

  const openCreate = () => {
    provision.reset()
    setProfile(emptyProfileDraft)
    setUsername('')
    setTeamId('')
    setRoleDraft(blankRoleDraft)
    setSubmitted(false)
    setCreating(true)
  }

  const profileErrors = validateProfile(profile, t)
  const errors = {
    ...profileErrors,
    ...(submitted && !USERNAME_PATTERN.test(username) ? { username: t('members.usernameInvalid') } : {}),
    ...(submitted && roleNeedsTeam(roleDraft.roleKey) && !teamId ? { team: t('members.teamRequired') } : {}),
    ...(submitted && roleDraft.roleKey === 'administration_manager' && !roleDraft.administrationId ? { administration: t('members.administrationRequired') } : {}),
    // field messages from a 422 validation list override nothing client-side but fill gaps
    ...Object.fromEntries(Object.entries(fieldErrors(provision.error)).filter(([k]) => !(k in profileErrors))),
  }
  const clientInvalid =
    Object.keys(profileErrors).length > 0 ||
    !USERNAME_PATTERN.test(username) ||
    (roleNeedsTeam(roleDraft.roleKey) && !teamId) ||
    (roleDraft.roleKey === 'administration_manager' && !roleDraft.administrationId)

  const submit = () => {
    setSubmitted(true)
    if (clientInvalid) return
    const p = draftToProfile(profile)
    provision.mutate(
      { ...p, ...roleFieldsFor(roleDraft.roleKey, roleDraft.administrationId), username, team_id: teamId || null },
      {
        onSuccess: (res) => {
          setCreating(false)
          toast(t('members.created'))
          setSecret({ name: res.member.full_name, username: res.member.username, password: res.temporary_password })
        },
      },
    )
  }

  if (members.isPending) return <Skeleton lines={6} />
  if (members.isError) return <ErrorState error={members.error} onRetry={() => void members.refetch()} />

  return (
    <>
      <PageHeader
        title={t('members.title')}
        description={t('members.description')}
        actions={<Button onClick={openCreate}><Plus size={18} aria-hidden="true" /> {t('members.add')}</Button>}
      />

      <div className={styles.filters}>
        <TextField label={t('members.search')} type="search" value={search} onChange={(e) => setSearch(e.target.value)} />
        <SelectField label={t('members.filter.status')} value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">{t('members.all')}</option>
          <option value="active">{t('members.status.active')}</option>
          <option value="deactivated">{t('members.status.deactivated')}</option>
        </SelectField>
        <SelectField label={t('members.filter.team')} value={team} onChange={(e) => setTeam(e.target.value)}>
          <option value="">{t('members.all')}</option>
          {teams.map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
        </SelectField>
        <SelectField label={t('members.filter.role')} value={role} onChange={(e) => setRole(e.target.value)}>
          <option value="">{t('members.all')}</option>
          {ROLE_KEYS.map((r) => <option key={r} value={r}>{roleLabel(t, r)}</option>)}
        </SelectField>
      </div>

      {members.data.length === 0 ? (
        <EmptyState title={t('members.emptyNone')} action={<Button onClick={openCreate}>{t('members.add')}</Button>} />
      ) : filtered.length === 0 ? (
        <EmptyState title={t('members.empty')} />
      ) : (
        <>
          <p className={styles.count} aria-live="polite">{t('members.count', { n: filtered.length })}</p>
          <RowList label={t('members.title')}>
            {filtered.map((m, i) => (
              <Row
                key={m.id}
                index={i}
                to={`/admin/members/${m.id}`}
                title={m.full_name}
                accent={m.status === 'active' ? 'green' : 'gray'}
                muted={m.status !== 'active'}
                leading={<Avatar tone={m.status === 'active' ? 'navy' : 'gray'}>{initialOf(m.full_name)}</Avatar>}
                meta={
                  <>
                    <span className={styles.mono}>{m.username}</span>
                    {nameOf(m.team_id) && <Chip tone="info">{nameOf(m.team_id)}</Chip>}
                    {m.role_key && <Chip>{roleLabel(t, m.role_key)}</Chip>}
                  </>
                }
                trailing={<Chip tone={m.status === 'active' ? 'success' : 'neutral'}>{t(`members.status.${m.status}`)}</Chip>}
              />
            ))}
          </RowList>
        </>
      )}

      <Modal
        open={creating}
        title={t('members.create.title')}
        onClose={() => setCreating(false)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setCreating(false)}>{t('common.cancel')}</Button>
            <Button loading={provision.isPending} onClick={submit}>{t('members.create.submit')}</Button>
          </>
        }
      >
        <div className={styles.form}>
          <div className={styles.twoCol}>
            <ProfileFields draft={profile} onChange={setProfile} errors={submitted ? errors : {}} />
          </div>
          <TextField
            label={t('members.field.username')}
            value={username}
            onChange={(e) => setUsername(e.target.value.toLowerCase())}
            hint={t('members.field.usernameHint')}
            error={errors.username}
            autoCapitalize="none"
            spellCheck={false}
            dir="ltr"
            required
          />
          <TeamSelect value={teamId} onChange={setTeamId} error={errors.team} required={roleNeedsTeam(roleDraft.roleKey)} />
          <RoleFieldsInput value={roleDraft} onChange={setRoleDraft} errors={errors} />
          <InlineError error={provision.error} />
        </div>
      </Modal>

      <TemporaryPasswordDialog secret={secret} onDone={() => setSecret(null)} />
    </>
  )
}
