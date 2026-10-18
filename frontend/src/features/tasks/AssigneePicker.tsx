import { useState } from 'react'
import { useI18n } from '@/shared/i18n/i18n'
import { TextField } from '@/shared/ui/Field'
import { isTopRole, useAllMembers, useMemberNames } from '@/features/members/directory'
import { roleLabel } from '@/features/access/labels'
import { useSession } from '@/features/auth/session'
import { matchesSearch } from '@/shared/lib/search'
import styles from './tasks.module.css'

interface Props {
  selected: string[]
  onChange: (ids: string[]) => void
  error?: string
  legend?: string
  /** Show the "Other" section (anyone outside the scope); tasks only. */
  external?: string[]
  onExternalChange?: (ids: string[]) => void
  /** Keep the top roles in the regular list (calendar invitations; they are eligible there). */
  includeTopRoles?: boolean
}

/** Searchable checklist of the Members the caller may pick. Eligibility is validated by the server. */
export function AssigneePicker({ selected, onChange, error, legend, external, onExternalChange, includeTopRoles }: Props) {
  const { t } = useI18n()
  const names = useMemberNames()
  const [filter, setFilter] = useState('')
  const shown = names.members.filter((m) => (includeTopRoles || !isTopRole(m.role_key)) && matchesSearch(filter, m.full_name))
  const { account } = useSession()
  const [otherOpen, setOtherOpen] = useState(false)
  const [otherFilter, setOtherFilter] = useState('')
  const all = useAllMembers(!!onExternalChange && otherOpen)
  const others = (all.data ?? []).filter(
    (m) => m.id !== account?.member_id && !selected.includes(m.id) && matchesSearch(otherFilter, m.full_name),
  )
  const toggleOther = (id: string) =>
    onExternalChange?.((external ?? []).includes(id) ? (external ?? []).filter((x) => x !== id) : [...(external ?? []), id])
  const toggle = (id: string) => onChange(selected.includes(id) ? selected.filter((x) => x !== id) : [...selected, id])

  const allShown = shown.length > 0 && shown.every((m) => selected.includes(m.id))
  const toggleAll = () => {
    const ids = shown.map((m) => m.id)
    onChange(allShown ? selected.filter((x) => !ids.includes(x)) : [...new Set([...selected, ...ids])])
  }

  return (
    <fieldset className={styles.assigneeBox}>
      <legend>{legend ?? t('tasks.field.assignees')} *</legend>
      <p className={styles.hint}>{t('tasks.assignees.hint')}</p>
      <TextField label={t('members.search')} type="search" value={filter} onChange={(e) => setFilter(e.target.value)} />
      {shown.length > 1 && (
        <button type="button" className={styles.pickAll} onClick={toggleAll}>
          {allShown ? t('tasks.assignees.clear') : t('tasks.assignees.all')}
        </button>
      )}
      {shown.length === 0 ? (
        <p className={styles.hint}>{t('tasks.noMembers')}</p>
      ) : (
        <ul className={styles.pickList}>
          {shown.map((m) => (
            <li key={m.id}>
              <label className={styles.pick}>
                <input type="checkbox" checked={selected.includes(m.id)} onChange={() => toggle(m.id)} /> {m.full_name}
              </label>
            </li>
          ))}
        </ul>
      )}
      {onExternalChange && (
        <div className={styles.otherBox}>
          <button type="button" className={styles.pickAll} aria-expanded={otherOpen} onClick={() => setOtherOpen((v) => !v)}>
            {t('tasks.assignees.other')}
          </button>
          {otherOpen && (
            <>
              <p className={styles.hint}>{t('tasks.assignees.otherHint')}</p>
              <TextField label={t('members.search')} type="search" value={otherFilter} onChange={(e) => setOtherFilter(e.target.value)} />
              <ul className={styles.pickList}>
                {[...(all.data ?? []).filter((m) => (external ?? []).includes(m.id)), ...others].map((m) => (
                  <li key={m.id}>
                    <label className={`${styles.pick} ${isTopRole(m.role_key) ? styles.pickTop : ''}`}>
                      <input type="checkbox" checked={(external ?? []).includes(m.id)} onChange={() => toggleOther(m.id)} /> {m.full_name}
                      {isTopRole(m.role_key) && m.role_key && <span className={styles.topBadge}>{roleLabel(t, m.role_key)}</span>}
                    </label>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}
      {error && <p className={styles.fieldError} role="alert">{error}</p>}
    </fieldset>
  )
}
