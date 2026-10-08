"""Loading effective access, and System Admin management of role defaults and overrides."""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import ColumnElement, and_, exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from kora_api.access.evaluation import AccessSnapshot, Decision, OverrideRule
from kora_api.access.models import (
    AccountDeactivation,
    AccountStatus,
    PermissionDefinition,
    PermissionOverride,
    RolePermissionDefault,
    UserAccount,
)
from kora_api.access.org_facts import OrganizationFacts, UnitInfo
from kora_api.access.permissions import OverrideEffect, Permission
from kora_api.access.service import AccountNotFoundError
from kora_api.core import clock


class UnknownRoleError(Exception):
    pass


class UnknownUnitError(Exception):
    pass


class DuplicateRuleError(Exception):
    """An identical rule is already in force."""


class RuleNotFoundError(Exception):
    pass


class RuleAlreadyEndedError(Exception):
    pass


class InactiveAccountError(Exception):
    pass


class EmptyReasonError(Exception):
    pass


def valid_at(
    valid_from: InstrumentedAttribute[datetime],
    valid_to: InstrumentedAttribute[datetime | None],
    at: datetime,
) -> ColumnElement[bool]:
    """SQL condition: the row's validity period contains `at`."""
    return and_(valid_from <= at, or_(valid_to.is_(None), valid_to > at))


# --- Effective access ---------------------------------------------------------------------------


async def load_snapshot(
    db: AsyncSession,
    facts: OrganizationFacts,
    account_id: uuid.UUID,
    at: datetime | None = None,
) -> AccessSnapshot:
    """Everything needed to decide the account's access at `at` (default: now).

    An account inactive at that time gets nothing: for the current time this is its current
    status; for a past time it is its deactivation history, so access that existed then can be
    reconstructed even if the account is deactivated now. System Admin authority is deliberately
    not consulted.
    """
    current = at is None
    at = at or clock.utcnow()
    units = await facts.units_at(db, at)
    parents = {unit.id: unit.parent_id for unit in units.values()}
    account = await db.get(UserAccount, account_id)
    if account is None or not await _active_at(db, account, at, current=current):
        return AccessSnapshot(at=at, parents=parents)

    role = await facts.role_at(db, account_id, at)
    role_permissions: frozenset[str] = frozenset()
    if role is not None:
        role_permissions = frozenset(
            await db.scalars(
                select(RolePermissionDefault.permission_key).where(
                    RolePermissionDefault.role_key == role.role_key,
                    valid_at(RolePermissionDefault.valid_from, RolePermissionDefault.valid_to, at),
                )
            )
        )
    overrides = await db.scalars(
        select(PermissionOverride).where(
            PermissionOverride.account_id == account_id,
            valid_at(PermissionOverride.valid_from, PermissionOverride.valid_to, at),
        )
    )
    return AccessSnapshot(
        at=at,
        parents=parents,
        role_unit_id=role.unit_id if role else None,
        role_permissions=role_permissions,
        overrides=tuple(
            OverrideRule(permission=o.permission_key, unit_id=o.unit_id, effect=o.effect)
            for o in overrides
        ),
    )


async def _active_at(
    db: AsyncSession, account: UserAccount, at: datetime, *, current: bool
) -> bool:
    if current:
        return account.status == AccountStatus.ACTIVE
    deactivated = await db.scalar(
        select(
            exists().where(
                AccountDeactivation.account_id == account.id,
                AccountDeactivation.deactivated_at <= at,
                or_(
                    AccountDeactivation.reactivated_at.is_(None),
                    AccountDeactivation.reactivated_at > at,
                ),
            )
        )
    )
    return not deactivated


@dataclass(frozen=True)
class UnitDecision:
    unit: UnitInfo
    decision: Decision


async def explain_access(
    db: AsyncSession, facts: OrganizationFacts, account_id: uuid.UUID, at: datetime | None = None
) -> tuple[datetime, dict[Permission, list[UnitDecision]]]:
    """For every catalog permission, the decision (and what decided it) on every unit."""
    snapshot = await load_snapshot(db, facts, account_id, at)
    units = await facts.units_at(db, snapshot.at)
    ordered = sorted(units.values(), key=lambda unit: (len(snapshot.chain(unit.id)), unit.name))
    return snapshot.at, {
        permission: [UnitDecision(unit, snapshot.decide(permission, unit.id)) for unit in ordered]
        for permission in Permission
    }


# --- Catalog and role defaults ------------------------------------------------------------------


async def list_permissions(db: AsyncSession) -> list[PermissionDefinition]:
    return list(await db.scalars(select(PermissionDefinition).order_by(PermissionDefinition.key)))


async def list_role_defaults(db: AsyncSession) -> list[RolePermissionDefault]:
    return list(
        await db.scalars(
            select(RolePermissionDefault).order_by(
                RolePermissionDefault.role_key, RolePermissionDefault.valid_from
            )
        )
    )


async def add_role_default(
    db: AsyncSession,
    facts: OrganizationFacts,
    role_key: str,
    permission: Permission,
    actor_id: uuid.UUID,
) -> RolePermissionDefault:
    if role_key not in facts.role_keys():
        raise UnknownRoleError
    existing = await db.scalar(
        select(RolePermissionDefault)
        .where(
            RolePermissionDefault.role_key == role_key,
            RolePermissionDefault.permission_key == permission,
            RolePermissionDefault.valid_to.is_(None),
        )
        .with_for_update()
    )
    if existing is not None:
        raise DuplicateRuleError
    row = RolePermissionDefault(
        role_key=role_key,
        permission_key=permission,
        valid_from=clock.utcnow(),
        created_by_account_id=actor_id,
    )
    db.add(row)
    await db.commit()
    return row


async def end_role_default(
    db: AsyncSession, default_id: uuid.UUID, actor_id: uuid.UUID
) -> RolePermissionDefault:
    row = await db.get(RolePermissionDefault, default_id, with_for_update=True)
    if row is None:
        raise RuleNotFoundError
    if row.valid_to is not None:
        raise RuleAlreadyEndedError
    row.valid_to = clock.utcnow()
    row.ended_by_account_id = actor_id
    await db.commit()
    return row


# --- Overrides ----------------------------------------------------------------------------------


async def list_overrides(db: AsyncSession, account_id: uuid.UUID) -> list[PermissionOverride]:
    return list(
        await db.scalars(
            select(PermissionOverride)
            .where(PermissionOverride.account_id == account_id)
            .order_by(PermissionOverride.valid_from)
        )
    )


async def create_override(
    db: AsyncSession,
    facts: OrganizationFacts,
    *,
    account_id: uuid.UUID,
    permission: Permission,
    unit_id: uuid.UUID,
    effect: OverrideEffect,
    reason: str,
    actor_id: uuid.UUID,
) -> PermissionOverride:
    reason = reason.strip()
    if not reason:
        raise EmptyReasonError
    account = await db.get(UserAccount, account_id, with_for_update=True)
    if account is None:
        raise AccountNotFoundError
    if account.status != AccountStatus.ACTIVE:
        raise InactiveAccountError
    now = clock.utcnow()
    unit = (await facts.units_at(db, now)).get(unit_id)
    if unit is None or not unit.active:
        raise UnknownUnitError
    duplicate = await db.scalar(
        select(PermissionOverride).where(
            PermissionOverride.account_id == account_id,
            PermissionOverride.permission_key == permission,
            PermissionOverride.unit_id == unit_id,
            PermissionOverride.effect == effect,
            PermissionOverride.valid_to.is_(None),
        )
    )
    if duplicate is not None:
        raise DuplicateRuleError
    override = PermissionOverride(
        account_id=account_id,
        permission_key=permission,
        unit_id=unit_id,
        effect=effect,
        reason=reason,
        valid_from=now,
        created_by_account_id=actor_id,
    )
    db.add(override)
    await db.commit()
    return override


async def end_override(
    db: AsyncSession, override_id: uuid.UUID, actor_id: uuid.UUID
) -> PermissionOverride:
    override = await db.get(PermissionOverride, override_id, with_for_update=True)
    if override is None:
        raise RuleNotFoundError
    if override.valid_to is not None:
        raise RuleAlreadyEndedError
    override.valid_to = clock.utcnow()
    override.ended_by_account_id = actor_id
    await db.commit()
    return override
