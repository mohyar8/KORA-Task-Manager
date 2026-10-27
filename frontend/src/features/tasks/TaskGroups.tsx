import { useState } from 'react'
import { useI18n } from '@/shared/i18n/i18n'
import type { MessageKey } from '@/shared/i18n/messages.en'
import { EmptyState } from '@/shared/ui/Feedback'
import { groupTasks, type TaskGroups as Groups } from './grouping'
import { TaskLine } from './TaskLine'
import type { Viewer } from './rules'
import type { Task } from './types'
import styles from './taskLists.module.css'

const SECTIONS: { key: keyof Groups; title: MessageKey; tone?: 'danger' }[] = [
  { key: 'overdue', title: 'taskGroups.overdue', tone: 'danger' },
  { key: 'week', title: 'taskGroups.week' },
  { key: 'later', title: 'taskGroups.later' },
  { key: 'noDue', title: 'taskGroups.noDue' },
  { key: 'done', title: 'taskGroups.done' },
]

interface Props {
  tasks: Task[]
  viewer: Viewer
  unitName?: (id: string) => string
  /** Completed tasks are listed (collapsed) only where the page asks for them. */
  showDone?: boolean
  empty: string
}

/** Tasks in the groups people scan for: late, this week, later, no date, done. */
export function TaskGroupList({ tasks, viewer, unitName, showDone, empty }: Props) {
  const { t } = useI18n()
  const [now] = useState(() => new Date())
  const [doneOpen, setDoneOpen] = useState(false)
  const groups = groupTasks(tasks, now)
  const sections = SECTIONS.filter((s) => (s.key !== 'done' || showDone) && groups[s.key].length > 0)
  if (sections.length === 0) return <EmptyState title={empty} />

  return (
    <div className={styles.groups}>
      {sections.map((s) => {
        const list = groups[s.key]
        const collapsed = s.key === 'done' && !doneOpen
        return (
          <section key={s.key} aria-label={t(s.title)}>
            <h3 className={`${styles.groupTitle} ${s.tone === 'danger' ? styles.danger : ''}`}>
              {s.key === 'done' ? (
                <button type="button" className={styles.toggle} aria-expanded={!collapsed} onClick={() => setDoneOpen((v) => !v)}>
                  {t(s.title)} ({list.length})
                </button>
              ) : (
                <>{t(s.title)} ({list.length})</>
              )}
            </h3>
            {!collapsed && (
              <ul className={styles.list}>
                {list.map((task) => (
                  <TaskLine key={task.id} task={task} viewer={viewer} unitName={unitName?.(task.scope_unit_id)} />
                ))}
              </ul>
            )}
          </section>
        )
      })}
    </div>
  )
}
