from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from kora_api.access.permissions import OverrideEffect, Permission
from tests.access.helpers import create_account, sign_in, signed_in
from tests.calendar.conftest import EVENTS, START, NewEvent, event_body
from tests.conftest import ClientFactory
from tests.organization.helpers import MEMBERS, add_override
from tests.tasks.conftest import Login, World

pytestmark = pytest.mark.anyio


# --- Permission defaults and overrides ------------------------------------------------------------


@pytest.mark.parametrize(
    ("user", "scope", "invitee", "allowed"),
    [
        ("leader", "kora", "m_b1", True),
        ("mgr_a", "admin_a", "m_a2", True),
        ("pmo_lead", "pmo", "pmo_m", True),
        ("pmo_m", "pmo", "pmo_lead", True),
        ("tl_a1", "team_a1", "m_a1", True),
        ("m_a1", "team_a1", "m_a1b", True),
        ("m_a1", "admin_a", "m_a1b", False),
        ("pmo_m", "team_a2", "m_a2", False),
        ("sysadmin", "kora", "m_a1", False),
    ],
)
async def test_every_role_creates_at_its_assigned_scope(
    world: World, login: Login, user: str, scope: str, invitee: str, allowed: bool
) -> None:
    response = await (await login(user)).post(EVENTS, event_body(world, scope, [invitee]))
    assert response.status_code == (201 if allowed else 403)


@pytest.mark.parametrize(
    ("user", "can_manage"),
    [("tl_a1", True), ("mgr_a", True), ("leader", True), ("pmo_lead", False), ("m_a1b", False)],
)
async def test_calendar_manage_defaults(
    world: World, login: Login, new_event: NewEvent, user: str, can_manage: bool
) -> None:
    event = await new_event(await login("m_a1"), "team_a1", ["m_a1"])
    api = await login(user)

    assert (await api.get(f"{EVENTS}/{event['id']}")).status_code == (200 if can_manage else 403)
    edited = await api.patch(f"{EVENTS}/{event['id']}", {"title": "Renamed"})
    assert edited.status_code == (200 if can_manage else 403)


async def test_overrides_grant_and_deny_calendar_permissions(
    world: World, login: Login, new_event: NewEvent, db_session: AsyncSession
) -> None:
    event = await new_event(await login("m_a1"), "team_a1", ["m_a1b"])
    team = world.structure.team_a1
    await add_override(
        db_session, world.account_ids["m_a2"], team, permission=Permission.CALENDAR_MANAGE
    )
    await add_override(
        db_session,
        world.account_ids["m_a1b"],
        team,
        OverrideEffect.DENY,
        Permission.CALENDAR_CREATE,
    )
    for permission in (Permission.CALENDAR_CREATE, Permission.CALENDAR_MANAGE):
        await add_override(
            db_session, world.account_ids["outsider"], world.unit("kora"), permission=permission
        )

    granted = await login("m_a2")
    assert (
        await granted.patch(f"{EVENTS}/{event['id']}", {"title": "By override"})
    ).status_code == 200
    denied = await login("m_a1b")
    assert (await denied.post(EVENTS, event_body(world, "team_a1", ["m_a1"]))).status_code == 403
    outsider = await login("outsider")  # not a Member: may manage but never organize
    assert (await outsider.get(f"{EVENTS}/{event['id']}")).status_code == 200
    assert (await outsider.post(EVENTS, event_body(world, "kora", ["m_a1"]))).status_code == 403


# --- Validation -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "change",
    [
        {"starts_at": "2030-03-10T09:00:00"},  # naive
        {"ends_at": START.isoformat()},  # end == start
        {"ends_at": (START - timedelta(minutes=1)).isoformat()},
        {"location_text": "Room 2", "online_url": "https://meet.example.test/x"},
        {"online_url": "not a url"},
        {"type": "conference"},
        {"title": "  "},
        {"invitee_member_ids": []},
    ],
)
async def test_invalid_events_are_rejected(
    world: World, login: Login, change: dict[str, Any]
) -> None:
    body = event_body(world, "team_a1", ["m_a1"]) | change
    assert (await (await login("tl_a1")).post(EVENTS, body)).status_code == 422


async def test_invitees_must_be_active_members_within_scope(world: World, login: Login) -> None:
    api = await login("tl_a1")
    admin = await login("sysadmin")
    await admin.post(f"{MEMBERS}/{world.member_ids['m_a1b']}/deactivate")

    for invitees in (["m_b1"], ["m_a1b"], ["m_a1", "m_a1"]):
        response = await api.post(EVENTS, event_body(world, "team_a1", invitees))
        assert response.status_code == 422, invitees


@pytest.mark.parametrize(
    "location",
    [{"location_text": "Main hall"}, {"online_url": "https://meet.example.test/abc"}, {}],
)
async def test_one_optional_location_method(
    world: World, login: Login, new_event: NewEvent, location: dict[str, str]
) -> None:
    event = await new_event(await login("tl_a1"), "team_a1", ["m_a1"], **location)
    assert event["location_text"] == location.get("location_text")
    assert event["online_url"] == location.get("online_url")
    assert event["starts_at"] == "2030-03-10T09:00:00Z"


# --- Access ---------------------------------------------------------------------------------------


async def test_organizer_invitees_and_scoped_managers_see_events(
    world: World, login: Login, new_event: NewEvent
) -> None:
    event = await new_event(await login("m_a1"), "team_a1", ["m_a1b"], title="Retro")
    url = f"{EVENTS}/{event['id']}"

    for user in ("m_a1", "m_a1b", "tl_a1", "mgr_a", "leader"):
        api = await login(user)
        assert (await api.get(url)).status_code == 200, user
        assert [e["title"] for e in (await api.get(EVENTS)).json()] == ["Retro"], user
    for user in ("m_a2", "pmo_lead", "sysadmin"):
        api = await login(user)
        assert (await api.get(url)).json() == {"detail": "Not permitted."}, user
        assert (await api.get(EVENTS)).json() == [], user
    invitee = await login("m_a1b")
    assert (await invitee.patch(url, {"title": "x"})).status_code == 403  # invitees only view


# --- Invitations ----------------------------------------------------------------------------------


async def test_invitation_add_remove_and_history(
    world: World, login: Login, new_event: NewEvent
) -> None:
    organizer = await login("m_a1")
    event = await new_event(organizer, "team_a1", ["m_a1b"])
    url = f"{EVENTS}/{event['id']}"

    out_of_scope = await organizer.post(
        f"{url}/invitees", {"member_id": str(world.member_ids["m_b1"])}
    )
    assert out_of_scope.status_code == 422
    added = await organizer.post(f"{url}/invitees", {"member_id": str(world.member_ids["tl_a1"])})
    assert added.status_code == 200
    assert (
        await organizer.post(f"{url}/invitees", {"member_id": str(world.member_ids["tl_a1"])})
    ).status_code == 409

    removed = await organizer.post(f"{url}/invitees/{world.member_ids['m_a1b']}/remove")
    assert removed.json()["invitee_member_ids"] == [str(world.member_ids["tl_a1"])]
    assert (await (await login("m_a1b")).get(url)).status_code == 403
    last = await organizer.post(f"{url}/invitees/{world.member_ids['tl_a1']}/remove")
    assert last.status_code == 422

    history = (await organizer.get(f"{url}/invitations")).json()
    assert [(h["member_id"], h["valid_to"] is None) for h in history] == [
        (str(world.member_ids["m_a1b"]), False),
        (str(world.member_ids["tl_a1"]), True),
    ]
    kinds = [h["kind"] for h in (await organizer.get(f"{url}/history")).json()]
    assert kinds == ["created", "invitee_added", "invitee_added", "invitee_removed"]
    assert (await (await login("tl_a1")).get(f"{url}/invitations")).status_code == 200  # manager


async def test_moved_invitee_keeps_access_and_deactivated_cannot_sign_in(
    world: World, login: Login, new_event: NewEvent, client_factory: ClientFactory
) -> None:
    event = await new_event(await login("tl_a1"), "team_a1", ["m_a1"])
    url = f"{EVENTS}/{event['id']}"
    admin = await login("sysadmin")

    await admin.post(
        f"{MEMBERS}/{world.member_ids['m_a1']}/team", {"team_id": str(world.structure.team_b1)}
    )
    assert (await (await login("m_a1")).get(url)).status_code == 200  # directly invited

    await admin.post(f"{MEMBERS}/{world.member_ids['m_a1']}/deactivate")
    assert (await sign_in(client_factory(), "m_a1")).status_code == 401


# --- Edits and cancellation -----------------------------------------------------------------------


async def test_edits_validate_and_keep_scope_fixed(
    world: World, login: Login, new_event: NewEvent
) -> None:
    organizer = await login("tl_a1")
    event = await new_event(organizer, "team_a1", ["m_a1"], location_text="Room 1")
    url = f"{EVENTS}/{event['id']}"

    moved_later = (START + timedelta(days=1)).isoformat()
    assert (
        await organizer.patch(url, {"starts_at": moved_later})
    ).status_code == 422  # end <= start
    assert (
        await organizer.patch(url, {"online_url": "https://meet.example.test/y"})
    ).status_code == 422
    switched = await organizer.patch(
        url, {"online_url": "https://meet.example.test/y", "location_text": None}
    )
    assert (switched.json()["online_url"], switched.json()["location_text"]) == (
        "https://meet.example.test/y",
        None,
    )
    renamed = await organizer.patch(url, {"title": "New"})
    assert (renamed.json()["title"], renamed.json()["scope_unit_id"]) == (
        "New",
        str(world.structure.team_a1),
    )
    assert (await organizer.patch(url, {"title": None})).status_code == 422


async def test_cancellation_is_read_only_and_never_deletes(
    world: World, login: Login, new_event: NewEvent
) -> None:
    organizer = await login("tl_a1")
    event = await new_event(organizer, "team_a1", ["m_a1"])
    url = f"{EVENTS}/{event['id']}"

    cancelled = await organizer.post(f"{url}/cancel")
    assert cancelled.json()["state"] == "cancelled"
    assert cancelled.json()["cancelled_at"] is not None
    assert (await organizer.post(f"{url}/cancel")).status_code == 409
    assert (await organizer.patch(url, {"title": "x"})).status_code == 409
    assert (
        await organizer.post(f"{url}/invitees", {"member_id": str(world.member_ids["m_a1b"])})
    ).status_code == 409
    assert (
        await organizer.post(f"{url}/invitees/{world.member_ids['m_a1']}/remove")
    ).status_code == 409
    assert (await (await login("m_a1")).get(url)).json()["state"] == "cancelled"  # still readable
    assert [h["kind"] for h in (await organizer.get(f"{url}/history")).json()][-1] == "cancelled"
    assert len((await organizer.get(f"{url}/invitations")).json()) == 1
    deleted = await organizer.client.delete(url, headers={"X-CSRF-Token": organizer.csrf})
    assert deleted.status_code == 405


# --- Gates ----------------------------------------------------------------------------------------


async def test_calendar_routes_enforce_csrf_and_temporary_password_gate(
    world: World, client_factory: ClientFactory, db_session: AsyncSession
) -> None:
    client = client_factory()
    await signed_in(client, "tl_a1")
    no_csrf = await client.post(EVENTS, json=event_body(world, "team_a1", ["m_a1"]))
    assert no_csrf.json() == {"detail": "CSRF token missing or invalid."}

    await create_account(db_session, "fresh", temporary=True)
    gated = client_factory()
    await signed_in(gated, "fresh")
    assert (await gated.get(EVENTS)).json() == {"detail": "Password change required."}


# --- Corrections: immutable scope and invitation privacy ------------------------------------------


@pytest.mark.parametrize("scope", ["team_a2", "team_a1"])
async def test_edit_with_scope_unit_id_is_rejected(
    world: World, login: Login, new_event: NewEvent, scope: str
) -> None:
    organizer = await login("tl_a1")
    event = await new_event(organizer, "team_a1", ["m_a1"])
    url = f"{EVENTS}/{event['id']}"

    # Rejected even when it names the current scope, and nothing else is applied.
    response = await organizer.patch(url, {"title": "New", "scope_unit_id": str(world.unit(scope))})

    assert response.status_code == 422
    unchanged = (await organizer.get(url)).json()
    assert (unchanged["title"], unchanged["scope_unit_id"]) == (
        "Planning",
        str(world.structure.team_a1),
    )


async def test_invitees_see_only_their_own_invitation(
    world: World, login: Login, new_event: NewEvent
) -> None:
    event = await new_event(await login("m_a1"), "team_a1", ["m_a1b", "tl_a1"])
    url = f"{EVENTS}/{event['id']}"
    invitee = await login("m_a1b")

    seen = (await invitee.get(url)).json()
    assert seen["title"] == "Planning"  # details are visible
    assert seen["invitee_member_ids"] is None
    assert seen["my_invitation"]["member_id"] == str(world.member_ids["m_a1b"])
    assert seen["my_invitation"]["invited_at"] is not None
    [listed] = (await invitee.get(EVENTS)).json()
    assert (listed["invitee_member_ids"], listed["my_invitation"]["member_id"]) == (
        None,
        str(world.member_ids["m_a1b"]),
    )
    calendar = (
        await invitee.get(
            "/api/v1/calendar",
            **{"from": "2030-03-01T00:00:00Z", "to": "2030-03-31T00:00:00Z"},
        )
    ).json()
    [item] = calendar["events"]
    assert item["invitee_member_ids"] is None
    assert item["my_invitation"]["member_id"] == str(world.member_ids["m_a1b"])
    assert (await invitee.get(f"{url}/invitations")).status_code == 403


@pytest.mark.parametrize(("user", "invited"), [("m_a1", False), ("tl_a1", True), ("mgr_a", False)])
async def test_organizer_and_scoped_managers_see_full_invitations(
    world: World, login: Login, new_event: NewEvent, user: str, invited: bool
) -> None:
    event = await new_event(await login("m_a1"), "team_a1", ["m_a1b", "tl_a1"])
    url = f"{EVENTS}/{event['id']}"
    api = await login(user)  # organizer, a Team Leader who is also invited, an Admin Manager

    seen = (await api.get(url)).json()

    assert sorted(seen["invitee_member_ids"]) == sorted(
        [str(world.member_ids["m_a1b"]), str(world.member_ids["tl_a1"])]
    )
    assert (seen["my_invitation"] is not None) == invited
    assert len((await api.get(f"{url}/invitations")).json()) == 2
