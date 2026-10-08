import enum
import uuid
from datetime import datetime

from sqlalchemy import Enum, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from kora_api.core.database import Base


class NotificationCategory(enum.StrEnum):
    TASK_ASSIGNMENT = "task_assignment"
    TASK_UPDATE = "task_update"
    TASK_COMMENT = "task_comment"
    ANNOUNCEMENT_NEW = "announcement_new"
    ANNOUNCEMENT_CHANGE = "announcement_change"


def _enum_values(enum_cls: type[enum.StrEnum]) -> list[str]:
    return [member.value for member in enum_cls]


def _category_enum() -> Enum:
    return Enum(NotificationCategory, name="notification_category", values_callable=_enum_values)


class Notification(Base):
    """One recipient's notification. Deleting it hides it for that recipient only."""

    __tablename__ = "notifications"
    __table_args__ = (
        Index(
            "ix_notifications_recipient_visible",
            "recipient_account_id",
            "created_at",
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    recipient_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_accounts.id"))
    category: Mapped[NotificationCategory] = mapped_column(_category_enum())
    # What happened, e.g. "assigned", "updated", "published". Not source content.
    kind: Mapped[str] = mapped_column(String(40))
    # Generic source reference; access is re-checked through the source's registered checker.
    source_type: Mapped[str] = mapped_column(String(40))
    source_id: Mapped[uuid.UUID]
    # Short source text (e.g. a title). Returned only while the reader can see the source.
    summary: Mapped[str | None] = mapped_column(String(300))
    actor_account_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_accounts.id"))
    created_at: Mapped[datetime]
    read_at: Mapped[datetime | None]
    deleted_at: Mapped[datetime | None]


class NotificationPreference(Base):
    """An explicit per-category choice. No row means enabled (the default)."""

    __tablename__ = "notification_preferences"
    __table_args__ = (UniqueConstraint("account_id", "category"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_accounts.id"))
    category: Mapped[NotificationCategory] = mapped_column(_category_enum())
    enabled: Mapped[bool]
    updated_at: Mapped[datetime]
