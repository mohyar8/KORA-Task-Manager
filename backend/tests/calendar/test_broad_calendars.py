"""The Administration and all-Administrations task calendars: defaults and System Admin grants."""

from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from kora_api.access.permissions import OverrideEffect, Permission
from tests.calendar.conftest import CALENDAR, START
from tests.organization.helpers import add_override
from tests.tasks.conftest import TASKS, Api, Login, World

pytestmark = pytest.mark.anyio

RANGE = {
    "from": (START - timedelta(days=1)).isoformat(),
    "to": (START + timedelta(days=6)).isoformat(),
}


async def _task(api: Api, world: World, scope: str, title: str, assignee: str) -> None:
    response = await api.post(
        TASKS,
        {
            "title": title,
            "scope_unit_id": str(world.unit(scope)),
            "assignee_member_ids": [str(world.member_ids[assignee])],
            "due_at": (START + timedelta(days=1)).isoformat(),
        },
    )
    assert response.status_code == 201, response.text


async def _titles(api: Api, path: str) -> list[str]:
    response = await api.get(f"{CALENDAR}/{path}", **RANGE)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return sorted(t["title"] for t in body["tasks"])


async def _seed(world: World, login: Login) -> None:
    leader = await login("leader")
    await _task(leader, world, "team_a1", "A1 task", "m_a1")
    await _task(leader, world, "team_a2", "A2 task", "m_a2")
    await _task(leader, world, "team_b1", "B1 task", "m_b1")


async def test_team_leader_sees_the_whole_administration_not_others(
    world: World, login: Login
) -> None:
    await _seed(world, login)
    team_leader = await login("tl_a1")
    assert await _titles(team_leader, "administration") == ["A1 task", "A2 task"]
    assert (await team_leader.get(f"{CALENDAR}/all", **RANGE)).status_code == 403


async def test_administration_manager_and_leadership_defaults(world: World, login: Login) -> None:
    await _seed(world, login)
    assert await _titles(await login("mgr_a"), "administration") == ["A1 task", "A2 task"]
    for user in ("leader", "pmo_lead", "pmo_m"):
        assert await _titles(await login(user), "all") == ["A1 task", "A2 task", "B1 task"]


async def test_plain_member_has_neither_view_until_granted(
    world: World, login: Login, db_session: AsyncSession
) -> None:
    await _seed(world, login)
    member = await login("m_a2")
    assert (await member.get(f"{CALENDAR}/administration", **RANGE)).status_code == 403
    assert (await member.get(f"{CALENDAR}/all", **RANGE)).status_code == 403

    await add_override(
        db_session,
        world.account_ids["m_a2"],
        world.structure.team_a2,
        OverrideEffect.GRANT,
        Permission.CALENDAR_VIEW_ADMINISTRATION,
    )
    assert await _titles(member, "administration") == ["A1 task", "A2 task"]
    # The grant is for the Administration of the unit it was given at, not for everything.
    assert (await member.get(f"{CALENDAR}/all", **RANGE)).status_code == 403
