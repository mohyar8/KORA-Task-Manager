import { useMemo } from 'react'
import { useSession } from '@/features/auth/session'
import { useMemberNames } from '@/features/members/directory'
import { flattenPeople, mockPersonName } from '@/mock/orgChart'

/** Everyone the person can message: the directory plus (until the backend serves the full structure) the mock organization. */
export function useChatPeople() {
  const { account } = useSession()
  const names = useMemberNames()
  return useMemo(() => {
    const me = account?.member_id ?? ''
    const byId = new Map<string, string>()
    for (const m of names.members) if (m.id !== me) byId.set(m.id, m.full_name)
    for (const m of flattenPeople()) byId.set(m.id, m.name)
    return {
      people: [...byId].map(([id, name]) => ({ id, name })).sort((a, b) => a.name.localeCompare(b.name)),
      nameOf: (id: string) => mockPersonName(id) ?? names.nameOf(id),
    }
  }, [account, names])
}
