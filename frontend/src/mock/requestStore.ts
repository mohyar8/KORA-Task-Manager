import { useSyncExternalStore } from 'react'

/**
 * MOCK: task requests between administrations (browser only). A manager asks another administration for work with
 * the full details; the receiving manager accepts (and picks who from their administration does it) or rejects.
 * Accepting will create the real task once the backend exists.
 */
export type RequestStatus = 'pending' | 'accepted' | 'rejected'

export interface TaskRequest {
  id: string
  title: string
  description: string
  dueDate: string | null
  priority: 'normal' | 'high' | 'urgent'
  fromUnit: string
  fromName: string
  toUnit: string
  status: RequestStatus
  assignees: string[]
  reason: string
  createdAt: string
}

const KEY = 'kora.mock.requests'
const listeners = new Set<() => void>()
let requests: TaskRequest[] = load()

function load(): TaskRequest[] {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? '[]') as TaskRequest[]
  } catch {
    return []
  }
}

function commit(next: TaskRequest[]) {
  requests = next
  try {
    localStorage.setItem(KEY, JSON.stringify(next))
  } catch {
    // keep working in memory
  }
  listeners.forEach((l) => l())
}

type NewRequest = Pick<TaskRequest, 'title' | 'description' | 'dueDate' | 'priority' | 'fromUnit' | 'fromName' | 'toUnit'>

export const requestActions = {
  create(r: NewRequest) {
    commit([{ ...r, id: crypto.randomUUID(), status: 'pending', assignees: [], reason: '', createdAt: new Date().toISOString() }, ...requests])
  },
  accept(id: string, assignees: string[]) {
    commit(requests.map((r) => (r.id === id ? { ...r, status: 'accepted', assignees } : r)))
  },
  reject(id: string, reason: string) {
    commit(requests.map((r) => (r.id === id ? { ...r, status: 'rejected', reason } : r)))
  },
  /** First visit: one sample request addressed to the person's own unit so the inbox can be judged. */
  seed(sample: NewRequest) {
    if (requests.some((r) => r.toUnit === sample.toUnit)) return
    requestActions.create(sample)
  },
}

export const useRequests = () => useSyncExternalStore((l) => { listeners.add(l); return () => listeners.delete(l) }, () => requests)
