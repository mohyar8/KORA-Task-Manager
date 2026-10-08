from datetime import timedelta
from typing import Any

import pytest

from kora_api.tasks.constants import MAX_SERIES_OCCURRENCES
from tests.conftest import FrozenClock
from tests.organization.helpers import MEMBERS
from tests.tasks.conftest import SERIES, TASKS, Api, Login, World

pytestmark = pytest.mark.anyio


def _series_body(world: World, clock: FrozenClock, weeks: int, **extra: Any) -> dict[str, Any]:
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
        **extra,
    }


async def _occurrences(api: Api, series: dict[str, Any]) -> list[dict[str, Any]]:
    return [(await api.get(f"{TASKS}/{task_id}")).json() for task_id in series["occurrence_ids"]]


async def test_weekly_series_generates_all_occurrences_with_subtasks(
    world: World, login: Login, frozen_clock: FrozenClock
) -> None:
    api = await login("tl_a1")

    response = await api.post(SERIES, _series_body(world, frozen_clock, weeks=4))

    assert response.status_code == 201, response.text
    series = response.json()
    occurrences = await _occurrences(api, series)
    assert len(occurrences) == 4
    dues = [o["due_at"] for o in occurrences]
    assert dues == sorted(dues)
    first_due = frozen_clock.now + timedelta(days=1)
    assert [o["due_at"] for o in occurrences] == [
        (first_due + timedelta(weeks=i)).isoformat().replace("+00:00", "Z") for i in range(4)
    ]
    for occurrence in occurrences:
        assert occurrence["series_id"] == series["id"]
        subtasks = (await api.get(f"{TASKS}/{occurrence['id']}/subtasks")).json()
        assert [s["title"] for s in subtasks] == ["Collect numbers"]


@pytest.mark.parametrize(
    "change",
    [
        {"ends_at": None},  # end timestamp required
        {"first_due_at": "2030-01-01T00:00:00"},  # offset required
        {"recurrence": "monthly"},  # weekly only: no other recurrence fields exist
    ],
)
async def test_series_requires_weekly_end(
    world: World, login: Login, frozen_clock: FrozenClock, change: dict[str, Any]
) -> None:
    body = _series_body(world, frozen_clock, weeks=2)
    for key, value in change.items():
        if value is None:
            body.pop(key)
        else:
            body[key] = value
    response = await (await login("tl_a1")).post(SERIES, body)
    assert response.status_code == (201 if "recurrence" in change else 422)


async def test_series_end_before_start_and_occurrence_cap(
    world: World, login: Login, frozen_clock: FrozenClock
) -> None:
    api = await login("tl_a1")
    body = _series_body(world, frozen_clock, weeks=1)
    body["ends_at"] = (frozen_clock.now - timedelta(days=1)).isoformat()
    assert (await api.post(SERIES, body)).status_code == 422
    too_long = _series_body(world, frozen_clock, weeks=MAX_SERIES_OCCURRENCES + 1)
    assert (await api.post(SERIES, too_long)).status_code == 422


async def test_series_edit_affects_only_future_unstarted_occurrences(
    world: World, login: Login, frozen_clock: FrozenClock
) -> None:
    owner = await login("tl_a1")
    series = (await owner.post(SERIES, _series_body(world, frozen_clock, weeks=5))).json()
    first, second, third, fourth, _ = series["occurrence_ids"]
    assignee = await login("m_a1")
    await assignee.post(f"{TASKS}/{first}/status", {"status": "completed"})
    await assignee.post(f"{TASKS}/{second}/status", {"status": "in_progress"})
    await owner.post(f"{TASKS}/{third}/status", {"status": "cancelled"})
    frozen_clock.advance(timedelta(minutes=5))

    response = await owner.patch(
        f"{SERIES}/{series['id']}",
        {"title": "Weekly report v2", "assignee_member_ids": [str(world.member_ids["m_a1b"])]},
    )

    assert response.status_code == 200
    occurrences = {o["id"]: o for o in await _occurrences(owner, series)}
    for unchanged in (first, second, third):
        assert occurrences[unchanged]["title"] == "Weekly report"
        assert occurrences[unchanged]["assignee_member_ids"] == [str(world.member_ids["m_a1"])]
    for future in (fourth, series["occurrence_ids"][4]):
        assert occurrences[future]["title"] == "Weekly report v2"
        assert occurrences[future]["assignee_member_ids"] == [str(world.member_ids["m_a1b"])]
    removed = [
        e
        for e in (await owner.get(f"{TASKS}/{fourth}/history")).json()
        if e["kind"] == "assignee_removed"
    ]
    assert removed[0]["data"]["reason"] == "series_update"


async def test_stopping_a_series_cancels_only_future_unstarted_occurrences(
    world: World, login: Login, frozen_clock: FrozenClock
) -> None:
    owner = await login("tl_a1")
    series = (await owner.post(SERIES, _series_body(world, frozen_clock, weeks=3))).json()
    first, second, third = series["occurrence_ids"]
    await (await login("m_a1")).post(f"{TASKS}/{first}/status", {"status": "in_progress"})
    frozen_clock.advance(timedelta(weeks=1, days=2))  # the second occurrence is now in the past
    owner = await login("tl_a1")  # the earlier session has idled out

    stopped = await owner.post(f"{SERIES}/{series['id']}/stop")

    assert stopped.status_code == 200
    assert stopped.json()["status"] == "stopped"
    occurrences = {o["id"]: o["status"] for o in await _occurrences(owner, series)}
    assert occurrences == {first: "in_progress", second: "new", third: "cancelled"}
    third_subtasks = (await owner.get(f"{TASKS}/{third}/subtasks")).json()
    assert [s["status"] for s in third_subtasks] == ["cancelled"]
    assert (await owner.post(f"{SERIES}/{series['id']}/stop")).status_code == 409
    assert (await owner.patch(f"{SERIES}/{series['id']}", {"title": "x"})).status_code == 409


async def test_series_administration_requires_creator_or_manager(
    world: World, login: Login, frozen_clock: FrozenClock
) -> None:
    series = (
        await (await login("m_a1")).post(SERIES, _series_body(world, frozen_clock, weeks=2))
    ).json()

    assert (
        await (await login("m_a1b")).patch(f"{SERIES}/{series['id']}", {"title": "x"})
    ).status_code == 403
    assert (
        await (await login("tl_a1")).patch(f"{SERIES}/{series['id']}", {"title": "y"})
    ).status_code == 200
    assert (await (await login("m_b1")).get(f"{SERIES}/{series['id']}")).status_code == 403


async def test_invalid_future_assignee_is_removed_with_reason(
    world: World, login: Login, frozen_clock: FrozenClock
) -> None:
    owner = await login("tl_a1")
    series = (await owner.post(SERIES, _series_body(world, frozen_clock, weeks=3))).json()
    first = series["occurrence_ids"][0]
    await (await login("m_a1")).post(f"{TASKS}/{first}/status", {"status": "completed"})
    frozen_clock.advance(timedelta(minutes=1))

    admin = await login("sysadmin")
    await admin.post(
        f"{MEMBERS}/{world.member_ids['m_a1']}/team", {"team_id": str(world.structure.team_b1)}
    )

    occurrences = await _occurrences(owner, series)
    assert occurrences[0]["assignee_member_ids"] == [str(world.member_ids["m_a1"])]  # completed
    for future in occurrences[1:]:
        assert future["assignee_member_ids"] == []
        reasons = [
            e["data"]["reason"]
            for e in (await owner.get(f"{TASKS}/{future['id']}/history")).json()
            if e["kind"] == "assignee_removed"
        ]
        assert reasons == ["out_of_scope"]
