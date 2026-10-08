import uuid
from collections.abc import Awaitable
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field, StringConstraints

from kora_api.access.dependencies import CurrentAccess
from kora_api.announcements import service
from kora_api.announcements.models import AnnouncementState
from kora_api.core.database import DbSession

router = APIRouter(prefix="/announcements", tags=["announcements"])

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
Body = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20_000)]


class CreateAnnouncementRequest(BaseModel):
    scope_unit_id: uuid.UUID
    title: Title
    body: Body


class EditAnnouncementRequest(BaseModel):
    title: Title | None = None
    body: Body | None = None


class PublishRequest(BaseModel):
    recipient_member_ids: Annotated[list[uuid.UUID], Field(min_length=1)]


class AnnouncementResponse(BaseModel):
    id: uuid.UUID
    scope_unit_id: uuid.UUID
    state: AnnouncementState
    current_version: int
    # Null with `content_hidden` true when a recipient views a withdrawn announcement.
    title: str | None
    body: str | None
    content_hidden: bool
    created_by_account_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    published_at: datetime | None
    published_by_account_id: uuid.UUID | None
    withdrawn_at: datetime | None
    withdrawn_by_account_id: uuid.UUID | None
    # Only for recipients: the latest version they opened, and whether it is the current one.
    my_read_version: int | None
    my_read_current: bool | None


class VersionResponse(BaseModel):
    version: int
    title: str
    body: str
    created_by_account_id: uuid.UUID
    created_at: datetime


class RecipientStatusResponse(BaseModel):
    member_id: uuid.UUID
    account_id: uuid.UUID
    read_version: int | None
    read_current: bool


async def _call(call: Awaitable[service.AnnouncementView]) -> AnnouncementResponse:
    try:
        return _response(await call)
    except service.AnnouncementNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Announcement not found.") from None
    except service.InvalidAnnouncementError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    except service.AnnouncementConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None


def _response(view: service.AnnouncementView) -> AnnouncementResponse:
    a = view.announcement
    return AnnouncementResponse(
        id=a.id,
        scope_unit_id=a.scope_unit_id,
        state=a.state,
        current_version=a.current_version,
        title=view.content.title if view.content else None,
        body=view.content.body if view.content else None,
        content_hidden=view.content is None,
        created_by_account_id=a.created_by_account_id,
        created_at=a.created_at,
        updated_at=a.updated_at,
        published_at=a.published_at,
        published_by_account_id=a.published_by_account_id,
        withdrawn_at=a.withdrawn_at,
        withdrawn_by_account_id=a.withdrawn_by_account_id,
        my_read_version=view.my_read.read_version if view.my_read else None,
        my_read_current=view.my_read.read_at_current if view.my_read else None,
    )


@router.get("")
async def list_announcements(
    access: CurrentAccess,
    db: DbSession,
    state: Annotated[AnnouncementState | None, Query()] = None,
) -> list[AnnouncementResponse]:
    return [_response(v) for v in await service.list_announcements(db, access, state=state)]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_draft(
    body: CreateAnnouncementRequest, access: CurrentAccess, db: DbSession
) -> AnnouncementResponse:
    return await _call(
        service.create_draft(
            db, access, scope_unit_id=body.scope_unit_id, title=body.title, body=body.body
        )
    )


@router.get("/{announcement_id}")
async def get_announcement(
    announcement_id: uuid.UUID, access: CurrentAccess, db: DbSession
) -> AnnouncementResponse:
    """Opening a published announcement as a recipient marks its current version read."""
    return await _call(service.get_announcement(db, access, announcement_id))


@router.patch("/{announcement_id}")
async def edit_announcement(
    announcement_id: uuid.UUID, body: EditAnnouncementRequest, access: CurrentAccess, db: DbSession
) -> AnnouncementResponse:
    return await _call(service.edit(db, access, announcement_id, title=body.title, body=body.body))


@router.post("/{announcement_id}/publish")
async def publish(
    announcement_id: uuid.UUID, body: PublishRequest, access: CurrentAccess, db: DbSession
) -> AnnouncementResponse:
    return await _call(service.publish(db, access, announcement_id, body.recipient_member_ids))


@router.post("/{announcement_id}/withdraw")
async def withdraw(
    announcement_id: uuid.UUID, access: CurrentAccess, db: DbSession
) -> AnnouncementResponse:
    return await _call(service.withdraw(db, access, announcement_id))


@router.get("/{announcement_id}/versions")
async def list_versions(
    announcement_id: uuid.UUID, access: CurrentAccess, db: DbSession
) -> list[VersionResponse]:
    try:
        rows = await service.versions(db, access, announcement_id)
    except service.AnnouncementNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Announcement not found.") from None
    return [
        VersionResponse(
            version=v.version,
            title=v.title,
            body=v.body,
            created_by_account_id=v.created_by_account_id,
            created_at=v.created_at,
        )
        for v in rows
    ]


@router.get("/{announcement_id}/recipients")
async def recipient_statuses(
    announcement_id: uuid.UUID, access: CurrentAccess, db: DbSession
) -> list[RecipientStatusResponse]:
    try:
        statuses = await service.recipient_statuses(db, access, announcement_id)
    except service.AnnouncementNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Announcement not found.") from None
    return [
        RecipientStatusResponse(
            member_id=s.recipient.member_id,
            account_id=s.recipient.account_id,
            read_version=s.read_version,
            read_current=s.read_current,
        )
        for s in statuses
    ]
