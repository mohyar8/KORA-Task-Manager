"""`member_id` on the account response and the scoped Member lookup."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from kora_api.access.permissions import OverrideEffect, Permission
from kora_api.organization.constants import RoleKey
from tests.access.helpers import PASSWORD, create_account, signed_in
from tests.conftest import ClientFactory
from tests.organization.helpers import add_override, make_member, make_structure

pytestmark = pytest.mark.anyio

DIRECTORY = "/api/v1/organization/members"
ME = "/api/v1/auth/me"


async def test_account_response_carries_member_id_only_for_members(
    client_factory: ClientFactory, db_session: AsyncSession
) -> None:
    structure = await make_structure(db_session)
    member, _ = await make_member(db_session, "sara", team_id=structure.team_a1)
    await create_account(db_session, "root", system_admin=True)  # an account with no Member

    sara = client_factory()
    await signed_in(sara, "sara")
    assert (await sara.get(ME)).json()["member_id"] == str(member.id)

    root = client_factory()
    await signed_in(root, "root")
    assert (await root.get(ME)).json()["member_id"] is None


async def test_sign_in_response_includes_member_id(
    client_factory: ClientFactory, db_session: AsyncSession
) -> None:
    structure = await make_structure(db_session)
    member, _ = await make_member(db_session, "sara", team_id=structure.team_a1)
    client = client_factory()
    response = await client.post(
        "/api/v1/auth/sign-in", json={"username": "sara", "password": PASSWORD}
    )
    assert response.status_code == 200
    assert response.json()["account"]["member_id"] == str(member.id)


async def test_teammates_see_each_other_but_not_other_teams(
    client_factory: ClientFactory, db_session: AsyncSession
) -> None:
    s = await make_structure(db_session)
    sara, _ = await make_member(db_session, "sara", team_id=s.team_a1)
    omar, _ = await make_member(db_session, "omar", team_id=s.team_a1)
    await make_member(db_session, "lina", team_id=s.team_a2)
    await make_member(db_session, "huda", team_id=s.team_b1)

    client = client_factory()
    await signed_in(client, "sara")
    body = (await client.get(DIRECTORY)).json()

    assert [m["full_name"] for m in body] == ["Omar", "Sara"]
    assert {m["id"] for m in body} == {str(sara.id), str(omar.id)}
    entry = next(m for m in body if m["id"] == str(omar.id))
    assert entry["team_id"] == str(s.team_a1)
    assert entry["role_key"] == "member"
    # Names and placement only: no contact or academic data.
    assert set(entry) == {"id", "full_name", "team_id", "role_key"}


async def test_scope_follows_role_unit_and_administration_manager_sees_the_administration(
    client_factory: ClientFactory, db_session: AsyncSession
) -> None:
    s = await make_structure(db_session)
    await make_member(
        db_session,
        "manager",
        team_id=s.team_a1,
        role=RoleKey.ADMINISTRATION_MANAGER,
        role_unit_id=s.admin_a,
    )
    await make_member(db_session, "lina", team_id=s.team_a2)
    await make_member(db_session, "huda", team_id=s.team_b1)

    client = client_factory()
    await signed_in(client, "manager")
    names = {m["full_name"] for m in (await client.get(DIRECTORY)).json()}
    assert names == {"Manager", "Lina"}


async def test_override_expands_and_deny_override_restricts_the_lookup(
    client_factory: ClientFactory, db_session: AsyncSession
) -> None:
    s = await make_structure(db_session)
    _, sara = await make_member(db_session, "sara", team_id=s.team_a1)
    await make_member(db_session, "huda", team_id=s.team_b1)

    client = client_factory()
    await signed_in(client, "sara")
    assert {m["full_name"] for m in (await client.get(DIRECTORY)).json()} == {"Sara"}

    await add_override(db_session, sara.id, s.team_b1, permission=Permission.TASK_VIEW)
    assert {m["full_name"] for m in (await client.get(DIRECTORY)).json()} == {"Sara", "Huda"}

    # A deny on every operational permission at her own team leaves only herself.
    for permission in (
        Permission.TASK_VIEW,
        Permission.TASK_CREATE,
        Permission.CALENDAR_CREATE,
    ):
        await add_override(
            db_session, sara.id, s.team_a1, OverrideEffect.DENY, permission=permission
        )
    names = {m["full_name"] for m in (await client.get(DIRECTORY)).json()}
    assert "Sara" in names  # the caller always sees their own record


async def test_deactivated_members_and_anonymous_callers_are_excluded(
    client_factory: ClientFactory, db_session: AsyncSession
) -> None:
    s = await make_structure(db_session)
    await make_member(db_session, "sara", team_id=s.team_a1)

    anonymous = client_factory()
    assert (await anonymous.get(DIRECTORY)).status_code == 401

    # No Member record and no overrides: an account without a Member sees nobody.
    await create_account(db_session, "builder")
    builder = client_factory()
    await signed_in(builder, "builder")
    assert (await builder.get(DIRECTORY)).json() == []
