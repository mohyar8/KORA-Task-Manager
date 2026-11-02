import { useQuery } from '@tanstack/react-query'
import { http } from '@/shared/api/http'

// Contract §9b. `version` 0 = never saved.
export interface NoteResponse {
  body: string
  version: number
  updated_at: string | null
}

export const noteKey = ['me', 'note'] as const

export const useNoteQuery = (enabled: boolean) =>
  useQuery({ queryKey: noteKey, queryFn: () => http.get<NoteResponse>('/me/note'), enabled, staleTime: Infinity })

export const saveNote = (body: string, version: number) => http.put<NoteResponse>('/me/note', { body, version })
