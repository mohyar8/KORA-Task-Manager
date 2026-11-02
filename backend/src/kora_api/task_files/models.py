"""Metadata of files attached to tasks; the bytes live in the object store."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Enum, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from kora_api.core.database import Base


class FileKind(enum.StrEnum):
    BRIEF = "brief"  # from whoever manages the task
    DELIVERY = "delivery"  # from the people doing it


class FileStatus(enum.StrEnum):
    PENDING = "pending"  # row exists, upload not confirmed yet
    READY = "ready"


def _values(enum_cls: type[enum.StrEnum]) -> list[str]:
    return [member.value for member in enum_cls]


class TaskFile(Base):
    """Soft-deleted only: removing a file hides it (the object is kept for the record)."""

    __tablename__ = "task_files"
    __table_args__ = (Index("ix_task_files_task_kind", "task_id", "kind"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id"))
    kind: Mapped[FileKind] = mapped_column(
        Enum(FileKind, name="task_file_kind", values_callable=_values)
    )
    name: Mapped[str] = mapped_column(String(200))
    size: Mapped[int] = mapped_column(BigInteger)
    content_type: Mapped[str | None] = mapped_column(String(100))
    # Unguessable and never returned to clients: `tasks/{task_id}/{file_id}`.
    storage_key: Mapped[str] = mapped_column(String(200), unique=True)
    uploaded_by_member_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("members.id"))
    status: Mapped[FileStatus] = mapped_column(
        Enum(FileStatus, name="task_file_status", values_callable=_values)
    )
    created_at: Mapped[datetime]
    deleted_at: Mapped[datetime | None]
