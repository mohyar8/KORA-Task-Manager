"""Public read interface of the organization module for other domains (e.g. `tasks`)."""

import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from kora_api.access.evaluation import AccessSnapshot
from kora_api.access.models import AccountStatus, UserAccount
from kora_api.access.org_facts import UnitInfo
from kora_api.access.permissions import Permission
from kora_api.core import clock
from kora_api.organization.constants import MemberStatus
from kora_api.organization.facts import SqlOrganizationFacts
from kora_api.organization.models import Member, MemberTeamPlacement, RoleAssignment

_FACTS = SqlOrganizationFacts()


@dataclass(frozen=True)
class MemberPosition:
    """Where a Member currently sits: their Team placement and their role's unit."""

    member_id: uuid.UUID
    account_id: uuid.UUID
    active: bool
    team_id: uuid.UUID | None
    role_unit_id: uuid.UUID | None


def _positions_query():
    return (
        select(Member, UserAccount.status, MemberTeamPlacement.team_id, RoleAssignment.unit_id)
        .join(UserAccount, UserAccount.id == Member.account_id)
        .outerjoin(
            MemberTeamPlacement,
            and_(
                MemberTeamPlacement.member_id == Member.id,
                MemberTeamPlacement.valid_to.is_(None),
            ),
        )
        .outerjoin(
            RoleAssignment,
            and_(RoleAssignment.member_id == Member.id, RoleAssignment.valid_to.is_(None)),
        )
    )


def _position(
    member: Member,
    account_status: AccountStatus,
    team_id: uuid.UUID | None,
    role_unit_id: uuid.UUID | None,
) -> MemberPosition:
    return MemberPosition(
        member_id=member.id,
        account_id=member.account_id,
        # Eligible only while both the Member and its account are active.
        active=member.status == MemberStatus.ACTIVE and account_status == AccountStatus.ACTIVE,
        team_id=team_id,
        role_unit_id=role_unit_id,
    )


async def member_for_account(db: AsyncSession, account_id: uuid.UUID) -> MemberPosition | None:
    row = (await db.execute(_positions_query().where(Member.account_id == account_id))).first()
    return _position(*row) if row else None


async def member_positions(
    db: AsyncSession, member_ids: Iterable[uuid.UUID]
) -> dict[uuid.UUID, MemberPosition]:
    ids = set(member_ids)
    if not ids:
        return {}
    rows = await db.execute(_positions_query().where(Member.id.in_(ids)))
    return {member.id: _position(member, status, team, role) for member, status, team, role in rows}


async def current_units(db: AsyncSession) -> Mapping[uuid.UUID, UnitInfo]:
    """The current unit structure (id -> parent, kind, active)."""
    return await _FACTS.units_at(db, clock.utcnow())


def unit_chain(unit_id: uuid.UUID | None, units: Mapping[uuid.UUID, UnitInfo]) -> list[uuid.UUID]:
    """The unit and its ancestors up to KORA (empty when unknown)."""
    chain: list[uuid.UUID] = []
    current = unit_id
    while current is not None and current in units and current not in chain:
        chain.append(current)
        current = units[current].parent_id
    return chain


def member_within_scope(
    position: MemberPosition, scope_unit_id: uuid.UUID, units: Mapping[uuid.UUID, UnitInfo]
) -> bool:
    """An active Member is within a scope when their Team or their role's unit lies in it."""
    if not position.active:
        return False
    return any(
        scope_unit_id in unit_chain(unit, units)
        for unit in (position.team_id, position.role_unit_id)
    )


# Holding any operational permission over a unit lets the caller see who works under it, because
# that is who they can assign, invite or address there. Deliberately NOT organization.manage alone.
DIRECTORY_PERMISSIONS = (
    Permission.TASK_VIEW,
    Permission.TASK_CREATE,
    Permission.TASK_MANAGE,
    Permission.ANNOUNCEMENT_PUBLISH,
    Permission.ANNOUNCEMENT_MANAGE,
    Permission.CALENDAR_CREATE,
    Permission.CALENDAR_MANAGE,
    Permission.ORGANIZATION_MANAGE,
)


@dataclass(frozen=True)
class DirectoryEntry:
    """A Member as other people may see them: name and organizational context, no contact data."""

    member_id: uuid.UUID
    full_name: str
    team_id: uuid.UUID | None
    role_key: str | None


async def member_directory(
    db: AsyncSession, snapshot: AccessSnapshot, account_id: uuid.UUID
) -> list[DirectoryEntry]:
    """Active Members within the scope of any unit where the caller holds an operational
    permission, plus the caller's own Member record. Ordered by name."""
    scope: set[uuid.UUID] = set()
    for permission in DIRECTORY_PERMISSIONS:
        scope |= snapshot.units_with(permission)
    units = await current_units(db)
    rows = await db.execute(
        _positions_query().add_columns(RoleAssignment.role_key).order_by(Member.full_name)
    )
    entries: list[DirectoryEntry] = []
    for member, account_status, team_id, role_unit_id, role_key in rows:
        position = _position(member, account_status, team_id, role_unit_id)
        if not position.active:
            continue
        reach = set(unit_chain(team_id, units)) | set(unit_chain(role_unit_id, units))
        if member.account_id == account_id or reach & scope:
            entries.append(
                DirectoryEntry(
                    member_id=member.id,
                    full_name=member.full_name,
                    team_id=team_id,
                    role_key=str(role_key) if role_key else None,
                )
            )
    return entries
