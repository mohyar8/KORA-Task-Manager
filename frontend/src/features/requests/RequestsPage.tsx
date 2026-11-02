import { useState, type FormEvent } from 'react'
import { Link } from 'react-router'
import { Check, Inbox, Plus, Send, Undo2, X } from 'lucide-react'
import { useI18n } from '@/shared/i18n/i18n'
import { formatDate } from '@/shared/lib/format'
import { Button } from '@/shared/ui/Button'
import { EmptyState, ErrorState, InlineError, Skeleton } from '@/shared/ui/Feedback'
import { PageHeader } from '@/shared/ui/Layout'
import { useRequestsData, type NewRequest, type RequestPriority, type RequestStatus } from './useRequestsData'
import styles from './requests.module.css'

/** Ask another administration for work, and answer the requests that reach yours. */
export function RequestsPage() {
  const { t, locale } = useI18n()
  const data = useRequestsData()
  const [tab, setTab] = useState<'in' | 'out'>('in')
  const [composing, setComposing] = useState(false)
  const [answering, setAnswering] = useState<string | null>(null)
  const [failure, setFailure] = useState<unknown>(null)

  const list = tab === 'in' ? data.incoming : data.outgoing
  const pendingIn = data.incoming.filter((r) => r.status === 'pending').length
  // Run an action; a rejected one (e.g. someone answered first) is shown instead of silently ignored.
  const run = (action: () => Promise<void>, done?: () => void) => {
    setFailure(null)
    action().then(done, (error: unknown) => setFailure(error))
  }

  if (data.isLoading) return <div className={styles.page}><Skeleton lines={5} /></div>
  if (data.error) return <div className={styles.page}><ErrorState error={data.error} /></div>

  return (
    <div className={styles.page}>
      <PageHeader title={t('requests.title')} description={t('requests.description')} actions={data.canSend ? <Button onClick={() => setComposing(true)}><Plus size={18} aria-hidden="true" /> {t('requests.new')}</Button> : undefined} />
      <div className={styles.tabs} role="tablist">
        <button type="button" role="tab" aria-selected={tab === 'in'} className={tab === 'in' ? styles.on : ''} onClick={() => setTab('in')}><Inbox size={16} aria-hidden="true" /> {t('requests.incoming')}{pendingIn > 0 && <span className={styles.count}>{pendingIn}</span>}</button>
        <button type="button" role="tab" aria-selected={tab === 'out'} className={tab === 'out' ? styles.on : ''} onClick={() => setTab('out')}><Send size={16} aria-hidden="true" /> {t('requests.outgoing')}</button>
      </div>
      {failure != null && <InlineError error={failure} />}

      <div className={styles.scroll}>
        {list.length === 0 && <EmptyState title={t(tab === 'in' ? 'requests.emptyIn' : 'requests.emptyOut')} />}
        <ul className={styles.list}>
          {list.map((r) => (
            <li key={r.id} className={styles.card}>
              <header>
                <h2>{r.title}</h2>
                <StatusChip status={r.status} />
              </header>
              {r.description && <p className={styles.body}>{r.description}</p>}
              <dl className={styles.facts}>
                <div><dt>{t('requests.from')}</dt><dd>{r.fromName} · {r.fromUnit}</dd></div>
                <div><dt>{t('requests.to')}</dt><dd>{r.toUnit}</dd></div>
                <div><dt>{t('requests.priority')}</dt><dd>{t(`requests.priority.${r.priority}` as 'requests.priority.high')}</dd></div>
                {r.dueDate && <div><dt>{t('requests.due')}</dt><dd>{formatDate(r.dueDate, locale)}</dd></div>}
                {r.status === 'accepted' && r.assignees.length > 0 && <div><dt>{t('requests.assignedTo')}</dt><dd>{r.assignees.join('، ')}</dd></div>}
                {r.status === 'rejected' && r.reason && <div><dt>{t('requests.reason')}</dt><dd>{r.reason}</dd></div>}
              </dl>
              {r.status === 'accepted' && r.taskId && <Link to={`/tasks/${r.taskId}`}>{t('requests.viewTask')}</Link>}
              {tab === 'out' && r.status === 'pending' && r.mine && data.actions.withdraw && (
                <Button variant="ghost" onClick={() => run(() => data.actions.withdraw!(r.id))}><Undo2 size={16} aria-hidden="true" /> {t('requests.withdraw')}</Button>
              )}
              {tab === 'in' && r.status === 'pending' && (answering === r.id
                ? <Answer staff={data.staffFor(r.toUnitId)} onAccept={(ids) => run(() => data.actions.accept(r.id, ids), () => setAnswering(null))} onReject={(reason) => run(() => data.actions.reject(r.id, reason), () => setAnswering(null))} onCancel={() => setAnswering(null)} />
                : <Button onClick={() => setAnswering(r.id)}>{t('requests.answer')}</Button>)}
            </li>
          ))}
        </ul>
      </div>

      {composing && <Compose targets={data.targets} onSend={(r) => run(() => data.actions.create(r), () => { setComposing(false); setTab('out') })} onClose={() => setComposing(false)} />}
    </div>
  )
}

function StatusChip({ status }: { status: RequestStatus }) {
  const { t } = useI18n()
  return <span className={`${styles.status} ${styles[status]}`}>{t(`requests.status.${status}` as 'requests.status.pending')}</span>
}

function Answer({ staff, onAccept, onReject, onCancel }: { staff: { id: string; name: string }[]; onAccept: (ids: string[]) => void; onReject: (reason: string) => void; onCancel: () => void }) {
  const { t } = useI18n()
  const [ids, setIds] = useState<string[]>([])
  const [reason, setReason] = useState('')
  return (
    <div className={styles.answer}>
      <fieldset>
        <legend>{t('requests.pickPeople')}</legend>
        {staff.map((m) => (
          <label key={m.id}><input type="checkbox" checked={ids.includes(m.id)} onChange={(e) => setIds(e.target.checked ? [...ids, m.id] : ids.filter((x) => x !== m.id))} /> {m.name}</label>
        ))}
      </fieldset>
      <input className={styles.reasonInput} value={reason} placeholder={t('requests.reasonPlaceholder')} aria-label={t('requests.reason')} onChange={(e) => setReason(e.target.value)} />
      <div className={styles.answerRow}>
        <Button disabled={ids.length === 0} onClick={() => onAccept(ids)}><Check size={16} aria-hidden="true" /> {t('requests.accept')}</Button>
        <Button variant="danger" onClick={() => onReject(reason.trim())}><X size={16} aria-hidden="true" /> {t('requests.reject')}</Button>
        <Button variant="ghost" onClick={onCancel}>{t('common.cancel')}</Button>
      </div>
    </div>
  )
}

function Compose({ targets, onSend, onClose }: { targets: { id: string; name: string }[]; onSend: (r: NewRequest) => void; onClose: () => void }) {
  const { t } = useI18n()
  const [form, setForm] = useState({ title: '', description: '', dueDate: '', priority: 'normal' as RequestPriority, toUnitId: targets[0]?.id ?? '' })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (!form.title.trim() || !form.toUnitId) return
    onSend({ ...form, title: form.title.trim(), description: form.description.trim() })
  }
  return (
    <div className={styles.overlay} role="dialog" aria-modal="true" aria-label={t('requests.new')}>
      <form className={styles.compose} onSubmit={submit}>
        <h2>{t('requests.new')}</h2>
        <label>{t('requests.to')}<select value={form.toUnitId} onChange={(e) => setForm({ ...form, toUnitId: e.target.value })}>{targets.map((n) => <option key={n.id} value={n.id}>{n.name}</option>)}</select></label>
        <label>{t('requests.titleField')}<input value={form.title} maxLength={300} onChange={(e) => setForm({ ...form, title: e.target.value })} /></label>
        <label>{t('requests.details')}<textarea rows={4} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></label>
        <div className={styles.two}>
          <label>{t('requests.due')}<input type="date" dir="ltr" value={form.dueDate} onChange={(e) => setForm({ ...form, dueDate: e.target.value })} /></label>
          <label>{t('requests.priority')}<select value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value as RequestPriority })}>
            {(['normal', 'high', 'urgent'] as const).map((p) => <option key={p} value={p}>{t(`requests.priority.${p}` as 'requests.priority.high')}</option>)}
          </select></label>
        </div>
        <div className={styles.answerRow}>
          <Button type="submit" disabled={!form.title.trim()}>{t('requests.send')}</Button>
          <Button type="button" variant="ghost" onClick={onClose}>{t('common.cancel')}</Button>
        </div>
      </form>
    </div>
  )
}
