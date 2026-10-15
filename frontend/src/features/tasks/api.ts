import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { http } from '@/shared/api/http'
import type { Task, TaskComment, TaskEvent, TaskFields, TaskStatus } from './types'

// Contract §9.3. Every key starts with 'tasks' so one invalidation refreshes lists, details and history.
export const tasksKey = ['tasks'] as const

export interface TaskFilters {
  status?: string
  scope_unit_id?: string
}

export const useTasks = (filters: TaskFilters) =>
  useQuery({ queryKey: [...tasksKey, 'list', filters], queryFn: () => http.get<Task[]>('/tasks', { ...filters }) })

export const useTask = (id: string) => useQuery({ queryKey: [...tasksKey, id], queryFn: () => http.get<Task>(`/tasks/${id}`) })

export const useSubtasks = (id: string) =>
  useQuery({ queryKey: [...tasksKey, id, 'subtasks'], queryFn: () => http.get<Task[]>(`/tasks/${id}/subtasks`) })

export const useTaskHistory = (id: string) =>
  useQuery({ queryKey: [...tasksKey, id, 'history'], queryFn: () => http.get<TaskEvent[]>(`/tasks/${id}/history`) })

export const useComments = (id: string) =>
  useQuery({ queryKey: [...tasksKey, id, 'comments'], queryFn: () => http.get<TaskComment[]>(`/tasks/${id}/comments`) })

function useRefresh() {
  const qc = useQueryClient()
  return () => void qc.invalidateQueries({ queryKey: tasksKey })
}

export interface NewTask extends TaskFields {
  assignee_member_ids: string[]
}

export function useCreateTask() {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: (body: NewTask & { scope_unit_id: string }) => http.post<Task>('/tasks', body),
    onSuccess: refresh,
  })
}

export function useCreateSubtask(parentId: string) {
  const refresh = useRefresh()
  return useMutation({ mutationFn: (body: NewTask) => http.post<Task>(`/tasks/${parentId}/subtasks`, body), onSuccess: refresh })
}

/** Partial update: pass only the changed fields (contract §9.3). */
export function useUpdateTask(id: string) {
  const refresh = useRefresh()
  return useMutation({ mutationFn: (body: Partial<TaskFields>) => http.patch<Task>(`/tasks/${id}`, body), onSuccess: refresh })
}

export function useSetStatus(id: string) {
  const refresh = useRefresh()
  return useMutation({ mutationFn: (status: TaskStatus) => http.post<Task>(`/tasks/${id}/status`, { status }), onSuccess: refresh })
}

export function useAddAssignee(id: string) {
  const refresh = useRefresh()
  return useMutation({ mutationFn: (member_id: string) => http.post<Task>(`/tasks/${id}/assignees`, { member_id }), onSuccess: refresh })
}

export function useRemoveAssignee(id: string) {
  const refresh = useRefresh()
  return useMutation({ mutationFn: (memberId: string) => http.post<Task>(`/tasks/${id}/assignees/${memberId}/remove`), onSuccess: refresh })
}

export function useMoveTask(id: string) {
  const refresh = useRefresh()
  return useMutation({ mutationFn: (scope_unit_id: string) => http.post<Task>(`/tasks/${id}/move`, { scope_unit_id }), onSuccess: refresh })
}

export function useAddComment(id: string) {
  const refresh = useRefresh()
  return useMutation({ mutationFn: (body: string) => http.post<TaskComment>(`/tasks/${id}/comments`, { body }), onSuccess: refresh })
}

export function useEditComment(id: string) {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: (v: { commentId: string; body: string }) => http.patch<TaskComment>(`/tasks/${id}/comments/${v.commentId}`, { body: v.body }),
    onSuccess: refresh,
  })
}

export function useDeleteComment(id: string) {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: (commentId: string) => http.post<TaskComment>(`/tasks/${id}/comments/${commentId}/delete`),
    onSuccess: refresh,
  })
}
