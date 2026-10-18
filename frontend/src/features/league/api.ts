import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { http } from '@/shared/api/http'

// Contract §16: the KORA league.
export interface Standing {
  rank: number
  team_id: string
  team_name: string
  administration_name: string | null
  points: number
}

export interface League {
  round_title: string | null
  updated_at: string | null
  standings: Standing[]
}

export const leagueKey = ['league'] as const

export const useLeague = () => useQuery({ queryKey: leagueKey, queryFn: () => http.get<League>('/league') })

export function useUpdateLeague() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { round_title: string | null; points: { team_id: string; points: number }[] }) => http.put<League>('/league', body),
    onSuccess: (data) => qc.setQueryData(leagueKey, data),
  })
}
