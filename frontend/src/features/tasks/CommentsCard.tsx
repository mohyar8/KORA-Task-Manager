import { useState } from 'react'
import { useI18n } from '@/shared/i18n/i18n'
import { formatDateTime } from '@/shared/lib/format'
import { Button } from '@/shared/ui/Button'
import { ErrorState, InlineError, Skeleton, useToast } from '@/shared/ui/Feedback'
import { TextAreaField } from '@/shared/ui/Field'
import { Card } from '@/shared/ui/Layout'
import { ConfirmDialog } from '@/shared/ui/Modal'
import { useAddComment, useComments, useDeleteComment, useEditComment } from './api'
import { canComment, type Viewer } from './rules'
import type { Task, TaskComment } from './types'
import styles from './tasks.module.css'

export function CommentsCard({ task, viewer }: { task: Task; viewer: Viewer }) {
  const { t, locale } = useI18n()
  const toast = useToast()
  const query = useComments(task.id)
  const add = useAddComment(task.id)
  const edit = useEditComment(task.id)
  const del = useDeleteComment(task.id)
  const [draft, setDraft] = useState('')
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editText, setEditText] = useState('')
  const [deleting, setDeleting] = useState<TaskComment | null>(null)

  const allowed = canComment(task, viewer)

  return (
    <Card>
      <h2 className={styles.cardTitle}>{t('tasks.comments.title')}</h2>
      {query.isPending && <Skeleton lines={2} />}
      {query.isError && <ErrorState error={query.error} onRetry={() => void query.refetch()} />}
      {query.data && query.data.length === 0 && <p className={styles.hint}>{t('tasks.comments.none')}</p>}
      {query.data && query.data.length > 0 && (
        <ul className={styles.list}>
          {query.data.map((c) => {
            const mine = c.author_account_id === viewer.accountId
            return (
              <li key={c.id} className={styles.comment}>
                <div className={styles.commentHead}>
                  <span>{formatDateTime(c.created_at, locale)}{c.edited_at && c.body !== null && ` · ${t('tasks.comments.edited')}`}</span>
                </div>
                {c.body === null ? (
                  <p className={styles.deleted}>{t('tasks.comments.deleted')}</p>
                ) : editingId === c.id ? (
                  <>
                    <TextAreaField label={t('tasks.comments.field')} value={editText} maxLength={5000} onChange={(e) => setEditText(e.target.value)} />
                    <InlineError error={edit.error} />
                    <div className={styles.actions}>
                      <Button
                        disabled={!editText.trim()}
                        loading={edit.isPending}
                        onClick={() => edit.mutate({ commentId: c.id, body: editText.trim() }, { onSuccess: () => setEditingId(null) })}
                      >
                        {t('tasks.comments.save')}
                      </Button>
                      <Button variant="ghost" onClick={() => setEditingId(null)}>{t('common.cancel')}</Button>
                    </div>
                  </>
                ) : (
                  <>
                    <p className={styles.commentBody}>{c.body}</p>
                    {mine && (
                      <div className={styles.actions}>
                        <Button variant="ghost" onClick={() => { edit.reset(); setEditText(c.body ?? ''); setEditingId(c.id) }}>{t('tasks.comments.edit')}</Button>
                        <Button variant="ghost" onClick={() => { del.reset(); setDeleting(c) }}>{t('tasks.comments.delete')}</Button>
                      </div>
                    )}
                  </>
                )}
              </li>
            )
          })}
        </ul>
      )}

      {allowed ? (
        <form
          className={styles.form}
          onSubmit={(e) => {
            e.preventDefault()
            if (!draft.trim()) return
            add.mutate(draft.trim(), { onSuccess: () => { setDraft(''); toast(t('tasks.comments.posted')) } })
          }}
        >
          <TextAreaField label={t('tasks.comments.field')} value={draft} maxLength={5000} onChange={(e) => setDraft(e.target.value)} />
          <InlineError error={add.error} />
          <div><Button type="submit" disabled={!draft.trim()} loading={add.isPending}>{t('tasks.comments.add')}</Button></div>
        </form>
      ) : (
        <p className={styles.hint}>{t('tasks.comments.cannot')}</p>
      )}

      <ConfirmDialog
        open={!!deleting}
        title={t('tasks.comments.deleteTitle')}
        body={<div className={styles.form}><p>{t('tasks.comments.deleteBody')}</p><InlineError error={del.error} /></div>}
        confirmLabel={t('tasks.comments.delete')}
        danger
        loading={del.isPending}
        onConfirm={() => deleting && del.mutate(deleting.id, { onSuccess: () => setDeleting(null) })}
        onClose={() => setDeleting(null)}
      />
    </Card>
  )
}
