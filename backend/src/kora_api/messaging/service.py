"""Chat rules. Every operation checks the caller's access itself.

- Only active Members chat. Any active Member may message any other (the structure is open).
- A direct chat is private to its two people: nobody else reads it, not even a System Admin.
- Unit channels (Team, Administration, PMO) and the organization channel belong to the unit, not to
  a person: whoever is currently in the unit may read the whole history and write.
- The author edits and deletes their own message; a holder of `chat.moderate` at the channel's
  unit deletes anyone's there (audited by ids only). Deleting blanks the text.
- Message text is never audited, logged or placed in a notification.
"""

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from kora_api.access.dependencies import AccessContext
from kora_api.access.evaluation import AccessDeniedError, AccessSnapshot
from kora_api.access.org_facts import UnitInfo
from kora_api.access.permissions import Permission
from kora_api.audit import service as audit
from kora_api.core import clock
from kora_api.messaging import audit_actions
from kora_api.messaging.models import (
    Conversation,
    ConversationKind,
    ConversationRead,
    Message,
)
from kora_api.notifications import service as notifications
from kora_api.notifications.models import Notification, NotificationCategory
from kora_api.organization import queries as org
from kora_api.organization.constants import KORA_UNIT_ID

MODERATE = Permission.CHAT_MODERATE
SOURCE = "conversation"
CHANNEL_UNIT_KINDS = ("team", "administration", "pmo")
RATE_LIMIT = 30  # messages per member per minute
RATE_WINDOW_SECONDS = 60


class ChatNotFoundError(Exception):
    pass


class InvalidChatError(Exception):
    """The request breaks a rule (422)."""


class ChatConflictError(Exception):
    """The state prevents the operation (409)."""


class RateLimitedError(Exception):
    pass


@dataclass(frozen=True)
class ChatActor:
    account_id: uuid.UUID
    member: org.MemberPosition  # always an active Member
    snapshot: AccessSnapshot

    @property
    def member_id(self) -> uuid.UUID:
        return self.member.member_id


async def actor_for(db: AsyncSession, access: AccessContext) -> ChatActor:
    position = await org.member_for_account(db, access.account.id)
    if position is None or not position.active:
        raise AccessDeniedError(MODERATE, None)  # only active Members chat
    return ChatActor(access.account.id, position, access.snapshot)


def _pair(a: uuid.UUID, b: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
    return (a, b) if str(a) < str(b) else (b, a)


def can_access(
    actor: ChatActor, conversation: Conversation, units: Mapping[uuid.UUID, UnitInfo]
) -> bool:
    if conversation.kind == ConversationKind.DIRECT:
        return actor.member_id in (conversation.direct_a_id, conversation.direct_b_id)
    if conversation.kind == ConversationKind.ORGANIZATION:
        return True
    assert conversation.unit_id is not None
    unit = units.get(conversation.unit_id)
    return (
        unit is not None
        and unit.active
        and org.member_within_scope(actor.member, conversation.unit_id, units)
    )


def _moderation_unit(conversation: Conversation) -> uuid.UUID | None:
    if conversation.kind == ConversationKind.ORGANIZATION:
        return KORA_UNIT_ID
    return conversation.unit_id  # None for a direct chat: nobody moderates it


async def _load(
    db: AsyncSession, actor: ChatActor, conversation_id: uuid.UUID
) -> tuple[Conversation, Mapping[uuid.UUID, UnitInfo]]:
    conversation = await db.get(Conversation, conversation_id)
    units = await org.current_units(db)
    # Not accessible looks the same as not existing: a private chat must not be probeable.
    if conversation is None or not can_access(actor, conversation, units):
        raise ChatNotFoundError
    return conversation, units


async def _ensure_channels(
    db: AsyncSession, actor: ChatActor, units: Mapping[uuid.UUID, UnitInfo]
) -> list[Conversation]:
    """The caller's channels: the organization and every active Team/Administration/PMO on the
    way up from their Team and their role's unit. Created on first use."""
    wanted: list[tuple[ConversationKind, uuid.UUID | None]] = [
        (ConversationKind.ORGANIZATION, None)
    ]
    seen: set[uuid.UUID] = set()
    for start in (actor.member.team_id, actor.member.role_unit_id):
        for unit_id in org.unit_chain(start, units):
            info = units[unit_id]
            if unit_id not in seen and info.active and info.kind in CHANNEL_UNIT_KINDS:
                seen.add(unit_id)
                wanted.append((ConversationKind.UNIT, unit_id))
    found = list(
        await db.scalars(
            select(Conversation).where(
                or_(
                    Conversation.kind == ConversationKind.ORGANIZATION,
                    and_(
                        Conversation.kind == ConversationKind.UNIT,
                        Conversation.unit_id.in_(seen),
                    ),
                )
            )
        )
    )
    have = {(c.kind, c.unit_id) for c in found}
    missing = [w for w in wanted if w not in have]
    if missing:
        for kind, unit_id in missing:
            try:
                async with db.begin_nested():
                    created = Conversation(kind=kind, unit_id=unit_id, created_at=clock.utcnow())
                    db.add(created)
                    await db.flush()
                found.append(created)
            except IntegrityError:  # another request created it first
                other = await db.scalar(
                    select(Conversation).where(
                        Conversation.kind == kind,
                        Conversation.unit_id.is_(None)
                        if unit_id is None
                        else Conversation.unit_id == unit_id,
                    )
                )
                assert other is not None
                found.append(other)
        await db.commit()
    return found


@dataclass(frozen=True)
class ConversationView:
    conversation: Conversation
    last_message: Message | None
    unread: int


async def _views(
    db: AsyncSession, actor: ChatActor, conversations: list[Conversation]
) -> list[ConversationView]:
    ids = [c.id for c in conversations]
    if not ids:
        return []
    latest_ids = (
        select(func.max(Message.id))
        .where(Message.conversation_id.in_(ids))
        .group_by(Message.conversation_id)
    )
    latest = {
        m.conversation_id: m
        for m in await db.scalars(select(Message).where(Message.id.in_(latest_ids)))
    }
    unread_rows = await db.execute(
        select(Message.conversation_id, func.count())
        .outerjoin(
            ConversationRead,
            and_(
                ConversationRead.conversation_id == Message.conversation_id,
                ConversationRead.member_id == actor.member_id,
            ),
        )
        .where(
            Message.conversation_id.in_(ids),
            Message.author_member_id != actor.member_id,
            Message.deleted_at.is_(None),
            Message.id > func.coalesce(ConversationRead.last_read_message_id, 0),
        )
        .group_by(Message.conversation_id)
    )
    unread = {conversation_id: count for conversation_id, count in unread_rows}
    views = [ConversationView(c, latest.get(c.id), unread.get(c.id, 0)) for c in conversations]
    return sorted(
        views,
        key=lambda v: v.last_message.created_at if v.last_message else v.conversation.created_at,
        reverse=True,
    )


async def list_conversations(db: AsyncSession, actor: ChatActor) -> list[ConversationView]:
    units = await org.current_units(db)
    channels = await _ensure_channels(db, actor, units)
    direct = list(
        await db.scalars(
            select(Conversation).where(
                Conversation.kind == ConversationKind.DIRECT,
                or_(
                    Conversation.direct_a_id == actor.member_id,
                    Conversation.direct_b_id == actor.member_id,
                ),
            )
        )
    )
    return await _views(db, actor, channels + direct)


async def open_direct(db: AsyncSession, actor: ChatActor, member_id: uuid.UUID) -> ConversationView:
    if member_id == actor.member_id:
        raise InvalidChatError("You cannot chat with yourself.")
    other = (await org.member_positions(db, [member_id])).get(member_id)
    if other is None or not other.active:
        raise InvalidChatError("The other person must be an active Member.")
    a, b = _pair(actor.member_id, member_id)
    where = and_(
        Conversation.kind == ConversationKind.DIRECT,
        Conversation.direct_a_id == a,
        Conversation.direct_b_id == b,
    )
    conversation = await db.scalar(select(Conversation).where(where))
    if conversation is None:
        try:
            async with db.begin_nested():
                conversation = Conversation(
                    kind=ConversationKind.DIRECT,
                    direct_a_id=a,
                    direct_b_id=b,
                    created_at=clock.utcnow(),
                )
                db.add(conversation)
                await db.flush()
        except IntegrityError:
            conversation = await db.scalar(select(Conversation).where(where))
        await db.commit()
    assert conversation is not None
    return (await _views(db, actor, [conversation]))[0]


async def list_messages(
    db: AsyncSession,
    actor: ChatActor,
    conversation_id: uuid.UUID,
    *,
    after: int | None,
    before: int | None,
    limit: int,
) -> list[Message]:
    await _load(db, actor, conversation_id)
    stmt = select(Message).where(Message.conversation_id == conversation_id)
    if after is not None:
        rows = await db.scalars(stmt.where(Message.id > after).order_by(Message.id).limit(limit))
        return list(rows)
    if before is not None:
        stmt = stmt.where(Message.id < before)
    rows = await db.scalars(stmt.order_by(Message.id.desc()).limit(limit))
    return list(reversed(list(rows)))


async def _mark_read(
    db: AsyncSession, member_id: uuid.UUID, conversation_id: uuid.UUID, message_id: int
) -> None:
    row = await db.get(ConversationRead, (conversation_id, member_id))
    if row is None:
        db.add(
            ConversationRead(
                conversation_id=conversation_id,
                member_id=member_id,
                last_read_message_id=message_id,
            )
        )
    elif message_id > row.last_read_message_id:
        row.last_read_message_id = message_id


async def send_message(
    db: AsyncSession, actor: ChatActor, conversation_id: uuid.UUID, body: str
) -> Message:
    conversation, _ = await _load(db, actor, conversation_id)
    now = clock.utcnow()
    recent = await db.scalar(
        select(func.count())
        .select_from(Message)
        .where(
            Message.author_member_id == actor.member_id,
            Message.created_at
            > now.replace(microsecond=0) - timedelta(seconds=RATE_WINDOW_SECONDS),
        )
    )
    if (recent or 0) >= RATE_LIMIT:
        raise RateLimitedError
    message = Message(
        conversation_id=conversation_id,
        author_member_id=actor.member_id,
        body=body,
        created_at=now,
    )
    db.add(message)
    await db.flush()
    await _mark_read(db, actor.member_id, conversation_id, message.id)
    if conversation.kind == ConversationKind.DIRECT:
        await _notify_direct(db, actor, conversation)
    await db.commit()
    return message


async def _notify_direct(db: AsyncSession, actor: ChatActor, conversation: Conversation) -> None:
    """One notification per direct chat until the recipient reads it (never the text)."""
    other_id = (
        conversation.direct_b_id
        if conversation.direct_a_id == actor.member_id
        else conversation.direct_a_id
    )
    assert other_id is not None
    other = (await org.member_positions(db, [other_id]))[other_id]
    pending = await db.scalar(
        select(Notification.id).where(
            Notification.recipient_account_id == other.account_id,
            Notification.source_type == SOURCE,
            Notification.source_id == conversation.id,
            Notification.read_at.is_(None),
            Notification.deleted_at.is_(None),
        )
    )
    if pending is None:
        await notifications.notify(
            db,
            recipient_account_ids=[other.account_id],
            actor_account_id=actor.account_id,
            category=NotificationCategory.CHAT_MESSAGE,
            source_type=SOURCE,
            source_id=conversation.id,
            kind="new_message",
        )


async def _own_message(db: AsyncSession, actor: ChatActor, message_id: int) -> Message:
    message = await db.get(Message, message_id)
    if message is None:
        raise ChatNotFoundError
    conversation = await db.get_one(Conversation, message.conversation_id)
    if not can_access(actor, conversation, await org.current_units(db)):
        raise ChatNotFoundError
    return message


async def edit_message(db: AsyncSession, actor: ChatActor, message_id: int, body: str) -> Message:
    message = await _own_message(db, actor, message_id)
    if message.author_member_id != actor.member_id:
        raise AccessDeniedError(MODERATE, None)
    if message.deleted_at is not None:
        raise ChatConflictError("The message was deleted.")
    message.body = body
    message.edited_at = clock.utcnow()
    await db.commit()
    return message


async def delete_message(db: AsyncSession, actor: ChatActor, message_id: int) -> Message:
    message = await _own_message(db, actor, message_id)
    if message.deleted_at is not None:
        return message  # already gone
    conversation = await db.get_one(Conversation, message.conversation_id)
    if message.author_member_id != actor.member_id:
        unit_id = _moderation_unit(conversation)
        if unit_id is None:
            raise AccessDeniedError(MODERATE, None)
        actor.snapshot.require(MODERATE, unit_id)
        audit.record(
            db,
            audit_actions.MESSAGE_MODERATED,
            actor_account_id=actor.account_id,
            resource_id=conversation.id,
            scope_unit_id=conversation.unit_id,
            after={
                "message_id": message.id,
                "conversation_id": conversation.id,
                "author_member_id": message.author_member_id,
            },
        )
    message.deleted_at = clock.utcnow()
    message.body = ""
    await db.commit()
    return message


async def mark_read(
    db: AsyncSession, actor: ChatActor, conversation_id: uuid.UUID, up_to: int | None
) -> None:
    await _load(db, actor, conversation_id)
    if up_to is None:
        up_to = await db.scalar(
            select(func.max(Message.id)).where(Message.conversation_id == conversation_id)
        )
    if up_to is not None:
        await _mark_read(db, actor.member_id, conversation_id, up_to)
        await db.commit()


async def visible_conversation_ids(
    db: AsyncSession, access: AccessContext, source_ids: set[uuid.UUID]
) -> set[uuid.UUID]:
    """Notification source checker: the conversations among `source_ids` the caller is in."""
    position = await org.member_for_account(db, access.account.id)
    if position is None or not position.active:
        return set()
    actor = ChatActor(access.account.id, position, access.snapshot)
    units = await org.current_units(db)
    rows = await db.scalars(select(Conversation).where(Conversation.id.in_(source_ids)))
    return {c.id for c in rows if can_access(actor, c, units)}
