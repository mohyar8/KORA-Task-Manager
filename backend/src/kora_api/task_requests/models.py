"""A request from one Administration (or the leadership) to another for a task."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from kora_api.core.database import Base
from kora_api.tasks.constants import TaskPriority


class RequestStatus(enum.StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


def _values(enum_cls: type[enum.StrEnum]) -> list[str]:
    return [member.value for member in enum_cls]


class TaskRequest(Base):
    """Never deleted. Accepting creates a real task (`resulting_task_id`) in the target
    Administration in the same transaction."""

    __tablename__ = "task_requests"
    __table_args__ = (
        CheckConstraint("from_unit_id <> to_unit_id", name="different_units"),
        Index("ix_task_requests_to_unit_status", "to_unit_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[TaskPriority | None] = mapped_column(
        Enum(TaskPriority, name="task_priority", values_callable=_values, create_type=False)
    )
    due_at: Mapped[datetime | None]
    from_unit_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("org_units.id"), index=True)
    to_unit_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("org_units.id"))
    requested_by_member_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("members.id"), index=True)
    requested_by_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_accounts.id"))
    status: Mapped[RequestStatus] = mapped_column(
        Enum(RequestStatus, name="task_request_status", values_callable=_values)
    )
    decided_by_member_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("members.id"))
    decided_at: Mapped[datetime | None]
    rejection_reason: Mapped[str | None] = mapped_column(String(1000))
    resulting_task_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tasks.id"))
    created_at: Mapped[datetime]
