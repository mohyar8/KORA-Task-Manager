import uuid
from collections.abc import Mapping
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from kora_api.access.dependencies import CurrentAccess
from kora_api.core.database import DbSession
from kora_api.notifications import service
from kora_api.notifications.models import NotificationCategory
from kora_api.notifications.service import SourceAccess, source_checkers

router = APIRouter(prefix="/notifications", tags=["notifications"])

Checkers = Annotated[Mapping[str, SourceAccess], Depends(source_checkers)]


class NotificationResponse(BaseModel):
    id: uuid.UUID
    category: NotificationCategory
    kind: str
    source_type: str
    source_id: uuid.UUID
    # Null (and `redacted` true) when the reader can no longer see the source.
    summary: str | None
    redacted: bool
    actor_account_id: uuid.UUID | None
    created_at: datetime
    read_at: datetime | None


def _response(view: service.NotificationView) -> NotificationResponse:
    n = view.notification
    return NotificationResponse(
        id=n.id,
        category=n.category,
        kind=n.kind,
        source_type=n.source_type,
        source_id=n.source_id,
        summary=None if view.redacted else n.summary,
        redacted=view.redacted,
        actor_account_id=n.actor_account_id,
        created_at=n.created_at,
        read_at=n.read_at,
    )


def _not_found() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, "Notification not found.")


@router.get("")
async def list_notifications(
    access: CurrentAccess, db: DbSession, checkers: Checkers, unread_only: bool = False
) -> list[NotificationResponse]:
    views = await service.list_notifications(db, access, checkers, unread_only=unread_only)
    return [_response(v) for v in views]


@router.get("/preferences")
async def get_preferences(access: CurrentAccess, db: DbSession) -> dict[NotificationCategory, bool]:
    """Every category, enabled unless turned off."""
    return await service.preferences(db, access.account.id)


@router.put("/preferences")
async def update_preferences(
    body: dict[NotificationCategory, bool], access: CurrentAccess, db: DbSession
) -> dict[NotificationCategory, bool]:
    return await service.set_preferences(db, access.account.id, body)


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
async def mark_all_read(access: CurrentAccess, db: DbSession) -> None:
    await service.mark_all_read(db, access)


@router.post("/delete-all", status_code=status.HTTP_204_NO_CONTENT)
async def delete_all(access: CurrentAccess, db: DbSession) -> None:
    await service.delete_all(db, access)


@router.get("/{notification_id}")
async def get_notification(
    notification_id: uuid.UUID, access: CurrentAccess, db: DbSession, checkers: Checkers
) -> NotificationResponse:
    try:
        return _response(await service.get_notification(db, access, checkers, notification_id))
    except service.NotificationNotFoundError:
        raise _not_found() from None


@router.post("/{notification_id}/read")
async def mark_read(
    notification_id: uuid.UUID, access: CurrentAccess, db: DbSession, checkers: Checkers
) -> NotificationResponse:
    try:
        return _response(await service.mark_read(db, access, checkers, notification_id))
    except service.NotificationNotFoundError:
        raise _not_found() from None


@router.post("/{notification_id}/delete", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notification(
    notification_id: uuid.UUID, access: CurrentAccess, db: DbSession
) -> None:
    try:
        await service.delete(db, access, notification_id)
    except service.NotificationNotFoundError:
        raise _not_found() from None
