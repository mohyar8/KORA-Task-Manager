import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    Enum,
    ForeignKey,
    Index,
    LargeBinary,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from kora_api.access.permissions import OverrideEffect
from kora_api.core.database import Base


def _enum_values(enum_cls: type[enum.StrEnum]) -> list[str]:
    """Persist enum values (not member names) in PostgreSQL enum types."""
    return [member.value for member in enum_cls]


class AccountStatus(enum.StrEnum):
    ACTIVE = "active"
    DEACTIVATED = "deactivated"


class SessionRevokeReason(enum.StrEnum):
    SIGN_OUT = "sign_out"
    SIGN_OUT_ALL = "sign_out_all"
    PASSWORD_CHANGE = "password_change"
    ACCOUNT_DEACTIVATED = "account_deactivated"


class UserAccount(Base):
    """A login identity. Distinct from organizational Member records. Never hard-deleted."""

    __tablename__ = "user_accounts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # Stored normalized (lowercase), which makes usernames case-insensitive.
    username: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    password_is_temporary: Mapped[bool]
    temporary_password_expires_at: Mapped[datetime | None]
    password_changed_at: Mapped[datetime]
    status: Mapped[AccountStatus] = mapped_column(
        Enum(AccountStatus, name="account_status", values_callable=_enum_values)
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class AuthSession(Base):
    """Server-side session. Only hashes of the session and CSRF tokens are stored."""

    __tablename__ = "auth_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_accounts.id"), index=True)
    token_hash: Mapped[bytes] = mapped_column(LargeBinary(32), unique=True)
    csrf_token_hash: Mapped[bytes] = mapped_column(LargeBinary(32))
    created_at: Mapped[datetime]
    last_seen_at: Mapped[datetime]
    expires_at: Mapped[datetime]
    revoked_at: Mapped[datetime | None]
    revoke_reason: Mapped[SessionRevokeReason | None] = mapped_column(
        Enum(SessionRevokeReason, name="session_revoke_reason", values_callable=_enum_values)
    )


class AccountDeactivation(Base):
    """A period during which an account was deactivated; open while it still is.

    Append-only history so access can be reconstructed for any past time. `UserAccount.status`
    is the current value; an account is inactive at T when a period here contains T.
    """

    __tablename__ = "account_deactivations"
    __table_args__ = (
        CheckConstraint(
            "reactivated_at IS NULL OR reactivated_at > deactivated_at", name="valid_period"
        ),
        Index(
            "uq_account_deactivations_open",
            "account_id",
            unique=True,
            postgresql_where=text("reactivated_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_accounts.id"), index=True)
    deactivated_at: Mapped[datetime]
    reactivated_at: Mapped[datetime | None]


class LoginThrottle(Base):
    """Failed sign-in counter per normalized username (existing or not)."""

    __tablename__ = "login_throttles"

    username: Mapped[str] = mapped_column(String(64), primary_key=True)
    failure_count: Mapped[int]
    window_started_at: Mapped[datetime]
    locked_until: Mapped[datetime | None]


class SystemAdminGrant(Base):
    """System Admin authority, kept separate from organizational roles.

    Append-only: revoking sets `revoked_at`/`revoked_by_account_id`; rows are never deleted.
    """

    __tablename__ = "system_admin_grants"
    __table_args__ = (
        Index(
            "uq_system_admin_grants_active_account",
            "account_id",
            unique=True,
            postgresql_where=text("revoked_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_accounts.id"))
    granted_at: Mapped[datetime]
    # NULL only for the bootstrap grant.
    granted_by_account_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_accounts.id"))
    revoked_at: Mapped[datetime | None]
    revoked_by_account_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_accounts.id"))


# --- Authorization ------------------------------------------------------------------------------
# Rows below are append-only: a change closes the current row (`valid_to`, `ended_by_account_id`)
# and inserts a new one. A row applies at time T when valid_from <= T < valid_to (or open).
# Foreign keys to `org_roles` / `org_units` are table-level only; `access` never imports
# `organization`.

_VALID_PERIOD = "valid_to IS NULL OR valid_to > valid_from"


class PermissionDefinition(Base):
    """The permission catalog, seeded by migration from `access.permissions.Permission`."""

    __tablename__ = "permissions"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    description: Mapped[str] = mapped_column(String(255))


class RolePermissionDefault(Base):
    """A permission an organizational role grants by default, scoped to the role's unit."""

    __tablename__ = "role_permission_defaults"
    __table_args__ = (
        CheckConstraint(_VALID_PERIOD, name="valid_period"),
        Index(
            "uq_role_permission_defaults_open",
            "role_key",
            "permission_key",
            unique=True,
            postgresql_where=text("valid_to IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    role_key: Mapped[str] = mapped_column(String(64), ForeignKey("org_roles.key"))
    permission_key: Mapped[str] = mapped_column(String(100), ForeignKey("permissions.key"))
    valid_from: Mapped[datetime]
    valid_to: Mapped[datetime | None]
    # NULL only for rows seeded by migration.
    created_by_account_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_accounts.id"))
    ended_by_account_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_accounts.id"))


class PermissionOverride(Base):
    """An explicit, reasoned grant or deny of one permission for one account at one unit scope.

    Applies to any active account, Member or not. Overrides do not expire; a System Admin ends them.
    """

    __tablename__ = "permission_overrides"
    __table_args__ = (
        CheckConstraint(_VALID_PERIOD, name="valid_period"),
        CheckConstraint("length(btrim(reason)) > 0", name="reason_required"),
        Index(
            "uq_permission_overrides_open",
            "account_id",
            "permission_key",
            "unit_id",
            "effect",
            unique=True,
            postgresql_where=text("valid_to IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_accounts.id"), index=True)
    permission_key: Mapped[str] = mapped_column(String(100), ForeignKey("permissions.key"))
    unit_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("org_units.id"))
    effect: Mapped[OverrideEffect] = mapped_column(
        Enum(OverrideEffect, name="override_effect", values_callable=_enum_values)
    )
    reason: Mapped[str] = mapped_column(Text)
    valid_from: Mapped[datetime]
    valid_to: Mapped[datetime | None]
    created_by_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_accounts.id"))
    ended_by_account_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_accounts.id"))
