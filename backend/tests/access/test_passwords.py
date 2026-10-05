import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from kora_api.access.dependencies import CurrentAccount
from tests.access.helpers import (
    CHANGE_PASSWORD,
    ME,
    PASSWORD,
    SIGN_OUT,
    create_account,
    csrf_headers,
    sign_in,
    signed_in,
)
from tests.conftest import ClientFactory

pytestmark = pytest.mark.anyio

PROTECTED = "/api/v1/_test/protected"
NEW_PASSWORD = "a brand new passphrase"


@pytest.fixture(autouse=True)
def protected_route(db_app: FastAPI) -> None:
    """Stands in for any normal route guarded by CurrentAccount."""

    @db_app.get(PROTECTED)
    async def protected(account: CurrentAccount) -> dict[str, str]:  # pyright: ignore[reportUnusedFunction]
        return {"username": account.username}


async def test_temporary_password_restricts_session_until_changed(
    db_client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_account(db_session, "alice", temporary=True)
    csrf = await signed_in(db_client, "alice")

    assert (await db_client.get(ME)).json()["must_change_password"] is True
    blocked = await db_client.get(PROTECTED)
    assert blocked.status_code == 403
    assert blocked.json() == {"detail": "Password change required."}

    changed = await db_client.post(
        CHANGE_PASSWORD,
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
        headers=csrf_headers(csrf),
    )

    assert changed.status_code == 200
    assert changed.json()["account"]["must_change_password"] is False
    assert (await db_client.get(PROTECTED)).status_code == 200


async def test_sign_out_remains_available_with_temporary_password(
    db_client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_account(db_session, "alice", temporary=True)
    csrf = await signed_in(db_client, "alice")

    assert (await db_client.post(SIGN_OUT, headers=csrf_headers(csrf))).status_code == 204


async def test_password_change_revokes_all_existing_sessions(
    client_factory: ClientFactory, db_session: AsyncSession
) -> None:
    await create_account(db_session, "alice")
    laptop, phone = client_factory(), client_factory()
    csrf = await signed_in(laptop, "alice")
    await signed_in(phone, "alice")
    old_token = laptop.cookies["kora_session"]

    response = await laptop.post(
        CHANGE_PASSWORD,
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
        headers=csrf_headers(csrf),
    )

    assert response.status_code == 200
    assert (await phone.get(ME)).status_code == 401
    assert laptop.cookies["kora_session"] != old_token
    assert (await laptop.get(ME)).status_code == 200  # the fresh session works
    assert (await sign_in(phone, "alice")).status_code == 401
    assert (await sign_in(phone, "alice", NEW_PASSWORD)).status_code == 200


async def test_change_password_rejects_wrong_current_password(
    db_client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_account(db_session, "alice")
    csrf = await signed_in(db_client, "alice")

    response = await db_client.post(
        CHANGE_PASSWORD,
        json={"current_password": "not it at all", "new_password": NEW_PASSWORD},
        headers=csrf_headers(csrf),
    )

    assert response.status_code == 400


@pytest.mark.parametrize("new_password", ["short77", "x" * 129])
async def test_change_password_enforces_length_policy(
    db_client: AsyncClient, db_session: AsyncSession, new_password: str
) -> None:
    await create_account(db_session, "alice")
    csrf = await signed_in(db_client, "alice")

    response = await db_client.post(
        CHANGE_PASSWORD,
        json={"current_password": PASSWORD, "new_password": new_password},
        headers=csrf_headers(csrf),
    )

    assert response.status_code == 422
