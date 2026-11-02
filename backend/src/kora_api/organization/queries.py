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
from kora_api.organization.constants import KORA_UNIT_ID, MemberStatus
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
    role_key: str | None = None


def _positions_query():
    return (
        select(
            Member,
            UserAccount.status,
            MemberTeamPlacement.team_id,
            RoleAssignment.unit_id,
            RoleAssignment.role_key,
        )
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
    role_key: str | None = None,
) -> MemberPosition:
    return MemberPosition(
        member_id=member.id,
        account_id=member.account_id,
        # Eligible only while both the Member and its account are active.
        active=member.status == MemberStatus.ACTIVE and account_status == AccountStatus.ACTIVE,
        team_id=team_id,
        role_unit_id=role_unit_id,
        role_key=str(role_key) if role_key else None,
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
    return {
        member.id: _position(member, status, team, unit, role)
        for member, status, team, unit, role in rows
    }


async def active_positions(db: AsyncSession) -> list[MemberPosition]:
    """Every active Member's position (used to find the leaders of a scope)."""
    rows = await db.execute(_positions_query())
    positions = [
        _position(member, status, team, unit, role) for member, status, team, unit, role in rows
    ]
    return [p for p in positions if p.active]


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


# The Event Leader, Deputy and PMO Leader cannot be given tasks through a Team's or
# Administration's normal assignee list; they are reachable only through the explicit "Other".
TOP_ROLES = frozenset({"event_project_leader", "deputy_leader", "pmo_leader"})


def is_top_role(position: MemberPosition) -> bool:
    return position.role_key in TOP_ROLES


def member_within_task_scope(
    position: MemberPosition, scope_unit_id: uuid.UUID, units: Mapping[uuid.UUID, UnitInfo]
) -> bool:
    """Regular task eligibility: in the scope, and not one of the top roles."""
    return member_within_scope(position, scope_unit_id, units) and not is_top_role(position)


async def member_names(db: AsyncSession, member_ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, str]:
    ids = set(member_ids)
    if not ids:
        return {}
    rows = await db.execute(select(Member.id, Member.full_name).where(Member.id.in_(ids)))
    return {member_id: name for member_id, name in rows}


def owns_scope(
    position: MemberPosition | None, scope_unit_id: uuid.UUID, units: Mapping[uuid.UUID, UnitInfo]
) -> bool:
    """True for the Team Leader or Administration Manager whose unit is the scope or above it."""
    return (
        position is not None
        and position.role_key in ("team_leader", "administration_manager")
        and position.role_unit_id in unit_chain(scope_unit_id, units)
    )


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
    db: AsyncSession, snapshot: AccessSnapshot, account_id: uuid.UUID, *, include_all: bool = False
) -> list[DirectoryEntry]:
    """Active Members within the scope of any unit where the caller holds an operational
    permission, plus the caller's own Member record. Ordered by name."""
    scope: set[uuid.UUID] = set()
    for permission in DIRECTORY_PERMISSIONS:
        scope |= snapshot.units_with(permission)
    # Task creators may pick anyone outside their own team through "Other" (names only).
    everyone = include_all and bool(snapshot.units_with(Permission.TASK_CREATE))
    units = await current_units(db)
    rows = await db.execute(_positions_query().order_by(Member.full_name))
    entries: list[DirectoryEntry] = []
    for member, account_status, team_id, role_unit_id, role_key in rows:
        position = _position(member, account_status, team_id, role_unit_id, role_key)
        if not position.active:
            continue
        reach = set(unit_chain(team_id, units)) | set(unit_chain(role_unit_id, units))
        if member.account_id == account_id or everyone or reach & scope:
            entries.append(
                DirectoryEntry(
                    member_id=member.id,
                    full_name=member.full_name,
                    team_id=team_id,
                    role_key=position.role_key,
                )
            )
    return entries


LEADER_ROLES = frozenset(
    {"event_project_leader", "pmo_leader", "administration_manager", "team_leader"}
)


@dataclass(frozen=True)
class StructureMember:
    member_id: uuid.UUID
    full_name: str
    role_key: str


@dataclass(frozen=True)
class StructureNode:
    unit_id: uuid.UUID
    name: str
    kind: str
    leader_ids: list[uuid.UUID]
    members: list[StructureMember]
    children: list["StructureNode"]


async def organization_structure(db: AsyncSession) -> StructureNode:
    """The whole active structure, KORA down to Teams, with each unit's active Members.

    Names and roles only (no contact data). A Member sits in their role's unit: Team roles at the
    Team, the Administration Manager at the Administration, PMO roles at the PMO, the top roles at
    KORA. Archived units and inactive Members are left out."""
    units = await current_units(db)
    by_unit: dict[uuid.UUID, list[StructureMember]] = {}
    rows = await db.execute(_positions_query().order_by(Member.full_name))
    for member, account_status, team_id, role_unit_id, role_key in rows:
        position = _position(member, account_status, team_id, role_unit_id, role_key)
        if position.active and position.role_unit_id and position.role_key:
            by_unit.setdefault(position.role_unit_id, []).append(
                StructureMember(member.id, member.full_name, position.role_key)
            )
    children: dict[uuid.UUID, list[uuid.UUID]] = {}
    for info in units.values():
        if info.active and info.parent_id is not None:
            children.setdefault(info.parent_id, []).append(info.id)

    def build(unit_id: uuid.UUID) -> StructureNode:
        info = units[unit_id]
        members = by_unit.get(unit_id, [])
        kids = sorted(children.get(unit_id, []), key=lambda u: units[u].name)
        return StructureNode(
            unit_id=unit_id,
            name=info.name,
            kind=info.kind,
            leader_ids=[m.member_id for m in members if m.role_key in LEADER_ROLES],
            members=members,
            children=[build(k) for k in kids],
        )

    return build(KORA_UNIT_ID)
