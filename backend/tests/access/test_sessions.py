from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kora_api.access import service
from kora_api.access.models import AuthSession, SessionRevokeReason
from kora_api.access.policy import SESSION_ABSOLUTE_LIFETIME, SESSION_IDLE_TIMEOUT
from tests.access.helpers import (
    ME,
    SIGN_OUT,
    SIGN_OUT_ALL,
    create_account,
    csrf_headers,
    signed_in,
)
from tests.conftest import ClientFactory, FrozenClock

pytestmark = pytest.mark.anyio


async def test_requests_without_a_session_are_rejected(db_client: AsyncClient) -> None:
    assert (await db_client.get(ME)).status_code == 401


async def test_unsafe_requests_require_matching_csrf_token(
    db_client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_account(db_session, "alice")
    csrf = await signed_in(db_client, "alice")

    assert (await db_client.post(SIGN_OUT)).status_code == 403
    assert (await db_client.post(SIGN_OUT, headers=csrf_headers("forged"))).status_code == 403
    assert (await db_client.get(ME)).status_code == 200  # session untouched
    assert (await db_client.post(SIGN_OUT, headers=csrf_headers(csrf))).status_code == 204


async def test_sign_out_revokes_the_session(
    client_factory: ClientFactory, db_session: AsyncSession
) -> None:
    await create_account(db_session, "alice")
    client = client_factory()
    csrf = await signed_in(client, "alice")
    token = client.cookies["kora_session"]

    assert (await client.post(SIGN_OUT, headers=csrf_headers(csrf))).status_code == 204

    # Replaying the old cookie value from elsewhere must not work.
    replay = await client_factory().get(ME, headers={"Cookie": f"kora_session={token}"})
    assert replay.status_code == 401
    session = await db_session.scalar(select(AuthSession))
    assert session is not None
    assert session.revoke_reason == SessionRevokeReason.SIGN_OUT


async def test_sign_out_all_revokes_every_session(
    client_factory: ClientFactory, db_session: AsyncSession
) -> None:
    await create_account(db_session, "alice")
    laptop, phone = client_factory(), client_factory()
    csrf = await signed_in(laptop, "alice")
    await signed_in(phone, "alice")

    assert (await laptop.post(SIGN_OUT_ALL, headers=csrf_headers(csrf))).status_code == 204

    assert (await phone.get(ME)).status_code == 401
    reasons = (await db_session.scalars(select(AuthSession.revoke_reason))).all()
    assert reasons == [SessionRevokeReason.SIGN_OUT_ALL] * 2


async def test_session_expires_after_idle_timeout(
    db_client: AsyncClient, db_session: AsyncSession, frozen_clock: FrozenClock
) -> None:
    await create_account(db_session, "alice")
    await signed_in(db_client, "alice")

    frozen_clock.advance(SESSION_IDLE_TIMEOUT - timedelta(minutes=1))
    assert (await db_client.get(ME)).status_code == 200  # activity extends the idle window

    frozen_clock.advance(SESSION_IDLE_TIMEOUT - timedelta(minutes=1))
    assert (await db_client.get(ME)).status_code == 200

    frozen_clock.advance(SESSION_IDLE_TIMEOUT)
    assert (await db_client.get(ME)).status_code == 401


async def test_session_expires_at_absolute_lifetime_despite_activity(
    db_client: AsyncClient, db_session: AsyncSession, frozen_clock: FrozenClock
) -> None:
    await create_account(db_session, "alice")
    await signed_in(db_client, "alice")
    step = timedelta(hours=7)
    elapsed = timedelta()

    while elapsed + step < SESSION_ABSOLUTE_LIFETIME:
        frozen_clock.advance(step)
        elapsed += step
        assert (await db_client.get(ME)).status_code == 200

    frozen_clock.advance(SESSION_ABSOLUTE_LIFETIME - elapsed)
    assert (await db_client.get(ME)).status_code == 401


async def test_deactivating_an_account_ends_its_sessions(
    db_client: AsyncClient, db_session: AsyncSession
) -> None:
    account = await create_account(db_session, "alice")
    await signed_in(db_client, "alice")

    await service.deactivate_account(db_session, account.id)

    assert (await db_client.get(ME)).status_code == 401
