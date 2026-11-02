import { useMemo } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { http } from '@/shared/api/http'
import { isMock } from '@/shared/config'
import { allowedUnits } from '@/features/auth/permissions'
import { useSession } from '@/features/auth/session'
import { isTopRole, useDisplayName, useMemberNames } from '@/features/members/directory'
import { flatten, useOrgTree } from '@/features/structure/useOrgTree'
import { summaryKey } from '@/features/summary/useBadges'
import { tasksKey } from '@/features/tasks/api'
import { mockOrg } from '@/mock/orgChart'
import { requestActions, useRequests as useMockRequests, type TaskRequest } from '@/mock/requestStore'
import { useMyRequestUnit } from './useIncoming'

export type RequestStatus = 'pending' | 'accepted' | 'rejected' | 'withdrawn'
export type RequestPriority = 'low' | 'normal' | 'high' | 'urgent'

/** One request as the screen shows it, whichever store it came from. */
export interface RequestView {
  id: string
  title: string
  description: string
  dueDate: string | null
  priority: RequestPriority
  fromUnit: string
  fromName: string
  toUnitId: string
  toUnit: string
  status: RequestStatus
  reason: string
  /** Mock only: the people picked when it was accepted. */
  assignees: string[]
  /** Real only: the task an accepted request became. */
  taskId: string | null
  /** The signed-in person sent it (can withdraw while pending). */
  mine: boolean
}

export interface NewRequest {
  title: string
  description: string
  dueDate: string
  priority: RequestPriority
  toUnitId: string
}

// Contract §9c.
interface ApiRequest {
  id: string
  title: string
  description: string | null
  priority: RequestPriority | null
  due_at: string | null
  from_unit_id: string
  to_unit_id: string
  requested_by_member_id: string
  status: RequestStatus
  rejection_reason: string | null
  resulting_task_id: string | null
}

const requestsKey = ['task-requests'] as const
const TOP_ROLES = new Set(['event_project_leader', 'deputy_leader', 'pmo_leader'])

/** The unit a person sends from: KORA for the leadership, otherwise their Administration. */
function sendingUnit(access: ReturnType<typeof useSession>['access']): string | null {
  const units = allowedUnits(access, 'task_request.create')
  return (units.find((u) => u.kind === 'organization') ?? units.find((u) => u.kind === 'administration'))?.unit_id ?? null
}

export function useRequestsData() {
  const { access, account } = useSession()
  const qc = useQueryClient()
  const { tree } = useOrgTree()
  const displayName = useDisplayName()
  const names = useMemberNames()
  const myMockUnit = useMyRequestUnit()
  const mock = useMockRequests()
  const mockMode = isMock()
  const me = account?.member_id ?? ''
  const fromUnitId = sendingUnit(access)

  const incoming = useQuery({
    queryKey: [...requestsKey, 'incoming'],
    queryFn: () => http.get<ApiRequest[]>('/task-requests', { box: 'incoming' }),
    enabled: !mockMode,
    refetchInterval: 30_000,
  })
  const outgoing = useQuery({
    queryKey: [...requestsKey, 'outgoing'],
    queryFn: () => http.get<ApiRequest[]>('/task-requests', { box: 'outgoing' }),
    enabled: !mockMode,
    refetchInterval: 30_000,
  })

  const refresh = () => {
    void qc.invalidateQueries({ queryKey: requestsKey })
    void qc.invalidateQueries({ queryKey: summaryKey })
    void qc.invalidateQueries({ queryKey: tasksKey })
  }
  const send = useMutation({
    mutationFn: (r: NewRequest) =>
      http.post('/task-requests', {
        title: r.title,
        description: r.description || null,
        priority: r.priority,
        due_at: r.dueDate ? new Date(`${r.dueDate}T23:59:00`).toISOString() : null,
        from_unit_id: fromUnitId,
        to_unit_id: r.toUnitId,
      }),
    onSuccess: refresh,
  })
  const accept = useMutation({
    mutationFn: ({ id, ids }: { id: string; ids: string[] }) => http.post(`/task-requests/${id}/accept`, { assignee_member_ids: ids }),
    onSuccess: refresh,
  })
  const reject = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) => http.post(`/task-requests/${id}/reject`, { reason }),
    onSuccess: refresh,
  })
  const withdraw = useMutation({ mutationFn: (id: string) => http.post(`/task-requests/${id}/withdraw`), onSuccess: refresh })

  return useMemo(() => {
    const people = new Map(tree ? flatten(tree).map((x) => [x.person.id, x.person.name]) : [])
    const units = new Map<string, string>()
    const walk = (n: NonNullable<typeof tree>) => { units.set(n.id, n.name); n.children.forEach(walk) }
    if (tree) walk(tree)

    if (mockMode) {
      const view = (r: TaskRequest): RequestView => ({
        id: r.id, title: r.title, description: r.description, dueDate: r.dueDate, priority: r.priority, fromUnit: r.fromUnit, fromName: r.fromName,
        toUnitId: r.toUnit, toUnit: r.toUnit, status: r.status, reason: r.reason, assignees: r.assignees.map((id) => names.nameOf(id)), taskId: null, mine: r.fromName === displayName,
      })
      return {
        incoming: mock.filter((r) => r.toUnit === myMockUnit).map(view),
        outgoing: mock.filter((r) => r.fromUnit === myMockUnit && r.fromName === displayName).map(view),
        targets: mockOrg.children.map((c) => c.name).filter((n) => n !== myMockUnit).map((n) => ({ id: n, name: n })),
        canSend: true,
        staffFor: () => names.members.filter((m) => !isTopRole(m.role_key)).map((m) => ({ id: m.id, name: m.full_name })),
        isLoading: false,
        error: null as unknown,
        actions: {
          create: async (r: NewRequest) => requestActions.create({ title: r.title, description: r.description, dueDate: r.dueDate || null, priority: r.priority === 'low' ? 'normal' : r.priority, fromUnit: myMockUnit, fromName: displayName, toUnit: r.toUnitId }),
          accept: async (id: string, ids: string[]) => requestActions.accept(id, ids),
          reject: async (id: string, reason: string) => requestActions.reject(id, reason),
          withdraw: undefined,
        },
      }
    }

    const view = (r: ApiRequest): RequestView => ({
      id: r.id,
      title: r.title,
      description: r.description ?? '',
      dueDate: r.due_at,
      priority: r.priority ?? 'normal',
      fromUnit: units.get(r.from_unit_id) ?? '',
      fromName: people.get(r.requested_by_member_id) ?? '',
      toUnitId: r.to_unit_id,
      toUnit: units.get(r.to_unit_id) ?? '',
      status: r.status,
      reason: r.rejection_reason ?? '',
      assignees: [],
      taskId: r.resulting_task_id,
      mine: r.requested_by_member_id === me,
    })
    const subtree = (unitId: string) => {
      const out: { id: string; name: string }[] = []
      const find = (n: NonNullable<typeof tree>): NonNullable<typeof tree> | null => (n.id === unitId ? n : n.children.map(find).find(Boolean) ?? null)
      const root = tree ? find(tree) : null
      if (root) for (const { person } of flatten(root)) if (!TOP_ROLES.has(person.role ?? '')) out.push({ id: person.id, name: person.name })
      return out
    }
    return {
      incoming: (incoming.data ?? []).map(view),
      outgoing: (outgoing.data ?? []).map(view),
      targets: (tree?.children ?? []).filter((c) => c.kind === 'administration' && c.id !== fromUnitId).map((c) => ({ id: c.id, name: c.name })),
      canSend: fromUnitId !== null,
      staffFor: subtree,
      isLoading: incoming.isPending || outgoing.isPending,
      error: (incoming.error ?? outgoing.error) as unknown,
      actions: {
        create: (r: NewRequest) => send.mutateAsync(r).then(() => undefined),
        accept: (id: string, ids: string[]) => accept.mutateAsync({ id, ids }).then(() => undefined),
        reject: (id: string, reason: string) => reject.mutateAsync({ id, reason }).then(() => undefined),
        withdraw: (id: string) => withdraw.mutateAsync(id).then(() => undefined),
      },
    }
  }, [mockMode, tree, mock, myMockUnit, displayName, names, incoming, outgoing, me, fromUnitId, send, accept, reject, withdraw])
}
