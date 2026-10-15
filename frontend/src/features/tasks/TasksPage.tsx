import { useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { LayoutGrid, List, Plus } from 'lucide-react'
import { useI18n } from '@/shared/i18n/i18n'
import { Button } from '@/shared/ui/Button'
import { Chip, EmptyState, ErrorState, Skeleton, useToast } from '@/shared/ui/Feedback'
import { SelectField, TextField } from '@/shared/ui/Field'
import { PageHeader } from '@/shared/ui/Layout'
import { Avatar, Row, RowList } from '@/shared/ui/RowList'
import { allUnits, allowedUnits } from '@/features/auth/permissions'
import { useSession } from '@/features/auth/session'
import { useMemberNames } from '@/features/members/directory'
import { useCreateTask, useTasks } from './api'
import { SeriesFormModal } from './SeriesForm'
import { useCreateSeries } from './seriesApi'
import { DueText, StatusChip, StatusIcon } from './TaskBits'
import { useViewer } from './useViewer'
import { useMediaQuery } from '@/shared/lib/useMediaQuery'
import { TaskBoard } from './TaskBoard'
import { TaskFormModal } from './TaskForm'
import { isAssignee, isCreator, statusAccent } from './rules'
import { TASK_STATUSES } from './types'
import styles from './tasks.module.css'

/** /tasks — filters live in the URL (?status=&scope=&mine=1&q=) so a filtered view can be linked. */
export function TasksPage() {
  const { t } = useI18n()
  const toast = useToast()
  const { access } = useSession()
  const viewer = useViewer()
  const names = useMemberNames()
  const [params, setParams] = useSearchParams()
  const status = params.get('status') ?? ''
  const scope = params.get('scope') ?? ''
  const mine = params.get('mine') === '1'
  const q = params.get('q') ?? ''
  // Tablets and desktops open the board; phones open the list. An explicit ?view= always wins.
  const wide = useMediaQuery('(min-width: 768px)')
  const asked = params.get('view')
  const view = asked === 'board' || asked === 'list' ? asked : wide ? 'board' : 'list'

  const tasks = useTasks({ status: status || undefined, scope_unit_id: scope || undefined })
  const create = useCreateTask()
  const createSeries = useCreateSeries()
  const [creating, setCreating] = useState(false)
  const [creatingSeries, setCreatingSeries] = useState(false)

  const units = allUnits(access)
  const unitName = (id: string) => units.find((u) => u.unit_id === id)?.name ?? id
  const creatable = allowedUnits(access, 'task.create').map((u) => ({ id: u.unit_id, name: u.name }))
  const canCreate = !!viewer.memberId && creatable.length > 0

  const set = (key: string, value: string) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    setParams(next, { replace: true })
  }

  const rows = (tasks.data ?? []).filter(
    (task) =>
      (!mine || isCreator(task, viewer) || isAssignee(task, viewer)) &&
      (!q.trim() || task.title.toLowerCase().includes(q.trim().toLowerCase())),
  )

  const names2 = (ids: string[]) => (ids.length ? ids.map((id) => names.nameOf(id)).join('، ') : '—')

  return (
    <>
      <PageHeader
        title={t('tasks.title')}
        description={t('tasks.description')}
        actions={
          canCreate && (
            <>
              <Button variant="secondary" onClick={() => { createSeries.reset(); setCreatingSeries(true) }}>{t('series.new')}</Button>
              <Button onClick={() => { create.reset(); setCreating(true) }}>
                <Plus size={18} aria-hidden="true" /> {t('tasks.new')}
              </Button>
            </>
          )
        }
      />
      {!viewer.memberId && <p className={styles.note}>{t('tasks.noMemberNote')}</p>}

      <div className={styles.filters}>
        <TextField label={t('tasks.filter.search')} type="search" value={q} onChange={(e) => set('q', e.target.value)} />
        <SelectField label={t('tasks.filter.status')} value={status} onChange={(e) => set('status', e.target.value)}>
          <option value="">{t('tasks.all')}</option>
          {TASK_STATUSES.map((s) => <option key={s} value={s}>{t(`task.status.${s}`)}</option>)}
        </SelectField>
        <SelectField label={t('tasks.filter.scope')} value={scope} onChange={(e) => set('scope', e.target.value)}>
          <option value="">{t('tasks.all')}</option>
          {units.map((u) => <option key={u.unit_id} value={u.unit_id}>{u.name}</option>)}
        </SelectField>
      </div>
      {viewer.memberId && (
        <label className={styles.check}>
          <input type="checkbox" checked={mine} onChange={(e) => set('mine', e.target.checked ? '1' : '')} /> {t('tasks.filter.mine')}
        </label>
      )}

      <div className={styles.viewSwitch} role="group" aria-label={t('tasks.view.label')}>
        <button type="button" className={view === 'list' ? styles.viewOn : undefined} aria-pressed={view === 'list'} onClick={() => set('view', 'list')}><List size={16} aria-hidden="true" /> {t('tasks.view.list')}</button>
        <button type="button" className={view === 'board' ? styles.viewOn : undefined} aria-pressed={view === 'board'} onClick={() => set('view', 'board')}><LayoutGrid size={16} aria-hidden="true" /> {t('tasks.view.board')}</button>
      </div>

      {tasks.isPending && <Skeleton lines={6} />}
      {tasks.isError && <ErrorState error={tasks.error} onRetry={() => void tasks.refetch()} />}
      {tasks.data && tasks.data.length === 0 && <EmptyState title={t('tasks.emptyNone')} />}
      {tasks.data && tasks.data.length > 0 && rows.length === 0 && <EmptyState title={t('tasks.empty')} />}
      {rows.length > 0 && view === 'board' && <TaskBoard tasks={rows} viewer={viewer} />}
      {rows.length > 0 && view === 'list' && (
        <RowList label={t('tasks.title')}>
          {rows.map((task, i) => (
            <Row
              key={task.id}
              index={i}
              to={`/tasks/${task.id}`}
              title={task.title}
              accent={statusAccent[task.status]}
              muted={task.status === 'cancelled'}
              leading={<Avatar tone={statusAccent[task.status]}><StatusIcon status={task.status} /></Avatar>}
              meta={
                <>
                  {task.series_id && <Link to={`/task-series/${task.series_id}`}><Chip>{t('tasks.series')}</Chip></Link>}
                  {task.priority && <Chip tone={task.priority === 'urgent' ? 'danger' : task.priority === 'high' ? 'warning' : 'neutral'}>{t(`task.priority.${task.priority}`)}</Chip>}
                  <span><DueText task={task} /></span>
                  <span>{unitName(task.scope_unit_id)}</span>
                  <span>{names2(task.assignee_member_ids)}</span>
                </>
              }
              trailing={<StatusChip status={task.status} />}
            />
          ))}
        </RowList>
      )}

      {creatingSeries && (
        <SeriesFormModal
          title={t('series.create.title')}
          submitLabel={t('series.create.submit')}
          scopeOptions={creatable}
          loading={createSeries.isPending}
          error={createSeries.error}
          onClose={() => setCreatingSeries(false)}
          onSubmit={(v) => createSeries.mutate(v, { onSuccess: () => { setCreatingSeries(false); toast(t('series.created')) } })}
        />
      )}

      {creating && (
        <TaskFormModal
          title={t('tasks.create.title')}
          submitLabel={t('tasks.create.submit')}
          scopeOptions={creatable}
          withAssignees
          loading={create.isPending}
          error={create.error}
          onClose={() => setCreating(false)}
          onSubmit={(v) =>
            create.mutate(
              { title: v.title, description: v.description, priority: v.priority, due_at: v.due_at, scope_unit_id: v.scope_unit_id, assignee_member_ids: v.assignee_member_ids },
              { onSuccess: () => { setCreating(false); toast(t('tasks.created')) } },
            )
          }
        />
      )}
    </>
  )
}
