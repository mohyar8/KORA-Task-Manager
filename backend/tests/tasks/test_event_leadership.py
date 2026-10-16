"""The Event Leader and Deputy can be given work in any scope, but only by leaders and managers."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from kora_api.organization.constants import RoleKey
from tests.organization.helpers import make_member
from tests.tasks.conftest import TASKS, Login, World

pytestmark = pytest.mark.anyio


async def _task_body(world: World, assignee: str) -> dict[str, object]:
    return {
        "title": "Meet the vendor",
        "scope_unit_id": str(world.structure.team_b1),
        "assignee_member_ids": [str(world.member_ids[assignee])],
    }


async def test_team_leader_can_assign_the_event_leader_outside_their_scope(
    world: World, login: Login, db_session: AsyncSession
) -> None:
    await make_member(
        db_session, "tl_b1", team_id=world.structure.team_b1, role=RoleKey.TEAM_LEADER
    )
    api = await login("tl_b1")
    response = await api.post(TASKS, await _task_body(world, "leader"))
    assert response.status_code == 201, response.text
    # The assignee stays on the task: they are not "out of scope".
    task_id = response.json()["id"]
    detail = (await api.get(f"{TASKS}/{task_id}")).json()
    assert str(world.member_ids["leader"]) in detail["assignee_member_ids"]


async def test_plain_member_cannot_assign_the_event_leader(world: World, login: Login) -> None:
    api = await login("m_b1")
    response = await api.post(TASKS, await _task_body(world, "leader"))
    assert response.status_code == 422
    assert "Event Leader" in response.text


async def test_plain_member_cannot_add_the_event_leader_later(world: World, login: Login) -> None:
    api = await login("m_b1")
    body = await _task_body(world, "m_b1")
    created = await api.post(TASKS, body)
    assert created.status_code == 201
    added = await api.post(
        f"{TASKS}/{created.json()['id']}/assignees",
        {"member_id": str(world.member_ids["leader"])},
    )
    assert added.status_code == 422


async def test_other_members_outside_the_scope_are_still_rejected(
    world: World, login: Login, db_session: AsyncSession
) -> None:
    await make_member(
        db_session, "tl_b1", team_id=world.structure.team_b1, role=RoleKey.TEAM_LEADER
    )
    api = await login("tl_b1")
    assert (await api.post(TASKS, await _task_body(world, "m_a1"))).status_code == 422
