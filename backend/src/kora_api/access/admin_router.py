"""System Admin management of permissions, overrides and System Admin grants, plus each
signed-in account's view of its own effective access."""

import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, status

from kora_api.access import authorization, service
from kora_api.access.admin_schemas import (
    EffectiveAccessResponse,
    OverrideRequest,
    OverrideResponse,
    PermissionAccessResponse,
    PermissionResponse,
    RoleDefaultRequest,
    RoleDefaultResponse,
    SystemAdminResponse,
    UnitDecisionResponse,
)
from kora_api.access.dependencies import CurrentAccount, OrgFacts, SystemAdmin
from kora_api.access.models import PermissionOverride, RolePermissionDefault, UserAccount
from kora_api.access.org_facts import OrganizationFacts
from kora_api.core.database import DbSession

admin_router = APIRouter(prefix="/admin", tags=["admin"])
access_router = APIRouter(prefix="/access", tags=["access"])


# --- Catalog and role defaults ------------------------------------------------------------------


@admin_router.get("/permissions")
async def list_permissions(_: SystemAdmin, db: DbSession) -> list[PermissionResponse]:
    return [
        PermissionResponse(key=p.key, description=p.description)
        for p in await authorization.list_permissions(db)
    ]


@admin_router.get("/role-defaults")
async def list_role_defaults(_: SystemAdmin, db: DbSession) -> list[RoleDefaultResponse]:
    return [_role_default(row) for row in await authorization.list_role_defaults(db)]


@admin_router.post("/role-defaults", status_code=status.HTTP_201_CREATED)
async def add_role_default(
    body: RoleDefaultRequest, admin: SystemAdmin, db: DbSession, facts: OrgFacts
) -> RoleDefaultResponse:
    try:
        row = await authorization.add_role_default(
            db, facts, body.role_key, body.permission, admin.id
        )
    except authorization.UnknownRoleError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unknown role.") from None
    except authorization.DuplicateRuleError:
        raise HTTPException(status.HTTP_409_CONFLICT, "That default is already in force.") from None
    return _role_default(row)


@admin_router.post("/role-defaults/{default_id}/end")
async def end_role_default(
    default_id: uuid.UUID, admin: SystemAdmin, db: DbSession
) -> RoleDefaultResponse:
    try:
        return _role_default(await authorization.end_role_default(db, default_id, admin.id))
    except authorization.RuleNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Role default not found.") from None
    except authorization.RuleAlreadyEndedError:
        raise HTTPException(status.HTTP_409_CONFLICT, "The default has already ended.") from None


# --- Overrides ----------------------------------------------------------------------------------


@admin_router.get("/accounts/{account_id}/overrides")
async def list_overrides(
    account_id: uuid.UUID, _: SystemAdmin, db: DbSession
) -> list[OverrideResponse]:
    await _require_account(db, account_id)
    return [_override(row) for row in await authorization.list_overrides(db, account_id)]


@admin_router.post("/accounts/{account_id}/overrides", status_code=status.HTTP_201_CREATED)
async def create_override(
    account_id: uuid.UUID,
    body: OverrideRequest,
    admin: SystemAdmin,
    db: DbSession,
    facts: OrgFacts,
) -> OverrideResponse:
    try:
        row = await authorization.create_override(
            db,
            facts,
            account_id=account_id,
            permission=body.permission,
            unit_id=body.unit_id,
            effect=body.effect,
            reason=body.reason,
            actor_id=admin.id,
        )
    except service.AccountNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Account not found.") from None
    except authorization.InactiveAccountError:
        raise HTTPException(status.HTTP_409_CONFLICT, "The account is not active.") from None
    except authorization.UnknownUnitError:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Unit not found or not active."
        ) from None
    except authorization.EmptyReasonError:  # pragma: no cover - also enforced by the schema
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "A reason is required."
        ) from None
    except authorization.DuplicateRuleError:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "An identical override is already in force."
        ) from None
    return _override(row)


@admin_router.post("/overrides/{override_id}/end")
async def end_override(
    override_id: uuid.UUID, admin: SystemAdmin, db: DbSession
) -> OverrideResponse:
    try:
        return _override(await authorization.end_override(db, override_id, admin.id))
    except authorization.RuleNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Override not found.") from None
    except authorization.RuleAlreadyEndedError:
        raise HTTPException(status.HTTP_409_CONFLICT, "The override has already ended.") from None


# --- Effective access ---------------------------------------------------------------------------


@admin_router.get("/accounts/{account_id}/effective-access")
async def inspect_effective_access(
    account_id: uuid.UUID,
    _: SystemAdmin,
    db: DbSession,
    facts: OrgFacts,
    as_of: datetime | None = None,
) -> EffectiveAccessResponse:
    """Any account's effective access, now or `as_of` a past time, with what decided each answer.

    A past time uses the account status, assignments, structure and rules valid at that time.
    """
    if as_of is not None and as_of.tzinfo is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "as_of must include a time zone offset."
        )
    await _require_account(db, account_id)
    return await _effective_access(db, facts, account_id, as_of)


@access_router.get("/me")
async def my_effective_access(
    account: CurrentAccount, db: DbSession, facts: OrgFacts
) -> EffectiveAccessResponse:
    return await _effective_access(db, facts, account.id, None)


# --- System Admin grants ------------------------------------------------------------------------


@admin_router.get("/system-admins")
async def list_system_admins(_: SystemAdmin, db: DbSession) -> list[SystemAdminResponse]:
    return [
        SystemAdminResponse(
            account_id=account.id,
            username=account.username,
            granted_at=grant.granted_at,
            granted_by_account_id=grant.granted_by_account_id,
        )
        for grant, account in await service.list_system_admins(db)
    ]


@admin_router.post("/accounts/{account_id}/system-admin", status_code=status.HTTP_201_CREATED)
async def grant_system_admin(
    account_id: uuid.UUID, admin: SystemAdmin, db: DbSession
) -> SystemAdminResponse:
    try:
        grant = await service.grant_system_admin(db, account_id, admin.id)
    except service.AccountNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Account not found.") from None
    except service.AccountStateError:
        raise HTTPException(status.HTTP_409_CONFLICT, "The account is not active.") from None
    except service.AlreadySystemAdminError:
        raise HTTPException(status.HTTP_409_CONFLICT, "Already a System Admin.") from None
    account = await db.get_one(UserAccount, account_id)
    return SystemAdminResponse(
        account_id=account.id,
        username=account.username,
        granted_at=grant.granted_at,
        granted_by_account_id=grant.granted_by_account_id,
    )


@admin_router.post(
    "/accounts/{account_id}/system-admin/revoke", status_code=status.HTTP_204_NO_CONTENT
)
async def revoke_system_admin(account_id: uuid.UUID, admin: SystemAdmin, db: DbSession) -> None:
    try:
        await service.revoke_system_admin(db, account_id, admin.id)
    except service.AccountStateError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not a System Admin.") from None
    except service.LastSystemAdminError:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "The final System Admin cannot be revoked."
        ) from None


# --- Helpers ------------------------------------------------------------------------------------


async def _require_account(db: DbSession, account_id: uuid.UUID) -> None:
    if await db.get(UserAccount, account_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Account not found.")


async def _effective_access(
    db: DbSession, facts: OrganizationFacts, account_id: uuid.UUID, at: datetime | None
) -> EffectiveAccessResponse:
    evaluated_at, by_permission = await authorization.explain_access(db, facts, account_id, at)
    return EffectiveAccessResponse(
        account_id=account_id,
        at=evaluated_at,
        permissions=[
            PermissionAccessResponse(
                permission=permission,
                units=[
                    UnitDecisionResponse(
                        unit_id=item.unit.id,
                        name=item.unit.name,
                        kind=item.unit.kind,
                        allowed=item.decision.allowed,
                        source=item.decision.source,
                        decided_at_unit_id=item.decision.decided_at_unit_id,
                    )
                    for item in items
                ],
            )
            for permission, items in by_permission.items()
        ],
    )


def _role_default(row: RolePermissionDefault) -> RoleDefaultResponse:
    return RoleDefaultResponse(
        id=row.id,
        role_key=row.role_key,
        permission=row.permission_key,
        valid_from=row.valid_from,
        valid_to=row.valid_to,
        created_by_account_id=row.created_by_account_id,
        ended_by_account_id=row.ended_by_account_id,
    )


def _override(row: PermissionOverride) -> OverrideResponse:
    return OverrideResponse(
        id=row.id,
        account_id=row.account_id,
        permission=row.permission_key,
        unit_id=row.unit_id,
        effect=row.effect,
        reason=row.reason,
        valid_from=row.valid_from,
        valid_to=row.valid_to,
        created_by_account_id=row.created_by_account_id,
        ended_by_account_id=row.ended_by_account_id,
    )
