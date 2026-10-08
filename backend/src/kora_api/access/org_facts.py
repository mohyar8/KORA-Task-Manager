"""What the access module needs to know about the organization, as an interface.

`access` never imports `organization`. The organization module implements `OrganizationFacts`
and the application factory installs it on `app.state.organization_facts`.
"""

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class UnitInfo:
    id: uuid.UUID
    name: str
    kind: str
    parent_id: uuid.UUID | None
    active: bool


@dataclass(frozen=True)
class RoleFact:
    role_key: str
    unit_id: uuid.UUID


class OrganizationFacts(Protocol):
    async def units_at(self, db: AsyncSession, at: datetime) -> Mapping[uuid.UUID, UnitInfo]:
        """Every unit in the structure at `at`, with its parent at that time (root: None)."""
        ...

    async def role_at(
        self, db: AsyncSession, account_id: uuid.UUID, at: datetime
    ) -> RoleFact | None:
        """The organizational role assignment held by the account's Member at `at`, if any."""
        ...

    def role_keys(self) -> frozenset[str]:
        """All organizational role keys."""
        ...
