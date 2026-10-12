"""Audit tests reuse the populated organization from the task tests."""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kora_api.audit.models import AuditRecord
from tests.calendar.conftest import new_event as new_event  # re-exported fixture
from tests.tasks.conftest import login as login  # re-exported fixture
from tests.tasks.conftest import new_task as new_task  # re-exported fixture
from tests.tasks.conftest import world as world  # re-exported fixture

AUDIT = "/api/v1/admin/audit-records"


async def audit_records(
    db: AsyncSession, action: str | None = None, resource_id: Any = None
) -> list[AuditRecord]:
    """Records in insertion order, optionally filtered."""
    stmt = select(AuditRecord).order_by(AuditRecord.sequence)
    if action is not None:
        stmt = stmt.where(AuditRecord.action == action)
    if resource_id is not None:
        stmt = stmt.where(AuditRecord.resource_id == uuid.UUID(str(resource_id)))
    return list(await db.scalars(stmt))


async def only(db: AsyncSession, action: str, resource_id: Any = None) -> AuditRecord:
    """The single record of `action` (asserts there is exactly one)."""
    found = await audit_records(db, action, resource_id)
    assert len(found) == 1, [(r.action, r.after) for r in found]
    return found[0]
