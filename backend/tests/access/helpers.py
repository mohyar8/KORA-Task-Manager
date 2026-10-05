from datetime import timedelta

from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from kora_api.access import security
from kora_api.access.dependencies import CSRF_HEADER
from kora_api.access.models import AccountStatus, SystemAdminGrant, UserAccount
from kora_api.core import clock

PASSWORD = "correct horse battery"
SIGN_IN = "/api/v1/auth/sign-in"
SIGN_OUT = "/api/v1/auth/sign-out"
SIGN_OUT_ALL = "/api/v1/auth/sign-out-all"
ME = "/api/v1/auth/me"
CHANGE_PASSWORD = "/api/v1/auth/change-password"


async def create_account(
    db: AsyncSession,
    username: str,
    password: str = PASSWORD,
    *,
    temporary: bool = False,
    temporary_expires_in: timedelta = timedelta(days=7),
    status: AccountStatus = AccountStatus.ACTIVE,
    system_admin: bool = False,
) -> UserAccount:
    now = clock.utcnow()
    account = UserAccount(
        username=username,
        password_hash=security.hash_password(password),
        password_is_temporary=temporary,
        temporary_password_expires_at=now + temporary_expires_in if temporary else None,
        password_changed_at=now,
        status=status,
    )
    db.add(account)
    await db.flush()
    if system_admin:
        db.add(SystemAdminGrant(account_id=account.id, granted_at=now))
    await db.commit()
    return account


async def sign_in(client: AsyncClient, username: str, password: str = PASSWORD) -> Response:
    return await client.post(SIGN_IN, json={"username": username, "password": password})


async def signed_in(client: AsyncClient, username: str, password: str = PASSWORD) -> str:
    """Sign in, assert success, and return the CSRF token."""
    response = await sign_in(client, username, password)
    assert response.status_code == 200, response.text
    csrf: str = response.json()["csrf_token"]
    return csrf


def csrf_headers(csrf_token: str) -> dict[str, str]:
    return {CSRF_HEADER: csrf_token}
