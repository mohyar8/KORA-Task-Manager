"""Creator, manager and assignee actions; moves with scope history; automatic assignee cleanup."""

from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kora_api.access.permissions import Permission
from kora_api.tasks.models import Task, TaskAssignment, TaskScopeChange
from tests.organization.helpers import MEMBERS, UNITS, add_override
from tests.tasks.conftest import TASKS, Api, Login, World

pytestmark = pytest.mark.anyio

NewTask = Callable[..., Awaitable[dict[str, Any]]]


async def _status(api: Api, task: dict[str, Any], target: str) -> int:
    return (await api.post(f"{TASKS}/{task['id']}/status", {"status": target})).status_code


async def _kinds(api: Api, task: dict[str, Any]) -> list[str]:
    return [e["kind"] for e in (await api.get(f"{TASKS}/{task['id']}/history")).json()]


# --- Creation rules -------------------------------------------------------------------------------


async def test_create_with_all_fields_and_utc_due(world: World, login: Login) -> None:
    api = await login("m_a1")
    response = await api.post(
        TASKS,
        {
            "title": "  Book hall  ",
            "description": "Main hall",
            "priority": "urgent",
            "due_at": "2030-05-01T12:00:00+03:00",
            "scope_unit_id": str(world.structure.team_a1),
            "assignee_member_ids": [str(world.member_ids["m_a1"]), str(world.member_ids["m_a1b"])],
        },
    )

    assert response.status_code == 201
    task = response.json()
    assert task["title"] == "Book hall"
    assert task["status"] == "new"
    assert task["due_at"] == "2030-05-01T09:00:00Z"
    assert task["created_by_member_id"] == str(world.member_ids["m_a1"])
    assert len(task["assignee_member_ids"]) == 2


@pytest.mark.parametrize(
    "body",
    [
        {"assignee_member_ids": []},  # at least one assignee
        {"assignee_member_ids": ["m_b1"]},  # outside the scope
        {"assignee_member_ids": ["m_a1", "m_a1"]},  # duplicates
        {"due_at": "2030-05-01T12:00:00"},  # due time must carry an offset
        {"title": "   "},
        {"priority": "critical"},
    ],
)
async def test_invalid_creation_is_rejected(
    world: World, login: Login, body: dict[str, Any]
) -> None:
    payload: dict[str, Any] = {
        "title": "T",
        "scope_unit_id": str(world.structure.team_a1),
        "assignee_member_ids": [str(world.member_ids["m_a1"])],
    }
    payload |= body
    if body.get("assignee_member_ids"):
        payload["assignee_member_ids"] = [
            str(world.member_ids[m]) for m in body["assignee_member_ids"]
        ]

    assert (await (await login("m_a1")).post(TASKS, payload)).status_code == 422


async def test_pmo_task_may_be_assigned_to_pmo_members(
    world: World, login: Login, new_task: NewTask
) -> None:
    task = await new_task(await login("pmo_lead"), "pmo", ["pmo_m", "pmo_lead"])
    assert len(task["assignee_member_ids"]) == 2


# --- Assignee, creator and manager actions --------------------------------------------------------


async def test_assignees_progress_and_complete_but_cannot_cancel(
    world: World, login: Login, new_task: NewTask
) -> None:
    task = await new_task(await login("m_a1b"), "team_a1", ["m_a1"])
    assignee = await login("m_a1")
    team_leader = await login("tl_a1")  # neither creator nor assignee, but manages Team A1

    assert await _status(assignee, task, "cancelled") == 403
    assert await _status(assignee, task, "in_progress") == 200
    assert await _status(assignee, task, "in_progress") == 409
    assert await _status(assignee, task, "completed") == 200
    assert await _status(assignee, task, "new") == 403  # reopening is for creator/managers
    assert await _status(team_leader, task, "new") == 200
    response = await assignee.get(f"{TASKS}/{task['id']}")
    assert response.json()["status"] == "new"
    assert response.json()["started_at"] is not None


async def test_non_participant_viewer_cannot_change_status(
    world: World, login: Login, new_task: NewTask
) -> None:
    task = await new_task(await login("tl_a1"), "team_a1", ["m_a1"])
    viewer = await login("m_a1b")

    assert await _status(viewer, task, "in_progress") == 403
    assert (await viewer.patch(f"{TASKS}/{task['id']}", {"title": "x"})).status_code == 403


async def test_creator_edits_cancels_reopens_and_manages_assignees(
    world: World, login: Login, new_task: NewTask
) -> None:
    creator = await login("m_a1")
    task = await new_task(creator, "team_a1", ["m_a1b"])
    url = f"{TASKS}/{task['id']}"

    edited = await creator.patch(url, {"description": "Details", "due_at": None, "priority": "low"})
    assert edited.status_code == 200
    assert edited.json()["priority"] == "low"
    assert (await creator.patch(url, {"title": None})).status_code == 422

    added = await creator.post(f"{url}/assignees", {"member_id": str(world.member_ids["tl_a1"])})
    assert added.status_code == 200
    assert (
        await creator.post(f"{url}/assignees", {"member_id": str(world.member_ids["m_b1"])})
    ).status_code == 422
    removed = await creator.post(f"{url}/assignees/{world.member_ids['m_a1b']}/remove")
    assert removed.json()["assignee_member_ids"] == [str(world.member_ids["tl_a1"])]
    last = await creator.post(f"{url}/assignees/{world.member_ids['tl_a1']}/remove")
    assert last.status_code == 422  # a task keeps at least one assignee

    assert await _status(creator, task, "in_progress") == 403  # creator is not an assignee
    assert await _status(creator, task, "cancelled") == 200
    assert await _status(creator, task, "new") == 200
    assert await _kinds(creator, task) == [
        "created",
        "updated",
        "assignee_added",
        "assignee_removed",
        "status_changed",
        "status_changed",
    ]


async def test_tasks_are_never_deleted(world: World, login: Login, new_task: NewTask) -> None:
    api = await login("leader")
    task = await new_task(api, "team_a1", ["m_a1"])

    response = await api.client.delete(f"{TASKS}/{task['id']}", headers={"X-CSRF-Token": api.csrf})

    assert response.status_code == 405
    assert await _status(api, task, "cancelled") == 200
    assert (await api.get(f"{TASKS}/{task['id']}")).json()["status"] == "cancelled"


# --- Moves ----------------------------------------------------------------------------------------


async def test_creator_moves_with_task_create_at_destination(
    world: World, login: Login, new_task: NewTask, db_session: AsyncSession
) -> None:
    creator = await login("m_a1")
    task = await new_task(creator, "team_a1", ["m_a1", "m_a1b"])
    subtask = (
        await creator.post(
            f"{TASKS}/{task['id']}/subtasks",
            {"title": "Sub", "assignee_member_ids": [str(world.member_ids["m_a1b"])]},
        )
    ).json()
    move = {"scope_unit_id": str(world.structure.team_a2)}

    assert (await creator.post(f"{TASKS}/{task['id']}/move", move)).status_code == 403
    await add_override(
        db_session,
        world.account_ids["m_a1"],
        world.structure.team_a2,
        permission=Permission.TASK_CREATE,
    )
    moved = await creator.post(f"{TASKS}/{task['id']}/move", move)

    assert moved.status_code == 200
    assert moved.json()["scope_unit_id"] == str(world.structure.team_a2)
    # Assignees outside Team A2 were removed, the task stays open.
    assert moved.json()["assignee_member_ids"] == []
    assert moved.json()["status"] == "new"
    scopes = (
        await db_session.scalars(
            select(TaskScopeChange.unit_id)
            .where(TaskScopeChange.task_id == task["id"])
            .order_by(TaskScopeChange.valid_from)
        )
    ).all()
    assert scopes == [world.structure.team_a1, world.structure.team_a2]
    moved_sub = await db_session.get_one(Task, subtask["id"])
    await db_session.refresh(moved_sub)
    assert moved_sub.scope_unit_id == world.structure.team_a2
    reasons = (
        await db_session.scalars(
            select(TaskAssignment.end_reason).where(TaskAssignment.task_id == task["id"])
        )
    ).all()
    assert set(reasons) == {"out_of_scope"}
    assert "scope_changed" in await _kinds(creator, task)


async def test_manager_needs_manage_at_source_and_destination(
    world: World, login: Login, new_task: NewTask
) -> None:
    task = await new_task(await login("m_a1"), "team_a1", ["m_a1"])
    move = {"scope_unit_id": str(world.structure.team_a2)}

    team_leader = await login("tl_a1")  # manages Team A1 only
    assert (await team_leader.post(f"{TASKS}/{task['id']}/move", move)).status_code == 403
    manager = await login("mgr_a")  # manages Admin A, so both Teams
    moved = await manager.post(f"{TASKS}/{task['id']}/move", move)
    assert moved.status_code == 200
    back = await manager.post(
        f"{TASKS}/{task['id']}/move", {"scope_unit_id": str(world.structure.admin_a)}
    )
    assert back.status_code == 200
    out = await manager.post(
        f"{TASKS}/{task['id']}/move", {"scope_unit_id": str(world.structure.team_b1)}
    )
    assert out.status_code == 403


async def test_subtasks_cannot_be_moved_on_their_own(
    world: World, login: Login, new_task: NewTask
) -> None:
    api = await login("leader")
    task = await new_task(api, "team_a1", ["m_a1"])
    subtask = (
        await api.post(
            f"{TASKS}/{task['id']}/subtasks",
            {"title": "Sub", "assignee_member_ids": [str(world.member_ids["m_a1"])]},
        )
    ).json()

    response = await api.post(
        f"{TASKS}/{subtask['id']}/move", {"scope_unit_id": str(world.structure.team_a2)}
    )

    assert response.status_code == 422


# --- Automatic assignee cleanup -------------------------------------------------------------------


async def test_deactivated_member_is_removed_from_open_tasks_only(
    world: World, login: Login, new_task: NewTask
) -> None:
    leader = await login("leader")
    open_task = await new_task(leader, "team_a1", ["m_a1", "m_a1b"])
    done_task = await new_task(leader, "team_a1", ["m_a1"])
    assert await _status(await login("m_a1"), done_task, "completed") == 200
    admin = await login("sysadmin")

    assert (await admin.post(f"{MEMBERS}/{world.member_ids['m_a1']}/deactivate")).status_code == 200

    after = (await leader.get(f"{TASKS}/{open_task['id']}")).json()
    assert after["assignee_member_ids"] == [str(world.member_ids["m_a1b"])]
    assert after["status"] == "new"
    removal = [
        e
        for e in (await leader.get(f"{TASKS}/{open_task['id']}/history")).json()
        if e["kind"] == "assignee_removed"
    ]
    assert removal[0]["data"]["reason"] == "member_inactive"
    assert removal[0]["actor_account_id"] == str(world.account_ids["sysadmin"])
    completed = (await leader.get(f"{TASKS}/{done_task['id']}")).json()
    assert completed["assignee_member_ids"] == [str(world.member_ids["m_a1"])]


async def test_member_leaving_scope_is_removed_but_kept_where_still_in_scope(
    world: World, login: Login, new_task: NewTask
) -> None:
    leader = await login("leader")
    team_task = await new_task(leader, "team_a1", ["m_a1"])
    org_task = await new_task(leader, "kora", ["m_a1"])
    admin = await login("sysadmin")

    changed = await admin.post(
        f"{MEMBERS}/{world.member_ids['m_a1']}/team", {"team_id": str(world.structure.team_b1)}
    )
    assert changed.status_code == 200

    assert (await leader.get(f"{TASKS}/{team_task['id']}")).json()["assignee_member_ids"] == []
    assert (await leader.get(f"{TASKS}/{org_task['id']}")).json()["assignee_member_ids"] == [
        str(world.member_ids["m_a1"])
    ]


async def test_team_move_removes_assignees_from_tasks_of_the_old_administration(
    world: World, login: Login, new_task: NewTask, db_session: AsyncSession
) -> None:
    leader = await login("leader")
    admin_task = await new_task(leader, "admin_a", ["m_a1"])
    team_task = await new_task(leader, "team_a1", ["m_a1"])
    await add_override(db_session, world.account_ids["leader"], world.unit("kora"))  # org.manage

    moved = await leader.post(
        f"{UNITS}/{world.structure.team_a1}/move",
        {"administration_id": str(world.structure.admin_b)},
    )
    assert moved.status_code == 200

    admin_after = (await leader.get(f"{TASKS}/{admin_task['id']}")).json()
    # m_a1 is in Team A1 (now under Admin B); no longer within Admin A.
    assert admin_after["assignee_member_ids"] == []
    assert (await leader.get(f"{TASKS}/{team_task['id']}")).json()["assignee_member_ids"] == [
        str(world.member_ids["m_a1"])
    ]
