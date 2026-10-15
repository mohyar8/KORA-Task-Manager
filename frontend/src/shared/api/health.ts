import { useQuery } from '@tanstack/react-query'
import { http } from './http'

/** GET /health: no auth, no database. Used by the connection-failure screen to say whether the server is back. */
export const useHealth = () =>
  useQuery({ queryKey: ['health'], queryFn: () => http.get<{ status: string }>('/health'), refetchInterval: 5000, retry: false })
