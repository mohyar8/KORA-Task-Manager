"""Recording and reading audit records.

Privacy: every action declares the only metadata keys it may store, and keys that look like
secrets, free-text content or contact details are rejected outright, so complete models or
request payloads can never be written. Values are limited to short scalars (strings are cut to
`MAX_TEXT_LENGTH`) and lists of them.
"""

import enum
import re
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kora_api.audit.models import AuditRecord
from kora_api.core import clock

MAX_TEXT_LENGTH = 120
MAX_PAGE_SIZE = 200

# Metadata keys containing any of these are refused, whatever the action declares.
FORBIDDEN_KEY_PARTS = (
    "password",
    "hash",
    "token",
    "csrf",
    "secret",
    "credential",
    "body",
    "description",
    "email",
    "phone",
    "university",
    "major",
    "academic",
    "full_name",
    "location",
    "url",
)
# ...unless the key names a flag or timestamp about the value, never the value itself
# (e.g. `password_is_temporary`, `body_changed`, `temporary_password_expires_at`).
STATE_KEY_SUFFIXES = ("_is_temporary", "_changed", "_changed_at", "_expires_at")
_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")

type Scalar = str | int | bool | uuid.UUID | datetime | enum.Enum | None
type Value = Scalar | Sequence[Scalar]
type Metadata = Mapping[str, Value]


class UnsafeAuditMetadataError(ValueError):
    """A caller tried to store metadata outside the action's allowlist (a programming error)."""


@dataclass(frozen=True)
class AuditAction:
    """An auditable action, e.g. `task.created`, with the metadata keys it may store."""

    key: str
    resource_type: str
    fields: frozenset[str]

    def __post_init__(self) -> None:
        if not _KEY_PATTERN.match(self.key) or len(self.key) > 64:
            raise ValueError(f"Invalid audit action key {self.key!r}.")
        unsafe = sorted(f for f in self.fields if not is_safe_key(f))
        if unsafe:
            raise UnsafeAuditMetadataError(f"{self.key}: forbidden metadata keys {unsafe}.")


def is_safe_key(key: str) -> bool:
    return key.endswith(STATE_KEY_SUFFIXES) or not any(p in key for p in FORBIDDEN_KEY_PARTS)


def action(key: str, resource_type: str, *fields: str) -> AuditAction:
    return AuditAction(key, resource_type, frozenset(fields))


def record(
    db: AsyncSession,
    audit_action: AuditAction,
    *,
    actor_account_id: uuid.UUID | None,
    resource_id: uuid.UUID,
    scope_unit_id: uuid.UUID | None = None,
    before: Metadata | None = None,
    after: Metadata | None = None,
) -> None:
    """Add one audit record to the caller's transaction. Does not flush or commit, so the
    record commits or rolls back together with the change it describes."""
    db.add(
        AuditRecord(
            occurred_at=clock.utcnow(),
            action=audit_action.key,
            actor_account_id=actor_account_id,
            resource_type=audit_action.resource_type,
            resource_id=resource_id,
            scope_unit_id=scope_unit_id,
            before=_safe(audit_action, before),
            after=_safe(audit_action, after),
        )
    )


def _safe(audit_action: AuditAction, metadata: Metadata | None) -> dict[str, Any] | None:
    if metadata is None:
        return None
    unknown = sorted(set(metadata) - audit_action.fields)
    if unknown:
        raise UnsafeAuditMetadataError(f"{audit_action.key}: keys not allowlisted {unknown}.")
    return {key: _value(value) for key, value in metadata.items()}


def _value(value: Value) -> Any:
    if isinstance(value, list | tuple):
        return [_scalar(item) for item in value]
    return _scalar(value)


def _scalar(value: object) -> Any:
    """Short JSON scalars only; anything else (dicts, models, nested lists) is refused."""
    if isinstance(value, enum.Enum):
        value = value.value
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, str):
        return value if len(value) <= MAX_TEXT_LENGTH else value[: MAX_TEXT_LENGTH - 1] + "…"
    if value is None or isinstance(value, int | bool):
        return value
    raise UnsafeAuditMetadataError(f"Unsupported audit value type {type(value).__name__}.")


# --- Reading (System Admin only; enforced by the route) ----------------------------------------


@dataclass(frozen=True)
class AuditFilter:
    occurred_from: datetime | None = None
    occurred_to: datetime | None = None
    action: str | None = None
    actor_account_id: uuid.UUID | None = None
    resource_type: str | None = None
    resource_id: uuid.UUID | None = None
    scope_unit_id: uuid.UUID | None = None


@dataclass(frozen=True)
class AuditPage:
    records: list[AuditRecord]
    next_cursor: int | None


async def list_records(
    db: AsyncSession, filters: AuditFilter, *, limit: int, cursor: int | None = None
) -> AuditPage:
    """Newest first. `cursor` is the `sequence` of the last record of the previous page.

    Returns only the stored metadata; nothing is reloaded from the source resources.
    """
    stmt = select(AuditRecord)
    if filters.occurred_from is not None:
        stmt = stmt.where(AuditRecord.occurred_at >= filters.occurred_from)
    if filters.occurred_to is not None:
        stmt = stmt.where(AuditRecord.occurred_at < filters.occurred_to)
    for column, value in (
        (AuditRecord.action, filters.action),
        (AuditRecord.resource_type, filters.resource_type),
    ):
        if value is not None:
            stmt = stmt.where(column == value)
    for id_column, id_value in (
        (AuditRecord.actor_account_id, filters.actor_account_id),
        (AuditRecord.resource_id, filters.resource_id),
        (AuditRecord.scope_unit_id, filters.scope_unit_id),
    ):
        if id_value is not None:
            stmt = stmt.where(id_column == id_value)
    if cursor is not None:
        stmt = stmt.where(AuditRecord.sequence < cursor)
    rows = list(await db.scalars(stmt.order_by(AuditRecord.sequence.desc()).limit(limit + 1)))
    has_more = len(rows) > limit
    records = rows[:limit]
    return AuditPage(records, records[-1].sequence if has_more else None)


async def get_record(db: AsyncSession, record_id: uuid.UUID) -> AuditRecord | None:
    return await db.get(AuditRecord, record_id)
