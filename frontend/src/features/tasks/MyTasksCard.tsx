import { useState } from 'react'
import { ChevronDown, ChevronLeft } from 'lucide-react'
import { useI18n } from '@/shared/i18n/i18n'
import type { MessageKey } from '@/shared/i18n/messages.en'
import { EmptyState } from '@/shared/ui/Feedback'
import { groupTasks, type TaskGroups } from './grouping'
import { TaskLine } from './TaskLine'
import type { Viewer } from './rules'
import type { Task } from './types'
import styles from './taskLists.module.css'

type Tab = 'upcoming' | 'overdue' | 'done'

const SECTIONS: Record<Tab, { key: keyof TaskGroups; title: MessageKey }[]> = {
  upcoming: [
    { key: 'week', title: 'taskGroups.week' },
    { key: 'later', title: 'taskGroups.later' },
    { key: 'noDue', title: 'taskGroups.noDue' },
  ],
  overdue: [{ key: 'overdue', title: 'taskGroups.overdue' }],
  done: [{ key: 'done', title: 'taskGroups.done' }],
}

const TAB_LABEL: Record<Tab, MessageKey> = { upcoming: 'myTasks.upcoming', overdue: 'myTasks.overdue', done: 'myTasks.done' }
const TAB_EMPTY: Record<Tab, MessageKey> = { upcoming: 'home.mine.empty', overdue: 'myTasks.noOverdue', done: 'myTasks.noDone' }

interface Props {
  tasks: Task[]
  viewer: Viewer
  unitName?: (id: string) => string
}

/** "My tasks" the way people expect it: Upcoming / Overdue / Completed tabs, collapsible sections, one compact row per task. */
export function MyTasksCard({ tasks, viewer, unitName }: Props) {
  const { t } = useI18n()
  const [now] = useState(() => new Date())
  const groups = groupTasks(tasks, now)
  const [tab, setTab] = useState<Tab>('upcoming')
  const [closed, setClosed] = useState<Record<string, boolean>>({})
  const counts: Record<Tab, number> = { upcoming: groups.week.length + groups.later.length + groups.noDue.length, overdue: groups.overdue.length, done: groups.done.length }
  const sections = SECTIONS[tab].filter((s) => groups[s.key].length > 0)

  return (
    <section className={styles.card} aria-label={t('home.mine')}>
      <h2 className={styles.cardTitle}><span className="eyebrow-num">01</span>{t('home.mine')}</h2>
      <div className={styles.tabs} role="tablist" aria-label={t('home.mine')}>
        {(Object.keys(SECTIONS) as Tab[]).map((id) => (
          <button key={id} type="button" role="tab" aria-selected={tab === id} className={`${styles.tabBtn} ${tab === id ? styles.tabOn : ''} ${id === 'overdue' && counts.overdue > 0 ? styles.tabLate : ''}`} onClick={() => setTab(id)}>
            {t(TAB_LABEL[id])}{counts[id] > 0 && <span className={styles.tabCount}>{counts[id]}</span>}
          </button>
        ))}
      </div>
      <div className={styles.cardScroll}>
      {sections.length === 0 ? (
        <EmptyState title={t(TAB_EMPTY[tab])} />
      ) : (
        sections.map((s) => {
          const list = groups[s.key]
          const open = !closed[s.key]
          const Chevron = open ? ChevronDown : ChevronLeft
          return (
            <div key={s.key} className={styles.section}>
              <button type="button" className={styles.sectionHead} aria-expanded={open} onClick={() => setClosed({ ...closed, [s.key]: open })}>
                <Chevron size={16} aria-hidden="true" /> {t(s.title)} <span className={styles.sectionCount}>{list.length}</span>
              </button>
              {open && <ul className={styles.rows}>{list.map((task) => <TaskLine key={task.id} task={task} viewer={viewer} unitName={unitName?.(task.scope_unit_id)} />)}</ul>}
            </div>
          )
        })
      )}
      </div>
    </section>
  )
}
