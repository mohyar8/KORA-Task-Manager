from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from kora_api.access.policy import LOGIN_LOCKOUT_DURATION
from tests.access.helpers import create_account, sign_in
from tests.conftest import FrozenClock

pytestmark = pytest.mark.anyio


async def _fail(client: AsyncClient, username: str, times: int) -> None:
    for _ in range(times):
        assert (await sign_in(client, username, "wrong password")).status_code == 401


async def test_fifth_failure_locks_username_for_15_minutes(
    db_client: AsyncClient, db_session: AsyncSession, frozen_clock: FrozenClock
) -> None:
    await create_account(db_session, "alice")
    await _fail(db_client, "alice", 5)

    locked = await sign_in(db_client, "Alice")  # correct password, any letter case
    assert locked.status_code == 429
    assert locked.headers["Retry-After"] == str(int(LOGIN_LOCKOUT_DURATION.total_seconds()))

    frozen_clock.advance(LOGIN_LOCKOUT_DURATION - timedelta(seconds=1))
    assert (await sign_in(db_client, "alice")).status_code == 429

    frozen_clock.advance(timedelta(seconds=1))
    assert (await sign_in(db_client, "alice")).status_code == 200


async def test_failures_outside_the_window_do_not_accumulate(
    db_client: AsyncClient, db_session: AsyncSession, frozen_clock: FrozenClock
) -> None:
    await create_account(db_session, "alice")
    await _fail(db_client, "alice", 4)

    frozen_clock.advance(timedelta(minutes=15))
    await _fail(db_client, "alice", 4)  # a new window starts; still under the limit

    assert (await sign_in(db_client, "alice")).status_code == 200


async def test_successful_sign_in_resets_failure_count(
    db_client: AsyncClient, db_session: AsyncSession, frozen_clock: FrozenClock
) -> None:
    await create_account(db_session, "alice")
    await _fail(db_client, "alice", 4)
    assert (await sign_in(db_client, "alice")).status_code == 200

    await _fail(db_client, "alice", 4)
    assert (await sign_in(db_client, "alice")).status_code == 200


async def test_unknown_usernames_are_throttled_identically(
    db_client: AsyncClient, frozen_clock: FrozenClock
) -> None:
    await _fail(db_client, "ghost", 5)

    assert (await sign_in(db_client, "ghost")).status_code == 429
