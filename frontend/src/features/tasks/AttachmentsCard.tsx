import { useRef, useState } from 'react'
import { Download, FileText, Paperclip, Trash2, Upload } from 'lucide-react'
import { useI18n } from '@/shared/i18n/i18n'
import { formatDateTime } from '@/shared/lib/format'
import { Card } from '@/shared/ui/Layout'
import { useDisplayName } from '@/features/members/directory'
import { checkFile, fileActions, useTaskFiles, type FileKind, type FileProblem, type TaskFile } from '@/mock/fileStore'
import { canAdminister, isAssignee, type Viewer } from './rules'
import type { Task } from './types'
import styles from './attachments.module.css'

export const formatSize = (bytes: number) => (bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`)

/** Files on a task: the brief from whoever created it, and the deliveries from the people doing it. */
export function AttachmentsCard({ task, viewer }: { task: Task; viewer: Viewer }) {
  const { t } = useI18n()
  const all = useTaskFiles().filter((f) => f.taskId === task.id)
  const admin = canAdminister(task, viewer)
  const assignee = isAssignee(task, viewer)
  const open = task.status === 'new' || task.status === 'in_progress'
  return (
    <Card>
      <h2 className={styles.title}><Paperclip size={18} aria-hidden="true" /> {t('files.title')}</h2>
      <Section task={task} viewer={viewer} kind="brief" files={all.filter((f) => f.kind === 'brief')} canAdd={admin && open} canRemoveAny={admin} />
      <Section task={task} viewer={viewer} kind="delivery" files={all.filter((f) => f.kind === 'delivery')} canAdd={assignee && open} canRemoveAny={admin} />
    </Card>
  )
}

function Section({ task, viewer, kind, files, canAdd, canRemoveAny }: { task: Task; viewer: Viewer; kind: FileKind; files: TaskFile[]; canAdd: boolean; canRemoveAny: boolean }) {
  const { t, locale } = useI18n()
  const name = useDisplayName()
  const input = useRef<HTMLInputElement>(null)
  const [problem, setProblem] = useState<FileProblem | null>(null)
  const [busy, setBusy] = useState(false)

  const pick = async (list: FileList | null) => {
    if (!list || !viewer.memberId) return
    setProblem(null)
    setBusy(true)
    let count = files.length
    for (const file of Array.from(list)) {
      const bad = checkFile(file, count)
      if (bad) {
        setProblem(bad)
        continue
      }
      await fileActions.add(task.id, kind, file, { id: viewer.memberId, name })
      count += 1
    }
    setBusy(false)
    if (input.current) input.current.value = ''
  }

  return (
    <section className={styles.section} aria-label={t(`files.${kind}`)}>
      <header>
        <h3>{t(`files.${kind}`)} <span className={styles.count}>{files.length}</span></h3>
        {canAdd && (
          <>
            <button type="button" className={styles.upload} disabled={busy} onClick={() => input.current?.click()}><Upload size={16} aria-hidden="true" /> {t(`files.add.${kind}`)}</button>
            <input ref={input} type="file" multiple hidden onChange={(e) => void pick(e.target.files)} aria-label={t(`files.add.${kind}`)} />
          </>
        )}
      </header>
      {problem && <p className={styles.problem} role="alert">{t(`files.problem.${problem}`)}</p>}
      {files.length === 0 ? (
        <p className={styles.empty}>{t(`files.empty.${kind}`)}</p>
      ) : (
        <ul className={styles.list}>
          {files.map((f) => (
            <li key={f.id}>
              <FileText size={20} aria-hidden="true" />
              <span className={styles.meta}>
                <b>{f.name}</b>
                <small>{formatSize(f.size)} · {f.authorName} · {formatDateTime(f.at, locale)}</small>
              </span>
              <button type="button" className={styles.icon} onClick={() => void fileActions.download(f)} aria-label={t('files.download', { name: f.name })}><Download size={18} aria-hidden="true" /></button>
              {(canRemoveAny || f.authorId === viewer.memberId) && (
                <button type="button" className={styles.icon} onClick={() => void fileActions.remove(f.id)} aria-label={t('files.remove', { name: f.name })}><Trash2 size={18} aria-hidden="true" /></button>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
