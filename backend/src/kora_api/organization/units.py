"""Organizational unit structure: create, move and archive, scoped by `organization.manage`.

Every operation checks the caller's access snapshot itself, so routes cannot skip it.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from kora_api.access.evaluation import AccessSnapshot
from kora_api.access.permissions import Permission
from kora_api.core import clock
from kora_api.organization import events
from kora_api.organization.constants import KORA_UNIT_ID, PMO_UNIT_ID, UnitKind, UnitStatus
from kora_api.organization.models import (
    MemberTeamPlacement,
    OrgUnit,
    OrgUnitPlacement,
    RoleAssignment,
)

MANAGE = Permission.ORGANIZATION_MANAGE


class UnitNotFoundError(Exception):
    pass


class InvalidStructureError(Exception):
    """The requested structure violates a structural rule."""


class StructureConflictError(Exception):
    """The unit's current state prevents the operation."""


@dataclass(frozen=True)
class UnitView:
    unit: OrgUnit
    parent_id: uuid.UUID | None


async def _current_parent_id(db: AsyncSession, unit_id: uuid.UUID) -> uuid.UUID | None:
    return await db.scalar(
        select(OrgUnitPlacement.parent_id).where(
            OrgUnitPlacement.unit_id == unit_id, OrgUnitPlacement.valid_to.is_(None)
        )
    )


async def list_manageable_units(db: AsyncSession, access: AccessSnapshot) -> list[UnitView]:
    """Units the caller may manage; inaccessible units are omitted."""
    unit_ids = access.units_with(MANAGE)
    if not unit_ids:
        return []
    units = await db.scalars(
        select(OrgUnit).where(OrgUnit.id.in_(unit_ids)).order_by(OrgUnit.kind, OrgUnit.name)
    )
    return [UnitView(unit, access.parents.get(unit.id)) for unit in units]


async def get_unit(db: AsyncSession, access: AccessSnapshot, unit_id: uuid.UUID) -> UnitView:
    access.require(MANAGE, unit_id)
    unit = await db.get(OrgUnit, unit_id)
    if unit is None:
        raise UnitNotFoundError
    return UnitView(unit, await _current_parent_id(db, unit_id))


async def create_unit(
    db: AsyncSession,
    access: AccessSnapshot,
    actor_id: uuid.UUID,
    *,
    kind: UnitKind,
    name: str,
    parent_id: uuid.UUID,
) -> UnitView:
    """Create an Administration (under KORA) or a Team (under an active Administration)."""
    access.require(MANAGE, parent_id)
    parent = await db.get(OrgUnit, parent_id, with_for_update=True)
    if parent is None:
        raise InvalidStructureError("Parent unit not found.")
    if kind == UnitKind.ADMINISTRATION:
        if parent.id != KORA_UNIT_ID:
            raise InvalidStructureError("Administrations must be placed directly under KORA.")
    elif kind == UnitKind.TEAM:
        if parent.kind != UnitKind.ADMINISTRATION:
            raise InvalidStructureError("Teams must be placed under an Administration.")
        if parent.status != UnitStatus.ACTIVE:
            raise InvalidStructureError("The Administration is archived.")
    else:
        raise InvalidStructureError("Only Administrations and Teams can be created.")

    now = clock.utcnow()
    unit = OrgUnit(
        kind=kind,
        name=name,
        status=UnitStatus.ACTIVE,
        created_at=now,
        created_by_account_id=actor_id,
    )
    db.add(unit)
    await db.flush()
    db.add(
        OrgUnitPlacement(
            unit_id=unit.id, parent_id=parent.id, valid_from=now, created_by_account_id=actor_id
        )
    )
    await db.commit()
    return UnitView(unit, parent.id)


async def move_team(
    db: AsyncSession,
    access: AccessSnapshot,
    actor_id: uuid.UUID,
    *,
    team_id: uuid.UUID,
    administration_id: uuid.UUID,
) -> UnitView:
    """Move a Team to another Administration, keeping the earlier placement as history.

    Requires `organization.manage` on the Team (in its current position) and the destination.
    """
    access.require(MANAGE, team_id)
    access.require(MANAGE, administration_id)
    team = await db.get(OrgUnit, team_id, with_for_update=True)
    if team is None:
        raise UnitNotFoundError
    if team.kind != UnitKind.TEAM:
        raise InvalidStructureError("Only Teams can be moved.")
    if team.status != UnitStatus.ACTIVE:
        raise StructureConflictError("Archived Teams cannot be moved.")
    destination = await db.get(OrgUnit, administration_id, with_for_update=True)
    if destination is None or destination.kind != UnitKind.ADMINISTRATION:
        raise InvalidStructureError("Teams can only be moved to an Administration.")
    if destination.status != UnitStatus.ACTIVE:
        raise InvalidStructureError("The Administration is archived.")

    current = await db.scalar(
        select(OrgUnitPlacement)
        .where(OrgUnitPlacement.unit_id == team_id, OrgUnitPlacement.valid_to.is_(None))
        .with_for_update()
    )
    if current is None:  # pragma: no cover - every Team is created with a placement
        raise StructureConflictError("Team has no current placement.")
    if current.parent_id == administration_id:
        raise InvalidStructureError("The Team is already in that Administration.")

    now = clock.utcnow()
    current.valid_to = now
    current.ended_by_account_id = actor_id
    await db.flush()
    db.add(
        OrgUnitPlacement(
            unit_id=team_id,
            parent_id=administration_id,
            valid_from=now,
            created_by_account_id=actor_id,
        )
    )
    placed = await db.scalars(
        select(MemberTeamPlacement.member_id).where(
            MemberTeamPlacement.team_id == team_id, MemberTeamPlacement.valid_to.is_(None)
        )
    )
    await events.membership_changed(db, frozenset(placed), actor_id)
    await db.commit()
    return UnitView(team, administration_id)


async def archive_unit(
    db: AsyncSession, access: AccessSnapshot, actor_id: uuid.UUID, unit_id: uuid.UUID
) -> UnitView:
    """Archive a unit that no longer has active Members, roles or active sub-units."""
    access.require(MANAGE, unit_id)
    unit = await db.get(OrgUnit, unit_id, with_for_update=True)
    if unit is None:
        raise UnitNotFoundError
    if unit.id in (KORA_UNIT_ID, PMO_UNIT_ID):
        raise InvalidStructureError("KORA and the PMO cannot be archived.")
    if unit.status != UnitStatus.ACTIVE:
        raise StructureConflictError("The unit is already archived.")

    blockers: list[str] = []
    active_children = exists().where(
        OrgUnitPlacement.parent_id == unit_id,
        OrgUnitPlacement.valid_to.is_(None),
        OrgUnit.id == OrgUnitPlacement.unit_id,
        OrgUnit.status == UnitStatus.ACTIVE,
    )
    if await db.scalar(select(active_children)):
        blockers.append("it contains active units")
    placed_members = exists().where(
        MemberTeamPlacement.team_id == unit_id, MemberTeamPlacement.valid_to.is_(None)
    )
    if await db.scalar(select(placed_members)):
        blockers.append("it has active Members")
    open_roles = exists().where(
        RoleAssignment.unit_id == unit_id, RoleAssignment.valid_to.is_(None)
    )
    if await db.scalar(select(open_roles)):
        blockers.append("roles are assigned to it")
    if blockers:
        raise StructureConflictError(f"Cannot archive: {', '.join(blockers)}.")

    unit.status = UnitStatus.ARCHIVED
    unit.archived_at = clock.utcnow()
    unit.archived_by_account_id = actor_id
    await db.commit()
    return UnitView(unit, await _current_parent_id(db, unit_id))
