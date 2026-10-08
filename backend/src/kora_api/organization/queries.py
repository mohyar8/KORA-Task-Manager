"""Public read interface of the organization module for other domains (e.g. `tasks`)."""

import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from kora_api.access.models import AccountStatus, UserAccount
from kora_api.access.org_facts import UnitInfo
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
