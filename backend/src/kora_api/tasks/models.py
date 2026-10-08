"""Task tables. Tasks are never hard-deleted; scope and assignment history is append-only."""

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Enum,
    ForeignKey,
    Identity,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from kora_api.core.database import Base
from kora_api.tasks.constants import AssignmentEndReason, SeriesStatus, TaskPriority, TaskStatus

_VALID_PERIOD = "valid_to IS NULL OR valid_to > valid_from"


def _enum_values(enum_cls: type[enum.StrEnum]) -> list[str]:
    return [member.value for member in enum_cls]


def _priority_enum() -> Enum:
    return Enum(TaskPriority, name="task_priority", values_callable=_enum_values)


class TaskSeries(Base):
    """A weekly recurrence. Its occurrences are independent tasks generated up front."""

    __tablename__ = "task_series"
    __table_args__ = (CheckConstraint("ends_at >= first_due_at", name="ends_after_start"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    scope_unit_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("org_units.id"))
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[TaskPriority | None] = mapped_column(_priority_enum())
    assignee_member_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(Uuid()))
    # [{"key", "title", "description", "priority", "assignee_member_ids"}], duplicated per
    # occurrence; generated subtasks carry the template's key in `series_template_key`.
    subtask_templates: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    first_due_at: Mapped[datetime]
    ends_at: Mapped[datetime]
    status: Mapped[SeriesStatus] = mapped_column(
        Enum(SeriesStatus, name="task_series_status", values_callable=_enum_values)
    )
    created_by_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_accounts.id"))
    created_by_member_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("members.id"))
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
    stopped_at: Mapped[datetime | None]
    stopped_by_account_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_accounts.id"))


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint("parent_id IS NULL OR parent_id <> id", name="not_own_parent"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[TaskPriority | None] = mapped_column(_priority_enum())
    due_at: Mapped[datetime | None]
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus, name="task_status", values_callable=_enum_values)
    )
    # Current scope; the full history is in task_scope_history.
    scope_unit_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("org_units.id"), index=True)
    # One subtask level only: a subtask's parent is always a top-level task.
    parent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tasks.id"), index=True)
    series_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("task_series.id"), index=True)
    # For subtasks generated from a series subtask template: that template's `key`.
    series_template_key: Mapped[uuid.UUID | None]
    created_by_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_accounts.id"))
    created_by_member_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("members.id"), index=True)
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
    # First time work started (in_progress or completed); never cleared.
    started_at: Mapped[datetime | None]


class TaskScopeChange(Base):
    """Append-only history of a task's organizational scope."""

    __tablename__ = "task_scope_history"
    __table_args__ = (
        CheckConstraint(_VALID_PERIOD, name="valid_period"),
        Index(
            "uq_task_scope_history_open",
            "task_id",
            unique=True,
            postgresql_where=text("valid_to IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id"), index=True)
    unit_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("org_units.id"))
    valid_from: Mapped[datetime]
    valid_to: Mapped[datetime | None]
    created_by_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_accounts.id"))
    ended_by_account_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_accounts.id"))


class TaskAssignment(Base):
    """An assignee over time. Equal assignees; one open row per (task, Member)."""

    __tablename__ = "task_assignments"
    __table_args__ = (
        CheckConstraint(_VALID_PERIOD, name="valid_period"),
        Index(
            "uq_task_assignments_open",
            "task_id",
            "member_id",
            unique=True,
            postgresql_where=text("valid_to IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id"), index=True)
    member_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("members.id"), index=True)
    valid_from: Mapped[datetime]
    valid_to: Mapped[datetime | None]
    created_by_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_accounts.id"))
    # The account whose action caused the removal (for automatic removals, e.g. a deactivation).
    ended_by_account_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_accounts.id"))
    end_reason: Mapped[AssignmentEndReason | None] = mapped_column(
        Enum(AssignmentEndReason, name="task_assignment_end_reason", values_callable=_enum_values)
    )


class TaskComment(Base):
    """Plain-text comment (no attachments). Deletion is soft; the row and its trace remain."""

    __tablename__ = "task_comments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id"), index=True)
    author_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_accounts.id"))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime]
    edited_at: Mapped[datetime | None]
    deleted_at: Mapped[datetime | None]


class TaskEvent(Base):
    """Task-local history: lifecycle, assignment, scope and comment changes. Append-only."""

    __tablename__ = "task_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # Insertion order; events in one transaction share a timestamp.
    seq: Mapped[int] = mapped_column(BigInteger, Identity(), unique=True)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    actor_account_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_accounts.id"))
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
