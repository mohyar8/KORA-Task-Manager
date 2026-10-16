// Contract §8.2 (System Admin only).
import type { RoleKey } from '@/features/access/types'
import type { MessageKey } from '@/shared/i18n/messages.en'

export type MemberStatus = 'active' | 'deactivated'

export interface MemberProfile {
  full_name: string
  university_id: string | null
  phone: string | null
  email: string | null
  major: string | null
  academic_year: string | null
}

export interface Member extends MemberProfile {
  id: string
  account_id: string
  username: string
  status: MemberStatus
  /** null when deactivated */
  team_id: string | null
  role_key: RoleKey | null
  role_unit_id: string | null
}

export interface RoleFields {
  role_key: RoleKey
  /** Required for `administration_manager` only; rejected for every other role. */
  administration_id: string | null
}

/** Profile text inputs, kept as strings in forms. */
export type ProfileDraft = { [K in keyof MemberProfile]: string }

export const emptyProfileDraft: ProfileDraft = { full_name: '', university_id: '', phone: '', email: '', major: '', academic_year: '' }

export const profileToDraft = (p: MemberProfile): ProfileDraft => ({
  full_name: p.full_name,
  university_id: p.university_id ?? '',
  phone: p.phone ?? '',
  email: p.email ?? '',
  major: p.major ?? '',
  academic_year: p.academic_year ?? '',
})

/** Blank → null, because the API stores blank, null and omitted identically. */
export const draftToProfile = (d: ProfileDraft): MemberProfile => {
  const opt = (v: string) => (v.trim() === '' ? null : v.trim())
  return {
    full_name: d.full_name.trim(),
    university_id: opt(d.university_id),
    phone: opt(d.phone),
    email: opt(d.email),
    major: opt(d.major),
    academic_year: opt(d.academic_year),
  }
}

/** Mirrors the contract's email rule: a single @, no whitespace, a dot in the domain. */
export const isValidEmail = (v: string) => /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(v.trim())

export const USERNAME_PATTERN = /^[a-z0-9._-]{3,64}$/

/** Team Leader and Member are held at a Team; the other roles (leadership, PMO, Administration Manager) need none. */
export const roleNeedsTeam = (roleKey: RoleKey) => roleKey === 'team_leader' || roleKey === 'member'

/** `administration_id` is required for administration_manager and forbidden for every other role. */
export function roleFieldsFor(roleKey: RoleKey, administrationId: string): RoleFields {
  return { role_key: roleKey, administration_id: roleKey === 'administration_manager' ? administrationId : null }
}

export interface RoleDraft {
  roleKey: RoleKey
  administrationId: string
}
export const blankRoleDraft: RoleDraft = { roleKey: 'member', administrationId: '' }

/** Pure profile validation shared by create and edit: field → message (empty object = valid). */
export function validateProfile(d: ProfileDraft, t: (key: MessageKey) => string): Partial<Record<string, string>> {
  const errors: Partial<Record<string, string>> = {}
  if (!d.full_name.trim()) errors.full_name = t('members.nameRequired')
  if (d.email.trim() && !isValidEmail(d.email)) errors.email = t('members.emailInvalid')
  return errors
}
