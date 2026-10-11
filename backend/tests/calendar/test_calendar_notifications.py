from typing import Any

import pytest

from tests.calendar.conftest import EVENTS, NewEvent
from tests.communication.conftest import NOTIFICATIONS, notifications_of
from tests.tasks.conftest import Login, World

pytestmark = pytest.mark.anyio


def _kinds(items: list[dict[str, Any]]) -> list[tuple[str, str]]:
    return sorted((n["category"], n["kind"]) for n in items)


async def test_creation_invites_everyone_but_the_organizer(
    world: World, login: Login, new_event: NewEvent
) -> None:
    organizer = await login("tl_a1")
    event = await new_event(organizer, "team_a1", ["tl_a1", "m_a1"], title="Sprint review")

    assert await notifications_of(organizer) == []
    [invited] = await notifications_of(await login("m_a1"))
    assert (invited["category"], invited["kind"], invited["source_type"]) == (
        "calendar_event",
        "invited",
        "calendar_event",
    )
    assert (invited["source_id"], invited["summary"]) == (event["id"], "Sprint review")


async def test_add_edit_cancel_notify_and_removal_is_silent(
    world: World, login: Login, new_event: NewEvent
) -> None:
    organizer = await login("tl_a1")
    event = await new_event(organizer, "team_a1", ["m_a1", "m_a1b"])
    url = f"{EVENTS}/{event['id']}"

    added = await organizer.post(f"{url}/invitees", {"member_id": str(world.member_ids["leader"])})
    assert added.status_code == 200
    await organizer.post(f"{url}/invitees/{world.member_ids['m_a1b']}/remove")
    await organizer.patch(url, {"title": "Planning (moved)"})
    manager = await login("mgr_a")  # a scoped manager cancels
    await manager.post(f"{url}/cancel")

    assert _kinds(await notifications_of(await login("m_a1"))) == [
        ("calendar_event", "cancelled"),
        ("calendar_event", "invited"),
        ("calendar_event", "updated"),
    ]
    assert _kinds(await notifications_of(await login("leader"))) == [
        ("calendar_event", "cancelled"),
        ("calendar_event", "invited"),
        ("calendar_event", "updated"),
    ]
    # Removed silently, and nothing about later changes.
    assert _kinds(await notifications_of(await login("m_a1b"))) == [("calendar_event", "invited")]
    assert await notifications_of(organizer) == []  # actor, and not an invitee
    assert await notifications_of(manager) == []  # actor


async def test_calendar_preference_is_respected(
    world: World, login: Login, new_event: NewEvent
) -> None:
    member = await login("m_a1")
    preferences = await member.client.put(
        f"{NOTIFICATIONS}/preferences",
        json={"calendar_event": False},
        headers={"X-CSRF-Token": member.csrf},
    )
    assert preferences.json()["calendar_event"] is False

    await new_event(await login("tl_a1"), "team_a1", ["m_a1", "m_a1b"])

    assert await notifications_of(member) == []
    assert len(await notifications_of(await login("m_a1b"))) == 1


async def test_notifications_redact_after_event_access_is_lost(
    world: World, login: Login, new_event: NewEvent
) -> None:
    organizer = await login("tl_a1")
    event = await new_event(organizer, "team_a1", ["m_a1", "m_a1b"], title="Confidential")
    member = await login("m_a1")
    [before] = await notifications_of(member)
    assert (before["summary"], before["redacted"]) == ("Confidential", False)

    await organizer.post(f"{EVENTS}/{event['id']}/invitees/{world.member_ids['m_a1']}/remove")

    [after] = await notifications_of(member)
    assert (after["summary"], after["redacted"]) == (None, True)
    opened = (await member.get(f"{NOTIFICATIONS}/{after['id']}")).json()
    assert opened["redacted"] is True
    assert (await member.get(f"{EVENTS}/{event['id']}")).status_code == 403
