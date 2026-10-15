import { useI18n } from '@/shared/i18n/i18n'
import { SelectField, TextField } from '@/shared/ui/Field'
import { roleLabel } from '@/features/access/labels'
import { ROLE_KEYS, type RoleKey } from '@/features/access/types'
import { useUnitDirectory } from '@/features/organization/directory'
import type { ProfileDraft, RoleDraft } from './types'

type Errors = Partial<Record<string, string>>

export function ProfileFields({ draft, onChange, errors }: { draft: ProfileDraft; onChange: (next: ProfileDraft) => void; errors: Errors }) {
  const { t } = useI18n()
  const set = (key: keyof ProfileDraft) => (e: { target: { value: string } }) => onChange({ ...draft, [key]: e.target.value })
  return (
    <>
      <TextField label={t('members.field.fullName')} value={draft.full_name} onChange={set('full_name')} maxLength={200} error={errors.full_name} required />
      <TextField label={t('members.field.universityId')} value={draft.university_id} onChange={set('university_id')} maxLength={64} error={errors.university_id} dir="ltr" />
      <TextField label={t('members.field.phone')} value={draft.phone} onChange={set('phone')} maxLength={32} error={errors.phone} type="tel" dir="ltr" />
      <TextField label={t('members.field.email')} value={draft.email} onChange={set('email')} maxLength={254} error={errors.email} type="email" dir="ltr" />
      <TextField label={t('members.field.major')} value={draft.major} onChange={set('major')} maxLength={200} error={errors.major} />
      <TextField label={t('members.field.academicYear')} value={draft.academic_year} onChange={set('academic_year')} maxLength={32} error={errors.academic_year} />
    </>
  )
}

/** Role select, plus the Administration select that appears only for Administration Managers. */
export function RoleFieldsInput({ value, onChange, errors }: { value: RoleDraft; onChange: (next: RoleDraft) => void; errors?: Errors }) {
  const { t } = useI18n()
  const { administrations } = useUnitDirectory()
  return (
    <>
      <SelectField
        label={t('members.field.role')}
        value={value.roleKey}
        onChange={(e) => onChange({ roleKey: e.target.value as RoleKey, administrationId: '' })}
        hint={t('members.placement.roleNote')}
      >
        {ROLE_KEYS.map((r) => <option key={r} value={r}>{roleLabel(t, r)}</option>)}
      </SelectField>
      {value.roleKey === 'administration_manager' && (
        <SelectField
          label={t('members.field.administration')}
          value={value.administrationId}
          onChange={(e) => onChange({ ...value, administrationId: e.target.value })}
          hint={t('members.field.administrationHint')}
          error={errors?.administration}
          required
        >
          <option value="">{t('members.pickAdministration')}</option>
          {administrations.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
        </SelectField>
      )}
    </>
  )
}

export function TeamSelect({ value, onChange, error }: { value: string; onChange: (id: string) => void; error?: string }) {
  const { t } = useI18n()
  const { teams, nameOf, byId } = useUnitDirectory()
  return (
    <SelectField label={t('members.field.team')} value={value} onChange={(e) => onChange(e.target.value)} error={error} required>
      <option value="">{t('members.pickTeam')}</option>
      {teams.map((u) => {
        const parent = nameOf(byId.get(u.id)?.parentId)
        return <option key={u.id} value={u.id}>{parent ? `${u.name} — ${parent}` : u.name}</option>
      })}
    </SelectField>
  )
}
