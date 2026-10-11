"""Calendar tables. Events are cancelled, never deleted; invitations and history are append-only."""

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
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from kora_api.core.database import Base


class CalendarEventType(enum.StrEnum):
    EVENT = "event"
    MEETING = "meeting"


class CalendarEventState(enum.StrEnum):
    SCHEDULED = "scheduled"
    CANCELLED = "cancelled"


def _enum_values(enum_cls: type[enum.StrEnum]) -> list[str]:
    return [member.value for member in enum_cls]


class CalendarEvent(Base):
    """An event or meeting. Its scope is fixed after creation."""

    __tablename__ = "calendar_events"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="valid_range"),
        CheckConstraint("location_text IS NULL OR online_url IS NULL", name="one_location_method"),
        Index("ix_calendar_events_range", "starts_at", "ends_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    type: Mapped[CalendarEventType] = mapped_column(
        Enum(CalendarEventType, name="calendar_event_type", values_callable=_enum_values)
    )
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    starts_at: Mapped[datetime]
    ends_at: Mapped[datetime]
    # At most one location method: a physical place or an online meeting URL.
    location_text: Mapped[str | None] = mapped_column(String(500))
    online_url: Mapped[str | None] = mapped_column(String(2000))
    scope_unit_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("org_units.id"), index=True)
    organizer_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_accounts.id"))
    organizer_member_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("members.id"), index=True)
    state: Mapped[CalendarEventState] = mapped_column(
        Enum(CalendarEventState, name="calendar_event_state", values_callable=_enum_values)
    )
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
    cancelled_at: Mapped[datetime | None]
    cancelled_by_account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user_accounts.id")
    )


class CalendarInvitation(Base):
    """An invitee over time. Removing ends the row (revoking access); history is kept."""

    __tablename__ = "calendar_invitations"
    __table_args__ = (
        CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name="valid_period"),
        Index(
            "uq_calendar_invitations_open",
            "event_id",
            "member_id",
            unique=True,
            postgresql_where=text("valid_to IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("calendar_events.id"), index=True)
    member_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("members.id"), index=True)
    valid_from: Mapped[datetime]
    valid_to: Mapped[datetime | None]
    created_by_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_accounts.id"))
    ended_by_account_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_accounts.id"))


class CalendarEventHistory(Base):
    """Event-local history: created, updated, cancelled, invitee added/removed. Append-only."""

    __tablename__ = "calendar_event_history"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    seq: Mapped[int] = mapped_column(BigInteger, Identity(), unique=True)
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("calendar_events.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    actor_account_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_accounts.id"))
    data: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime]
