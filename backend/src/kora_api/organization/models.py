"""Organization tables. History rows are append-only: a change closes the current row
(`valid_to`, `ended_by_account_id`) and opens a new one. Nothing is hard-deleted."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from kora_api.core.database import Base
from kora_api.organization.constants import MemberStatus, UnitKind, UnitStatus

_VALID_PERIOD = "valid_to IS NULL OR valid_to > valid_from"


def _enum_values(enum_cls: type[enum.StrEnum]) -> list[str]:
    return [member.value for member in enum_cls]


def _unit_kind_enum() -> Enum:
    return Enum(UnitKind, name="org_unit_kind", values_callable=_enum_values)


class OrgUnit(Base):
    """KORA (root), the PMO, Administrations and Teams. Archived, never deleted."""

    __tablename__ = "org_units"
    __table_args__ = (
        Index(
            "uq_org_units_single_organization",
            "kind",
            unique=True,
            postgresql_where=text("kind = 'organization'"),
        ),
        Index(
            "uq_org_units_single_pmo", "kind", unique=True, postgresql_where=text("kind = 'pmo'")
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    kind: Mapped[UnitKind] = mapped_column(_unit_kind_enum())
    name: Mapped[str] = mapped_column(String(200))
    status: Mapped[UnitStatus] = mapped_column(
        Enum(UnitStatus, name="org_unit_status", values_callable=_enum_values)
    )
    created_at: Mapped[datetime]
    # NULL only for units seeded by migration.
    created_by_account_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_accounts.id"))
    archived_at: Mapped[datetime | None]
    archived_by_account_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_accounts.id"))


class OrgUnitPlacement(Base):
    """A unit's parent over time. Moving a Team closes its placement and opens a new one."""

    __tablename__ = "org_unit_placements"
    __table_args__ = (
        CheckConstraint(_VALID_PERIOD, name="valid_period"),
        CheckConstraint("unit_id <> parent_id", name="not_own_parent"),
        Index(
            "uq_org_unit_placements_open",
            "unit_id",
            unique=True,
            postgresql_where=text("valid_to IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    unit_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("org_units.id"), index=True)
    parent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("org_units.id"), index=True)
    valid_from: Mapped[datetime]
    valid_to: Mapped[datetime | None]
    # NULL only for placements seeded by migration.
    created_by_account_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_accounts.id"))
    ended_by_account_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_accounts.id"))


class OrgRole(Base):
    """Fixed catalog of organizational roles, seeded by migration from `constants.ROLES`."""

    __tablename__ = "org_roles"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    unit_kind: Mapped[UnitKind] = mapped_column(_unit_kind_enum())


class Member(Base):
    """A person in the organization. Always linked to exactly one User Account."""

    __tablename__ = "members"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_accounts.id"), unique=True)
    full_name: Mapped[str] = mapped_column(String(200))
    # Optional profile data; only the account link is unique.
    university_id: Mapped[str | None] = mapped_column(String(64))
    phone: Mapped[str | None] = mapped_column(String(32))
    email: Mapped[str | None] = mapped_column(String(254))
    major: Mapped[str | None] = mapped_column(String(200))
    academic_year: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[MemberStatus] = mapped_column(
        Enum(MemberStatus, name="member_status", values_callable=_enum_values)
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class MemberTeamPlacement(Base):
    """The Team a Member belongs to over time. An active Member has exactly one open row."""

    __tablename__ = "member_team_placements"
    __table_args__ = (
        CheckConstraint(_VALID_PERIOD, name="valid_period"),
        Index(
            "uq_member_team_placements_open",
            "member_id",
            unique=True,
            postgresql_where=text("valid_to IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    member_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("members.id"), index=True)
    team_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("org_units.id"), index=True)
    valid_from: Mapped[datetime]
    valid_to: Mapped[datetime | None]
    created_by_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_accounts.id"))
    ended_by_account_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_accounts.id"))


class RoleAssignment(Base):
    """A Member's organizational role and its scope unit. An active Member has one open row."""

    __tablename__ = "role_assignments"
    __table_args__ = (
        CheckConstraint(_VALID_PERIOD, name="valid_period"),
        Index(
            "uq_role_assignments_open",
            "member_id",
            unique=True,
            postgresql_where=text("valid_to IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    member_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("members.id"), index=True)
    role_key: Mapped[str] = mapped_column(String(64), ForeignKey("org_roles.key"))
    unit_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("org_units.id"), index=True)
    valid_from: Mapped[datetime]
    valid_to: Mapped[datetime | None]
    created_by_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_accounts.id"))
    ended_by_account_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_accounts.id"))
