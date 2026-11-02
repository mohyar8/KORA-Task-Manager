import { useQueryClient } from '@tanstack/react-query'
import { isMock } from '@/shared/config'
import { useI18n } from '@/shared/i18n/i18n'
import { useToast } from '@/shared/ui/Feedback'
import { useDisplayName } from '@/features/members/directory'
import { useSession } from '@/features/auth/session'
import { fileActions, type FileKind } from '@/mock/fileStore'
import { storageUnavailable, taskFilesKey, uploadTaskFile } from './filesApi'

export const formatSize = (bytes: number) => (bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`)

/**
 * Returns a function that attaches the chosen files to a task: the brief of a new task, or a delivery.
 * Real: uploads straight to the bucket one by one and says which file could not be uploaded.
 */
export function useAttach(kind: FileKind) {
  const { t } = useI18n()
  const toast = useToast()
  const qc = useQueryClient()
  const { account } = useSession()
  const name = useDisplayName()
  return (taskId: string, files: File[]) => {
    if (files.length === 0) return
    if (isMock()) {
      const id = account?.member_id
      if (!id) return
      for (const file of files) void fileActions.add(taskId, kind, file, { id, name })
      return
    }
    void (async () => {
      for (const file of files) {
        try {
          await uploadTaskFile(taskId, kind, file)
        } catch (error) {
          toast(storageUnavailable(error) ? t('files.error.storage') : t('files.error.upload', { name: file.name }), 'danger')
          if (storageUnavailable(error)) break
        }
      }
      void qc.invalidateQueries({ queryKey: taskFilesKey(taskId) })
    })()
  }
}

export const useAttachAfterCreate = () => useAttach('brief')
