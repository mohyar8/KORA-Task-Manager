"""Announcement rules. Every operation checks the caller's access itself.

- Drafts: created by holders of `announcement.publish` at the scope; visible to their creator
  and to current `announcement.manage` holders at the scope.
- Publishing (immediate only) needs `announcement.publish` at the scope. The recipients (active
  Members within the scope) are fixed at that moment.
- Published: visible to its direct recipients (regardless of later scope changes), its publisher
  and current scoped managers. The publisher or a scoped manager may edit (new immutable version)
  or withdraw it. Withdrawn content is hidden from recipients; the record and history remain.
"""

import enum
import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import ColumnElement, and_, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from kora_api.access.dependencies import AccessContext
from kora_api.access.evaluation import AccessDeniedError
from kora_api.access.permissions import Permission
from kora_api.announcements.models import (
    Announcement,
    AnnouncementRead,
    AnnouncementRecipient,
    AnnouncementState,
    AnnouncementVersion,
)
from kora_api.core import clock
from kora_api.notifications import service as notifications
from kora_api.notifications.models import NotificationCategory
from kora_api.organization import queries as org

PUBLISH = Permission.ANNOUNCEMENT_PUBLISH
MANAGE = Permission.ANNOUNCEMENT_MANAGE
NOTIFICATION_SOURCE = "announcement"


class AnnouncementNotFoundError(Exception):
    pass


class InvalidAnnouncementError(Exception):
    """The request breaks an announcement rule (422)."""


class AnnouncementConflictError(Exception):
    """The announcement's state prevents the operation (409)."""


class Visibility(enum.Enum):
    NONE = "none"
    RECORD = "record"  # withdrawn, seen by a recipient: no content
    FULL = "full"


@dataclass(frozen=True)
class ReadState:
    read_version: int | None
    read_at_current: bool


@dataclass(frozen=True)
class AnnouncementView:
    announcement: Announcement
    content: AnnouncementVersion | None  # None when the content is hidden from the caller
    my_read: ReadState | None  # set only when the caller is a recipient


@dataclass(frozen=True)
class RecipientStatus:
    recipient: AnnouncementRecipient
    read_version: int | None
    read_current: bool


# --- Access -------------------------------------------------------------------------------------


def _is_manager(access: AccessContext, announcement: Announcement) -> bool:
    return access.snapshot.allows(MANAGE, announcement.scope_unit_id)


def _is_publisher(access: AccessContext, announcement: Announcement) -> bool:
    return announcement.published_by_account_id == access.account.id


async def _is_recipient(
    db: AsyncSession, announcement_id: uuid.UUID, account_id: uuid.UUID
) -> bool:
    return bool(
        await db.scalar(
            select(
                exists().where(
                    AnnouncementRecipient.announcement_id == announcement_id,
                    AnnouncementRecipient.account_id == account_id,
                )
            )
        )
    )


async def visibility(
    db: AsyncSession, access: AccessContext, announcement: Announcement
) -> Visibility:
    if announcement.state == AnnouncementState.DRAFT:
        creator = announcement.created_by_account_id == access.account.id
        return Visibility.FULL if creator or _is_manager(access, announcement) else Visibility.NONE
    if _is_publisher(access, announcement) or _is_manager(access, announcement):
        return Visibility.FULL
    if await _is_recipient(db, announcement.id, access.account.id):
        published = announcement.state == AnnouncementState.PUBLISHED
        return Visibility.FULL if published else Visibility.RECORD
    return Visibility.NONE


def _can_administer(access: AccessContext, announcement: Announcement) -> bool:
    """Edit or withdraw: drafts by creator or managers; published by publisher or managers."""
    if announcement.state == AnnouncementState.DRAFT:
        return announcement.created_by_account_id == access.account.id or _is_manager(
            access, announcement
        )
    return _is_publisher(access, announcement) or _is_manager(access, announcement)


async def _load(
    db: AsyncSession, announcement_id: uuid.UUID, *, lock: bool = False
) -> Announcement:
    announcement = await db.get(Announcement, announcement_id, with_for_update=lock)
    if announcement is None:
        raise AnnouncementNotFoundError
    return announcement


async def _require_visible(
    db: AsyncSession, access: AccessContext, announcement: Announcement
) -> Visibility:
    level = await visibility(db, access, announcement)
    if level == Visibility.NONE:
        raise AccessDeniedError(MANAGE, announcement.scope_unit_id)
    return level


# --- Reads --------------------------------------------------------------------------------------


async def get_announcement(
    db: AsyncSession, access: AccessContext, announcement_id: uuid.UUID
) -> AnnouncementView:
    """Opening a published announcement as a recipient marks its current version read."""
    announcement = await _load(db, announcement_id)
    level = await _require_visible(db, access, announcement)
    is_recipient = await _is_recipient(db, announcement.id, access.account.id)
    if is_recipient and announcement.state == AnnouncementState.PUBLISHED:
        await _mark_read(db, announcement, access.account.id)
        await db.commit()
    return await _view(db, access, announcement, level, is_recipient)


async def list_announcements(
    db: AsyncSession, access: AccessContext, *, state: AnnouncementState | None = None
) -> list[AnnouncementView]:
    """Announcements the caller can see; everything else is omitted."""
    account_id = access.account.id
    managed = access.snapshot.units_with(MANAGE)
    received = select(AnnouncementRecipient.announcement_id).where(
        AnnouncementRecipient.account_id == account_id
    )
    conditions: list[ColumnElement[bool]] = [
        Announcement.scope_unit_id.in_(managed),
        and_(
            Announcement.state == AnnouncementState.DRAFT,
            Announcement.created_by_account_id == account_id,
        ),
        and_(
            Announcement.state != AnnouncementState.DRAFT,
            or_(Announcement.published_by_account_id == account_id, Announcement.id.in_(received)),
        ),
    ]
    stmt = select(Announcement).where(or_(*conditions))
    if state is not None:
        stmt = stmt.where(Announcement.state == state)
    views: list[AnnouncementView] = []
    for announcement in await db.scalars(stmt.order_by(Announcement.updated_at.desc())):
        level = await visibility(db, access, announcement)
        if level != Visibility.NONE:
            is_recipient = await _is_recipient(db, announcement.id, account_id)
            views.append(await _view(db, access, announcement, level, is_recipient))
    return views


async def versions(
    db: AsyncSession, access: AccessContext, announcement_id: uuid.UUID
) -> list[AnnouncementVersion]:
    """Full version history, for the draft creator, the publisher and scoped managers."""
    announcement = await _load(db, announcement_id)
    if not _can_administer(access, announcement):
        raise AccessDeniedError(MANAGE, announcement.scope_unit_id)
    return list(
        await db.scalars(
            select(AnnouncementVersion)
            .where(AnnouncementVersion.announcement_id == announcement_id)
            .order_by(AnnouncementVersion.version)
        )
    )


async def recipient_statuses(
    db: AsyncSession, access: AccessContext, announcement_id: uuid.UUID
) -> list[RecipientStatus]:
    """Read status of every recipient (publisher and scoped managers only)."""
    announcement = await _load(db, announcement_id)
    if announcement.state == AnnouncementState.DRAFT or not _can_administer(access, announcement):
        raise AccessDeniedError(MANAGE, announcement.scope_unit_id)
    recipients = list(
        await db.scalars(
            select(AnnouncementRecipient)
            .where(AnnouncementRecipient.announcement_id == announcement_id)
            .order_by(AnnouncementRecipient.added_at, AnnouncementRecipient.member_id)
        )
    )
    rows = await db.execute(
        select(AnnouncementRead.account_id, func.max(AnnouncementRead.version))
        .where(AnnouncementRead.announcement_id == announcement_id)
        .group_by(AnnouncementRead.account_id)
    )
    latest: dict[uuid.UUID, int] = {account_id: version for account_id, version in rows}
    return [
        RecipientStatus(
            recipient=r,
            read_version=latest.get(r.account_id),
            read_current=latest.get(r.account_id) == announcement.current_version,
        )
        for r in recipients
    ]


# --- Changes ------------------------------------------------------------------------------------


async def create_draft(
    db: AsyncSession, access: AccessContext, *, scope_unit_id: uuid.UUID, title: str, body: str
) -> AnnouncementView:
    access.snapshot.require(PUBLISH, scope_unit_id)
    unit = (await org.current_units(db)).get(scope_unit_id)
    if unit is None or not unit.active:
        raise InvalidAnnouncementError("Scope unit not found or not active.")
    now = clock.utcnow()
    announcement = Announcement(
        scope_unit_id=scope_unit_id,
        state=AnnouncementState.DRAFT,
        current_version=1,
        created_by_account_id=access.account.id,
        created_at=now,
        updated_at=now,
    )
    db.add(announcement)
    await db.flush()
    db.add(_version(announcement, 1, title, body, access.account.id))
    await db.commit()
    return await _view(db, access, announcement, Visibility.FULL, False)


async def edit(
    db: AsyncSession,
    access: AccessContext,
    announcement_id: uuid.UUID,
    *,
    title: str | None,
    body: str | None,
) -> AnnouncementView:
    """Add a new immutable version. Recipients of a published announcement are notified."""
    announcement = await _load(db, announcement_id, lock=True)
    await _require_visible(db, access, announcement)
    if not _can_administer(access, announcement):
        raise AccessDeniedError(MANAGE, announcement.scope_unit_id)
    if announcement.state == AnnouncementState.WITHDRAWN:
        raise AnnouncementConflictError("A withdrawn announcement cannot be edited.")
    current = await _current_version(db, announcement)
    new_title = current.title if title is None else title
    new_body = current.body if body is None else body
    if (new_title, new_body) != (current.title, current.body):
        now = clock.utcnow()
        announcement.current_version += 1
        announcement.updated_at = now
        db.add(
            _version(
                announcement, announcement.current_version, new_title, new_body, access.account.id
            )
        )
        if announcement.state == AnnouncementState.PUBLISHED:
            await _notify_recipients(
                db,
                announcement,
                NotificationCategory.ANNOUNCEMENT_CHANGE,
                "edited",
                access,
                new_title,
            )
        await db.commit()
    return await _view(db, access, announcement, Visibility.FULL, False)


async def publish(
    db: AsyncSession,
    access: AccessContext,
    announcement_id: uuid.UUID,
    recipient_member_ids: Sequence[uuid.UUID],
) -> AnnouncementView:
    """Publish now to a fixed list of active Members within the announcement's scope."""
    announcement = await _load(db, announcement_id, lock=True)
    await _require_visible(db, access, announcement)
    access.snapshot.require(PUBLISH, announcement.scope_unit_id)
    if announcement.state != AnnouncementState.DRAFT:
        raise AnnouncementConflictError("Only drafts can be published.")
    if not recipient_member_ids:
        raise InvalidAnnouncementError("Select at least one recipient.")
    if len(set(recipient_member_ids)) != len(recipient_member_ids):
        raise InvalidAnnouncementError("Recipients must be distinct.")
    units = await org.current_units(db)
    positions = await org.member_positions(db, recipient_member_ids)
    invalid = [
        str(m)
        for m in recipient_member_ids
        if m not in positions
        or not org.member_within_scope(positions[m], announcement.scope_unit_id, units)
    ]
    if invalid:
        raise InvalidAnnouncementError(
            f"Recipients must be active Members within the scope: {', '.join(invalid)}."
        )

    now = clock.utcnow()
    for member_id in recipient_member_ids:
        db.add(
            AnnouncementRecipient(
                announcement_id=announcement.id,
                member_id=member_id,
                account_id=positions[member_id].account_id,
                added_at=now,
            )
        )
    announcement.state = AnnouncementState.PUBLISHED
    announcement.published_at = now
    announcement.published_by_account_id = access.account.id
    announcement.updated_at = now
    current = await _current_version(db, announcement)
    await _notify_recipients(
        db, announcement, NotificationCategory.ANNOUNCEMENT_NEW, "published", access, current.title
    )
    await db.commit()
    return await _view(db, access, announcement, Visibility.FULL, False)


async def withdraw(
    db: AsyncSession, access: AccessContext, announcement_id: uuid.UUID
) -> AnnouncementView:
    announcement = await _load(db, announcement_id, lock=True)
    await _require_visible(db, access, announcement)
    if announcement.state != AnnouncementState.PUBLISHED:
        raise AnnouncementConflictError("Only published announcements can be withdrawn.")
    if not _can_administer(access, announcement):
        raise AccessDeniedError(MANAGE, announcement.scope_unit_id)
    now = clock.utcnow()
    announcement.state = AnnouncementState.WITHDRAWN
    announcement.withdrawn_at = now
    announcement.withdrawn_by_account_id = access.account.id
    announcement.updated_at = now
    # No summary: recipients can no longer see the content.
    await _notify_recipients(
        db, announcement, NotificationCategory.ANNOUNCEMENT_CHANGE, "withdrawn", access, None
    )
    await db.commit()
    return await _view(db, access, announcement, Visibility.FULL, False)


async def visible_announcement_ids(
    db: AsyncSession, access: AccessContext, source_ids: set[uuid.UUID]
) -> set[uuid.UUID]:
    """Notification source checker: announcements whose content the caller can see now."""
    announcements = await db.scalars(select(Announcement).where(Announcement.id.in_(source_ids)))
    return {a.id for a in announcements if await visibility(db, access, a) == Visibility.FULL}


# --- Helpers ------------------------------------------------------------------------------------


def _version(
    announcement: Announcement, number: int, title: str, body: str, actor_id: uuid.UUID
) -> AnnouncementVersion:
    return AnnouncementVersion(
        announcement_id=announcement.id,
        version=number,
        title=title,
        body=body,
        created_by_account_id=actor_id,
        created_at=clock.utcnow(),
    )


async def _current_version(db: AsyncSession, announcement: Announcement) -> AnnouncementVersion:
    version = await db.scalar(
        select(AnnouncementVersion).where(
            AnnouncementVersion.announcement_id == announcement.id,
            AnnouncementVersion.version == announcement.current_version,
        )
    )
    assert version is not None
    return version


async def _mark_read(db: AsyncSession, announcement: Announcement, account_id: uuid.UUID) -> None:
    already = await db.scalar(
        select(
            exists().where(
                AnnouncementRead.announcement_id == announcement.id,
                AnnouncementRead.account_id == account_id,
                AnnouncementRead.version == announcement.current_version,
            )
        )
    )
    if not already:
        db.add(
            AnnouncementRead(
                announcement_id=announcement.id,
                account_id=account_id,
                version=announcement.current_version,
                read_at=clock.utcnow(),
            )
        )


async def _view(
    db: AsyncSession,
    access: AccessContext,
    announcement: Announcement,
    level: Visibility,
    is_recipient: bool,
) -> AnnouncementView:
    content = await _current_version(db, announcement) if level == Visibility.FULL else None
    my_read: ReadState | None = None
    if is_recipient:
        read_version = await db.scalar(
            select(func.max(AnnouncementRead.version)).where(
                AnnouncementRead.announcement_id == announcement.id,
                AnnouncementRead.account_id == access.account.id,
            )
        )
        my_read = ReadState(read_version, read_version == announcement.current_version)
    return AnnouncementView(announcement, content, my_read)


async def _notify_recipients(
    db: AsyncSession,
    announcement: Announcement,
    category: NotificationCategory,
    kind: str,
    access: AccessContext,
    summary: str | None,
) -> None:
    recipients = await db.scalars(
        select(AnnouncementRecipient.account_id).where(
            AnnouncementRecipient.announcement_id == announcement.id
        )
    )
    await notifications.notify(
        db,
        recipient_account_ids=set(recipients),
        actor_account_id=access.account.id,
        category=category,
        source_type=NOTIFICATION_SOURCE,
        source_id=announcement.id,
        kind=kind,
        summary=summary,
    )
