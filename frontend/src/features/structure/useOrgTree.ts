import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { http } from '@/shared/api/http'
import { isMock } from '@/shared/config'
import { useSession } from '@/features/auth/session'
import { useDisplayName } from '@/features/members/directory'
import { workUnits } from '@/features/teams/units'
import { mockOrg } from '@/mock/orgChart'

export interface OrgPerson {
  id: string
  name: string
  role?: string
}
export type OrgKind = 'organization' | 'administration' | 'team'
export interface OrgNode {
  id: string
  name: string
  kind: OrgKind
  leader: OrgPerson | null
  members: OrgPerson[]
  children: OrgNode[]
}

// Contract §8.1b.
interface StructureNode {
  unit_id: string
  name: string
  kind: 'organization' | 'pmo' | 'administration' | 'team'
  leader_ids: string[]
  members: { member_id: string; full_name: string; role_key: string }[]
  children: StructureNode[]
}

export const structureKey = ['organization', 'structure'] as const

function toNode(n: StructureNode): OrgNode {
  const people: OrgPerson[] = n.members.map((m) => ({ id: m.member_id, name: m.full_name, role: m.role_key }))
  const first = n.leader_ids[0]
  const leader = people.find((p) => p.id === first) ?? null
  return {
    id: n.unit_id,
    name: n.name,
    // The PMO is drawn like an Administration.
    kind: n.kind === 'pmo' ? 'administration' : n.kind,
    leader,
    members: people.filter((p) => p.id !== leader?.id),
    children: n.children.map(toNode),
  }
}

export function flatten(node: OrgNode): { person: OrgPerson; unit: OrgNode }[] {
  return [
    ...(node.leader ? [{ person: node.leader, unit: node }] : []),
    ...node.members.map((person) => ({ person, unit: node })),
    ...node.children.flatMap(flatten),
  ]
}

/** The whole organization as one tree. Real: the server's structure; mock: the browser-only chart. */
export function useOrgTree() {
  const { access, account } = useSession()
  const displayName = useDisplayName()
  const real = useQuery({
    queryKey: structureKey,
    queryFn: () => http.get<StructureNode>('/organization/structure'),
    enabled: !isMock(),
    staleTime: 60_000,
    select: toNode,
  })
  const me = account?.member_id ?? ''
  const mine = useMemo(() => workUnits(access), [access])

  return useMemo(() => {
    const myNames = new Set(mine.map((u) => u.name))
    const myIds = new Set(mine.map((u) => u.unit_id))
    if (!isMock()) {
      return { tree: real.data ?? null, isLoading: real.isPending, error: real.error, isMine: (n: OrgNode) => myIds.has(n.id) }
    }
    // The signed-in person appears as a member of their own team in the mock tree.
    const addMe = (n: OrgNode): OrgNode => ({
      ...n,
      members: me && n.kind === 'team' && myNames.has(n.name) && displayName ? [...n.members, { id: me, name: displayName }] : n.members,
      children: n.children.map(addMe),
    })
    return { tree: addMe(mockOrg), isLoading: false, error: null, isMine: (n: OrgNode) => myNames.has(n.name) }
  }, [real.data, real.isPending, real.error, mine, me, displayName])
}
