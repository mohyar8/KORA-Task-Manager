import { useState } from 'react'
import { Crown, Minus, Pencil, Plus } from 'lucide-react'
import { useI18n } from '@/shared/i18n/i18n'
import { Button } from '@/shared/ui/Button'
import { EmptyState, ErrorState, InlineError, Skeleton, useToast } from '@/shared/ui/Feedback'
import { TextField } from '@/shared/ui/Field'
import { BallMark } from '@/shared/brand/BallMark'
import { canAnywhere } from '@/features/auth/permissions'
import { useSession } from '@/features/auth/session'
import { formatDateTime } from '@/shared/lib/format'
import { useCountUp } from '@/shared/lib/useCountUp'
import { useLeague, useUpdateLeague, type League, type Standing } from './api'
import styles from './league.module.css'

function Points({ value }: { value: number }) {
  const shown = useCountUp(value, 900)
  return <span className={styles.points}>{shown}</span>
}

/** /league — the teams' table for the whole event. Everyone reads it; the PMO Leader edits it. */
export function LeaguePage() {
  const { t, locale } = useI18n()
  const toast = useToast()
  const { access } = useSession()
  const query = useLeague()
  const update = useUpdateLeague()
  const [editing, setEditing] = useState(false)
  const [title, setTitle] = useState('')
  const [draft, setDraft] = useState<Record<string, number>>({})
  const canEdit = canAnywhere(access, 'league.manage')

  if (query.isPending) return <Skeleton lines={8} />
  if (query.isError) return <ErrorState error={query.error} onRetry={() => void query.refetch()} />
  const league: League = query.data
  const max = Math.max(1, ...league.standings.map((s) => s.points))

  const startEdit = () => {
    update.reset()
    setTitle(league.round_title ?? '')
    setDraft(Object.fromEntries(league.standings.map((s) => [s.team_id, s.points])))
    setEditing(true)
  }
  const setPoints = (id: string, value: number) => setDraft((d) => ({ ...d, [id]: Math.min(9999, Math.max(0, Number.isFinite(value) ? Math.trunc(value) : 0)) }))
  const save = () =>
    update.mutate(
      { round_title: title.trim() || null, points: Object.entries(draft).map(([team_id, points]) => ({ team_id, points })) },
      { onSuccess: () => { setEditing(false); toast(t('league.saved')) } },
    )

  const rowsFor = (list: Standing[]) =>
    list.map((s) => (
      <li key={s.team_id} className={`${styles.row} ${s.rank === 1 ? styles.first : ''}`} style={{ ['--i' as string]: s.rank }}>
        <span className={styles.rank}>{s.rank === 1 && s.points > 0 ? <Crown size={18} aria-label={t('league.leader')} /> : s.rank}</span>
        <span className={styles.team}>
          <span className={styles.teamName}>{s.team_name}</span>
          {s.administration_name && <span className={styles.admin}>{s.administration_name}</span>}
          <span className={styles.bar} aria-hidden="true"><i style={{ inlineSize: `${(s.points / max) * 100}%` }} /></span>
        </span>
        {editing ? (
          <span className={styles.stepper}>
            <button type="button" className={styles.step} aria-label={t('league.minus', { team: s.team_name })} onClick={() => setPoints(s.team_id, (draft[s.team_id] ?? 0) - 1)}><Minus size={16} aria-hidden="true" /></button>
            <input
              className={styles.input}
              type="number"
              inputMode="numeric"
              min={0}
              max={9999}
              aria-label={t('league.pointsOf', { team: s.team_name })}
              value={draft[s.team_id] ?? 0}
              onChange={(e) => setPoints(s.team_id, Number(e.target.value))}
            />
            <button type="button" className={styles.step} aria-label={t('league.plus', { team: s.team_name })} onClick={() => setPoints(s.team_id, (draft[s.team_id] ?? 0) + 1)}><Plus size={16} aria-hidden="true" /></button>
          </span>
        ) : (
          <Points value={s.points} />
        )}
      </li>
    ))

  const list = editing
    ? [...league.standings].sort((a, b) => (draft[b.team_id] ?? 0) - (draft[a.team_id] ?? 0) || a.team_name.localeCompare(b.team_name)).map((s, i) => ({ ...s, rank: i + 1 }))
    : league.standings

  return (
    <div className={styles.page}>
      <h1 className="visually-hidden">{t('league.title')}</h1>
      <section className={styles.hero}>
        <BallMark className={styles.ball} />
        <div className={styles.ribbon}>{t('league.title')}</div>
        <div className={styles.tagline}>{t('league.tagline')}</div>
        {(league.round_title || editing) && (
          <div className={styles.round}>{editing ? (title || t('league.roundPlaceholder')) : league.round_title}</div>
        )}
      </section>

      {canEdit && (
        <div className={styles.tools}>
          {editing ? (
            <>
              <TextField label={t('league.roundTitle')} value={title} maxLength={100} onChange={(e) => setTitle(e.target.value)} />
              <div className={styles.toolButtons}>
                <Button variant="ghost" onClick={() => setEditing(false)}>{t('common.cancel')}</Button>
                <Button loading={update.isPending} onClick={save}>{t('common.save')}</Button>
              </div>
              <InlineError error={update.error} />
            </>
          ) : (
            <Button variant="secondary" onClick={startEdit}><Pencil size={16} aria-hidden="true" /> {t('league.edit')}</Button>
          )}
        </div>
      )}

      {list.length === 0 ? (
        <EmptyState title={t('league.empty')} />
      ) : (
        <ol className={styles.table} aria-label={t('league.title')}>{rowsFor(list)}</ol>
      )}
      {league.updated_at && <p className={styles.updated}>{t('league.updated', { at: formatDateTime(league.updated_at, locale) })}</p>}
      <p className={styles.footer}>{t('league.footer')}</p>
    </div>
  )
}
