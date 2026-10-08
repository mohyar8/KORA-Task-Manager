"""Direct-to-database setup helpers for organization and authorization tests."""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from kora_api.access import authorization
from kora_api.access.evaluation import AccessSnapshot
from kora_api.access.models import PermissionOverride, UserAccount
from kora_api.access.permissions import OverrideEffect, Permission
from kora_api.core import clock
from kora_api.organization.constants import (
    KORA_UNIT_ID,
    PMO_UNIT_ID,
    MemberStatus,
    RoleKey,
    UnitKind,
    UnitStatus,
)
from kora_api.organization.facts import SqlOrganizationFacts
from kora_api.organization.models import (
    Member,
    MemberTeamPlacement,
    OrgUnit,
    OrgUnitPlacement,
    RoleAssignment,
)
from tests.access.helpers import create_account

UNITS = "/api/v1/organization/units"
MEMBERS = "/api/v1/admin/members"
MANAGE = Permission.ORGANIZATION_MANAGE
FACTS = SqlOrganizationFacts()


async def make_unit(
    db: AsyncSession, kind: UnitKind, name: str, parent_id: uuid.UUID = KORA_UNIT_ID
) -> OrgUnit:
    now = clock.utcnow()
    unit = OrgUnit(kind=kind, name=name, status=UnitStatus.ACTIVE, created_at=now)
    db.add(unit)
    await db.flush()
    db.add(OrgUnitPlacement(unit_id=unit.id, parent_id=parent_id, valid_from=now))
    await db.commit()
    return unit


@dataclass(frozen=True)
class Structure:
    """KORA -> Admin A (Team A1, Team A2), Admin B (Team B1); plus the seeded PMO."""

    admin_a: uuid.UUID
    team_a1: uuid.UUID
    team_a2: uuid.UUID
    admin_b: uuid.UUID
    team_b1: uuid.UUID
    kora: uuid.UUID = KORA_UNIT_ID
    pmo: uuid.UUID = PMO_UNIT_ID


async def make_structure(db: AsyncSession) -> Structure:
    admin_a = await make_unit(db, UnitKind.ADMINISTRATION, "Admin A")
    admin_b = await make_unit(db, UnitKind.ADMINISTRATION, "Admin B")
    team_a1 = await make_unit(db, UnitKind.TEAM, "Team A1", admin_a.id)
    team_a2 = await make_unit(db, UnitKind.TEAM, "Team A2", admin_a.id)
    team_b1 = await make_unit(db, UnitKind.TEAM, "Team B1", admin_b.id)
    return Structure(admin_a.id, team_a1.id, team_a2.id, admin_b.id, team_b1.id)


async def make_member(
    db: AsyncSession,
    username: str,
    *,
    team_id: uuid.UUID,
    role: RoleKey = RoleKey.MEMBER,
    role_unit_id: uuid.UUID | None = None,
    system_admin: bool = False,
) -> tuple[Member, UserAccount]:
    """An active Member with a usable password (tests.access.helpers.PASSWORD)."""
    account = await create_account(db, username, system_admin=system_admin)
    now = clock.utcnow()
    member = Member(
        account_id=account.id,
        full_name=username.title(),
        university_id=f"U-{username}",
        phone="0500000000",
        email=f"{username}@example.test",
        major="Engineering",
        academic_year="3",
        status=MemberStatus.ACTIVE,
    )
    db.add(member)
    await db.flush()
    db.add(
        MemberTeamPlacement(
            member_id=member.id, team_id=team_id, valid_from=now, created_by_account_id=account.id
        )
    )
    db.add(
        RoleAssignment(
            member_id=member.id,
            role_key=role,
            unit_id=role_unit_id or team_id,
            valid_from=now,
            created_by_account_id=account.id,
        )
    )
    await db.commit()
    return member, account


async def add_override(
    db: AsyncSession,
    account_id: uuid.UUID,
    unit_id: uuid.UUID,
    effect: OverrideEffect = OverrideEffect.GRANT,
    permission: str = MANAGE,
) -> PermissionOverride:
    override = PermissionOverride(
        account_id=account_id,
        permission_key=permission,
        unit_id=unit_id,
        effect=effect,
        reason="test setup",
        valid_from=clock.utcnow(),
        created_by_account_id=account_id,
    )
    db.add(override)
    await db.commit()
    return override


async def snapshot(
    db: AsyncSession, account_id: uuid.UUID, at: datetime | None = None
) -> AccessSnapshot:
    return await authorization.load_snapshot(db, FACTS, account_id, at)
