import enum
from datetime import timedelta


class TaskStatus(enum.StrEnum):
    NEW = "new"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


OPEN_STATUSES = frozenset({TaskStatus.NEW, TaskStatus.IN_PROGRESS})


class TaskPriority(enum.StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class AssignmentEndReason(enum.StrEnum):
    REMOVED = "removed"  # removed by the creator or a manager
    MEMBER_INACTIVE = "member_inactive"
    OUT_OF_SCOPE = "out_of_scope"  # Member or task moved so the Member is no longer in scope
    SERIES_UPDATE = "series_update"  # dropped from the series' assignees


class SeriesStatus(enum.StrEnum):
    ACTIVE = "active"
    STOPPED = "stopped"


class EventKind(enum.StrEnum):
    """Task-local history entries (not a general audit log)."""

    CREATED = "created"
    UPDATED = "updated"
    STATUS_CHANGED = "status_changed"
    ASSIGNEE_ADDED = "assignee_added"
    ASSIGNEE_REMOVED = "assignee_removed"
    ASSIGNEE_NOT_ADDED = "assignee_not_added"
    SCOPE_CHANGED = "scope_changed"
    SUBTASK_CREATED = "subtask_created"
    COMMENT_ADDED = "comment_added"
    COMMENT_EDITED = "comment_edited"
    COMMENT_DELETED = "comment_deleted"


RECURRENCE_INTERVAL = timedelta(weeks=1)
# Intentional anti-abuse limit: occurrences are generated up front, so an unbounded end time
# could create an unbounded number of tasks. 104 weekly occurrences is two years.
MAX_SERIES_OCCURRENCES = 104
