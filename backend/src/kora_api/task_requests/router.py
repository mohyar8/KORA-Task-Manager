import uuid
from collections.abc import Awaitable
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import AwareDatetime, BaseModel, Field, StringConstraints

from kora_api.access.dependencies import CurrentAccess
from kora_api.core.database import DbSession
from kora_api.core.errors import AUTHENTICATED, errors
from kora_api.task_requests import service
from kora_api.task_requests.models import RequestStatus, TaskRequest
from kora_api.tasks import service as tasks
from kora_api.tasks.constants import TaskPriority

router = APIRouter(prefix="/task-requests", tags=["task-requests"], responses=AUTHENTICATED)

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1_000)]


class CreateRequest(BaseModel):
    title: Title
    description: Annotated[str, StringConstraints(max_length=10_000)] | None = None
    priority: TaskPriority | None = None
    due_at: AwareDatetime | None = None
    # The unit asking: the caller's Administration, or KORA for the leadership.
    from_unit_id: uuid.UUID
    to_unit_id: uuid.UUID


class AcceptRequest(BaseModel):
    # Members of the target Administration who will do the work.
    assignee_member_ids: Annotated[list[uuid.UUID], Field(min_length=1)]


class RejectRequest(BaseModel):
    reason: Reason


class RequestResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    priority: TaskPriority | None
    due_at: datetime | None
    from_unit_id: uuid.UUID
    to_unit_id: uuid.UUID
    requested_by_member_id: uuid.UUID
    status: RequestStatus
    decided_by_member_id: uuid.UUID | None
    decided_at: datetime | None
    rejection_reason: str | None
    resulting_task_id: uuid.UUID | None
    created_at: datetime


def _response(r: TaskRequest) -> RequestResponse:
    return RequestResponse(
        id=r.id,
        title=r.title,
        description=r.description,
        priority=r.priority,
        due_at=r.due_at,
        from_unit_id=r.from_unit_id,
        to_unit_id=r.to_unit_id,
        requested_by_member_id=r.requested_by_member_id,
        status=r.status,
        decided_by_member_id=r.decided_by_member_id,
        decided_at=r.decided_at,
        rejection_reason=r.rejection_reason,
        resulting_task_id=r.resulting_task_id,
        created_at=r.created_at,
    )


async def _call(call: Awaitable[TaskRequest]) -> RequestResponse:
    try:
        return _response(await call)
    except service.RequestNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found.") from None
    except service.InvalidRequestError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    except service.RequestConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None


@router.get("")
async def list_requests(
    access: CurrentAccess,
    db: DbSession,
    box: Literal["incoming", "outgoing"],
    status: RequestStatus | None = None,
) -> list[RequestResponse]:
    """`incoming`: sent to an Administration the caller may answer for. `outgoing`: sent from a
    unit the caller may send for, or by the caller. Newest first."""
    actor = await tasks.actor_for(db, access)
    return [_response(r) for r in await service.list_requests(db, actor, box, status)]


@router.post("", status_code=status.HTTP_201_CREATED, responses=errors(422))
async def create_request(
    body: CreateRequest, access: CurrentAccess, db: DbSession
) -> RequestResponse:
    actor = await tasks.actor_for(db, access)
    return await _call(
        service.create_request(
            db,
            actor,
            from_unit_id=body.from_unit_id,
            to_unit_id=body.to_unit_id,
            title=body.title,
            description=body.description,
            priority=body.priority,
            due_at=body.due_at,
        )
    )


@router.get("/{request_id}", responses=errors(404))
async def get_request(
    request_id: uuid.UUID, access: CurrentAccess, db: DbSession
) -> RequestResponse:
    actor = await tasks.actor_for(db, access)
    return await _call(service.get_request(db, actor, request_id))


@router.post("/{request_id}/accept", responses=errors(404, 409, 422))
async def accept_request(
    request_id: uuid.UUID, body: AcceptRequest, access: CurrentAccess, db: DbSession
) -> RequestResponse:
    """Accept and create the real task in the target Administration (the caller is its creator)."""
    actor = await tasks.actor_for(db, access)
    return await _call(service.accept_request(db, actor, request_id, body.assignee_member_ids))


@router.post("/{request_id}/reject", responses=errors(404, 409, 422))
async def reject_request(
    request_id: uuid.UUID, body: RejectRequest, access: CurrentAccess, db: DbSession
) -> RequestResponse:
    actor = await tasks.actor_for(db, access)
    return await _call(service.reject_request(db, actor, request_id, body.reason))


@router.post("/{request_id}/withdraw", responses=errors(404, 409))
async def withdraw_request(
    request_id: uuid.UUID, access: CurrentAccess, db: DbSession
) -> RequestResponse:
    """The sender takes back a request that is still pending."""
    actor = await tasks.actor_for(db, access)
    return await _call(service.withdraw_request(db, actor, request_id))
