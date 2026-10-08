"""Account authentication, sessions and System Admin rules. All times are UTC via `clock`."""

import math
import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import case, exists, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from kora_api.access import security
from kora_api.access.models import (
    AccountDeactivation,
    AccountStatus,
    AuthSession,
    LoginThrottle,
    SessionRevokeReason,
    SystemAdminGrant,
    UserAccount,
)
from kora_api.access.policy import (
    LOGIN_FAILURE_WINDOW,
    LOGIN_LOCKOUT_DURATION,
    LOGIN_MAX_FAILURES,
    SESSION_ABSOLUTE_LIFETIME,
    SESSION_IDLE_TIMEOUT,
    SESSION_TOUCH_INTERVAL,
    TEMPORARY_PASSWORD_LIFETIME,
)
from kora_api.core import clock


class AuthenticationFailedError(Exception):
    """Generic credential failure. Never says which part of the credentials was wrong."""


class SignInLockedError(Exception):
    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__("Too many failed sign-in attempts.")
        self.retry_after_seconds = retry_after_seconds


class CurrentPasswordIncorrectError(Exception):
    pass


class InvalidPasswordError(Exception):
    pass


class InvalidUsernameError(Exception):
    pass


class UsernameTakenError(Exception):
    pass


class BootstrapAlreadyCompletedError(Exception):
    pass


class LastSystemAdminError(Exception):
    pass


class AccountNotFoundError(Exception):
    pass


class AccountStateError(Exception):
    """The account is not in a state that allows the operation (e.g. inactive)."""


class AlreadySystemAdminError(Exception):
    pass


@dataclass(frozen=True)
class IssuedSession:
    session: AuthSession
    token: str
    csrf_token: str


# --- Sign-in -----------------------------------------------------------------------------------


async def sign_in(db: AsyncSession, raw_username: str, password: str) -> IssuedSession:
    now = clock.utcnow()
    username = security.normalize_username(raw_username)
    if username is None:
        # Cannot match any account; spend equal work and fail without creating a throttle row.
        security.burn_password_check(password)
        raise AuthenticationFailedError

    throttle = await db.get(LoginThrottle, username, populate_existing=True)
    if throttle and throttle.locked_until and throttle.locked_until > now:
        raise SignInLockedError(math.ceil((throttle.locked_until - now).total_seconds()))

    account = await db.scalar(select(UserAccount).where(UserAccount.username == username))
    if account is None:
        security.burn_password_check(password)
        valid = False
    else:
        valid = (
            security.verify_password(account.password_hash, password)
            and account.status == AccountStatus.ACTIVE
            and not _temporary_password_expired(account, now)
        )

    if account is None or not valid:
        await _record_failed_sign_in(db, username, now)
        await db.commit()
        raise AuthenticationFailedError

    if throttle is not None:
        await db.delete(throttle)
    if security.password_needs_rehash(account.password_hash):
        account.password_hash = security.hash_password(password)
    issued = _issue_session(db, account.id, now)
    await db.commit()
    return issued


async def _record_failed_sign_in(db: AsyncSession, username: str, now: datetime) -> None:
    """Atomically count a failure in the current window and lock once the limit is reached."""
    table = LoginThrottle.__table__
    window_expired = table.c.window_started_at <= now - LOGIN_FAILURE_WINDOW
    new_count = case((window_expired, 1), else_=table.c.failure_count + 1)
    stmt = (
        pg_insert(LoginThrottle)
        .values(username=username, failure_count=1, window_started_at=now, locked_until=None)
        .on_conflict_do_update(
            index_elements=[LoginThrottle.username],
            set_={
                "failure_count": new_count,
                "window_started_at": case((window_expired, now), else_=table.c.window_started_at),
                "locked_until": case(
                    (new_count >= LOGIN_MAX_FAILURES, now + LOGIN_LOCKOUT_DURATION), else_=None
                ),
            },
        )
    )
    await db.execute(stmt)


def _temporary_password_expired(account: UserAccount, now: datetime) -> bool:
    expires_at = account.temporary_password_expires_at
    return account.password_is_temporary and (expires_at is None or expires_at <= now)


# --- Sessions ----------------------------------------------------------------------------------


def _issue_session(db: AsyncSession, account_id: uuid.UUID, now: datetime) -> IssuedSession:
    token = security.generate_token()
    csrf_token = security.generate_token()
    session = AuthSession(
        account_id=account_id,
        token_hash=security.hash_token(token),
        csrf_token_hash=security.hash_token(csrf_token),
        created_at=now,
        last_seen_at=now,
        expires_at=now + SESSION_ABSOLUTE_LIFETIME,
        revoked_at=None,
        revoke_reason=None,
    )
    db.add(session)
    return IssuedSession(session=session, token=token, csrf_token=csrf_token)


async def resolve_session(db: AsyncSession, token: str) -> tuple[AuthSession, UserAccount] | None:
    """Return the live session and its account, or None if it is unknown, revoked or expired."""
    now = clock.utcnow()
    row = (
        await db.execute(
            select(AuthSession, UserAccount)
            .join(UserAccount, UserAccount.id == AuthSession.account_id)
            .where(AuthSession.token_hash == security.hash_token(token))
        )
    ).one_or_none()
    if row is None:
        return None
    session, account = row
    if (
        session.revoked_at is not None
        or now >= session.expires_at
        or now - session.last_seen_at >= SESSION_IDLE_TIMEOUT
        or account.status != AccountStatus.ACTIVE
    ):
        return None
    if now - session.last_seen_at >= SESSION_TOUCH_INTERVAL:
        session.last_seen_at = now
        await db.commit()
    return session, account


async def sign_out(db: AsyncSession, session: AuthSession) -> None:
    session.revoked_at = clock.utcnow()
    session.revoke_reason = SessionRevokeReason.SIGN_OUT
    await db.commit()


async def sign_out_all(db: AsyncSession, account_id: uuid.UUID) -> None:
    await _revoke_all_sessions(db, account_id, SessionRevokeReason.SIGN_OUT_ALL)
    await db.commit()


async def _revoke_all_sessions(
    db: AsyncSession, account_id: uuid.UUID, reason: SessionRevokeReason
) -> None:
    await db.execute(
        update(AuthSession)
        .where(AuthSession.account_id == account_id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=clock.utcnow(), revoke_reason=reason)
        .execution_options(synchronize_session="fetch")
    )


# --- Passwords ---------------------------------------------------------------------------------


async def change_password(
    db: AsyncSession, account: UserAccount, current_password: str, new_password: str
) -> IssuedSession:
    """Change the password, revoke every existing session, and issue a fresh one."""
    now = clock.utcnow()
    if _temporary_password_expired(account, now) or not security.verify_password(
        account.password_hash, current_password
    ):
        raise CurrentPasswordIncorrectError
    if not security.is_valid_password(new_password):
        raise InvalidPasswordError

    account.password_hash = security.hash_password(new_password)
    account.password_is_temporary = False
    account.temporary_password_expires_at = None
    account.password_changed_at = now
    await _revoke_all_sessions(db, account.id, SessionRevokeReason.PASSWORD_CHANGE)
    issued = _issue_session(db, account.id, now)
    await db.commit()
    return issued


# --- Accounts and System Admin -----------------------------------------------------------------


async def is_system_admin(db: AsyncSession, account_id: uuid.UUID) -> bool:
    stmt = select(
        exists().where(
            SystemAdminGrant.account_id == account_id, SystemAdminGrant.revoked_at.is_(None)
        )
    )
    return bool(await db.scalar(stmt))


async def bootstrap_first_system_admin(
    db: AsyncSession, raw_username: str
) -> tuple[UserAccount, str]:
    """Create the first System Admin with a temporary password. Works only once, ever."""
    if security.normalize_username(raw_username) is None:
        raise InvalidUsernameError
    # Serialize concurrent bootstraps; the lock is released at commit/rollback.
    await db.execute(text("LOCK TABLE system_admin_grants IN EXCLUSIVE MODE"))
    if await db.scalar(select(exists().select_from(SystemAdminGrant))):
        raise BootstrapAlreadyCompletedError

    account, temporary_password = await create_account_with_temporary_password(db, raw_username)
    db.add(
        SystemAdminGrant(
            account_id=account.id, granted_at=clock.utcnow(), granted_by_account_id=None
        )
    )
    await db.commit()
    return account, temporary_password


# Transactional building blocks: these flush but never commit, so callers (e.g. Member
# provisioning) can combine them with their own changes in a single transaction.


async def create_account_with_temporary_password(
    db: AsyncSession, raw_username: str
) -> tuple[UserAccount, str]:
    """Create an active account whose password is temporary. Does not commit."""
    username = security.normalize_username(raw_username)
    if username is None:
        raise InvalidUsernameError
    if await db.scalar(select(exists().where(UserAccount.username == username))):
        raise UsernameTakenError

    now = clock.utcnow()
    temporary_password = security.generate_temporary_password()
    account = UserAccount(
        username=username,
        password_hash=security.hash_password(temporary_password),
        password_is_temporary=True,
        temporary_password_expires_at=now + TEMPORARY_PASSWORD_LIFETIME,
        password_changed_at=now,
        status=AccountStatus.ACTIVE,
    )
    db.add(account)
    await db.flush()
    return account, temporary_password


async def reset_to_temporary_password(db: AsyncSession, account_id: uuid.UUID) -> str:
    """Replace the password with a new temporary one and end all sessions. Does not commit."""
    account = await db.get_one(UserAccount, account_id, with_for_update=True)
    now = clock.utcnow()
    temporary_password = security.generate_temporary_password()
    account.password_hash = security.hash_password(temporary_password)
    account.password_is_temporary = True
    account.temporary_password_expires_at = now + TEMPORARY_PASSWORD_LIFETIME
    account.password_changed_at = now
    await _revoke_all_sessions(db, account_id, SessionRevokeReason.PASSWORD_CHANGE)
    return temporary_password


async def deactivate_account(db: AsyncSession, account_id: uuid.UUID) -> None:
    """Deactivate an account and end its sessions. Does not commit.

    Refused for the final active System Admin.
    """
    await _ensure_not_final_system_admin(db, account_id)
    account = await db.get_one(UserAccount, account_id, with_for_update=True)
    account.status = AccountStatus.DEACTIVATED
    db.add(AccountDeactivation(account_id=account_id, deactivated_at=clock.utcnow()))
    await _revoke_all_sessions(db, account_id, SessionRevokeReason.ACCOUNT_DEACTIVATED)


async def reactivate_account(db: AsyncSession, account_id: uuid.UUID) -> None:
    """Make a deactivated account active again. Does not commit."""
    account = await db.get_one(UserAccount, account_id, with_for_update=True)
    account.status = AccountStatus.ACTIVE
    await db.execute(
        update(AccountDeactivation)
        .where(
            AccountDeactivation.account_id == account_id,
            AccountDeactivation.reactivated_at.is_(None),
        )
        .values(reactivated_at=clock.utcnow())
    )


async def grant_system_admin(
    db: AsyncSession, account_id: uuid.UUID, granted_by_account_id: uuid.UUID
) -> SystemAdminGrant:
    account = await db.get(UserAccount, account_id, with_for_update=True)
    if account is None:
        raise AccountNotFoundError
    if account.status != AccountStatus.ACTIVE:
        raise AccountStateError
    if await is_system_admin(db, account_id):
        raise AlreadySystemAdminError
    grant = SystemAdminGrant(
        account_id=account_id,
        granted_at=clock.utcnow(),
        granted_by_account_id=granted_by_account_id,
    )
    db.add(grant)
    await db.commit()
    return grant


async def list_system_admins(db: AsyncSession) -> list[tuple[SystemAdminGrant, UserAccount]]:
    rows = await db.execute(
        select(SystemAdminGrant, UserAccount)
        .join(UserAccount, UserAccount.id == SystemAdminGrant.account_id)
        .where(SystemAdminGrant.revoked_at.is_(None))
        .order_by(UserAccount.username)
    )
    return [(grant, account) for grant, account in rows]


async def revoke_system_admin(
    db: AsyncSession, account_id: uuid.UUID, revoked_by_account_id: uuid.UUID
) -> None:
    """Revoke System Admin authority. Refused for the final active System Admin."""
    if not await is_system_admin(db, account_id):
        raise AccountStateError
    await _ensure_not_final_system_admin(db, account_id)
    await db.execute(
        update(SystemAdminGrant)
        .where(SystemAdminGrant.account_id == account_id, SystemAdminGrant.revoked_at.is_(None))
        .values(revoked_at=clock.utcnow(), revoked_by_account_id=revoked_by_account_id)
    )
    await db.commit()


async def _ensure_not_final_system_admin(db: AsyncSession, account_id: uuid.UUID) -> None:
    # Locks every active grant and its account so concurrent removals are serialized.
    active_admin_ids = (
        await db.scalars(
            select(SystemAdminGrant.account_id)
            .join(UserAccount, UserAccount.id == SystemAdminGrant.account_id)
            .where(
                SystemAdminGrant.revoked_at.is_(None),
                UserAccount.status == AccountStatus.ACTIVE,
            )
            .with_for_update()
        )
    ).all()
    if list(active_admin_ids) == [account_id]:
        raise LastSystemAdminError
