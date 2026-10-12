"""System Admin-only, read-only access to the central audit log.

An explicit audit-only exception to "System Admin has no implicit operational access": it
exposes only the stored safe metadata and grants nothing on the source resources (tasks,
announcements, events, Members), whose own routes keep their normal checks.
There is deliberately no edit, delete, export or bulk endpoint.
"""

import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from kora_api.access.dependencies import SystemAdmin
from kora_api.audit import service as audit
from kora_api.audit.models import AuditRecord
from kora_api.core.database import DbSession
from kora_api.core.errors import AUTHENTICATED, errors

router = APIRouter(prefix="/admin/audit-records", tags=["admin"], responses=AUTHENTICATED)


class AuditRecordResponse(BaseModel):
    id: uuid.UUID
    sequence: int
    occurred_at: datetime
    action: str
    actor_account_id: uuid.UUID | None
    resource_type: str
    resource_id: uuid.UUID
    scope_unit_id: uuid.UUID | None
    before: dict[str, Any] | None
    after: dict[str, Any] | None


class AuditPageResponse(BaseModel):
    items: list[AuditRecordResponse]
    # Pass as `cursor` to get the next (older) page; null on the last page.
    next_cursor: int | None


@router.get("", responses=errors(422))
async def list_audit_records(
    _: SystemAdmin,
    db: DbSession,
    occurred_from: datetime | None = None,
    occurred_to: datetime | None = None,
    action: Annotated[str | None, Query(max_length=64)] = None,
    actor_account_id: uuid.UUID | None = None,
    resource_type: Annotated[str | None, Query(max_length=64)] = None,
    resource_id: uuid.UUID | None = None,
    scope_unit_id: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=audit.MAX_PAGE_SIZE)] = 50,
    cursor: Annotated[int | None, Query(ge=1)] = None,
) -> AuditPageResponse:
    """Newest first. The time range is [occurred_from, occurred_to), with time zone offsets."""
    for value in (occurred_from, occurred_to):
        if value is not None and value.tzinfo is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "Times must include a time zone offset."
            )
    page = await audit.list_records(
        db,
        audit.AuditFilter(
            occurred_from=occurred_from,
            occurred_to=occurred_to,
            action=action,
            actor_account_id=actor_account_id,
            resource_type=resource_type,
            resource_id=resource_id,
            scope_unit_id=scope_unit_id,
        ),
        limit=limit,
        cursor=cursor,
    )
    return AuditPageResponse(items=[_record(r) for r in page.records], next_cursor=page.next_cursor)


@router.get("/{record_id}", responses=errors(404))
async def get_audit_record(
    record_id: uuid.UUID, _: SystemAdmin, db: DbSession
) -> AuditRecordResponse:
    found = await audit.get_record(db, record_id)
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Audit record not found.")
    return _record(found)


def _record(row: AuditRecord) -> AuditRecordResponse:
    return AuditRecordResponse(
        id=row.id,
        sequence=row.sequence,
        occurred_at=row.occurred_at,
        action=row.action,
        actor_account_id=row.actor_account_id,
        resource_type=row.resource_type,
        resource_id=row.resource_id,
        scope_unit_id=row.scope_unit_id,
        before=row.before,
        after=row.after,
    )
