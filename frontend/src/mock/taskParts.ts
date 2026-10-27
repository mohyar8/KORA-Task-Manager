import { useSyncExternalStore } from 'react'

/**
 * MOCK: "I finished my part" marks, per task and person. Members cannot close a task: they flag their part, the
 * leader sees it and closes the task. With one assignee this is the "ready for review" signal; with several it is
 * each person's own progress. The backend will keep it as a per-assignee row.
 *
 * Flagging also opens a review item for the leader ("review X's work on task Y"); ticking it off records that the
 * leader looked at the work. The backend will create that as a real task assigned to the leader.
 */
const PARTS_KEY = 'kora.mock.taskParts'
const REVIEWS_KEY = 'kora.mock.taskReviews'

export interface Review {
  done: boolean
}

function load<T>(key: string): Record<string, T> {
  try {
    return JSON.parse(localStorage.getItem(key) ?? '{}') as Record<string, T>
  } catch {
    return {}
  }
}

function save(key: string, value: unknown) {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch {
    // keep working in memory
  }
}

let parts = load<string>(PARTS_KEY)
let reviews = load<Review>(REVIEWS_KEY)
const listeners = new Set<() => void>()
const emit = () => listeners.forEach((l) => l())
const subscribe = (l: () => void) => {
  listeners.add(l)
  return () => listeners.delete(l)
}

export const partKey = (taskId: string, memberId: string) => `${taskId}:${memberId}`

export const taskParts = {
  toggle(taskId: string, memberId: string) {
    const k = partKey(taskId, memberId)
    const nextParts = { ...parts }
    const nextReviews = { ...reviews }
    if (nextParts[k]) {
      delete nextParts[k]
      delete nextReviews[k]
    } else {
      nextParts[k] = new Date().toISOString()
      nextReviews[k] = { done: false }
    }
    parts = nextParts
    reviews = nextReviews
    save(PARTS_KEY, parts)
    save(REVIEWS_KEY, reviews)
    emit()
  },
  setReviewed(key: string, done: boolean) {
    if (!reviews[key]) return
    reviews = { ...reviews, [key]: { done } }
    save(REVIEWS_KEY, reviews)
    emit()
  },
}

export const useTaskParts = () => useSyncExternalStore(subscribe, () => parts)
export const useTaskReviews = () => useSyncExternalStore(subscribe, () => reviews)
