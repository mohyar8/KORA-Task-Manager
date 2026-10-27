import { useState } from 'react'
import { useI18n } from '@/shared/i18n/i18n'
import { Button } from '@/shared/ui/Button'
import { Modal } from '@/shared/ui/Modal'
import { FilePicker, useAttach } from './FilePicker'
import styles from './attachments.module.css'

interface Props {
  taskId: string
  title: string
  /** `flag`: a member tells the leader their part is done. `close`: someone who may close the task closes it. */
  mode: 'flag' | 'close'
  loading?: boolean
  onConfirm: () => void
  onClose: () => void
}

/** "Are you sure you finished?" with an optional delivery file, shown whenever someone ticks a task off. */
export function CompleteDialog({ taskId, title, mode, loading, onConfirm, onClose }: Props) {
  const { t } = useI18n()
  const attach = useAttach('delivery')
  const [files, setFiles] = useState<File[]>([])

  return (
    <Modal
      open
      title={t(mode === 'flag' ? 'complete.flag.title' : 'complete.close.title')}
      onClose={onClose}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>{t('common.cancel')}</Button>
          <Button loading={loading} onClick={() => { attach(taskId, files); onConfirm() }}>{t(mode === 'flag' ? 'complete.flag.confirm' : 'complete.close.confirm')}</Button>
        </>
      }
    >
      <p className={styles.dialogTask}>{title}</p>
      <p>{t(mode === 'flag' ? 'complete.flag.body' : 'complete.close.body')}</p>
      <p className={styles.dialogLabel}>{t('complete.files')}</p>
      <FilePicker files={files} onChange={setFiles} />
    </Modal>
  )
}
