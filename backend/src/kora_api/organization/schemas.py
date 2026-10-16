import re
import uuid
from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, StringConstraints

from kora_api.organization.constants import MemberStatus, RoleKey, UnitKind, UnitStatus

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


def _blank_to_none(value: str | None) -> str | None:
    return value or None


# Optional profile text: omitted, null or blank are all stored as NULL.
OptionalText200 = Annotated[
    Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] | None,
    AfterValidator(_blank_to_none),
]
OptionalText64 = Annotated[
    Annotated[str, StringConstraints(strip_whitespace=True, max_length=64)] | None,
    AfterValidator(_blank_to_none),
]
OptionalText32 = Annotated[
    Annotated[str, StringConstraints(strip_whitespace=True, max_length=32)] | None,
    AfterValidator(_blank_to_none),
]
# One "@", no whitespace, and a dot in the domain. Deliberately simple: deliverability is not
# checked, and no dependency is needed.
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _valid_email(value: str | None) -> str | None:
    if value is not None and not _EMAIL.fullmatch(value):
        raise ValueError("value is not a valid email address")
    return value


OptionalEmail = Annotated[
    Annotated[str, StringConstraints(strip_whitespace=True, max_length=254)] | None,
    AfterValidator(_blank_to_none),
    AfterValidator(_valid_email),
]


# --- Units --------------------------------------------------------------------------------------


class CreateUnitRequest(BaseModel):
    kind: UnitKind
    name: Name
    parent_id: uuid.UUID


class MoveTeamRequest(BaseModel):
    administration_id: uuid.UUID


class UnitResponse(BaseModel):
    id: uuid.UUID
    kind: UnitKind
    name: str
    status: UnitStatus
    parent_id: uuid.UUID | None
    archived_at: datetime | None


# --- Members ------------------------------------------------------------------------------------


class MemberProfileFields(BaseModel):
    full_name: Name
    university_id: OptionalText64 = None
    phone: OptionalText32 = None
    email: OptionalEmail = None
    major: OptionalText200 = None
    academic_year: OptionalText32 = None


class RoleFields(BaseModel):
    role_key: RoleKey
    # Required for Administration Manager only.
    administration_id: uuid.UUID | None = None


class CreateMemberRequest(MemberProfileFields, RoleFields):
    username: Annotated[str, StringConstraints(min_length=1, max_length=256)]
    # Required for Team Leader and Member; optional for the roles held at KORA, the PMO or an
    # Administration.
    team_id: uuid.UUID | None = None


class ChangeTeamRequest(BaseModel):
    team_id: uuid.UUID


class ReactivateMemberRequest(RoleFields):
    team_id: uuid.UUID | None = None


class MemberResponse(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID
    username: str
    full_name: str
    university_id: str | None
    phone: str | None
    email: str | None
    major: str | None
    academic_year: str | None
    status: MemberStatus
    # Null while deactivated.
    team_id: uuid.UUID | None
    role_key: RoleKey | None
    role_unit_id: uuid.UUID | None


class MemberCreatedResponse(BaseModel):
    member: MemberResponse
    temporary_password: str


class TemporaryPasswordResponse(BaseModel):
    temporary_password: str


class DirectoryMemberResponse(BaseModel):
    """A Member as visible to colleagues: no contact or academic data."""

    id: uuid.UUID
    full_name: str
    team_id: uuid.UUID | None
    role_key: RoleKey | None
