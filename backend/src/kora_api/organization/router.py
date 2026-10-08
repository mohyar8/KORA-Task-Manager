import uuid
from collections.abc import Awaitable

from fastapi import APIRouter, HTTPException, status

from kora_api.access import service as access_service
from kora_api.access.dependencies import CurrentAccess, SystemAdmin
from kora_api.core.database import DbSession
from kora_api.organization import members, units
from kora_api.organization.schemas import (
    ChangeTeamRequest,
    CreateMemberRequest,
    CreateUnitRequest,
    MemberCreatedResponse,
    MemberProfileFields,
    MemberResponse,
    MoveTeamRequest,
    ReactivateMemberRequest,
    RoleFields,
    TemporaryPasswordResponse,
    UnitResponse,
)

units_router = APIRouter(prefix="/organization/units", tags=["organization"])
members_router = APIRouter(prefix="/admin/members", tags=["admin"])


# --- Units: scoped by organization.manage --------------------------------------------------------


@units_router.get("")
async def list_units(access: CurrentAccess, db: DbSession) -> list[UnitResponse]:
    """Units the caller may manage. Units outside the caller's scope are omitted."""
    return [_unit(view) for view in await units.list_manageable_units(db, access.snapshot)]


@units_router.get("/{unit_id}")
async def get_unit(unit_id: uuid.UUID, access: CurrentAccess, db: DbSession) -> UnitResponse:
    return await _unit_call(units.get_unit(db, access.snapshot, unit_id))


@units_router.post("", status_code=status.HTTP_201_CREATED)
async def create_unit(
    body: CreateUnitRequest, access: CurrentAccess, db: DbSession
) -> UnitResponse:
    return await _unit_call(
        units.create_unit(
            db,
            access.snapshot,
            access.account.id,
            kind=body.kind,
            name=body.name,
            parent_id=body.parent_id,
        )
    )


@units_router.post("/{unit_id}/move")
async def move_team(
    unit_id: uuid.UUID, body: MoveTeamRequest, access: CurrentAccess, db: DbSession
) -> UnitResponse:
    return await _unit_call(
        units.move_team(
            db,
            access.snapshot,
            access.account.id,
            team_id=unit_id,
            administration_id=body.administration_id,
        )
    )


@units_router.post("/{unit_id}/archive")
async def archive_unit(unit_id: uuid.UUID, access: CurrentAccess, db: DbSession) -> UnitResponse:
    return await _unit_call(units.archive_unit(db, access.snapshot, access.account.id, unit_id))


async def _unit_call(call: Awaitable[units.UnitView]) -> UnitResponse:
    try:
        return _unit(await call)
    except units.UnitNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unit not found.") from None
    except units.InvalidStructureError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    except units.StructureConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None


def _unit(view: units.UnitView) -> UnitResponse:
    unit = view.unit
    return UnitResponse(
        id=unit.id,
        kind=unit.kind,
        name=unit.name,
        status=unit.status,
        parent_id=view.parent_id,
        archived_at=unit.archived_at,
    )


# --- Members: System Admin only ------------------------------------------------------------------


@members_router.get("")
async def list_members(_: SystemAdmin, db: DbSession) -> list[MemberResponse]:
    return [_member(view) for view in await members.list_members(db)]


@members_router.get("/{member_id}")
async def get_member(member_id: uuid.UUID, _: SystemAdmin, db: DbSession) -> MemberResponse:
    return await _member_call(members.get_member(db, member_id))


@members_router.post("", status_code=status.HTTP_201_CREATED)
async def create_member(
    body: CreateMemberRequest, admin: SystemAdmin, db: DbSession
) -> MemberCreatedResponse:
    try:
        view, temporary_password = await members.create_member(
            db,
            admin.id,
            username=body.username,
            profile=_profile(body),
            team_id=body.team_id,
            role=_role(body),
        )
    except access_service.InvalidUsernameError:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Username must be 3-64 characters of letters, digits, '.', '_' or '-'.",
        ) from None
    except access_service.UsernameTakenError:
        raise HTTPException(status.HTTP_409_CONFLICT, "That username is already in use.") from None
    except members.InvalidMemberChangeError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    return MemberCreatedResponse(member=_member(view), temporary_password=temporary_password)


@members_router.put("/{member_id}")
async def update_member(
    member_id: uuid.UUID, body: MemberProfileFields, _: SystemAdmin, db: DbSession
) -> MemberResponse:
    return await _member_call(members.update_profile(db, member_id, _profile(body)))


@members_router.post("/{member_id}/team")
async def change_team(
    member_id: uuid.UUID, body: ChangeTeamRequest, admin: SystemAdmin, db: DbSession
) -> MemberResponse:
    return await _member_call(members.change_team(db, admin.id, member_id, body.team_id))


@members_router.post("/{member_id}/role")
async def change_role(
    member_id: uuid.UUID, body: RoleFields, admin: SystemAdmin, db: DbSession
) -> MemberResponse:
    return await _member_call(members.change_role(db, admin.id, member_id, _role(body)))


@members_router.post("/{member_id}/deactivate")
async def deactivate_member(
    member_id: uuid.UUID, admin: SystemAdmin, db: DbSession
) -> MemberResponse:
    return await _member_call(members.deactivate_member(db, admin.id, member_id))


@members_router.post("/{member_id}/reactivate")
async def reactivate_member(
    member_id: uuid.UUID, body: ReactivateMemberRequest, admin: SystemAdmin, db: DbSession
) -> MemberResponse:
    return await _member_call(
        members.reactivate_member(db, admin.id, member_id, team_id=body.team_id, role=_role(body))
    )


@members_router.post("/{member_id}/reset-password")
async def reset_member_password(
    member_id: uuid.UUID, _: SystemAdmin, db: DbSession
) -> TemporaryPasswordResponse:
    try:
        return TemporaryPasswordResponse(
            temporary_password=await members.reset_password(db, member_id)
        )
    except members.MemberNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found.") from None
    except members.MemberStateError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None


async def _member_call(call: Awaitable[members.MemberView]) -> MemberResponse:
    try:
        return _member(await call)
    except members.MemberNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found.") from None
    except members.InvalidMemberChangeError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    except members.MemberStateError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None
    except access_service.LastSystemAdminError:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "The final active System Admin cannot be deactivated."
        ) from None


def _profile(body: MemberProfileFields) -> members.MemberProfile:
    return members.MemberProfile(
        full_name=body.full_name,
        university_id=body.university_id,
        phone=body.phone,
        email=body.email,
        major=body.major,
        academic_year=body.academic_year,
    )


def _role(body: RoleFields) -> members.RoleChoice:
    return members.RoleChoice(role_key=body.role_key, administration_id=body.administration_id)


def _member(view: members.MemberView) -> MemberResponse:
    member = view.member
    return MemberResponse(
        id=member.id,
        account_id=member.account_id,
        username=view.username,
        full_name=member.full_name,
        university_id=member.university_id,
        phone=member.phone,
        email=member.email,
        major=member.major,
        academic_year=member.academic_year,
        status=member.status,
        team_id=view.team_id,
        role_key=view.role_key,
        role_unit_id=view.role_unit_id,
    )
