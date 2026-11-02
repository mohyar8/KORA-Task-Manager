"""Chat tables. Membership of unit channels is derived from the organization (never stored), so
it follows transfers and deactivations by itself; only direct chats name their two people."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, Enum, ForeignKey, Identity, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from kora_api.core.database import Base

MAX_BODY = 2_000


class ConversationKind(enum.StrEnum):
    DIRECT = "direct"
    UNIT = "unit"  # a Team, an Administration or the PMO
    ORGANIZATION = "organization"


def _values(enum_cls: type[enum.StrEnum]) -> list[str]:
    return [member.value for member in enum_cls]


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        CheckConstraint(
            "(kind = 'direct' AND direct_a_id IS NOT NULL AND direct_b_id IS NOT NULL"
            " AND direct_a_id < direct_b_id AND unit_id IS NULL)"
            " OR (kind = 'unit' AND unit_id IS NOT NULL AND direct_a_id IS NULL"
            " AND direct_b_id IS NULL)"
            " OR (kind = 'organization' AND unit_id IS NULL AND direct_a_id IS NULL"
            " AND direct_b_id IS NULL)",
            name="shape",
        ),
        Index(
            "uq_conversations_direct",
            "direct_a_id",
            "direct_b_id",
            unique=True,
            postgresql_where=text("kind = 'direct'"),
        ),
        Index(
            "uq_conversations_unit",
            "unit_id",
            unique=True,
            postgresql_where=text("kind = 'unit'"),
        ),
        Index(
            "uq_conversations_organization",
            "kind",
            unique=True,
            postgresql_where=text("kind = 'organization'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    kind: Mapped[ConversationKind] = mapped_column(
        Enum(ConversationKind, name="conversation_kind", values_callable=_values)
    )
    unit_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("org_units.id"))
    # The two people of a direct chat, ordered so the pair is unique.
    direct_a_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("members.id"))
    direct_b_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("members.id"))
    created_at: Mapped[datetime]


class Message(Base):
    """Soft-deleted messages keep their place but lose their text. Never audited or logged."""

    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_conversation_id_id", "conversation_id", "id"),
        Index("ix_messages_author_created", "author_member_id", "created_at"),
    )

    # Monotonic: the cursor for `after` / `before` and for read markers.
    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversations.id"))
    author_member_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("members.id"))
    body: Mapped[str] = mapped_column(String(MAX_BODY))
    created_at: Mapped[datetime]
    edited_at: Mapped[datetime | None]
    deleted_at: Mapped[datetime | None]


class ConversationRead(Base):
    __tablename__ = "conversation_reads"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id"), primary_key=True
    )
    member_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("members.id"), primary_key=True)
    last_read_message_id: Mapped[int] = mapped_column(BigInteger)
