from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.access.helpers import create_account, signed_in
from tests.communication.conftest import (
    ANNOUNCEMENTS,
    NOTIFICATIONS,
    draft,
    notifications_of,
    publish,
)
from tests.conftest import ClientFactory
from tests.organization.helpers import MEMBERS
from tests.tasks.conftest import TASKS, Login, World

pytestmark = pytest.mark.anyio

NewTask = Callable[..., Awaitable[dict[str, Any]]]


def _kinds(items: list[dict[str, Any]]) -> list[tuple[str, str]]:
    return sorted((n["category"], n["kind"]) for n in items)


# --- Task notifications ---------------------------------------------------------------------------


async def test_assignment_notifies_assignees_but_never_the_actor(
    world: World, login: Login, new_task: NewTask
) -> None:
    creator = await login("m_a1")
    task = await new_task(creator, "team_a1", ["m_a1", "m_a1b"], title="Book hall")

    assert await notifications_of(creator) == []  # self-assigned by the actor
    [received] = await notifications_of(await login("m_a1b"))
    assert (received["category"], received["kind"]) == ("task_assignment", "assigned")
    assert (received["source_type"], received["source_id"]) == ("task", task["id"])
    assert (received["summary"], received["redacted"]) == ("Book hall", False)
    assert received["actor_account_id"] == str(world.account_ids["m_a1"])
    assert received["read_at"] is None


async def test_changes_comments_and_removals_notify_the_right_people(
    world: World, login: Login, new_task: NewTask
) -> None:
    creator = await login("m_a1")
    task = await new_task(creator, "team_a1", ["m_a1b", "tl_a1"])
    url = f"{TASKS}/{task['id']}"
    team_leader = await login("tl_a1")
    assignee = await login("m_a1b")

    await team_leader.patch(url, {"priority": "high"})  # update by a manager-assignee
    await assignee.post(f"{url}/status", {"status": "in_progress"})
    await assignee.post(f"{url}/comments", {"body": "On it"})
    await creator.post(f"{url}/assignees/{world.member_ids['tl_a1']}/remove")

    assert _kinds(await notifications_of(creator)) == [
        ("task_comment", "commented"),
        ("task_update", "status_changed"),
        ("task_update", "updated"),
    ]
    assert _kinds(await notifications_of(assignee)) == [
        ("task_assignment", "assigned"),
        ("task_update", "updated"),
    ]
    assert _kinds(await notifications_of(team_leader)) == [
        ("task_assignment", "assigned"),
        ("task_assignment", "unassigned"),
        ("task_comment", "commented"),
        ("task_update", "status_changed"),
    ]


async def test_preferences_default_enabled_and_are_respected(
    world: World, login: Login, new_task: NewTask
) -> None:
    member = await login("m_a1")
    preferences = (await member.get(f"{NOTIFICATIONS}/preferences")).json()
    assert preferences == dict.fromkeys(
        [
            "task_assignment",
            "task_update",
            "task_comment",
            "announcement_new",
            "announcement_change",
        ],
        True,
    )
    updated = await member.client.put(
        f"{NOTIFICATIONS}/preferences",
        json={"task_update": False},
        headers={"X-CSRF-Token": member.csrf},
    )
    assert updated.json()["task_update"] is False

    leader = await login("leader")
    task = await new_task(leader, "team_a1", ["m_a1"])
    await leader.patch(f"{TASKS}/{task['id']}", {"title": "Renamed"})

    assert _kinds(await notifications_of(member)) == [("task_assignment", "assigned")]


# --- Announcement notifications -------------------------------------------------------------------


async def test_announcement_publish_edit_withdraw_notify_direct_recipients(
    world: World, login: Login
) -> None:
    publisher = await login("tl_a1")
    item = await draft(publisher, world, title="Venue change")
    await publish(publisher, world, item["id"], ["m_a1", "tl_a1"])
    url = f"{ANNOUNCEMENTS}/{item['id']}"
    await publisher.patch(url, {"body": "New body"})
    recipient = await login("m_a1")
    published_and_edited = await notifications_of(recipient)
    assert _kinds(published_and_edited) == [
        ("announcement_change", "edited"),
        ("announcement_new", "published"),
    ]
    assert {n["summary"] for n in published_and_edited} == {"Venue change"}

    await publisher.post(f"{url}/withdraw")

    assert await notifications_of(publisher) == []  # publisher is a recipient but the actor
    assert await notifications_of(await login("m_a1b")) == []  # in scope, not a recipient
    after = await notifications_of(recipient)
    assert len(after) == 3
    # Content is no longer visible to recipients, so every notification is now redacted.
    assert all(n["redacted"] and n["summary"] is None for n in after)
    assert ("announcement_change", "withdrawn") in _kinds(after)


# --- Reader actions -------------------------------------------------------------------------------


async def test_read_and_delete_affect_only_the_readers_own_records(
    world: World, login: Login, new_task: NewTask
) -> None:
    leader = await login("leader")
    first = await new_task(leader, "team_a1", ["m_a1", "m_a1b"])
    await new_task(leader, "team_a1", ["m_a1"])
    member = await login("m_a1")
    other = await login("m_a1b")
    mine = await notifications_of(member)
    [theirs] = await notifications_of(other)
    assert len(mine) == 2

    read = await member.post(f"{NOTIFICATIONS}/{mine[0]['id']}/read")
    assert read.json()["read_at"] is not None
    assert len((await member.get(NOTIFICATIONS, unread_only="true")).json()) == 1
    assert (await member.post(f"{NOTIFICATIONS}/read-all")).status_code == 204
    assert (await member.get(NOTIFICATIONS, unread_only="true")).json() == []

    # Another user's notification is invisible to me.
    assert (await member.get(f"{NOTIFICATIONS}/{theirs['id']}")).status_code == 404
    assert (await member.post(f"{NOTIFICATIONS}/{theirs['id']}/delete")).status_code == 404

    assert (await member.post(f"{NOTIFICATIONS}/{mine[0]['id']}/delete")).status_code == 204
    assert len(await notifications_of(member)) == 1
    assert (await member.post(f"{NOTIFICATIONS}/delete-all")).status_code == 204
    assert await notifications_of(member) == []

    # The source and other users' records are untouched.
    assert (await member.get(f"{TASKS}/{first['id']}")).status_code == 200
    assert [n["id"] for n in await notifications_of(other)] == [theirs["id"]]
    assert (await other.get(f"{NOTIFICATIONS}/{theirs['id']}")).json()["read_at"] is None


async def test_notifications_are_redacted_after_source_access_is_lost(
    world: World, login: Login, new_task: NewTask
) -> None:
    leader = await login("leader")
    task = await new_task(leader, "team_a1", ["m_a1"], title="Secret plan")
    member = await login("m_a1")
    [before] = await notifications_of(member)
    assert before["summary"] == "Secret plan"

    admin = await login("sysadmin")
    await admin.post(
        f"{MEMBERS}/{world.member_ids['m_a1']}/team", {"team_id": str(world.structure.team_b1)}
    )

    after = await notifications_of(member)
    assert len(after) == 2  # assigned, then unassigned (left the task's scope)
    assert all(n["redacted"] and n["summary"] is None for n in after)
    opened = (await member.get(f"{NOTIFICATIONS}/{before['id']}")).json()
    assert (opened["redacted"], opened["summary"]) == (True, None)
    assert (await member.get(f"{TASKS}/{task['id']}")).status_code == 403


# --- Gates ----------------------------------------------------------------------------------------


async def test_notification_routes_enforce_csrf_and_temporary_password_gate(
    world: World, client_factory: ClientFactory, db_session: AsyncSession
) -> None:
    client = client_factory()
    await signed_in(client, "m_a1")
    assert (await client.post(f"{NOTIFICATIONS}/read-all")).json() == {
        "detail": "CSRF token missing or invalid."
    }

    await create_account(db_session, "fresh", temporary=True)
    gated = client_factory()
    await signed_in(gated, "fresh")
    assert (await gated.get(NOTIFICATIONS)).json() == {"detail": "Password change required."}
