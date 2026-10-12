"""Audit table. Append-only: a database trigger rejects UPDATE, DELETE and TRUNCATE."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Identity, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from kora_api.core.database import Base


class AuditRecord(Base):
    """One successful state change. `before`/`after` hold only allowlisted, safe metadata.

    Foreign keys to `user_accounts` / `org_units` are table-level only; `audit` imports no domain.
    """

    __tablename__ = "audit_records"
    __table_args__ = (
        CheckConstraint("length(action) > 0", name="action_required"),
        CheckConstraint("length(resource_type) > 0", name="resource_type_required"),
        Index("ix_audit_records_resource", "resource_type", "resource_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # Insertion order (records written in one transaction may share a timestamp); the list cursor.
    sequence: Mapped[int] = mapped_column(BigInteger, Identity(), unique=True)
    occurred_at: Mapped[datetime] = mapped_column(index=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    actor_account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user_accounts.id"), index=True
    )
    resource_type: Mapped[str] = mapped_column(String(64))
    resource_id: Mapped[uuid.UUID]
    scope_unit_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("org_units.id"), index=True)
    before: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
