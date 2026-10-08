"""Recurring series send one consolidated assignment notification per Member, not one per
occurrence; individual task assignments keep their normal notification."""

import uuid
from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from kora_api.notifications.models import Notification
from kora_api.tasks.constants import MAX_SERIES_OCCURRENCES
from kora_api.tasks.models import Task
from tests.communication.conftest import NOTIFICATIONS, notifications_of
from tests.conftest import FrozenClock
from tests.organization.helpers import MEMBERS
from tests.tasks.conftest import SERIES, TASKS, Login, World

pytestmark = pytest.mark.anyio


def _series_body(
    world: World, clock: FrozenClock, weeks: int, assignees: list[str], **extra: Any
) -> dict[str, Any]:
    first_due = clock.now + timedelta(days=1)
    return {
        "scope_unit_id": str(world.structure.team_a1),
        "title": "Weekly report",
        "first_due_at": first_due.isoformat(),
        "ends_at": (first_due + timedelta(weeks=weeks - 1, hours=1)).isoformat(),
        "assignee_member_ids": [str(world.member_ids[a]) for a in assignees],
        **extra,
    }


async def test_full_length_series_sends_one_notification_per_assignee(
    world: World, login: Login, frozen_clock: FrozenClock
) -> None:
    owner = await login("tl_a1")
    body = _series_body(
        world,
        frozen_clock,
        weeks=MAX_SERIES_OCCURRENCES,
        assignees=["m_a1", "tl_a1"],
        subtasks=[{"title": "Collect", "assignee_member_ids": [str(world.member_ids["m_a1b"])]}],
    )

    response = await owner.post(SERIES, body)

    assert response.status_code == 201
    series = response.json()
    assert len(series["occurrence_ids"]) == MAX_SERIES_OCCURRENCES
    ends = series["ends_at"][:10]
    for user in ("m_a1", "m_a1b"):  # occurrence assignee and subtask-template assignee
        [notification] = await notifications_of(await login(user))
        assert notification["category"] == "task_assignment"
        assert notification["kind"] == "series_assigned"
        assert (notification["source_type"], notification["source_id"]) == (
            "task_series",
            series["id"],
        )
        assert notification["summary"] == f"Weekly report (repeats weekly until {ends})"
        assert notification["redacted"] is False
    assert await notifications_of(owner) == []  # the actor is never notified

    # A manual assignment on one occurrence still produces that task's normal notification.
    occurrence = series["occurrence_ids"][4]
    added = await owner.post(
        f"{TASKS}/{occurrence}/assignees", {"member_id": str(world.member_ids["m_a1b"])}
    )
    assert added.status_code == 200
    received = await notifications_of(await login("m_a1b"))
    assert sorted((n["source_type"], n["kind"]) for n in received) == [
        ("task", "assigned"),
        ("task_series", "series_assigned"),
    ]
    individual = next(n for n in received if n["source_type"] == "task")
    assert individual["source_id"] == occurrence


async def test_individual_task_assignment_notification_is_unchanged(
    world: World, login: Login
) -> None:
    leader = await login("leader")
    created = await leader.post(
        TASKS,
        {
            "title": "One-off",
            "scope_unit_id": str(world.structure.team_a1),
            "assignee_member_ids": [str(world.member_ids["m_a1"])],
        },
    )

    [notification] = await notifications_of(await login("m_a1"))
    assert (notification["source_type"], notification["kind"]) == ("task", "assigned")
    assert notification["source_id"] == created.json()["id"]


async def test_series_edit_sends_at_most_one_notification_per_affected_member(
    world: World, login: Login, frozen_clock: FrozenClock
) -> None:
    owner = await login("tl_a1")
    series = (
        await owner.post(SERIES, _series_body(world, frozen_clock, weeks=10, assignees=["m_a1"]))
    ).json()
    for user in ("m_a1", "m_a1b"):
        await (await login(user)).post(f"{NOTIFICATIONS}/delete-all")
    frozen_clock.advance(timedelta(minutes=1))

    response = await owner.patch(
        f"{SERIES}/{series['id']}",
        {"assignee_member_ids": [str(world.member_ids["m_a1b"])], "title": "Weekly report v2"},
    )

    assert response.status_code == 200
    [removed] = await notifications_of(await login("m_a1"))  # removed: no update notification
    assert (removed["kind"], removed["source_type"]) == ("series_unassigned", "task_series")
    added_and_updated = await notifications_of(await login("m_a1b"))
    assert sorted(n["kind"] for n in added_and_updated) == ["series_assigned", "series_updated"]
    [added] = [n for n in added_and_updated if n["kind"] == "series_assigned"]
    assert added["kind"] == "series_assigned"
    assert added["summary"].startswith("Weekly report v2 (repeats weekly until ")


async def test_membership_change_removes_from_series_with_one_notification(
    world: World, login: Login, frozen_clock: FrozenClock
) -> None:
    owner = await login("tl_a1")
    await owner.post(SERIES, _series_body(world, frozen_clock, weeks=10, assignees=["m_a1"]))
    frozen_clock.advance(timedelta(minutes=1))
    admin = await login("sysadmin")

    await admin.post(
        f"{MEMBERS}/{world.member_ids['m_a1']}/team", {"team_id": str(world.structure.team_b1)}
    )

    received = await notifications_of(await login("m_a1"))
    assert sorted(n["kind"] for n in received) == ["series_assigned", "series_unassigned"]
    # m_a1 can no longer see the series (other scope, no assignments), so both are redacted.
    assert all(n["redacted"] for n in received)


async def test_series_notification_respects_preferences(
    world: World, login: Login, frozen_clock: FrozenClock
) -> None:
    member = await login("m_a1")
    await member.client.put(
        f"{NOTIFICATIONS}/preferences",
        json={"task_assignment": False},
        headers={"X-CSRF-Token": member.csrf},
    )

    await (await login("tl_a1")).post(
        SERIES, _series_body(world, frozen_clock, weeks=5, assignees=["m_a1"])
    )

    assert await notifications_of(member) == []


# --- Every series operation is consolidated -------------------------------------------------------


async def _clear(login: Login, *users: str) -> None:
    for user in users:
        await (await login(user)).post(f"{NOTIFICATIONS}/delete-all")


def _shape(received: list[dict[str, Any]]) -> list[tuple[str, str, str]]:
    return sorted((n["category"], n["kind"], n["source_type"]) for n in received)


async def _per_occurrence_rows(db_session: AsyncSession, series_id: str) -> int:
    """Notifications (including deleted ones) pointing at any task of the series."""
    task_ids = select(Task.id).where(Task.series_id == uuid.UUID(series_id))
    count = await db_session.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.source_type == "task", Notification.source_id.in_(task_ids))
    )
    return count or 0


async def test_editing_a_full_series_sends_one_notification_per_recipient_and_category(
    world: World, login: Login, frozen_clock: FrozenClock, db_session: AsyncSession
) -> None:
    creator = await login("m_a1")
    body = _series_body(
        world,
        frozen_clock,
        weeks=MAX_SERIES_OCCURRENCES,
        assignees=["m_a1b", "tl_a1"],
        subtasks=[{"title": "Collect", "assignee_member_ids": [str(world.member_ids["m_a1b"])]}],
    )
    series = (await creator.post(SERIES, body)).json()
    users = ("m_a1", "m_a1b", "tl_a1", "leader", "mgr_a")
    await _clear(login, *users)
    frozen_clock.advance(timedelta(minutes=1))

    # One operation changes content and assignees (tl_a1 out, leader in); mgr_a is the actor.
    manager = await login("mgr_a")
    response = await manager.patch(
        f"{SERIES}/{series['id']}",
        {
            "title": "Weekly report v2",
            "priority": "high",
            "assignee_member_ids": [
                str(world.member_ids["m_a1b"]),
                str(world.member_ids["leader"]),
            ],
        },
    )
    assert response.status_code == 200

    shapes = {user: _shape(await notifications_of(await login(user))) for user in users}
    update = ("task_update", "series_updated", "task_series")
    assert shapes == {
        "m_a1": [update],  # creator
        "m_a1b": [update],  # kept assignee
        "leader": [("task_assignment", "series_assigned", "task_series"), update],
        "tl_a1": [("task_assignment", "series_unassigned", "task_series")],  # removed only
        "mgr_a": [],  # actor
    }
    [creator_update] = await notifications_of(await login("m_a1"))
    assert creator_update["source_id"] == series["id"]
    assert creator_update["summary"].startswith("Weekly report v2 (repeats weekly until ")
    assert await _per_occurrence_rows(db_session, series["id"]) == 0


async def test_template_edit_move_and_stop_are_each_one_update_per_recipient(
    world: World, login: Login, frozen_clock: FrozenClock, db_session: AsyncSession
) -> None:
    creator = await login("m_a1")
    body = _series_body(
        world,
        frozen_clock,
        weeks=MAX_SERIES_OCCURRENCES,
        assignees=["m_a1b"],
        subtasks=[{"title": "Collect", "assignee_member_ids": [str(world.member_ids["m_a1b"])]}],
    )
    series = (await creator.post(SERIES, body)).json()
    [template] = series["subtask_templates"]
    url = f"{SERIES}/{series['id']}"
    update = ("task_update", "series_updated", "task_series")

    for operation in ("templates", "move", "stop"):
        await _clear(login, "m_a1", "m_a1b")
        frozen_clock.advance(timedelta(minutes=1))
        manager = await login("mgr_a")
        if operation == "templates":
            response = await manager.patch(
                url,
                {
                    "subtasks": [
                        {
                            "key": template["key"],
                            "title": "Collect figures",
                            "assignee_member_ids": [str(world.member_ids["m_a1b"])],
                        }
                    ]
                },
            )
        elif operation == "move":  # Team A1 to Admin A keeps everyone eligible
            response = await manager.post(
                f"{url}/move", {"scope_unit_id": str(world.structure.admin_a)}
            )
        else:
            response = await manager.post(f"{url}/stop")
        assert response.status_code == 200, (operation, response.text)
        for user in ("m_a1", "m_a1b"):
            received = _shape(await notifications_of(await login(user)))
            assert received == [update], (operation, user)
    assert await _per_occurrence_rows(db_session, series["id"]) == 0


async def test_consolidated_updates_respect_preferences_and_exclude_the_actor(
    world: World, login: Login, frozen_clock: FrozenClock, db_session: AsyncSession
) -> None:
    creator = await login("tl_a1")
    series = (
        await creator.post(
            SERIES,
            _series_body(
                world, frozen_clock, weeks=MAX_SERIES_OCCURRENCES, assignees=["m_a1", "m_a1b"]
            ),
        )
    ).json()
    member = await login("m_a1")
    await member.client.put(
        f"{NOTIFICATIONS}/preferences",
        json={"task_update": False},
        headers={"X-CSRF-Token": member.csrf},
    )
    await _clear(login, "m_a1", "m_a1b", "tl_a1")
    frozen_clock.advance(timedelta(minutes=1))

    # The creator edits their own series: they are the actor and get nothing.
    creator = await login("tl_a1")
    response = await creator.patch(f"{SERIES}/{series['id']}", {"description": "New details"})

    assert response.status_code == 200
    assert await notifications_of(await login("tl_a1")) == []
    assert await notifications_of(await login("m_a1")) == []  # task_update turned off
    [received] = await notifications_of(await login("m_a1b"))
    assert (received["category"], received["kind"]) == ("task_update", "series_updated")
    assert await _per_occurrence_rows(db_session, series["id"]) == 0


async def test_individual_occurrence_actions_still_notify_per_task(
    world: World, login: Login, frozen_clock: FrozenClock
) -> None:
    creator = await login("tl_a1")
    series = (
        await creator.post(SERIES, _series_body(world, frozen_clock, weeks=3, assignees=["m_a1"]))
    ).json()
    await _clear(login, "m_a1")
    occurrence = series["occurrence_ids"][1]

    await creator.patch(f"{TASKS}/{occurrence}", {"title": "Just this week"})

    [received] = await notifications_of(await login("m_a1"))
    assert (received["source_type"], received["source_id"], received["kind"]) == (
        "task",
        occurrence,
        "updated",
    )
