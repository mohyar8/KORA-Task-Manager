"""Member lifecycle (System Admin only). Every operation is a single transaction.

Invariants: an active Member has exactly one open Team placement and one open role assignment;
Team Leader / Member roles are always held at the Member's current Team.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kora_api.access import service as access_service
from kora_api.access.models import UserAccount
from kora_api.core import clock
from kora_api.organization import events
from kora_api.organization.constants import (
    KORA_UNIT_ID,
    PMO_UNIT_ID,
    ROLES,
    MemberStatus,
    RoleKey,
    UnitKind,
    UnitStatus,
)
from kora_api.organization.models import (
    Member,
    MemberTeamPlacement,
    OrgUnit,
    RoleAssignment,
)


class MemberNotFoundError(Exception):
    pass


class InvalidMemberChangeError(Exception):
    """The requested Team or role is not valid."""


class MemberStateError(Exception):
    """The Member's status does not allow the operation."""


@dataclass(frozen=True)
class MemberProfile:
    full_name: str
    university_id: str | None = None
    phone: str | None = None
    email: str | None = None
    major: str | None = None
    academic_year: str | None = None


@dataclass(frozen=True)
class RoleChoice:
    role_key: RoleKey
    # Required for Administration Manager only; the other roles have a fixed or Team scope.
    administration_id: uuid.UUID | None = None


@dataclass(frozen=True)
class MemberView:
    member: Member
    username: str
    team_id: uuid.UUID | None
    role_key: str | None
    role_unit_id: uuid.UUID | None


# --- Reads --------------------------------------------------------------------------------------


async def get_member(db: AsyncSession, member_id: uuid.UUID) -> MemberView:
    member = await db.get(Member, member_id)
    if member is None:
        raise MemberNotFoundError
    return await _view(db, member)


async def list_members(db: AsyncSession) -> list[MemberView]:
    members = await db.scalars(select(Member).order_by(Member.full_name))
    return [await _view(db, member) for member in members]


async def _view(db: AsyncSession, member: Member) -> MemberView:
    account = await db.get_one(UserAccount, member.account_id)
    placement = await _open_placement(db, member.id, lock=False)
    assignment = await _open_assignment(db, member.id, lock=False)
    return MemberView(
        member=member,
        username=account.username,
        team_id=placement.team_id if placement else None,
        role_key=assignment.role_key if assignment else None,
        role_unit_id=assignment.unit_id if assignment else None,
    )


# --- Lifecycle ----------------------------------------------------------------------------------


async def create_member(
    db: AsyncSession,
    actor_id: uuid.UUID,
    *,
    username: str,
    profile: MemberProfile,
    team_id: uuid.UUID,
    role: RoleChoice,
) -> tuple[MemberView, str]:
    """Create a Member, its account (temporary password), Team placement and role."""
    await _require_active_team(db, team_id)
    role_unit_id = await _role_unit(db, role, team_id)
    account, temporary_password = await access_service.create_account_with_temporary_password(
        db, username
    )
    member = Member(account_id=account.id, status=MemberStatus.ACTIVE, **vars(profile))
    db.add(member)
    await db.flush()
    _open_team_placement(db, member.id, team_id, actor_id)
    _open_role(db, member.id, role.role_key, role_unit_id, actor_id)
    await db.commit()
    return await _view(db, member), temporary_password


async def update_profile(
    db: AsyncSession, member_id: uuid.UUID, profile: MemberProfile
) -> MemberView:
    member = await _lock_member(db, member_id)
    for field, value in vars(profile).items():
        setattr(member, field, value)
    await db.commit()
    return await _view(db, member)


async def change_team(
    db: AsyncSession, actor_id: uuid.UUID, member_id: uuid.UUID, team_id: uuid.UUID
) -> MemberView:
    """Move a Member to another Team. A Team-level role moves with them."""
    member = await _lock_active_member(db, member_id)
    await _require_active_team(db, team_id)
    placement = await _open_placement(db, member_id)
    assignment = await _open_assignment(db, member_id)
    assert placement is not None and assignment is not None  # active-Member invariant
    if placement.team_id == team_id:
        raise InvalidMemberChangeError("The Member is already in that Team.")

    role_follows_team = ROLES[RoleKey(assignment.role_key)][1] == UnitKind.TEAM
    _close(placement, actor_id)
    if role_follows_team:
        _close(assignment, actor_id)
    await db.flush()
    _open_team_placement(db, member_id, team_id, actor_id)
    if role_follows_team:
        _open_role(db, member_id, RoleKey(assignment.role_key), team_id, actor_id)
    await events.membership_changed(db, frozenset({member_id}), actor_id)
    await db.commit()
    return await _view(db, member)


async def change_role(
    db: AsyncSession, actor_id: uuid.UUID, member_id: uuid.UUID, role: RoleChoice
) -> MemberView:
    member = await _lock_active_member(db, member_id)
    placement = await _open_placement(db, member_id)
    assignment = await _open_assignment(db, member_id)
    assert placement is not None and assignment is not None  # active-Member invariant
    role_unit_id = await _role_unit(db, role, placement.team_id)
    if assignment.role_key == role.role_key and assignment.unit_id == role_unit_id:
        raise InvalidMemberChangeError("The Member already holds that role.")

    _close(assignment, actor_id)
    await db.flush()
    _open_role(db, member_id, role.role_key, role_unit_id, actor_id)
    await events.membership_changed(db, frozenset({member_id}), actor_id)
    await db.commit()
    return await _view(db, member)


async def deactivate_member(
    db: AsyncSession, actor_id: uuid.UUID, member_id: uuid.UUID
) -> MemberView:
    """End the Team placement and role, deactivate the account and revoke its sessions."""
    member = await _lock_active_member(db, member_id)
    # Raises LastSystemAdminError (and changes nothing) for the final active System Admin.
    await access_service.deactivate_account(db, member.account_id)
    for row in (await _open_placement(db, member_id), await _open_assignment(db, member_id)):
        if row is not None:
            _close(row, actor_id)
    member.status = MemberStatus.DEACTIVATED
    await events.membership_changed(db, frozenset({member_id}), actor_id)
    await db.commit()
    return await _view(db, member)


async def reactivate_member(
    db: AsyncSession,
    actor_id: uuid.UUID,
    member_id: uuid.UUID,
    *,
    team_id: uuid.UUID,
    role: RoleChoice,
) -> MemberView:
    """Reactivate with a new Team placement and role assignment."""
    member = await _lock_member(db, member_id)
    if member.status != MemberStatus.DEACTIVATED:
        raise MemberStateError("The Member is already active.")
    await _require_active_team(db, team_id)
    role_unit_id = await _role_unit(db, role, team_id)
    await access_service.reactivate_account(db, member.account_id)
    member.status = MemberStatus.ACTIVE
    _open_team_placement(db, member_id, team_id, actor_id)
    _open_role(db, member_id, role.role_key, role_unit_id, actor_id)
    await db.commit()
    return await _view(db, member)


async def reset_password(db: AsyncSession, member_id: uuid.UUID) -> str:
    """Issue a new temporary password for an active Member's account; ends its sessions."""
    member = await _lock_active_member(db, member_id)
    temporary_password = await access_service.reset_to_temporary_password(db, member.account_id)
    await db.commit()
    return temporary_password


# --- Helpers ------------------------------------------------------------------------------------


async def _lock_member(db: AsyncSession, member_id: uuid.UUID) -> Member:
    member = await db.get(Member, member_id, with_for_update=True)
    if member is None:
        raise MemberNotFoundError
    return member


async def _lock_active_member(db: AsyncSession, member_id: uuid.UUID) -> Member:
    member = await _lock_member(db, member_id)
    if member.status != MemberStatus.ACTIVE:
        raise MemberStateError("The Member is deactivated.")
    return member


async def _require_active_team(db: AsyncSession, team_id: uuid.UUID) -> None:
    team = await db.get(OrgUnit, team_id)
    if team is None or team.kind != UnitKind.TEAM or team.status != UnitStatus.ACTIVE:
        raise InvalidMemberChangeError("Team not found or not active.")


async def _role_unit(db: AsyncSession, role: RoleChoice, team_id: uuid.UUID) -> uuid.UUID:
    """The scope unit for a role, enforcing which unit each role may be held at."""
    unit_kind = ROLES[role.role_key][1]
    if unit_kind != UnitKind.ADMINISTRATION and role.administration_id is not None:
        raise InvalidMemberChangeError("Only Administration Managers take an Administration.")
    match unit_kind:
        case UnitKind.ORGANIZATION:
            return KORA_UNIT_ID
        case UnitKind.PMO:
            return PMO_UNIT_ID
        case UnitKind.TEAM:
            return team_id
        case UnitKind.ADMINISTRATION:
            if role.administration_id is None:
                raise InvalidMemberChangeError("An Administration is required for this role.")
            administration = await db.get(OrgUnit, role.administration_id)
            if (
                administration is None
                or administration.kind != UnitKind.ADMINISTRATION
                or administration.status != UnitStatus.ACTIVE
            ):
                raise InvalidMemberChangeError("Administration not found or not active.")
            return administration.id


async def _open_placement(
    db: AsyncSession, member_id: uuid.UUID, *, lock: bool = True
) -> MemberTeamPlacement | None:
    stmt = select(MemberTeamPlacement).where(
        MemberTeamPlacement.member_id == member_id, MemberTeamPlacement.valid_to.is_(None)
    )
    return await db.scalar(stmt.with_for_update() if lock else stmt)


async def _open_assignment(
    db: AsyncSession, member_id: uuid.UUID, *, lock: bool = True
) -> RoleAssignment | None:
    stmt = select(RoleAssignment).where(
        RoleAssignment.member_id == member_id, RoleAssignment.valid_to.is_(None)
    )
    return await db.scalar(stmt.with_for_update() if lock else stmt)


def _open_team_placement(
    db: AsyncSession, member_id: uuid.UUID, team_id: uuid.UUID, actor_id: uuid.UUID
) -> None:
    db.add(
        MemberTeamPlacement(
            member_id=member_id,
            team_id=team_id,
            valid_from=clock.utcnow(),
            created_by_account_id=actor_id,
        )
    )


def _open_role(
    db: AsyncSession,
    member_id: uuid.UUID,
    role_key: RoleKey,
    unit_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> None:
    db.add(
        RoleAssignment(
            member_id=member_id,
            role_key=role_key,
            unit_id=unit_id,
            valid_from=clock.utcnow(),
            created_by_account_id=actor_id,
        )
    )


def _close(row: MemberTeamPlacement | RoleAssignment, actor_id: uuid.UUID) -> None:
    row.valid_to = clock.utcnow()
    row.ended_by_account_id = actor_id
