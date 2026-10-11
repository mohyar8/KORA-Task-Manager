from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kora_api.access.permissions import OverrideEffect, Permission
from kora_api.calendar.models import CalendarEvent
from tests.calendar.conftest import CALENDAR, START, NewEvent
from tests.organization.helpers import add_override
from tests.tasks.conftest import TASKS, Api, Login, World

pytestmark = pytest.mark.anyio

RANGE = {
    "from": (START - timedelta(days=1)).isoformat(),
    "to": (START + timedelta(days=6)).isoformat(),
}


async def _task(api: Api, world: World, title: str, assignees: list[str], due: Any) -> str:
    body: dict[str, Any] = {
        "title": title,
        "scope_unit_id": str(world.structure.team_a1),
        "assignee_member_ids": [str(world.member_ids[a]) for a in assignees],
    }
    if due is not None:
        body["due_at"] = due.isoformat()
    response = await api.post(TASKS, body)
    assert response.status_code == 201, response.text
    task_id: str = response.json()["id"]
    return task_id


async def test_range_is_required_aware_and_bounded(world: World, login: Login) -> None:
    api = await login("m_a1")
    for params in (
        {},
        {"from": "2030-03-01T00:00:00", "to": "2030-03-02T00:00:00"},
        {"from": "2030-03-02T00:00:00Z", "to": "2030-03-01T00:00:00Z"},
        {"from": "2030-01-01T00:00:00Z", "to": "2031-02-01T00:00:00Z"},
    ):
        assert (await api.get(CALENDAR, **params)).status_code == 422, params


async def test_my_calendar_merges_events_and_derived_task_due_dates(
    world: World, login: Login, new_event: NewEvent, db_session: AsyncSession
) -> None:
    member = await login("m_a1")
    leader = await login("leader")
    in_range = await new_event(leader, "team_a1", ["m_a1"], title="In range")
    await new_event(
        leader,
        "team_a1",
        ["m_a1"],
        title="Next month",
        starts_at=(START + timedelta(days=30)).isoformat(),
        ends_at=(START + timedelta(days=30, hours=1)).isoformat(),
    )
    await new_event(leader, "team_a1", ["m_a1b"], title="Not invited")

    due = START + timedelta(days=2)
    created = await _task(member, world, "I created", ["m_a1b"], due)
    assigned = await _task(leader, world, "Assigned to me", ["m_a1"], due + timedelta(hours=1))
    await _task(leader, world, "Not mine", ["m_a1b"], due)  # visible, but not created/assigned
    await _task(leader, world, "No due date", ["m_a1"], None)
    await _task(leader, world, "Too late", ["m_a1"], START + timedelta(days=20))
    done = await _task(leader, world, "Completed", ["m_a1"], due)
    await member.post(f"{TASKS}/{done}/status", {"status": "completed"})
    cancelled = await _task(leader, world, "Cancelled", ["m_a1"], due)
    await leader.post(f"{TASKS}/{cancelled}/status", {"status": "cancelled"})
    started = await _task(leader, world, "Started", ["m_a1"], due)
    await member.post(f"{TASKS}/{started}/status", {"status": "in_progress"})

    response = await member.get(CALENDAR, **RANGE)

    assert response.status_code == 200
    body = response.json()
    assert [(e["item_type"], e["id"]) for e in body["events"]] == [("event", in_range["id"])]
    assert sorted((t["item_type"], t["title"], t["status"]) for t in body["task_due_dates"]) == [
        ("task_due", "Assigned to me", "new"),
        ("task_due", "I created", "new"),
        ("task_due", "Started", "in_progress"),
    ]
    assert {t["task_id"] for t in body["task_due_dates"]} == {created, assigned, started}
    # Derived only: nothing is copied into calendar tables.
    titles = set(await db_session.scalars(select(CalendarEvent.title)))
    assert titles == {"In range", "Next month", "Not invited"}


async def test_task_due_dates_recheck_task_access(
    world: World, login: Login, db_session: AsyncSession
) -> None:
    leader = await login("leader")
    due = START + timedelta(days=1)
    await _task(leader, world, "Hidden", ["m_a1"], due)
    await add_override(
        db_session,
        world.account_ids["m_a1"],
        world.structure.team_a1,
        OverrideEffect.DENY,
        Permission.TASK_VIEW,
    )

    body = (await (await login("m_a1")).get(CALENDAR, **RANGE)).json()

    assert body["task_due_dates"] == []
