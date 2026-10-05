from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from kora_api.access.dependencies import CSRF_COOKIE, SESSION_COOKIE
from kora_api.access.models import AccountStatus
from tests.access.helpers import ME, PASSWORD, create_account, sign_in

pytestmark = pytest.mark.anyio

GENERIC_FAILURE = {"detail": "Invalid username or password."}


async def test_sign_in_sets_session_and_returns_account(
    db_client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_account(db_session, "alice")

    response = await sign_in(db_client, "alice")

    assert response.status_code == 200
    body = response.json()
    assert body["account"]["username"] == "alice"
    assert body["account"]["must_change_password"] is False
    assert body["account"]["is_system_admin"] is False
    assert body["csrf_token"]
    set_cookie = response.headers.get_list("set-cookie")
    session_cookie = next(c for c in set_cookie if c.startswith(f"{SESSION_COOKIE}="))
    assert "HttpOnly" in session_cookie
    assert "Secure" in session_cookie
    assert any(c.startswith(f"{CSRF_COOKIE}=") for c in set_cookie)
    assert (await db_client.get(ME)).status_code == 200


async def test_username_is_case_insensitive(
    db_client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_account(db_session, "alice")

    response = await sign_in(db_client, "ALIce")

    assert response.status_code == 200
    assert response.json()["account"]["username"] == "alice"


@pytest.mark.parametrize(
    ("username", "password"),
    [
        ("alice", "wrong password"),  # wrong password
        ("nobody", PASSWORD),  # unknown account
        ("bad name!", PASSWORD),  # violates username rules
        ("deactivated", PASSWORD),  # deactivated account, correct password
        ("expiredtemp", PASSWORD),  # temporary password past its expiry
    ],
)
async def test_credential_failures_are_generic(
    db_client: AsyncClient, db_session: AsyncSession, username: str, password: str
) -> None:
    await create_account(db_session, "alice")
    await create_account(db_session, "deactivated", status=AccountStatus.DEACTIVATED)
    await create_account(
        db_session, "expiredtemp", temporary=True, temporary_expires_in=timedelta(seconds=-1)
    )

    response = await sign_in(db_client, username, password)

    assert response.status_code == 401
    assert response.json() == GENERIC_FAILURE
    assert "set-cookie" not in response.headers
