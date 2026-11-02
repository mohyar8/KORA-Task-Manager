"""Finished parts and review tasks.

An assignee can start work but never closes a task: they flag "I finished my part", which opens a
review task for the leaders (the creator and the Team Leader / Administration Manager over the
scope). Leaders close the task or send the work back.
"""

from collections.abc import Awaitable, Callable
from typing import Any

import pytest

from tests.tasks.conftest import TASKS, Api, Login, World

pytestmark = pytest.mark.anyio

NewTask = Callable[..., Awaitable[dict[str, Any]]]
NOTIFICATIONS = "/api/v1/notifications"


async def _two_assignee_task(new_task: NewTask, login: Login) -> tuple[Api, dict[str, Any]]:
    leader = await login("tl_a1")
    return leader, await new_task(leader, "team_a1", ["m_a1", "m_a1b"])


async def _reviews(api: Api) -> list[dict[str, Any]]:
    return [t for t in (await api.get(TASKS)).json() if t["kind"] == "review"]


async def test_an_assignee_can_start_work_but_not_close_the_task(
    world: World, login: Login, new_task: NewTask
) -> None:
    _, task = await _two_assignee_task(new_task, login)
    member = await login("m_a1b")
    assert (
        await member.post(f"{TASKS}/{task['id']}/status", {"status": "in_progress"})
    ).status_code == 200
    closed = await member.post(f"{TASKS}/{task['id']}/status", {"status": "completed"})
    assert closed.status_code == 403


async def test_finishing_a_part_opens_a_review_for_the_leaders_only(
    world: World, login: Login, new_task: NewTask
) -> None:
    leader, task = await _two_assignee_task(new_task, login)
    member = await login("m_a1b")
    flagged = await member.put(f"{TASKS}/{task['id']}/progress", {"finished": True})
    assert flagged.status_code == 200, flagged.text
    body = flagged.json()
    me = str(world.member_ids["m_a1b"])
    assert body["finished_member_ids"] == [me]
    assert body["status"] == "in_progress"  # work has started

    # The Team Leader (also the creator) and the Administration Manager each get the review.
    for user in ("tl_a1", "mgr_a"):
        reviews = await _reviews(await login(user))
        assert len(reviews) == 1, user
        assert reviews[0]["review_of_task_id"] == task["id"]
        assert reviews[0]["review_member_id"] == me
        assert reviews[0]["title"] == task["title"]
    # Not the assignees, nor other Members who merely see the team's tasks. The Event Leader may
    # oversee it but is not one of its assignees.
    assert await _reviews(member) == []
    assert await _reviews(await login("m_a2")) == []
    overseen = await _reviews(await login("leader"))
    assert all(str(world.member_ids["leader"]) not in r["assignee_member_ids"] for r in overseen)
    assert set((await _reviews(leader))[0]["assignee_member_ids"]) == {
        str(world.member_ids["tl_a1"]),
        str(world.member_ids["mgr_a"]),
    }

    # The leader sees every finished part; the other assignee sees only their own (none).
    assert (await leader.get(f"{TASKS}/{task['id']}")).json()["finished_member_ids"] == [me]
    other = await (await login("m_a1")).get(f"{TASKS}/{task['id']}")
    assert other.json()["finished_member_ids"] == []

    notes = (await leader.get(NOTIFICATIONS)).json()
    assert any(n["category"] == "task_review" and n["kind"] == "review_requested" for n in notes)


async def test_flagging_twice_keeps_one_review_and_taking_it_back_cancels_it(
    world: World, login: Login, new_task: NewTask
) -> None:
    leader, task = await _two_assignee_task(new_task, login)
    member = await login("m_a1b")
    url = f"{TASKS}/{task['id']}/progress"
    await member.put(url, {"finished": True})
    await member.put(url, {"finished": True})
    first = await _reviews(leader)
    assert len(first) == 1

    undone = await member.put(url, {"finished": False})
    assert undone.json()["finished_member_ids"] == []
    assert (await _reviews(leader))[0]["status"] == "cancelled"

    await member.put(url, {"finished": True})  # finishing again reopens the same review
    again = await _reviews(leader)
    assert [r["id"] for r in again] == [first[0]["id"]]
    assert again[0]["status"] == "new"


async def test_closing_the_task_closes_its_reviews_and_reopening_clears_flags(
    world: World, login: Login, new_task: NewTask
) -> None:
    leader, task = await _two_assignee_task(new_task, login)
    member = await login("m_a1b")
    await member.put(f"{TASKS}/{task['id']}/progress", {"finished": True})

    closed = await leader.post(f"{TASKS}/{task['id']}/status", {"status": "completed"})
    assert closed.status_code == 200
    assert (await _reviews(leader))[0]["status"] == "completed"
    assert (
        await member.put(f"{TASKS}/{task['id']}/progress", {"finished": False})
    ).status_code == 409

    reopened = await leader.post(f"{TASKS}/{task['id']}/status", {"status": "new"})
    assert reopened.json()["finished_member_ids"] == []


async def test_a_leader_can_send_work_back_with_a_comment(
    world: World, login: Login, new_task: NewTask
) -> None:
    leader, task = await _two_assignee_task(new_task, login)
    member = await login("m_a1b")
    await member.put(f"{TASKS}/{task['id']}/progress", {"finished": True})
    me = world.member_ids["m_a1b"]

    # Only the creator or a manager may send it back; the assignee cannot.
    assert (await member.post(f"{TASKS}/{task['id']}/progress/{me}/return", {})).status_code == 403
    back = await leader.post(
        f"{TASKS}/{task['id']}/progress/{me}/return", {"note": "Redo the logo"}
    )
    assert back.status_code == 200, back.text
    assert back.json()["finished_member_ids"] == []
    assert (await _reviews(leader))[0]["status"] == "completed"
    comments = (await leader.get(f"{TASKS}/{task['id']}/comments")).json()
    assert [c["body"] for c in comments] == ["Redo the logo"]
    notes = (await member.get(NOTIFICATIONS)).json()
    assert any(n["category"] == "task_review" and n["kind"] == "returned" for n in notes)
    # Nothing to send back any more.
    assert (await leader.post(f"{TASKS}/{task['id']}/progress/{me}/return", {})).status_code == 404


async def test_only_an_assignee_can_flag_a_part(
    world: World, login: Login, new_task: NewTask
) -> None:
    leader, task = await _two_assignee_task(new_task, login)
    url = f"{TASKS}/{task['id']}/progress"
    assert (await leader.put(url, {"finished": True})).status_code == 403  # creator, not assignee
    assert (await (await login("m_b1")).put(url, {"finished": True})).status_code == 403


async def test_review_tasks_are_managed_automatically(
    world: World, login: Login, new_task: NewTask
) -> None:
    leader, task = await _two_assignee_task(new_task, login)
    await (await login("m_a1b")).put(f"{TASKS}/{task['id']}/progress", {"finished": True})
    review = (await _reviews(leader))[0]
    url = f"{TASKS}/{review['id']}"
    assert (await leader.patch(url, {"title": "x"})).status_code == 409
    add = await leader.post(f"{url}/assignees", {"member_id": str(world.member_ids["m_a2"])})
    assert add.status_code == 409
    assert (await leader.put(f"{url}/progress", {"finished": True})).status_code == 409
    # A reviewer closes it like any task.
    assert (await leader.post(f"{url}/status", {"status": "completed"})).status_code == 200


async def test_removing_an_assignee_drops_their_flag_and_review(
    world: World, login: Login, new_task: NewTask
) -> None:
    leader, task = await _two_assignee_task(new_task, login)
    await (await login("m_a1b")).put(f"{TASKS}/{task['id']}/progress", {"finished": True})
    removed = await leader.post(
        f"{TASKS}/{task['id']}/assignees/{world.member_ids['m_a1b']}/remove"
    )
    assert removed.status_code == 200
    assert removed.json()["finished_member_ids"] == []
    assert (await _reviews(leader))[0]["status"] == "cancelled"


async def test_reviews_stay_out_of_the_follow_up_page(
    world: World, login: Login, new_task: NewTask
) -> None:
    _, task = await _two_assignee_task(new_task, login)
    await (await login("m_a1b")).put(f"{TASKS}/{task['id']}/progress", {"finished": True})
    followed = (await (await login("pmo_lead")).get(f"{TASKS}/follow")).json()
    assert [t["id"] for t in followed] == [task["id"]]
