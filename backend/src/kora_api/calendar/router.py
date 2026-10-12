import uuid
from collections.abc import Awaitable
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal, Self, cast

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import (
    AfterValidator,
    AnyHttpUrl,
    AwareDatetime,
    BaseModel,
    Field,
    StringConstraints,
    model_validator,
)
from pydantic.json_schema import SkipJsonSchema

from kora_api.access.dependencies import CurrentAccess
from kora_api.calendar import service
from kora_api.calendar.models import CalendarEventState, CalendarEventType, CalendarInvitation
from kora_api.core.database import DbSession
from kora_api.core.errors import AUTHENTICATED, errors
from kora_api.tasks.constants import TaskStatus

router = APIRouter(prefix="/calendar", tags=["calendar"], responses=AUTHENTICATED)

# A "my calendar" query may span at most this long (keeps responses bounded).
MAX_RANGE = timedelta(days=366)


def _to_utc(value: datetime) -> datetime:
    return value.astimezone(UTC)


UtcDatetime = Annotated[AwareDatetime, AfterValidator(_to_utc)]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
Description = Annotated[str, StringConstraints(max_length=10_000)]
Location = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
Url = Annotated[AnyHttpUrl, Field(max_length=2000)]


class EventFieldsRequest(BaseModel):
    type: CalendarEventType
    title: Title
    starts_at: UtcDatetime
    ends_at: UtcDatetime
    description: Description | None = None
    location_text: Location | None = None
    online_url: Url | None = None

    @model_validator(mode="after")
    def _checks(self) -> Self:
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        if self.location_text is not None and self.online_url is not None:
            raise ValueError("use either location_text or online_url, not both")
        return self


class CreateEventRequest(EventFieldsRequest):
    scope_unit_id: uuid.UUID
    invitee_member_ids: Annotated[list[uuid.UUID], Field(min_length=1)]


class UpdateEventRequest(BaseModel):
    """Only the fields sent are changed. The scope cannot change: sending `scope_unit_id` is
    rejected with 422."""

    type: CalendarEventType | None = None
    title: Title | None = None
    starts_at: UtcDatetime | None = None
    ends_at: UtcDatetime | None = None
    description: Description | None = None
    location_text: Location | None = None
    online_url: Url | None = None
    # Accepted only so it can be rejected explicitly (never silently ignored).
    # Hidden from the schema: it is not an accepted field.
    scope_unit_id: SkipJsonSchema[uuid.UUID | None] = None

    @model_validator(mode="after")
    def _required_not_null(self) -> Self:
        if "scope_unit_id" in self.model_fields_set:
            raise ValueError(
                "scope_unit_id cannot be changed; create a new event and cancel this one"
            )
        for field in ("type", "title", "starts_at", "ends_at"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self

    def changes(self) -> dict[str, Any]:
        changes = {field: getattr(self, field) for field in self.model_fields_set}
        if changes.get("online_url") is not None:
            changes["online_url"] = str(changes["online_url"])
        return changes


class InviteeRequest(BaseModel):
    member_id: uuid.UUID


class EventResponse(BaseModel):
    id: uuid.UUID
    type: CalendarEventType
    title: str
    description: str | None
    starts_at: datetime
    ends_at: datetime
    location_text: str | None
    online_url: str | None
    scope_unit_id: uuid.UUID
    organizer_account_id: uuid.UUID
    organizer_member_id: uuid.UUID
    state: CalendarEventState
    created_at: datetime
    updated_at: datetime
    cancelled_at: datetime | None
    # Only for the organizer and scoped managers; null for everyone else.
    invitee_member_ids: list[uuid.UUID] | None
    # The caller's own current invitation, if they are invited.
    my_invitation: "MyInvitation | None"


class MyInvitation(BaseModel):
    member_id: uuid.UUID
    invited_at: datetime


class InvitationResponse(BaseModel):
    member_id: uuid.UUID
    valid_from: datetime
    valid_to: datetime | None
    created_by_account_id: uuid.UUID
    ended_by_account_id: uuid.UUID | None


HistoryKind = Literal["created", "updated", "cancelled", "invitee_added", "invitee_removed"]


class HistoryResponse(BaseModel):
    kind: HistoryKind
    actor_account_id: uuid.UUID | None
    data: dict[str, Any]
    created_at: datetime


class TaskDueItem(BaseModel):
    """Derived from a task (read-only here; change it through the task routes)."""

    item_type: Literal["task_due"] = "task_due"
    task_id: uuid.UUID
    title: str
    due_at: datetime
    status: TaskStatus
    scope_unit_id: uuid.UUID


class EventItem(EventResponse):
    item_type: Literal["event"] = "event"


class MyCalendarResponse(BaseModel):
    starts_at: datetime
    ends_at: datetime
    events: list[EventItem]
    task_due_dates: list[TaskDueItem]


async def _call[T](call: Awaitable[T]) -> T:
    try:
        return await call
    except service.EventNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found.") from None
    except service.InvalidEventError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    except service.EventConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None


async def _event(db: DbSession, actor: service.Actor, view: service.EventView) -> EventResponse:
    """Full invitee list only for the organizer and scoped managers; invitees see their own."""
    e = view.event
    full = service.can_administer(actor, e)
    mine = await service.my_invitation(db, actor, e.id)
    return EventResponse(
        id=e.id,
        type=e.type,
        title=e.title,
        description=e.description,
        starts_at=e.starts_at,
        ends_at=e.ends_at,
        location_text=e.location_text,
        online_url=e.online_url,
        scope_unit_id=e.scope_unit_id,
        organizer_account_id=e.organizer_account_id,
        organizer_member_id=e.organizer_member_id,
        state=e.state,
        created_at=e.created_at,
        updated_at=e.updated_at,
        cancelled_at=e.cancelled_at,
        invitee_member_ids=sorted(view.invitee_member_ids, key=str) if full else None,
        my_invitation=MyInvitation(member_id=mine.member_id, invited_at=mine.valid_from)
        if mine
        else None,
    )


def _range(starts_at: datetime, ends_at: datetime) -> tuple[datetime, datetime]:
    if starts_at.tzinfo is None or ends_at.tzinfo is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "from and to must include a time zone offset."
        )
    if ends_at <= starts_at or ends_at - starts_at > MAX_RANGE:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "to must be after from, within a range of at most 366 days.",
        )
    return starts_at.astimezone(UTC), ends_at.astimezone(UTC)


@router.get("", responses=errors(422))
async def my_calendar(
    access: CurrentAccess,
    db: DbSession,
    starts_at: Annotated[datetime, Query(alias="from")],
    ends_at: Annotated[datetime, Query(alias="to")],
) -> MyCalendarResponse:
    """Accessible events and meetings overlapping [from, to), plus due dates of open tasks the
    caller created or is assigned to."""
    start, end = _range(starts_at, ends_at)
    actor = await service.actor_for(db, access)
    items = await service.my_calendar(db, actor, start, end)
    return MyCalendarResponse(
        starts_at=start,
        ends_at=end,
        events=[EventItem(**(await _event(db, actor, v)).model_dump()) for v in items.events],
        task_due_dates=[
            TaskDueItem(
                task_id=v.task.id,
                title=v.task.title,
                due_at=v.task.due_at,
                status=v.task.status,
                scope_unit_id=v.task.scope_unit_id,
            )
            for v in items.due_tasks
            if v.task.due_at is not None
        ],
    )


@router.get("/events")
async def list_events(access: CurrentAccess, db: DbSession) -> list[EventResponse]:
    actor = await service.actor_for(db, access)
    return [await _event(db, actor, v) for v in await service.list_events(db, actor)]


@router.post("/events", status_code=status.HTTP_201_CREATED, responses=errors(422))
async def create_event(
    body: CreateEventRequest, access: CurrentAccess, db: DbSession
) -> EventResponse:
    actor = await service.actor_for(db, access)
    fields = service.EventFields(
        type=body.type,
        title=body.title,
        starts_at=body.starts_at,
        ends_at=body.ends_at,
        description=body.description,
        location_text=body.location_text,
        online_url=str(body.online_url) if body.online_url else None,
    )
    view = await _call(
        service.create_event(
            db,
            actor,
            scope_unit_id=body.scope_unit_id,
            fields=fields,
            invitee_member_ids=body.invitee_member_ids,
        )
    )
    return await _event(db, actor, view)


@router.get("/events/{event_id}", responses=errors(404))
async def get_event(event_id: uuid.UUID, access: CurrentAccess, db: DbSession) -> EventResponse:
    actor = await service.actor_for(db, access)
    return await _event(db, actor, await _call(service.get_event(db, actor, event_id)))


@router.patch("/events/{event_id}", responses=errors(404, 409, 422))
async def update_event(
    event_id: uuid.UUID, body: UpdateEventRequest, access: CurrentAccess, db: DbSession
) -> EventResponse:
    actor = await service.actor_for(db, access)
    return await _event(
        db, actor, await _call(service.update_event(db, actor, event_id, body.changes()))
    )


@router.post("/events/{event_id}/cancel", responses=errors(404, 409))
async def cancel_event(event_id: uuid.UUID, access: CurrentAccess, db: DbSession) -> EventResponse:
    actor = await service.actor_for(db, access)
    return await _event(db, actor, await _call(service.cancel_event(db, actor, event_id)))


@router.post("/events/{event_id}/invitees", responses=errors(404, 409, 422))
async def add_invitee(
    event_id: uuid.UUID, body: InviteeRequest, access: CurrentAccess, db: DbSession
) -> EventResponse:
    actor = await service.actor_for(db, access)
    return await _event(
        db, actor, await _call(service.add_invitee(db, actor, event_id, body.member_id))
    )


@router.post("/events/{event_id}/invitees/{member_id}/remove", responses=errors(404, 409, 422))
async def remove_invitee(
    event_id: uuid.UUID, member_id: uuid.UUID, access: CurrentAccess, db: DbSession
) -> EventResponse:
    actor = await service.actor_for(db, access)
    return await _event(
        db, actor, await _call(service.remove_invitee(db, actor, event_id, member_id))
    )


@router.get("/events/{event_id}/invitations", responses=errors(404))
async def invitation_history(
    event_id: uuid.UUID, access: CurrentAccess, db: DbSession
) -> list[InvitationResponse]:
    actor = await service.actor_for(db, access)
    rows: list[CalendarInvitation] = await _call(service.invitations(db, actor, event_id))
    return [
        InvitationResponse(
            member_id=r.member_id,
            valid_from=r.valid_from,
            valid_to=r.valid_to,
            created_by_account_id=r.created_by_account_id,
            ended_by_account_id=r.ended_by_account_id,
        )
        for r in rows
    ]


@router.get("/events/{event_id}/history", responses=errors(404))
async def event_history(
    event_id: uuid.UUID, access: CurrentAccess, db: DbSession
) -> list[HistoryResponse]:
    actor = await service.actor_for(db, access)
    return [
        HistoryResponse(
            kind=cast(HistoryKind, h.kind),
            actor_account_id=h.actor_account_id,
            data=h.data,
            created_at=h.created_at,
        )
        for h in await _call(service.history(db, actor, event_id))
    ]
