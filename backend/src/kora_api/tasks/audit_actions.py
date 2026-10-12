"""Audited task actions and the only metadata each may store.

Titles are kept as short summaries; descriptions and comment bodies are never stored (an edit
records only which fields changed). Series operations are audited once per series, not once
per generated occurrence.
"""

from kora_api.audit.service import action

TASK = "task"
TASK_CREATED = action(
    "task.created",
    TASK,
    "title",
    "status",
    "priority",
    "due_at",
    "parent_id",
    "assignee_member_ids",
)
TASK_UPDATED = action("task.updated", TASK, "changed_fields", "title", "priority", "due_at")
TASK_STATUS_CHANGED = action("task.status_changed", TASK, "status")
TASK_CANCELLED = action("task.cancelled", TASK, "status")
TASK_REOPENED = action("task.reopened", TASK, "status")
TASK_MOVED = action(
    "task.moved", TASK, "scope_unit_id", "subtask_count", "removed_assignee_member_ids"
)
TASK_ASSIGNEE_ADDED = action("task.assignee_added", TASK, "member_id")
TASK_ASSIGNEE_REMOVED = action("task.assignee_removed", TASK, "member_id", "end_reason")

COMMENT = "task_comment"
COMMENT_CREATED = action("task_comment.created", COMMENT, "task_id")
COMMENT_EDITED = action("task_comment.edited", COMMENT, "task_id", "edited_at")
COMMENT_DELETED = action("task_comment.deleted", COMMENT, "task_id", "deleted_at")

SERIES = "task_series"
SERIES_CREATED = action(
    "task_series.created",
    SERIES,
    "title",
    "status",
    "priority",
    "first_due_at",
    "ends_at",
    "occurrence_count",
    "assignee_member_ids",
    "subtask_template_count",
)
SERIES_UPDATED = action(
    "task_series.updated",
    SERIES,
    "changed_fields",
    "title",
    "priority",
    "assignee_member_ids",
    "subtask_template_count",
    "affected_occurrence_count",
)
SERIES_MOVED = action(
    "task_series.moved",
    SERIES,
    "scope_unit_id",
    "moved_occurrence_count",
    "removed_assignee_member_ids",
)
SERIES_STOPPED = action("task_series.stopped", SERIES, "status", "cancelled_occurrence_count")
# Members removed from future occurrences after a membership change (one record per series).
SERIES_ASSIGNEES_REMOVED = action(
    "task_series.assignees_removed", SERIES, "member_ids", "occurrence_count"
)
