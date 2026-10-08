from collections.abc import Awaitable, Callable
from typing import Any

import pytest

from tests.tasks.conftest import TASKS, Api, Login, World

pytestmark = pytest.mark.anyio

NewTask = Callable[..., Awaitable[dict[str, Any]]]


async def _subtask(api: Api, world: World, parent_id: str, assignee: str) -> Any:
    return await api.post(
        f"{TASKS}/{parent_id}/subtasks",
        {"title": "Sub", "assignee_member_ids": [str(world.member_ids[assignee])]},
    )


# --- Subtasks -------------------------------------------------------------------------------------


async def test_one_subtask_level_with_inherited_scope_and_independent_status(
    world: World, login: Login, new_task: NewTask
) -> None:
    api = await login("tl_a1")
    parent = await new_task(api, "team_a1", ["m_a1"])

    created = await _subtask(api, world, parent["id"], "m_a1b")
    assert created.status_code == 201
    subtask = created.json()
    assert subtask["parent_id"] == parent["id"]
    assert subtask["scope_unit_id"] == parent["scope_unit_id"]
    assert (await _subtask(api, world, subtask["id"], "m_a1b")).status_code == 422  # one level
    assert (await _subtask(api, world, parent["id"], "m_b1")).status_code == 422  # out of scope

    sub_assignee = await login("m_a1b")
    done = await sub_assignee.post(f"{TASKS}/{subtask['id']}/status", {"status": "completed"})
    assert done.status_code == 200
    assert (await api.get(f"{TASKS}/{parent['id']}")).json()["status"] == "new"
    listed = (await api.get(f"{TASKS}/{parent['id']}/subtasks")).json()
    assert [t["id"] for t in listed] == [subtask["id"]]
    assert [t["id"] for t in (await api.get(TASKS)).json()] == [parent["id"]]  # top-level only
    history = (await api.get(f"{TASKS}/{parent['id']}/history")).json()
    assert history[-1]["kind"] == "subtask_created"


async def test_subtask_creation_needs_task_create_at_parent_scope(
    world: World, login: Login, new_task: NewTask
) -> None:
    parent = await new_task(await login("leader"), "admin_a", ["m_a1"])
    member = await login("m_a1")  # assignee (can view) but no task.create at Admin A

    assert (await _subtask(member, world, parent["id"], "m_a1")).status_code == 403


# --- Comments -------------------------------------------------------------------------------------


async def test_participants_and_managers_comment_others_cannot(
    world: World, login: Login, new_task: NewTask
) -> None:
    task = await new_task(await login("m_a1"), "team_a1", ["m_a1b"])
    url = f"{TASKS}/{task['id']}/comments"

    for user in ("m_a1", "m_a1b", "tl_a1", "leader"):  # creator, assignee, managers
        response = await (await login(user)).post(url, {"body": f"from {user}"})
        assert response.status_code == 201, user
    viewer_without_role = await login("pmo_m")  # cannot even see Team A1 tasks
    assert (await viewer_without_role.post(url, {"body": "hi"})).status_code == 403
    outsider_viewer = await login("m_a2")
    assert (await outsider_viewer.post(url, {"body": "hi"})).status_code == 403
    assert (await (await login("m_a1")).post(url, {"body": "   "})).status_code == 422


async def test_comment_viewer_who_is_not_participant_cannot_comment(
    world: World, login: Login, new_task: NewTask
) -> None:
    task = await new_task(await login("tl_a1"), "team_a1", ["m_a1"])
    viewer = await login("m_a1b")  # has task.view at Team A1

    assert (await viewer.get(f"{TASKS}/{task['id']}/comments")).status_code == 200
    assert (await viewer.post(f"{TASKS}/{task['id']}/comments", {"body": "x"})).status_code == 403


async def test_authors_edit_and_soft_delete_their_own_comments(
    world: World, login: Login, new_task: NewTask
) -> None:
    author = await login("m_a1")
    task = await new_task(author, "team_a1", ["m_a1b"])
    url = f"{TASKS}/{task['id']}/comments"
    comment = (await author.post(url, {"body": "First"})).json()
    other = await login("tl_a1")

    assert (await other.patch(f"{url}/{comment['id']}", {"body": "Hijack"})).status_code == 403
    assert (await other.post(f"{url}/{comment['id']}/delete")).status_code == 403
    edited = await author.patch(f"{url}/{comment['id']}", {"body": "Second"})
    assert edited.json()["body"] == "Second"
    assert edited.json()["edited_at"] is not None
    deleted = await author.post(f"{url}/{comment['id']}/delete")
    assert deleted.status_code == 200
    assert (await author.patch(f"{url}/{comment['id']}", {"body": "Again"})).status_code == 409

    [listed] = (await other.get(url)).json()
    assert listed["id"] == comment["id"]
    assert listed["body"] is None
    assert listed["deleted_at"] is not None
    events = [
        (e["kind"], e["data"].get("previous_body"))
        for e in (await other.get(f"{TASKS}/{task['id']}/history")).json()
        if e["kind"].startswith("comment")
    ]
    assert events == [
        ("comment_added", None),
        ("comment_edited", "First"),
        ("comment_deleted", None),
    ]
