"""Implementation of `access.org_facts.OrganizationFacts` over the organization tables."""

import uuid
from collections.abc import Mapping
from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from kora_api.access.authorization import valid_at
from kora_api.access.org_facts import RoleFact, UnitInfo
from kora_api.organization.constants import KORA_UNIT_ID, RoleKey
from kora_api.organization.models import Member, OrgUnit, OrgUnitPlacement, RoleAssignment


class SqlOrganizationFacts:
    async def units_at(self, db: AsyncSession, at: datetime) -> Mapping[uuid.UUID, UnitInfo]:
        rows = await db.execute(
            select(OrgUnit, OrgUnitPlacement.parent_id)
            .outerjoin(
                OrgUnitPlacement,
                (OrgUnitPlacement.unit_id == OrgUnit.id)
                & valid_at(OrgUnitPlacement.valid_from, OrgUnitPlacement.valid_to, at),
            )
            .where(or_(OrgUnit.id == KORA_UNIT_ID, OrgUnitPlacement.id.is_not(None)))
        )
        return {
            unit.id: UnitInfo(
                id=unit.id,
                name=unit.name,
                kind=unit.kind.value,
                parent_id=parent_id,
                active=unit.archived_at is None or unit.archived_at > at,
            )
            for unit, parent_id in rows
        }

    async def role_at(
        self, db: AsyncSession, account_id: uuid.UUID, at: datetime
    ) -> RoleFact | None:
        row = (
            await db.execute(
                select(RoleAssignment.role_key, RoleAssignment.unit_id)
                .join(Member, Member.id == RoleAssignment.member_id)
                .where(
                    Member.account_id == account_id,
                    valid_at(RoleAssignment.valid_from, RoleAssignment.valid_to, at),
                )
            )
        ).one_or_none()
        if row is None:
            return None
        role_key, unit_id = row
        return RoleFact(role_key=role_key, unit_id=unit_id)

    def role_keys(self) -> frozenset[str]:
        return frozenset(RoleKey)
