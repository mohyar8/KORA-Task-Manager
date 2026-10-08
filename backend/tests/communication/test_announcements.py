import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from kora_api.access.permissions import OverrideEffect, Permission
from tests.access.helpers import create_account, sign_in, signed_in
from tests.communication.conftest import ANNOUNCEMENTS, draft, publish
from tests.conftest import ClientFactory
from tests.organization.helpers import MEMBERS, add_override
from tests.tasks.conftest import Login, World

pytestmark = pytest.mark.anyio


# --- Permission defaults and overrides ------------------------------------------------------------


@pytest.mark.parametrize(
    ("user", "scope", "allowed"),
    [
        ("leader", "kora", True),
        ("mgr_a", "admin_a", True),
        ("mgr_a", "admin_b", False),
        ("pmo_lead", "pmo", True),
        ("tl_a1", "team_a1", True),
        ("tl_a1", "team_a2", False),
        ("pmo_m", "pmo", False),
        ("m_a1", "team_a1", False),
        ("sysadmin", "kora", False),
    ],
)
async def test_publish_defaults(
    world: World, login: Login, user: str, scope: str, allowed: bool
) -> None:
    response = await (await login(user)).post(
        ANNOUNCEMENTS, {"scope_unit_id": str(world.unit(scope)), "title": "T", "body": "B"}
    )
    assert response.status_code == (201 if allowed else 403)


async def test_overrides_grant_and_deny_announcement_permissions(
    world: World, login: Login, db_session: AsyncSession
) -> None:
    team = world.structure.team_a1
    await add_override(
        db_session, world.account_ids["m_a1"], team, permission=Permission.ANNOUNCEMENT_PUBLISH
    )
    await add_override(
        db_session,
        world.account_ids["tl_a1"],
        team,
        OverrideEffect.DENY,
        Permission.ANNOUNCEMENT_PUBLISH,
    )

    assert (await draft(await login("m_a1"), world))["state"] == "draft"
    denied = await (await login("tl_a1")).post(
        ANNOUNCEMENTS, {"scope_unit_id": str(team), "title": "T", "body": "B"}
    )
    assert denied.status_code == 403


# --- Drafts ---------------------------------------------------------------------------------------


async def test_draft_visible_to_creator_and_scoped_managers_only(
    world: World, login: Login
) -> None:
    item = await draft(await login("tl_a1"), world)
    url = f"{ANNOUNCEMENTS}/{item['id']}"

    for user in ("tl_a1", "mgr_a", "leader"):
        assert (await (await login(user)).get(url)).status_code == 200, user
    for user in ("m_a1", "pmo_lead", "sysadmin"):
        assert (await (await login(user)).get(url)).status_code == 403, user
    assert (await (await login("m_a1")).get(ANNOUNCEMENTS)).json() == []

    manager = await login("mgr_a")
    edited = await manager.patch(url, {"body": "Updated draft"})
    assert edited.json()["current_version"] == 2


# --- Publishing and recipients --------------------------------------------------------------------


async def test_recipients_must_be_active_members_in_scope_and_are_fixed(
    world: World, login: Login
) -> None:
    publisher = await login("tl_a1")
    item = await draft(publisher, world)

    assert (await publish(publisher, world, item["id"], ["m_b1"])).status_code == 422
    assert (
        await publisher.post(f"{ANNOUNCEMENTS}/{item['id']}/publish", {"recipient_member_ids": []})
    ).status_code == 422
    published = await publish(publisher, world, item["id"], ["m_a1", "tl_a1"])
    assert published.status_code == 200
    assert published.json()["state"] == "published"
    assert (await publish(publisher, world, item["id"], ["m_a1b"])).status_code == 409

    statuses = (await publisher.get(f"{ANNOUNCEMENTS}/{item['id']}/recipients")).json()
    assert {s["member_id"] for s in statuses} == {
        str(world.member_ids["m_a1"]),
        str(world.member_ids["tl_a1"]),
    }


async def test_deactivated_member_cannot_be_a_recipient(world: World, login: Login) -> None:
    admin = await login("sysadmin")
    await admin.post(f"{MEMBERS}/{world.member_ids['m_a1b']}/deactivate")
    publisher = await login("tl_a1")
    item = await draft(publisher, world)

    assert (await publish(publisher, world, item["id"], ["m_a1b"])).status_code == 422


async def test_published_visibility_and_recipient_keeps_access_after_moving(
    world: World, login: Login, client_factory: ClientFactory
) -> None:
    publisher = await login("tl_a1")
    item = await draft(publisher, world)
    await publish(publisher, world, item["id"], ["m_a1"])
    url = f"{ANNOUNCEMENTS}/{item['id']}"

    for user in ("m_a1", "tl_a1", "mgr_a", "leader"):
        response = await (await login(user)).get(url)
        assert response.status_code == 200, user
        assert response.json()["body"] == "The meeting is now at 5pm."
    for user in ("m_a1b", "m_a2", "sysadmin"):  # in scope but not recipients, or unrelated
        assert (await (await login(user)).get(url)).status_code == 403, user

    admin = await login("sysadmin")
    await admin.post(
        f"{MEMBERS}/{world.member_ids['m_a1']}/team", {"team_id": str(world.structure.team_b1)}
    )
    assert (await (await login("m_a1")).get(url)).status_code == 200  # still a direct recipient

    await admin.post(f"{MEMBERS}/{world.member_ids['m_a1']}/deactivate")
    assert (await sign_in(client_factory(), "m_a1")).status_code == 401


# --- Editing, versions and read state -------------------------------------------------------------


async def test_edit_creates_version_and_resets_read_state(world: World, login: Login) -> None:
    publisher = await login("tl_a1")
    item = await draft(publisher, world)
    await publish(publisher, world, item["id"], ["m_a1", "m_a1b"])
    url = f"{ANNOUNCEMENTS}/{item['id']}"
    reader = await login("m_a1")

    opened = (await reader.get(url)).json()
    assert (opened["my_read_version"], opened["my_read_current"]) == (1, True)

    edited = await publisher.patch(url, {"title": "Meeting moved again"})
    assert edited.json()["current_version"] == 2

    [listed] = (await reader.get(ANNOUNCEMENTS)).json()
    assert (listed["my_read_version"], listed["my_read_current"]) == (1, False)
    statuses = {
        s["member_id"]: (s["read_version"], s["read_current"])
        for s in (await publisher.get(f"{url}/recipients")).json()
    }
    assert statuses == {
        str(world.member_ids["m_a1"]): (1, False),
        str(world.member_ids["m_a1b"]): (None, False),
    }
    reopened = (await reader.get(url)).json()
    assert (reopened["title"], reopened["my_read_current"]) == ("Meeting moved again", True)

    versions = (await publisher.get(f"{url}/versions")).json()
    assert [(v["version"], v["title"]) for v in versions] == [
        (1, "Meeting moved"),
        (2, "Meeting moved again"),
    ]
    assert (await reader.get(f"{url}/versions")).status_code == 403
    assert (await reader.get(f"{url}/recipients")).status_code == 403


async def test_only_publisher_or_scoped_manager_edits_and_withdraws(
    world: World, login: Login
) -> None:
    publisher = await login("tl_a1")
    item = await draft(publisher, world)
    await publish(publisher, world, item["id"], ["m_a1"])
    url = f"{ANNOUNCEMENTS}/{item['id']}"

    recipient = await login("m_a1")
    assert (await recipient.patch(url, {"body": "x"})).status_code == 403
    assert (await recipient.post(f"{url}/withdraw")).status_code == 403
    assert (await (await login("pmo_lead")).post(f"{url}/withdraw")).status_code == 403
    assert (await (await login("mgr_a")).patch(url, {"body": "Manager fix"})).status_code == 200
    assert (await (await login("leader")).post(f"{url}/withdraw")).status_code == 200


async def test_withdrawal_hides_content_but_keeps_record_and_history(
    world: World, login: Login
) -> None:
    publisher = await login("tl_a1")
    item = await draft(publisher, world)
    await publish(publisher, world, item["id"], ["m_a1"])
    url = f"{ANNOUNCEMENTS}/{item['id']}"

    withdrawn = await publisher.post(f"{url}/withdraw")
    assert withdrawn.json()["state"] == "withdrawn"

    seen = (await (await login("m_a1")).get(url)).json()
    assert seen["state"] == "withdrawn"
    assert (seen["title"], seen["body"], seen["content_hidden"]) == (None, None, True)
    assert seen["withdrawn_at"] is not None
    assert (await publisher.get(url)).json()["body"] == "The meeting is now at 5pm."
    assert len((await publisher.get(f"{url}/versions")).json()) == 1
    assert (await publisher.patch(url, {"body": "x"})).status_code == 409
    assert (await publisher.post(f"{url}/withdraw")).status_code == 409
    no_delete = await publisher.client.delete(url, headers={"X-CSRF-Token": publisher.csrf})
    assert no_delete.status_code == 405


# --- Gates ----------------------------------------------------------------------------------------


async def test_announcement_routes_enforce_csrf_and_temporary_password_gate(
    world: World, client_factory: ClientFactory, db_session: AsyncSession
) -> None:
    client = client_factory()
    await signed_in(client, "tl_a1")
    no_csrf = await client.post(
        ANNOUNCEMENTS,
        json={"scope_unit_id": str(world.structure.team_a1), "title": "T", "body": "B"},
    )
    assert no_csrf.json() == {"detail": "CSRF token missing or invalid."}

    await create_account(db_session, "fresh", temporary=True)
    gated = client_factory()
    await signed_in(gated, "fresh")
    assert (await gated.get(ANNOUNCEMENTS)).json() == {"detail": "Password change required."}
