import { useState } from 'react'
import { useI18n } from '@/shared/i18n/i18n'
import { TextField } from '@/shared/ui/Field'
import { useMemberNames } from '@/features/members/directory'
import { matchesSearch } from '@/shared/lib/search'
import styles from './tasks.module.css'

interface Props {
  selected: string[]
  onChange: (ids: string[]) => void
  error?: string
  legend?: string
}

/** Searchable checklist of the Members the caller may pick. Eligibility is validated by the server. */
export function AssigneePicker({ selected, onChange, error, legend }: Props) {
  const { t } = useI18n()
  const names = useMemberNames()
  const [filter, setFilter] = useState('')
  const shown = names.members.filter((m) => matchesSearch(filter, m.full_name))
  const toggle = (id: string) => onChange(selected.includes(id) ? selected.filter((x) => x !== id) : [...selected, id])

  return (
    <fieldset className={styles.assigneeBox}>
      <legend>{legend ?? t('tasks.field.assignees')} *</legend>
      <p className={styles.hint}>{t('tasks.assignees.hint')}</p>
      <TextField label={t('members.search')} type="search" value={filter} onChange={(e) => setFilter(e.target.value)} />
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
      {error && <p className={styles.fieldError} role="alert">{error}</p>}
    </fieldset>
  )
}
