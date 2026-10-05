import enum
import uuid
from datetime import datetime

from sqlalchemy import Enum, ForeignKey, Index, LargeBinary, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

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
