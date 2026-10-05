from datetime import timedelta

import pytest
from fastapi.routing import APIRoute
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kora_api.access import service
from kora_api.access.models import AccountStatus, SystemAdminGrant, UserAccount
from kora_api.access.policy import TEMPORARY_PASSWORD_LIFETIME
from kora_api.core.config import Settings
from kora_api.main import create_app
from tests.access.helpers import ME, create_account, sign_in
from tests.conftest import FrozenClock

pytestmark = pytest.mark.anyio


# --- Bootstrap ---------------------------------------------------------------------------------


async def test_bootstrap_creates_system_admin_with_temporary_password(
    db_client: AsyncClient, db_session: AsyncSession, frozen_clock: FrozenClock
) -> None:
    account, temporary_password = await service.bootstrap_first_system_admin(db_session, "Root")

    assert account.username == "root"
    assert account.password_is_temporary is True
    assert account.temporary_password_expires_at == frozen_clock.now + TEMPORARY_PASSWORD_LIFETIME
    assert await service.is_system_admin(db_session, account.id)

    response = await sign_in(db_client, "root", temporary_password)
    assert response.status_code == 200
    assert response.json()["account"] == {
        "id": str(account.id),
        "username": "root",
        "must_change_password": True,
        "is_system_admin": True,
    }


async def test_bootstrap_temporary_password_expires(
    db_client: AsyncClient, db_session: AsyncSession, frozen_clock: FrozenClock
) -> None:
    _, temporary_password = await service.bootstrap_first_system_admin(db_session, "root")

    frozen_clock.advance(TEMPORARY_PASSWORD_LIFETIME + timedelta(seconds=1))

    assert (await sign_in(db_client, "root", temporary_password)).status_code == 401


async def test_bootstrap_runs_only_once(db_session: AsyncSession) -> None:
    await service.bootstrap_first_system_admin(db_session, "root")

    with pytest.raises(service.BootstrapAlreadyCompletedError):
        await service.bootstrap_first_system_admin(db_session, "another")


async def test_bootstrap_refused_once_any_grant_ever_existed(db_session: AsyncSession) -> None:
    first = await create_account(db_session, "first", system_admin=True)
    second = await create_account(db_session, "second", system_admin=True)
    await service.revoke_system_admin(db_session, first.id, revoked_by_account_id=second.id)

    with pytest.raises(service.BootstrapAlreadyCompletedError):
        await service.bootstrap_first_system_admin(db_session, "root")


@pytest.mark.parametrize("username", ["ab", "has space", "x" * 65, "ünicode"])
async def test_bootstrap_rejects_invalid_username(db_session: AsyncSession, username: str) -> None:
    with pytest.raises(service.InvalidUsernameError):
        await service.bootstrap_first_system_admin(db_session, username)


async def test_bootstrap_rejects_taken_username(db_session: AsyncSession) -> None:
    await create_account(db_session, "root")

    with pytest.raises(service.UsernameTakenError):
        await service.bootstrap_first_system_admin(db_session, "ROOT")


def test_bootstrap_has_no_http_endpoint() -> None:
    app = create_app(Settings(environment="test"))
    paths = [route.path for route in app.routes if isinstance(route, APIRoute)]
    assert not [path for path in paths if "bootstrap" in path or "admin" in path]


# --- Final System Admin protection -------------------------------------------------------------


async def test_final_system_admin_cannot_be_deactivated(db_session: AsyncSession) -> None:
    admin = await create_account(db_session, "admin", system_admin=True)

    with pytest.raises(service.LastSystemAdminError):
        await service.deactivate_account(db_session, admin.id)

    await db_session.refresh(admin)
    assert admin.status == AccountStatus.ACTIVE


async def test_final_system_admin_authority_cannot_be_revoked(db_session: AsyncSession) -> None:
    admin = await create_account(db_session, "admin", system_admin=True)

    with pytest.raises(service.LastSystemAdminError):
        await service.revoke_system_admin(db_session, admin.id, revoked_by_account_id=admin.id)

    assert await service.is_system_admin(db_session, admin.id)


async def test_deactivated_admins_do_not_count_toward_the_remaining_admins(
    db_session: AsyncSession,
) -> None:
    first = await create_account(db_session, "first", system_admin=True)
    second = await create_account(db_session, "second", system_admin=True)
    await service.deactivate_account(db_session, first.id)

    with pytest.raises(service.LastSystemAdminError):
        await service.revoke_system_admin(db_session, second.id, revoked_by_account_id=second.id)


async def test_revocation_keeps_grant_history(
    db_client: AsyncClient, db_session: AsyncSession
) -> None:
    first = await create_account(db_session, "first", system_admin=True)
    second = await create_account(db_session, "second", system_admin=True)

    await service.revoke_system_admin(db_session, first.id, revoked_by_account_id=second.id)

    grants = (
        await db_session.scalars(
            select(SystemAdminGrant).where(SystemAdminGrant.account_id == first.id)
        )
    ).all()
    assert len(grants) == 1
    assert grants[0].revoked_at is not None
    assert grants[0].revoked_by_account_id == second.id
    assert not await service.is_system_admin(db_session, first.id)
    account = await db_session.get_one(UserAccount, first.id)
    assert account.status == AccountStatus.ACTIVE
    assert (await sign_in(db_client, "first")).status_code == 200
    assert (await db_client.get(ME)).json()["is_system_admin"] is False
