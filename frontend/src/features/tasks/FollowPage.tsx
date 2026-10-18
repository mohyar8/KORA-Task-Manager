import { useMemo, useState } from 'react'
import { Link } from 'react-router'
import { useI18n } from '@/shared/i18n/i18n'
import { Chip, EmptyState, ErrorState, Skeleton } from '@/shared/ui/Feedback'
import { SelectField } from '@/shared/ui/Field'
import { PageHeader } from '@/shared/ui/Layout'
import { matchesSearch } from '@/shared/lib/search'
import { TextField } from '@/shared/ui/Field'
import { useFollowTasks, type FollowTask } from './api'
import { DueText, StatusChip } from './TaskBits'
import { TASK_STATUSES } from './types'
import styles from './tasks.module.css'

/** /follow — the PMO's follow-up: one section per team, kept apart from the PMO's own tasks. */
export function FollowPage() {
  const { t } = useI18n()
  const [status, setStatus] = useState('')
  const [admin, setAdmin] = useState('')
  const [q, setQ] = useState('')
  const query = useFollowTasks(status || undefined)

  const all = useMemo(() => query.data ?? [], [query.data])
  const administrations = useMemo(() => {
    const seen = new Map<string, string>()
    for (const x of all) if (x.administration_id && x.administration_name) seen.set(x.administration_id, x.administration_name)
    return [...seen.entries()].sort((a, b) => a[1].localeCompare(b[1]))
  }, [all])

  const sections = useMemo(() => {
    const filtered = all.filter((x) => (!admin || x.administration_id === admin) && matchesSearch(q, x.title, x.unit_name, ...x.assignee_names))
    const map = new Map<string, { name: string; admin: string | null; tasks: FollowTask[] }>()
    for (const x of filtered) {
      const entry = map.get(x.scope_unit_id) ?? { name: x.unit_name, admin: x.administration_name, tasks: [] }
      entry.tasks.push(x)
      map.set(x.scope_unit_id, entry)
    }
    return [...map.entries()].sort((a, b) => (a[1].admin ?? '').localeCompare(b[1].admin ?? '') || a[1].name.localeCompare(b[1].name))
  }, [all, admin, q])

  return (
    <>
      <PageHeader title={t('follow.title')} description={t('follow.description')} />
      <div className={styles.followFilters}>
        <TextField label={t('members.search')} type="search" value={q} onChange={(e) => setQ(e.target.value)} />
        <SelectField label={t('cal.filter.administration')} value={admin} onChange={(e) => setAdmin(e.target.value)}>
          <option value="">{t('cal.filter.allAdministrations')}</option>
          {administrations.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
        </SelectField>
        <SelectField label={t('cal.filter.status')} value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">{t('cal.filter.allStatuses')}</option>
          {TASK_STATUSES.map((s) => <option key={s} value={s}>{t(`task.status.${s}`)}</option>)}
        </SelectField>
      </div>

      {query.isPending && <Skeleton lines={6} />}
      {query.isError && <ErrorState error={query.error} onRetry={() => void query.refetch()} />}
      {query.data && sections.length === 0 && <EmptyState title={t('follow.empty')} />}
      {sections.map(([unitId, section]) => {
        const done = section.tasks.filter((x) => x.status === 'completed').length
        return (
          <section key={unitId} className={styles.followSection} aria-label={section.name}>
            <header className={styles.followHead}>
              <h2 className={styles.followTitle}>{section.name}</h2>
              {section.admin && <span className={styles.hint}>{section.admin}</span>}
              <Chip tone="info">{t('follow.count', { done, total: section.tasks.length })}</Chip>
            </header>
            <ul className={styles.followList}>
              {section.tasks.map((x) => (
                <li key={x.id} className={styles.followRow}>
                  <Link to={`/tasks/${x.id}`} className={styles.followLink}>{x.title}</Link>
                  <StatusChip status={x.status} />
                  {x.from_outside && <Chip tone="info">{t('tasks.fromOutside')}</Chip>}
                  <DueText task={x} />
                  <span className={styles.hint}>{x.assignee_names.join('، ')}</span>
                </li>
              ))}
            </ul>
          </section>
        )
      })}
    </>
  )
}
