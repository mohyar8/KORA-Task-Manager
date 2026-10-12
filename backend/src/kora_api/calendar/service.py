"""Calendar rules. Every operation checks the caller's access itself.

- Create: an active Member with `calendar.create` at the scope; one or more invitees, each an
  active Member within the scope (Team or role unit).
- View: the active organizer, current invitees (even after they move scope) and holders of
  `calendar.manage` at the event scope. Removed invitees lose access.
- Edit, cancel, manage invitations: the active organizer or a scoped `calendar.manage` holder.
  Cancelled events are read-only. Nothing is hard-deleted; history is append-only.
"""

import enum
import uuid
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import ColumnElement, and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from kora_api.access.dependencies import AccessContext
from kora_api.access.evaluation import AccessDeniedError
from kora_api.access.org_facts import UnitInfo
from kora_api.access.permissions import Permission
from kora_api.audit import service as audit
from kora_api.calendar import audit_actions
from kora_api.calendar.models import (
    CalendarEvent,
    CalendarEventHistory,
    CalendarEventState,
    CalendarEventType,
    CalendarInvitation,
)
from kora_api.core import clock
from kora_api.notifications import service as notifications
from kora_api.notifications.models import NotificationCategory
from kora_api.organization import queries as org
from kora_api.tasks import service as tasks

CREATE = Permission.CALENDAR_CREATE
MANAGE = Permission.CALENDAR_MANAGE
NOTIFICATION_SOURCE = "calendar_event"
EDITABLE = ("type", "title", "description", "starts_at", "ends_at", "location_text", "online_url")
# Edited fields whose values are audited; the others are recorded only as changed.
AUDITED_FIELDS = ("type", "title", "starts_at", "ends_at")


class EventNotFoundError(Exception):
    pass


class InvalidEventError(Exception):
    """The request breaks a calendar rule (422)."""


class EventConflictError(Exception):
    """The event's state prevents the operation (409)."""


@dataclass(frozen=True)
class Actor:
    access: AccessContext
    member: org.MemberPosition | None  # set only for an active Member

    @property
    def account_id(self) -> uuid.UUID:
        return self.access.account.id

    @property
    def member_id(self) -> uuid.UUID | None:
        return self.member.member_id if self.member else None


@dataclass(frozen=True)
class EventView:
    event: CalendarEvent
    invitee_member_ids: frozenset[uuid.UUID]


@dataclass(frozen=True)
class EventFields:
    type: CalendarEventType
    title: str
    starts_at: datetime
    ends_at: datetime
    description: str | None = None
    location_text: str | None = None
    online_url: str | None = None


async def actor_for(db: AsyncSession, access: AccessContext) -> Actor:
    position = await org.member_for_account(db, access.account.id)
    return Actor(access, position if position is not None and position.active else None)


# --- Access -------------------------------------------------------------------------------------


def _is_organizer(actor: Actor, event: CalendarEvent) -> bool:
    return actor.member_id is not None and actor.member_id == event.organizer_member_id


def _is_manager(actor: Actor, event: CalendarEvent) -> bool:
    return actor.access.snapshot.allows(MANAGE, event.scope_unit_id)


def can_view(actor: Actor, event: CalendarEvent, invitees: frozenset[uuid.UUID]) -> bool:
    invited = actor.member_id is not None and actor.member_id in invitees
    return _is_organizer(actor, event) or invited or _is_manager(actor, event)


def can_administer(actor: Actor, event: CalendarEvent) -> bool:
    """Organizer or scoped manager: may change the event and see all invitations."""
    return _is_organizer(actor, event) or _is_manager(actor, event)


async def invitees_of(
    db: AsyncSession, event_ids: Iterable[uuid.UUID]
) -> dict[uuid.UUID, frozenset[uuid.UUID]]:
    ids = set(event_ids)
    result: dict[uuid.UUID, set[uuid.UUID]] = {event_id: set() for event_id in ids}
    if ids:
        rows = await db.execute(
            select(CalendarInvitation.event_id, CalendarInvitation.member_id).where(
                CalendarInvitation.event_id.in_(ids), CalendarInvitation.valid_to.is_(None)
            )
        )
        for event_id, member_id in rows:
            result[event_id].add(member_id)
    return {event_id: frozenset(members) for event_id, members in result.items()}


async def _load_visible(
    db: AsyncSession, actor: Actor, event_id: uuid.UUID, *, lock: bool = False
) -> EventView:
    event = await db.get(CalendarEvent, event_id, with_for_update=lock)
    if event is None:
        raise EventNotFoundError
    invitees = (await invitees_of(db, [event_id]))[event_id]
    if not can_view(actor, event, invitees):
        raise AccessDeniedError(MANAGE, event.scope_unit_id)
    return EventView(event, invitees)


async def _load_administrable(db: AsyncSession, actor: Actor, event_id: uuid.UUID) -> EventView:
    view = await _load_visible(db, actor, event_id, lock=True)
    if not can_administer(actor, view.event):
        raise AccessDeniedError(MANAGE, view.event.scope_unit_id)
    if view.event.state == CalendarEventState.CANCELLED:
        raise EventConflictError("The event is cancelled.")
    return view


# --- Reads --------------------------------------------------------------------------------------


async def get_event(db: AsyncSession, actor: Actor, event_id: uuid.UUID) -> EventView:
    return await _load_visible(db, actor, event_id)


async def list_events(
    db: AsyncSession,
    actor: Actor,
    *,
    starts_at: datetime | None = None,
    ends_at: datetime | None = None,
) -> list[EventView]:
    """Accessible events (optionally overlapping a range); inaccessible ones are omitted."""
    conditions: list[ColumnElement[bool]] = [
        CalendarEvent.scope_unit_id.in_(actor.access.snapshot.units_with(MANAGE))
    ]
    if actor.member_id is not None:
        invited = select(CalendarInvitation.event_id).where(
            CalendarInvitation.member_id == actor.member_id, CalendarInvitation.valid_to.is_(None)
        )
        conditions += [
            CalendarEvent.organizer_member_id == actor.member_id,
            CalendarEvent.id.in_(invited),
        ]
    stmt = select(CalendarEvent).where(or_(*conditions))
    if starts_at is not None and ends_at is not None:
        stmt = stmt.where(
            and_(CalendarEvent.starts_at < ends_at, CalendarEvent.ends_at > starts_at)
        )
    events = list(await db.scalars(stmt.order_by(CalendarEvent.starts_at)))
    invitees = await invitees_of(db, (e.id for e in events))
    return [EventView(e, invitees[e.id]) for e in events if can_view(actor, e, invitees[e.id])]


async def my_invitation(
    db: AsyncSession, actor: Actor, event_id: uuid.UUID
) -> CalendarInvitation | None:
    """The caller's own current invitation, if any (all an invitee may see of invitations)."""
    if actor.member_id is None:
        return None
    return await db.scalar(
        select(CalendarInvitation).where(
            CalendarInvitation.event_id == event_id,
            CalendarInvitation.member_id == actor.member_id,
            CalendarInvitation.valid_to.is_(None),
        )
    )


async def invitations(
    db: AsyncSession, actor: Actor, event_id: uuid.UUID
) -> list[CalendarInvitation]:
    """Full invitation history (current and removed), for the organizer and scoped managers."""
    view = await _load_visible(db, actor, event_id)
    if not can_administer(actor, view.event):
        raise AccessDeniedError(MANAGE, view.event.scope_unit_id)
    return list(
        await db.scalars(
            select(CalendarInvitation)
            .where(CalendarInvitation.event_id == event_id)
            .order_by(CalendarInvitation.valid_from, CalendarInvitation.member_id)
        )
    )


async def history(
    db: AsyncSession, actor: Actor, event_id: uuid.UUID
) -> list[CalendarEventHistory]:
    await _load_visible(db, actor, event_id)
    return list(
        await db.scalars(
            select(CalendarEventHistory)
            .where(CalendarEventHistory.event_id == event_id)
            .order_by(CalendarEventHistory.seq)
        )
    )


@dataclass(frozen=True)
class CalendarItems:
    events: list[EventView]
    due_tasks: list[tasks.TaskView]


async def my_calendar(
    db: AsyncSession, actor: Actor, starts_at: datetime, ends_at: datetime
) -> CalendarItems:
    """Accessible events overlapping the range plus derived due dates of open tasks the caller
    created or is assigned to. Task data is read live from tasks; nothing is copied."""
    return CalendarItems(
        events=await list_events(db, actor, starts_at=starts_at, ends_at=ends_at),
        due_tasks=await tasks.due_tasks(db, actor.access, starts_at, ends_at),
    )


# --- Changes ------------------------------------------------------------------------------------


async def create_event(
    db: AsyncSession,
    actor: Actor,
    *,
    scope_unit_id: uuid.UUID,
    fields: EventFields,
    invitee_member_ids: Sequence[uuid.UUID],
) -> EventView:
    if actor.member is None:
        raise AccessDeniedError(CREATE, scope_unit_id)  # only active Members organize
    actor.access.snapshot.require(CREATE, scope_unit_id)
    units = await org.current_units(db)
    unit = units.get(scope_unit_id)
    if unit is None or not unit.active:
        raise InvalidEventError("Scope unit not found or not active.")
    _validate(fields.starts_at, fields.ends_at, fields.location_text, fields.online_url)
    if not invitee_member_ids:
        raise InvalidEventError("Invite at least one Member.")
    await _require_eligible(db, invitee_member_ids, scope_unit_id, units)

    now = clock.utcnow()
    event = CalendarEvent(
        type=fields.type,
        title=fields.title,
        description=fields.description,
        starts_at=fields.starts_at,
        ends_at=fields.ends_at,
        location_text=fields.location_text,
        online_url=fields.online_url,
        scope_unit_id=scope_unit_id,
        organizer_account_id=actor.account_id,
        organizer_member_id=actor.member.member_id,
        state=CalendarEventState.SCHEDULED,
        created_at=now,
        updated_at=now,
    )
    db.add(event)
    await db.flush()
    for member_id in invitee_member_ids:
        _invite(db, event.id, member_id, actor.account_id)
    _record(db, event.id, "created", actor.account_id, fields=_snapshot(event))
    for member_id in invitee_member_ids:
        _record(db, event.id, "invitee_added", actor.account_id, member_id=member_id)
    await _notify(db, event, set(invitee_member_ids), "invited", actor.account_id)
    audit.record(
        db,
        audit_actions.EVENT_CREATED,
        actor_account_id=actor.account_id,
        resource_id=event.id,
        scope_unit_id=scope_unit_id,
        after={
            "type": event.type,
            "title": event.title,
            "starts_at": event.starts_at,
            "ends_at": event.ends_at,
            "state": event.state,
            "invitee_member_ids": sorted(invitee_member_ids, key=str),
        },
    )
    await db.commit()
    return EventView(event, frozenset(invitee_member_ids))


async def update_event(
    db: AsyncSession, actor: Actor, event_id: uuid.UUID, changes: Mapping[str, Any]
) -> EventView:
    view = await _load_administrable(db, actor, event_id)
    event = view.event
    merged = {field: changes.get(field, getattr(event, field)) for field in EDITABLE}
    if merged["title"] is None or merged["type"] is None:
        raise InvalidEventError("Title and type are required.")
    _validate(merged["starts_at"], merged["ends_at"], merged["location_text"], merged["online_url"])
    diff = {
        field: [_jsonable(getattr(event, field)), _jsonable(merged[field])]
        for field in EDITABLE
        if merged[field] != getattr(event, field)
    }
    if diff:
        previous = {field: getattr(event, field) for field in diff if field in AUDITED_FIELDS}
        for field in diff:
            setattr(event, field, merged[field])
        event.updated_at = clock.utcnow()
        _record(db, event.id, "updated", actor.account_id, changes=diff)
        await _notify(db, event, set(view.invitee_member_ids), "updated", actor.account_id)
        audit.record(
            db,
            audit_actions.EVENT_UPDATED,
            actor_account_id=actor.account_id,
            resource_id=event.id,
            scope_unit_id=event.scope_unit_id,
            before=previous,
            after={"changed_fields": list(diff)}
            | {field: getattr(event, field) for field in previous},
        )
        await db.commit()
    return view


async def cancel_event(db: AsyncSession, actor: Actor, event_id: uuid.UUID) -> EventView:
    """Cancel: the event, its invitations and history stay; it becomes read-only."""
    view = await _load_administrable(db, actor, event_id)
    event = view.event
    now = clock.utcnow()
    event.state = CalendarEventState.CANCELLED
    event.cancelled_at = now
    event.cancelled_by_account_id = actor.account_id
    event.updated_at = now
    _record(db, event.id, "cancelled", actor.account_id)
    await _notify(db, event, set(view.invitee_member_ids), "cancelled", actor.account_id)
    audit.record(
        db,
        audit_actions.EVENT_CANCELLED,
        actor_account_id=actor.account_id,
        resource_id=event.id,
        scope_unit_id=event.scope_unit_id,
        before={"state": CalendarEventState.SCHEDULED},
        after={"state": event.state},
    )
    await db.commit()
    return view


async def add_invitee(
    db: AsyncSession, actor: Actor, event_id: uuid.UUID, member_id: uuid.UUID
) -> EventView:
    view = await _load_administrable(db, actor, event_id)
    if member_id in view.invitee_member_ids:
        raise EventConflictError("Already invited.")
    await _require_eligible(db, [member_id], view.event.scope_unit_id, await org.current_units(db))
    _invite(db, event_id, member_id, actor.account_id)
    _record(db, event_id, "invitee_added", actor.account_id, member_id=member_id)
    await _notify(db, view.event, {member_id}, "invited", actor.account_id)
    audit.record(
        db,
        audit_actions.INVITEE_ADDED,
        actor_account_id=actor.account_id,
        resource_id=event_id,
        scope_unit_id=view.event.scope_unit_id,
        after={"member_id": member_id},
    )
    await db.commit()
    return EventView(view.event, view.invitee_member_ids | {member_id})


async def remove_invitee(
    db: AsyncSession, actor: Actor, event_id: uuid.UUID, member_id: uuid.UUID
) -> EventView:
    """Revoke the invitee's access silently (no notification); history is kept."""
    view = await _load_administrable(db, actor, event_id)
    if member_id not in view.invitee_member_ids:
        raise EventNotFoundError
    if len(view.invitee_member_ids) == 1:
        raise InvalidEventError("An event needs at least one invitee.")
    invitation = await db.scalar(
        select(CalendarInvitation)
        .where(
            CalendarInvitation.event_id == event_id,
            CalendarInvitation.member_id == member_id,
            CalendarInvitation.valid_to.is_(None),
        )
        .with_for_update()
    )
    assert invitation is not None
    invitation.valid_to = clock.utcnow()
    invitation.ended_by_account_id = actor.account_id
    _record(db, event_id, "invitee_removed", actor.account_id, member_id=member_id)
    audit.record(
        db,
        audit_actions.INVITEE_REMOVED,
        actor_account_id=actor.account_id,
        resource_id=event_id,
        scope_unit_id=view.event.scope_unit_id,
        before={"member_id": member_id},
        after={"member_id": None},
    )
    await db.commit()
    return EventView(view.event, view.invitee_member_ids - {member_id})


async def visible_event_ids(
    db: AsyncSession, access: AccessContext, source_ids: set[uuid.UUID]
) -> set[uuid.UUID]:
    """Notification source checker: events among `source_ids` the caller can see now."""
    actor = await actor_for(db, access)
    events = list(await db.scalars(select(CalendarEvent).where(CalendarEvent.id.in_(source_ids))))
    invitees = await invitees_of(db, (e.id for e in events))
    return {e.id for e in events if can_view(actor, e, invitees[e.id])}


# --- Helpers ------------------------------------------------------------------------------------


def _validate(
    starts_at: datetime, ends_at: datetime, location_text: str | None, online_url: str | None
) -> None:
    if starts_at.tzinfo is None or ends_at.tzinfo is None:
        raise InvalidEventError("Times must include a time zone offset.")
    if ends_at <= starts_at:
        raise InvalidEventError("The end must be after the start.")
    if location_text is not None and online_url is not None:
        raise InvalidEventError("Use either a physical location or an online URL, not both.")


async def _require_eligible(
    db: AsyncSession,
    member_ids: Sequence[uuid.UUID],
    scope_unit_id: uuid.UUID,
    units: Mapping[uuid.UUID, UnitInfo],
) -> None:
    if len(set(member_ids)) != len(member_ids):
        raise InvalidEventError("Invitees must be distinct.")
    positions = await org.member_positions(db, member_ids)
    invalid = [
        str(m)
        for m in member_ids
        if m not in positions or not org.member_within_scope(positions[m], scope_unit_id, units)
    ]
    if invalid:
        raise InvalidEventError(
            f"Invitees must be active Members within the event scope: {', '.join(invalid)}."
        )


def _invite(
    db: AsyncSession, event_id: uuid.UUID, member_id: uuid.UUID, actor_account_id: uuid.UUID
) -> None:
    db.add(
        CalendarInvitation(
            event_id=event_id,
            member_id=member_id,
            valid_from=clock.utcnow(),
            created_by_account_id=actor_account_id,
        )
    )


def _record(
    db: AsyncSession, event_id: uuid.UUID, kind: str, actor_account_id: uuid.UUID, **data: Any
) -> None:
    db.add(
        CalendarEventHistory(
            event_id=event_id,
            kind=kind,
            actor_account_id=actor_account_id,
            data={key: _jsonable(value) for key, value in data.items()},
            created_at=clock.utcnow(),
        )
    )


def _snapshot(event: CalendarEvent) -> dict[str, Any]:
    return {field: _jsonable(getattr(event, field)) for field in EDITABLE} | {
        "scope_unit_id": str(event.scope_unit_id)
    }


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}  # pyright: ignore[reportUnknownVariableType]
    return value


async def _notify(
    db: AsyncSession,
    event: CalendarEvent,
    member_ids: set[uuid.UUID],
    kind: str,
    actor_account_id: uuid.UUID,
) -> None:
    positions = await org.member_positions(db, member_ids)
    await notifications.notify(
        db,
        recipient_account_ids={p.account_id for p in positions.values()},
        actor_account_id=actor_account_id,
        category=NotificationCategory.CALENDAR_EVENT,
        source_type=NOTIFICATION_SOURCE,
        source_id=event.id,
        kind=kind,
        summary=event.title,
    )
