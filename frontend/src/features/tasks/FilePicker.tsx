import { useRef, useState } from 'react'
import { Paperclip, X } from 'lucide-react'
import { useI18n } from '@/shared/i18n/i18n'
import { useDisplayName } from '@/features/members/directory'
import { useSession } from '@/features/auth/session'
import { checkFile, fileActions, type FileKind, type FileProblem } from '@/mock/fileStore'
import { formatSize } from './AttachmentsCard'
import styles from './attachments.module.css'

/** Files chosen while writing a task; they are attached once the task exists (see `useAttachAfterCreate`). */
export function FilePicker({ files, onChange }: { files: File[]; onChange: (files: File[]) => void }) {
  const { t } = useI18n()
  const input = useRef<HTMLInputElement>(null)
  const [problem, setProblem] = useState<FileProblem | null>(null)

  const add = (list: FileList | null) => {
    if (!list) return
    setProblem(null)
    const next = [...files]
    for (const file of Array.from(list)) {
      const bad = checkFile(file, next.length)
      if (bad) setProblem(bad)
      else next.push(file)
    }
    onChange(next)
    if (input.current) input.current.value = ''
  }

  return (
    <div>
      <div className={styles.pickRow}>
        <button type="button" className={styles.upload} onClick={() => input.current?.click()}>
          <Paperclip size={16} aria-hidden="true" /> {t('files.attach')}{files.length > 0 && ` (${files.length})`}
        </button>
        <input ref={input} type="file" multiple hidden onChange={(e) => add(e.target.files)} aria-label={t('files.attach')} />
      </div>
      {problem && <p className={styles.problem} role="alert">{t(`files.problem.${problem}`)}</p>}
      {files.length > 0 && (
        <ul className={styles.picked}>
          {files.map((f, i) => (
            <li key={`${f.name}-${i}`}>
              {f.name} ({formatSize(f.size)})
              <button type="button" className={styles.icon} style={{ inlineSize: 28, blockSize: 28 }} onClick={() => onChange(files.filter((_, j) => j !== i))} aria-label={t('files.remove', { name: f.name })}><X size={14} aria-hidden="true" /></button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

/** Returns a function that attaches the chosen files to a task: the brief of a new task, or a delivery. */
export function useAttach(kind: FileKind) {
  const { account } = useSession()
  const name = useDisplayName()
  return (taskId: string, files: File[]) => {
    const id = account?.member_id
    if (!id) return
    for (const file of files) void fileActions.add(taskId, kind, file, { id, name })
  }
}

export const useAttachAfterCreate = () => useAttach('brief')
