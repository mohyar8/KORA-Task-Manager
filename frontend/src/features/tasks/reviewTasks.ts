import { useMemo } from 'react'
import { useI18n } from '@/shared/i18n/i18n'
import { useChatPeople } from '@/features/chat/people'
import { useTaskReviews } from '@/mock/taskParts'
import { canFinish, type Viewer } from './rules'
import type { Task } from './types'

export const REVIEW_PREFIX = 'review:'

/** A review item's id is `review:<taskId>:<memberId>`; this returns the underlying task and the review key. */
export function parseReview(id: string): { key: string; taskId: string } | null {
  if (!id.startsWith(REVIEW_PREFIX)) return null
  const key = id.slice(REVIEW_PREFIX.length)
  return { key, taskId: key.slice(0, key.lastIndexOf(':')) }
}

/**
 * When a member finishes their part, the leader gets a task of their own: "review X's work on task Y".
 * MOCK: built here from the flags; the backend will create it as a real task assigned to the leader.
 */
export function useReviewTasks(tasks: Task[], viewer: Viewer): Task[] {
  const { t } = useI18n()
  const people = useChatPeople()
  const reviews = useTaskReviews()
  return useMemo(() => {
    if (!viewer.memberId) return []
    const out: Task[] = []
    for (const [key, review] of Object.entries(reviews)) {
      const split = key.lastIndexOf(':')
      const taskId = key.slice(0, split)
      const memberId = key.slice(split + 1)
      const task = tasks.find((x) => x.id === taskId)
      if (!task || memberId === viewer.memberId || !canFinish(task, viewer)) continue
      out.push({
        ...task,
        id: `${REVIEW_PREFIX}${key}`,
        title: t('review.title', { name: people.nameOf(memberId), task: task.title }),
        description: null,
        status: review.done ? 'completed' : 'new',
        parent_id: null,
        series_id: null,
        assignee_member_ids: [viewer.memberId],
        external_assignees: [],
      })
    }
    return out
  }, [reviews, tasks, viewer, people, t])
}
