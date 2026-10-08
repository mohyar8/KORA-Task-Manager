"""Announcement tables. Nothing is hard-deleted; versions, recipients and reads are append-only."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from kora_api.core.database import Base


class AnnouncementState(enum.StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    WITHDRAWN = "withdrawn"


def _enum_values(enum_cls: type[enum.StrEnum]) -> list[str]:
    return [member.value for member in enum_cls]


class Announcement(Base):
    __tablename__ = "announcements"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    scope_unit_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("org_units.id"), index=True)
    state: Mapped[AnnouncementState] = mapped_column(
        Enum(AnnouncementState, name="announcement_state", values_callable=_enum_values)
    )
    # The latest version number; content lives in announcement_versions.
    current_version: Mapped[int]
    created_by_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_accounts.id"))
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
    published_at: Mapped[datetime | None]
    published_by_account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user_accounts.id")
    )
    withdrawn_at: Mapped[datetime | None]
    withdrawn_by_account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user_accounts.id")
    )


class AnnouncementVersion(Base):
    """Immutable content. Every edit adds a version; earlier versions are kept."""

    __tablename__ = "announcement_versions"
    __table_args__ = (UniqueConstraint("announcement_id", "version"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    announcement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("announcements.id"), index=True)
    version: Mapped[int]
    title: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text)
    created_by_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_accounts.id"))
    created_at: Mapped[datetime]


class AnnouncementRecipient(Base):
    """A direct recipient, fixed at publication. The account is captured with the Member."""

    __tablename__ = "announcement_recipients"
    __table_args__ = (UniqueConstraint("announcement_id", "member_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    announcement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("announcements.id"), index=True)
    member_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("members.id"))
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_accounts.id"), index=True)
    added_at: Mapped[datetime]


class AnnouncementRead(Base):
    """A recipient opened a specific version. Reading an older version is not reading the new."""

    __tablename__ = "announcement_reads"
    __table_args__ = (UniqueConstraint("announcement_id", "account_id", "version"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    announcement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("announcements.id"), index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_accounts.id"))
    version: Mapped[int]
    read_at: Mapped[datetime]
