import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Protocol, cast

from fastapi import Request
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from kora_api.access.dependencies import AccessContext
from kora_api.core import clock
from kora_api.notifications.models import (
    Notification,
    NotificationCategory,
    NotificationPreference,
)


class SourceAccess(Protocol):
    """Returns the subset of `source_ids` whose content the caller may currently see."""

    async def __call__(
        self, db: AsyncSession, access: AccessContext, source_ids: set[uuid.UUID]
    ) -> set[uuid.UUID]: ...


def source_checkers(request: Request) -> Mapping[str, SourceAccess]:
    return cast(Mapping[str, SourceAccess], request.app.state.notification_sources)


class NotificationNotFoundError(Exception):
    pass


@dataclass(frozen=True)
class NotificationView:
    notification: Notification
    redacted: bool


# --- Creation (called by source modules inside their transaction) -------------------------------


async def notify(
    db: AsyncSession,
    *,
    recipient_account_ids: Iterable[uuid.UUID],
    actor_account_id: uuid.UUID | None,
    category: NotificationCategory,
    source_type: str,
    source_id: uuid.UUID,
    kind: str,
    summary: str | None = None,
) -> None:
    """Queue notifications for direct recipients. Never notifies the actor; honours each
    recipient's preference for the category. Does not commit: it is part of the caller's change."""
    recipients = set(recipient_account_ids) - {actor_account_id}
    if not recipients:
        return
    disabled = set(
        await db.scalars(
            select(NotificationPreference.account_id).where(
                NotificationPreference.account_id.in_(recipients),
                NotificationPreference.category == category,
                NotificationPreference.enabled.is_(False),
            )
        )
    )
    now = clock.utcnow()
    for recipient in recipients - disabled:
        db.add(
            Notification(
                recipient_account_id=recipient,
                category=category,
                kind=kind,
                source_type=source_type,
                source_id=source_id,
                summary=summary[:300] if summary else None,
                actor_account_id=actor_account_id,
                created_at=now,
            )
        )


# --- Reader actions -----------------------------------------------------------------------------


async def list_notifications(
    db: AsyncSession,
    access: AccessContext,
    checkers: Mapping[str, SourceAccess],
    *,
    unread_only: bool = False,
) -> list[NotificationView]:
    stmt = select(Notification).where(
        Notification.recipient_account_id == access.account.id,
        Notification.deleted_at.is_(None),
    )
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    notifications = list(await db.scalars(stmt.order_by(Notification.created_at.desc())))
    return await _with_access(db, access, checkers, notifications)


async def get_notification(
    db: AsyncSession,
    access: AccessContext,
    checkers: Mapping[str, SourceAccess],
    notification_id: uuid.UUID,
) -> NotificationView:
    [view] = await _with_access(db, access, checkers, [await _own(db, access, notification_id)])
    return view


async def mark_read(
    db: AsyncSession,
    access: AccessContext,
    checkers: Mapping[str, SourceAccess],
    notification_id: uuid.UUID,
) -> NotificationView:
    notification = await _own(db, access, notification_id)
    if notification.read_at is None:
        notification.read_at = clock.utcnow()
        await db.commit()
    [view] = await _with_access(db, access, checkers, [notification])
    return view


async def mark_all_read(db: AsyncSession, access: AccessContext) -> None:
    await db.execute(
        update(Notification)
        .where(
            Notification.recipient_account_id == access.account.id,
            Notification.deleted_at.is_(None),
            Notification.read_at.is_(None),
        )
        .values(read_at=clock.utcnow())
    )
    await db.commit()


async def delete(db: AsyncSession, access: AccessContext, notification_id: uuid.UUID) -> None:
    """Remove from the reader's own list only; the source and other users are unaffected."""
    notification = await _own(db, access, notification_id)
    notification.deleted_at = clock.utcnow()
    await db.commit()


async def delete_all(db: AsyncSession, access: AccessContext) -> None:
    await db.execute(
        update(Notification)
        .where(
            Notification.recipient_account_id == access.account.id,
            Notification.deleted_at.is_(None),
        )
        .values(deleted_at=clock.utcnow())
    )
    await db.commit()


# --- Preferences --------------------------------------------------------------------------------


async def preferences(db: AsyncSession, account_id: uuid.UUID) -> dict[NotificationCategory, bool]:
    stored = {
        p.category: p.enabled
        for p in await db.scalars(
            select(NotificationPreference).where(NotificationPreference.account_id == account_id)
        )
    }
    return {category: stored.get(category, True) for category in NotificationCategory}


async def set_preferences(
    db: AsyncSession, account_id: uuid.UUID, changes: Mapping[NotificationCategory, bool]
) -> dict[NotificationCategory, bool]:
    now = clock.utcnow()
    for category, enabled in changes.items():
        row = await db.scalar(
            select(NotificationPreference)
            .where(
                NotificationPreference.account_id == account_id,
                NotificationPreference.category == category,
            )
            .with_for_update()
        )
        if row is None:
            db.add(
                NotificationPreference(
                    account_id=account_id, category=category, enabled=enabled, updated_at=now
                )
            )
        else:
            row.enabled = enabled
            row.updated_at = now
    await db.commit()
    return await preferences(db, account_id)


# --- Helpers ------------------------------------------------------------------------------------


async def _own(db: AsyncSession, access: AccessContext, notification_id: uuid.UUID) -> Notification:
    notification = await db.get(Notification, notification_id)
    if (
        notification is None
        or notification.recipient_account_id != access.account.id
        or notification.deleted_at is not None
    ):
        raise NotificationNotFoundError
    return notification


async def _with_access(
    db: AsyncSession,
    access: AccessContext,
    checkers: Mapping[str, SourceAccess],
    notifications: list[Notification],
) -> list[NotificationView]:
    """Re-check source access now; notifications for unreadable sources are redacted."""
    by_type: dict[str, set[uuid.UUID]] = {}
    for notification in notifications:
        by_type.setdefault(notification.source_type, set()).add(notification.source_id)
    visible: set[tuple[str, uuid.UUID]] = set()
    for source_type, ids in by_type.items():
        checker = checkers.get(source_type)
        if checker is not None:
            visible |= {(source_type, i) for i in await checker(db, access, ids)}
    return [NotificationView(n, (n.source_type, n.source_id) not in visible) for n in notifications]
