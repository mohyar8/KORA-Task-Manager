import { useQuery } from '@tanstack/react-query'
import { ApiError, http } from '@/shared/api/http'
import type { FileKind } from '@/mock/fileStore'

// Contract §9f. The bytes go straight to the bucket with a presigned URL; the API only holds the details.
export interface ApiTaskFile {
  id: string
  task_id: string
  kind: FileKind
  name: string
  size: number
  content_type: string | null
  uploaded_by_member_id: string
  created_at: string
}

interface UploadTicket {
  file: ApiTaskFile
  upload_url: string
  expires_in: number
}

export const taskFilesKey = (taskId: string) => ['tasks', taskId, 'files'] as const

export const useTaskFileList = (taskId: string, enabled: boolean) =>
  useQuery({ queryKey: taskFilesKey(taskId), queryFn: () => http.get<ApiTaskFile[]>(`/tasks/${taskId}/files`), enabled })

/** Register, upload and confirm one file. Throws `ApiError` (503 = storage not set up) or `UploadFailedError`. */
export async function uploadTaskFile(taskId: string, kind: FileKind, file: File): Promise<ApiTaskFile> {
  const ticket = await http.post<UploadTicket>(`/tasks/${taskId}/files`, { kind, name: file.name, size: file.size, content_type: file.type || null })
  let response: Response
  try {
    response = await fetch(ticket.upload_url, { method: 'PUT', body: file })
  } catch {
    throw new UploadFailedError()
  }
  if (!response.ok) throw new UploadFailedError()
  return http.post<ApiTaskFile>(`/tasks/${taskId}/files/${ticket.file.id}/complete`)
}

export class UploadFailedError extends Error {
  constructor() {
    super('upload failed')
    this.name = 'UploadFailedError'
  }
}

export const storageUnavailable = (error: unknown) => error instanceof ApiError && error.status === 503

/** Opens the file through a short-lived link that forces a download. */
export async function downloadTaskFile(taskId: string, fileId: string): Promise<void> {
  const { url } = await http.get<{ url: string }>(`/tasks/${taskId}/files/${fileId}/download`)
  const a = document.createElement('a')
  a.href = url
  a.rel = 'noopener'
  a.click()
}

export const removeTaskFile = (taskId: string, fileId: string) => http.delete<void>(`/tasks/${taskId}/files/${fileId}`)
