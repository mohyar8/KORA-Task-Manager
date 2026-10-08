"""Eligibility-based assignee cleanup, series moves, and series subtask-template edits."""

from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kora_api.tasks.models import TaskScopeChange
from tests.conftest import FrozenClock
from tests.organization.helpers import MEMBERS, UNITS, add_override
from tests.tasks.conftest import SERIES, TASKS, Api, Login, World

pytestmark = pytest.mark.anyio

NewTask = Callable[..., Awaitable[dict[str, Any]]]


async def _assignees(api: Api, task_id: str) -> list[str]:
    response = await api.get(f"{TASKS}/{task_id}")
    assignees: list[str] = response.json()["assignee_member_ids"]
    return assignees


async def _removals(api: Api, task_id: str) -> list[str]:
    history = (await api.get(f"{TASKS}/{task_id}/history")).json()
    return [e["data"]["reason"] for e in history if e["kind"] == "assignee_removed"]


# --- 1. Eligibility-based cleanup -----------------------------------------------------------------


async def test_team_leader_becoming_member_in_same_team_stays_assigned(
    world: World, login: Login, new_task: NewTask
) -> None:
    leader = await login("leader")
    task = await new_task(leader, "team_a1", ["tl_a1"])
    admin = await login("sysadmin")

    changed = await admin.post(
        f"{MEMBERS}/{world.member_ids['tl_a1']}/role", {"role_key": "member"}
    )

    assert changed.status_code == 200
    assert await _assignees(leader, task["id"]) == [str(world.member_ids["tl_a1"])]
    assert await _removals(leader, task["id"]) == []


async def test_role_change_removes_only_when_scope_is_lost(
    world: World, login: Login, new_task: NewTask
) -> None:
    leader = await login("leader")
    admin_task = await new_task(leader, "admin_a", ["mgr_a"])  # mgr_a's Team A1 is in Admin A
    pmo_task = await new_task(leader, "pmo", ["pmo_m"])  # pmo_m is in PMO only through the role
    admin = await login("sysadmin")

    for name in ("mgr_a", "pmo_m"):
        response = await admin.post(
            f"{MEMBERS}/{world.member_ids[name]}/role", {"role_key": "member"}
        )
        assert response.status_code == 200

    assert await _assignees(leader, admin_task["id"]) == [str(world.member_ids["mgr_a"])]
    assert await _assignees(leader, pmo_task["id"]) == []
    assert await _removals(leader, pmo_task["id"]) == ["out_of_scope"]


async def test_team_move_keeps_assignees_of_tasks_scoped_to_that_team(
    world: World, login: Login, new_task: NewTask, db_session: AsyncSession
) -> None:
    leader = await login("leader")
    team_task = await new_task(leader, "team_a1", ["m_a1", "tl_a1"])
    await add_override(db_session, world.account_ids["leader"], world.unit("kora"))

    moved = await leader.post(
        f"{UNITS}/{world.structure.team_a1}/move",
        {"administration_id": str(world.structure.admin_b)},
    )

    assert moved.status_code == 200
    assert sorted(await _assignees(leader, team_task["id"])) == sorted(
        [str(world.member_ids["m_a1"]), str(world.member_ids["tl_a1"])]
    )
    assert await _removals(leader, team_task["id"]) == []


# --- 2. Series moves ------------------------------------------------------------------------------


def _series_body(world: World, clock: FrozenClock, weeks: int) -> dict[str, Any]:
    first_due = clock.now + timedelta(days=1)
    return {
        "scope_unit_id": str(world.structure.team_a1),
        "title": "Weekly report",
        "first_due_at": first_due.isoformat(),
        "ends_at": (first_due + timedelta(weeks=weeks - 1, hours=1)).isoformat(),
        "assignee_member_ids": [str(world.member_ids["m_a1"])],
        "subtasks": [
            {"title": "Collect numbers", "assignee_member_ids": [str(world.member_ids["m_a1b"])]}
        ],
    }


async def _subtasks(api: Api, task_id: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = (await api.get(f"{TASKS}/{task_id}/subtasks")).json()
    return result


async def test_series_move_affects_only_future_unstarted_occurrences(
    world: World, login: Login, frozen_clock: FrozenClock, db_session: AsyncSession
) -> None:
    owner = await login("tl_a1")
    series = (await owner.post(SERIES, _series_body(world, frozen_clock, weeks=3))).json()
    started, future_1, future_2 = series["occurrence_ids"]
    await (await login("m_a1")).post(f"{TASKS}/{started}/status", {"status": "in_progress"})
    frozen_clock.advance(timedelta(minutes=1))
    url = f"{SERIES}/{series['id']}/move"

    # Creator without task.create at Team A2, Team Leader without manage there: refused.
    assert (
        await owner.post(url, {"scope_unit_id": str(world.structure.team_a2)})
    ).status_code == 403

    manager = await login("mgr_a")  # task.manage over Admin A: source and destination
    within = await manager.post(url, {"scope_unit_id": str(world.structure.admin_a)})
    assert within.status_code == 200
    assert within.json()["scope_unit_id"] == str(world.structure.admin_a)
    # Moving up to Admin A keeps everyone eligible (Team A1 lies in Admin A).
    assert await _assignees(manager, future_1) == [str(world.member_ids["m_a1"])]

    frozen_clock.advance(timedelta(minutes=1))
    away = await manager.post(url, {"scope_unit_id": str(world.structure.team_a2)})
    assert away.status_code == 200

    occurrences = {i: (await manager.get(f"{TASKS}/{i}")).json() for i in series["occurrence_ids"]}
    assert occurrences[started]["scope_unit_id"] == str(world.structure.team_a1)
    assert occurrences[started]["assignee_member_ids"] == [str(world.member_ids["m_a1"])]
    for future in (future_1, future_2):
        assert occurrences[future]["scope_unit_id"] == str(world.structure.team_a2)
        assert occurrences[future]["assignee_member_ids"] == []
        assert await _removals(manager, future) == ["out_of_scope"]
        [subtask] = await _subtasks(manager, future)
        assert subtask["scope_unit_id"] == str(world.structure.team_a2)
        assert subtask["assignee_member_ids"] == []
    [started_subtask] = await _subtasks(manager, started)
    assert started_subtask["scope_unit_id"] == str(world.structure.team_a1)
    scopes = (
        await db_session.scalars(
            select(TaskScopeChange.unit_id)
            .where(TaskScopeChange.task_id == future_1)
            .order_by(TaskScopeChange.valid_from)
        )
    ).all()
    assert scopes == [world.structure.team_a1, world.structure.admin_a, world.structure.team_a2]
    assert away.json()["assignee_member_ids"] == []  # template assignees kept eligible only


# --- 3. Series subtask-template edits -------------------------------------------------------------


async def test_series_edit_syncs_subtasks_of_future_unstarted_occurrences(
    world: World, login: Login, frozen_clock: FrozenClock
) -> None:
    owner = await login("tl_a1")
    series = (await owner.post(SERIES, _series_body(world, frozen_clock, weeks=3))).json()
    started, future_1, future_2 = series["occurrence_ids"]
    [template] = series["subtask_templates"]
    await (await login("m_a1")).post(f"{TASKS}/{started}/status", {"status": "in_progress"})
    # A started subtask inside a future occurrence is left alone too.
    [busy_subtask] = await _subtasks(owner, future_2)
    await (await login("m_a1b")).post(
        f"{TASKS}/{busy_subtask['id']}/status", {"status": "in_progress"}
    )
    frozen_clock.advance(timedelta(minutes=1))

    response = await owner.patch(
        f"{SERIES}/{series['id']}",
        {
            "subtasks": [
                {
                    "key": template["key"],
                    "title": "Collect figures",
                    "assignee_member_ids": [str(world.member_ids["m_a1"])],
                },
                {"title": "Check totals", "assignee_member_ids": [str(world.member_ids["m_a1b"])]},
            ]
        },
    )

    assert response.status_code == 200, response.text
    assert [t["title"] for t in response.json()["subtask_templates"]] == [
        "Collect figures",
        "Check totals",
    ]
    assert [s["title"] for s in await _subtasks(owner, started)] == ["Collect numbers"]
    first = {s["title"]: s for s in await _subtasks(owner, future_1)}
    assert set(first) == {"Collect figures", "Check totals"}
    assert first["Collect figures"]["assignee_member_ids"] == [str(world.member_ids["m_a1"])]
    assert first["Check totals"]["assignee_member_ids"] == [str(world.member_ids["m_a1b"])]
    second = {s["title"]: s for s in await _subtasks(owner, future_2)}
    assert set(second) == {"Collect numbers", "Check totals"}  # started subtask unchanged
    history = [e["kind"] for e in (await owner.get(f"{TASKS}/{future_1}/history")).json()]
    assert history.count("subtask_created") == 2

    frozen_clock.advance(timedelta(minutes=1))
    removed = await owner.patch(f"{SERIES}/{series['id']}", {"subtasks": []})
    assert removed.status_code == 200
    statuses = {s["title"]: s["status"] for s in await _subtasks(owner, future_1)}
    assert statuses == {"Collect figures": "cancelled", "Check totals": "cancelled"}
    assert {s["status"] for s in await _subtasks(owner, started)} == {"new"}
    cancelled = next(iter(await _subtasks(owner, future_1)))
    reasons = [
        e["data"].get("reason")
        for e in (await owner.get(f"{TASKS}/{cancelled['id']}/history")).json()
        if e["kind"] == "status_changed"
    ]
    assert reasons == ["series_template_removed"]


async def test_series_edit_rejects_unknown_template_keys(
    world: World, login: Login, frozen_clock: FrozenClock
) -> None:
    owner = await login("tl_a1")
    series = (await owner.post(SERIES, _series_body(world, frozen_clock, weeks=2))).json()

    response = await owner.patch(
        f"{SERIES}/{series['id']}",
        {
            "subtasks": [
                {
                    "key": "00000000-0000-4000-8000-000000000000",
                    "title": "X",
                    "assignee_member_ids": [str(world.member_ids["m_a1"])],
                }
            ]
        },
    )

    assert response.status_code == 422
