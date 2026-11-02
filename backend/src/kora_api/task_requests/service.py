"""Task-request rules. Each operation checks the caller's access itself.

- create: an active Member with `task_request.create` at the sending unit (an Administration, or
  KORA for the leadership), to another active Administration.
- respond (accept / reject): `task_request.respond` at the target Administration.
- withdraw: the person who sent it, while it is pending.
- view: whoever may respond, whoever may send from that unit, or the sender.
Accepting creates the real task in the target Administration, in the same transaction; the sender
may then read and comment on it (never administer it).
"""

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import ColumnElement, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from kora_api.access.dependencies import AccessContext
from kora_api.access.evaluation import AccessDeniedError
from kora_api.access.permissions import Permission
from kora_api.audit import service as audit
from kora_api.core import clock
from kora_api.notifications import service as notifications
from kora_api.notifications.models import NotificationCategory as Category
from kora_api.organization import queries as org
from kora_api.task_requests import audit_actions
from kora_api.task_requests.models import RequestStatus, TaskRequest
from kora_api.tasks import service as tasks
from kora_api.tasks.constants import TaskPriority
from kora_api.tasks.service import TaskActor

CREATE, RESPOND = Permission.TASK_REQUEST_CREATE, Permission.TASK_REQUEST_RESPOND
SOURCE = "task_request"
SENDER_KINDS = ("administration", "organization")


class RequestNotFoundError(Exception):
    pass


class InvalidRequestError(Exception):
    """The request breaks a rule (422)."""


class RequestConflictError(Exception):
    """The request's current state prevents the operation (409)."""


def can_view(actor: TaskActor, request: TaskRequest) -> bool:
    return (
        actor.snapshot.allows(RESPOND, request.to_unit_id)
        or actor.snapshot.allows(CREATE, request.from_unit_id)
        or (actor.member_id is not None and actor.member_id == request.requested_by_member_id)
    )


async def _lock(db: AsyncSession, actor: TaskActor, request_id: uuid.UUID) -> TaskRequest:
    request = await db.scalar(
        select(TaskRequest).where(TaskRequest.id == request_id).with_for_update()
    )
    if request is None:
        raise RequestNotFoundError
    if not can_view(actor, request):
        raise AccessDeniedError(RESPOND, request.to_unit_id)
    return request


async def get_request(db: AsyncSession, actor: TaskActor, request_id: uuid.UUID) -> TaskRequest:
    request = await db.get(TaskRequest, request_id)
    if request is None:
        raise RequestNotFoundError
    if not can_view(actor, request):
        raise AccessDeniedError(RESPOND, request.to_unit_id)
    return request


async def list_requests(
    db: AsyncSession, actor: TaskActor, box: str, status: RequestStatus | None
) -> list[TaskRequest]:
    snapshot = actor.snapshot
    conditions: list[ColumnElement[bool]]
    if box == "incoming":
        conditions = [TaskRequest.to_unit_id.in_(snapshot.units_with(RESPOND))]
    else:
        conditions = [TaskRequest.from_unit_id.in_(snapshot.units_with(CREATE))]
        if actor.member_id is not None:
            conditions.append(TaskRequest.requested_by_member_id == actor.member_id)
    stmt = select(TaskRequest).where(or_(*conditions)).order_by(TaskRequest.created_at.desc())
    if status is not None:
        stmt = stmt.where(TaskRequest.status == status)
    return list(await db.scalars(stmt))


async def _responders(db: AsyncSession, to_unit_id: uuid.UUID) -> set[uuid.UUID]:
    """Accounts to tell about a request: the Administration's Manager(s); with none active, the
    Event Leader and Deputy (who hold the permission over everything)."""
    units = await org.current_units(db)
    positions = await org.active_positions(db)
    managers = {
        p.account_id
        for p in positions
        if p.role_key == "administration_manager" and org.owns_scope(p, to_unit_id, units)
    }
    if managers:
        return managers
    top = ("event_project_leader", "deputy_leader")
    return {p.account_id for p in positions if p.role_key in top}


async def _notify(
    db: AsyncSession,
    recipients: set[uuid.UUID],
    request: TaskRequest,
    kind: str,
    actor_account_id: uuid.UUID,
) -> None:
    await notifications.notify(
        db,
        recipient_account_ids=recipients,
        actor_account_id=actor_account_id,
        category=Category.TASK_REQUEST,
        source_type=SOURCE,
        source_id=request.id,
        kind=kind,
        summary=request.title,
    )


async def create_request(
    db: AsyncSession,
    actor: TaskActor,
    *,
    from_unit_id: uuid.UUID,
    to_unit_id: uuid.UUID,
    title: str,
    description: str | None,
    priority: TaskPriority | None,
    due_at: datetime | None,
) -> TaskRequest:
    if actor.member is None:
        raise AccessDeniedError(CREATE, from_unit_id)  # only active Members send requests
    actor.snapshot.require(CREATE, from_unit_id)
    units = await org.current_units(db)
    sender, target = units.get(from_unit_id), units.get(to_unit_id)
    if sender is None or not sender.active or sender.kind not in SENDER_KINDS:
        raise InvalidRequestError("The sending unit must be an active Administration or KORA.")
    if target is None or not target.active or target.kind != "administration":
        raise InvalidRequestError("Requests go to an active Administration.")
    if from_unit_id == to_unit_id:
        raise InvalidRequestError("A request must go to a different Administration.")
    assert actor.member_id is not None
    request = TaskRequest(
        title=title,
        description=description,
        priority=priority,
        due_at=due_at,
        from_unit_id=from_unit_id,
        to_unit_id=to_unit_id,
        requested_by_member_id=actor.member_id,
        requested_by_account_id=actor.account_id,
        status=RequestStatus.PENDING,
        created_at=clock.utcnow(),
    )
    db.add(request)
    await db.flush()
    audit.record(
        db,
        audit_actions.REQUEST_CREATED,
        actor_account_id=actor.account_id,
        resource_id=request.id,
        scope_unit_id=to_unit_id,
        after={
            "title": title,
            "priority": priority,
            "due_at": due_at,
            "from_unit_id": from_unit_id,
            "to_unit_id": to_unit_id,
        },
    )
    await _notify(db, await _responders(db, to_unit_id), request, "received", actor.account_id)
    await db.commit()
    return request


def _pending(request: TaskRequest) -> None:
    if request.status != RequestStatus.PENDING:
        raise RequestConflictError(f"The request is already {request.status.value}.")


async def accept_request(
    db: AsyncSession,
    actor: TaskActor,
    request_id: uuid.UUID,
    assignee_member_ids: Sequence[uuid.UUID],
) -> TaskRequest:
    request = await _lock(db, actor, request_id)
    actor.snapshot.require(RESPOND, request.to_unit_id)
    _pending(request)
    units = await org.current_units(db)
    target = units.get(request.to_unit_id)
    if target is None or not target.active:
        raise RequestConflictError("The target Administration is no longer active.")
    await tasks.require_creator(db, actor, request.to_unit_id)
    try:
        await tasks.require_eligible(db, assignee_member_ids, request.to_unit_id, units)
    except tasks.InvalidTaskError as exc:
        raise InvalidRequestError(str(exc)) from None
    view = await tasks.insert_task(
        db,
        scope_unit_id=request.to_unit_id,
        fields=tasks.TaskFields(
            request.title, request.description, request.priority, request.due_at
        ),
        creator=actor,
        assignee_member_ids=assignee_member_ids,
        requested_by_member_id=request.requested_by_member_id,
        requested_from_unit_id=request.from_unit_id,
        event_data={"request_id": str(request.id)},
    )
    tasks.audit_created(db, view, actor.account_id)
    request.status = RequestStatus.ACCEPTED
    request.decided_by_member_id = actor.member_id
    request.decided_at = clock.utcnow()
    request.resulting_task_id = view.task.id
    audit.record(
        db,
        audit_actions.REQUEST_ACCEPTED,
        actor_account_id=actor.account_id,
        resource_id=request.id,
        scope_unit_id=request.to_unit_id,
        after={
            "status": request.status,
            "resulting_task_id": view.task.id,
            "assignee_member_ids": sorted(assignee_member_ids, key=str),
        },
    )
    await _notify(db, {request.requested_by_account_id}, request, "accepted", actor.account_id)
    await db.commit()
    return request


async def reject_request(
    db: AsyncSession, actor: TaskActor, request_id: uuid.UUID, reason: str
) -> TaskRequest:
    request = await _lock(db, actor, request_id)
    actor.snapshot.require(RESPOND, request.to_unit_id)
    _pending(request)
    request.status = RequestStatus.REJECTED
    request.decided_by_member_id = actor.member_id
    request.decided_at = clock.utcnow()
    request.rejection_reason = reason
    audit.record(
        db,
        audit_actions.REQUEST_REJECTED,
        actor_account_id=actor.account_id,
        resource_id=request.id,
        scope_unit_id=request.to_unit_id,
        after={"status": request.status},
    )
    await _notify(db, {request.requested_by_account_id}, request, "rejected", actor.account_id)
    await db.commit()
    return request


async def withdraw_request(
    db: AsyncSession, actor: TaskActor, request_id: uuid.UUID
) -> TaskRequest:
    request = await _lock(db, actor, request_id)
    if actor.member_id is None or actor.member_id != request.requested_by_member_id:
        raise AccessDeniedError(CREATE, request.from_unit_id)
    _pending(request)
    request.status = RequestStatus.WITHDRAWN
    request.decided_by_member_id = actor.member_id
    request.decided_at = clock.utcnow()
    audit.record(
        db,
        audit_actions.REQUEST_WITHDRAWN,
        actor_account_id=actor.account_id,
        resource_id=request.id,
        scope_unit_id=request.to_unit_id,
        after={"status": request.status},
    )
    await _notify(
        db, await _responders(db, request.to_unit_id), request, "withdrawn", actor.account_id
    )
    await db.commit()
    return request


async def visible_request_ids(
    db: AsyncSession, access: AccessContext, source_ids: set[uuid.UUID]
) -> set[uuid.UUID]:
    """Notification source checker: the requests among `source_ids` the caller can view now."""
    actor = await tasks.actor_for(db, access)
    rows = await db.scalars(select(TaskRequest).where(TaskRequest.id.in_(source_ids)))
    return {r.id for r in rows if can_view(actor, r)}
