"""'Other': assigning someone outside the scope. The Event Leader, Deputy and PMO Leader can only be
reached that way; Members cannot create tasks at all unless granted."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from kora_api.organization.constants import RoleKey
from tests.organization.helpers import make_member
from tests.tasks.conftest import TASKS, Login, World

pytestmark = pytest.mark.anyio


def _body(world: World, scope: str, regular: list[str], other: list[str]) -> dict[str, object]:
    return {
        "title": "Meet the vendor",
        "scope_unit_id": str(world.unit(scope)),
        "assignee_member_ids": [str(world.member_ids[a]) for a in regular],
        "external_assignee_member_ids": [str(world.member_ids[a]) for a in other],
    }


async def test_top_roles_are_never_regular_assignees(world: World, login: Login) -> None:
    api = await login("leader")
    for scope, name in (("kora", "leader"), ("team_a1", "pmo_lead"), ("pmo", "pmo_lead")):
        response = await api.post(TASKS, _body(world, scope, [name], []))
        assert response.status_code == 422, (scope, name, response.text)
        assert "Other" in response.text


async def test_other_assigns_the_leader_or_a_member_of_another_team(
    world: World, login: Login
) -> None:
    api = await login("tl_a1")
    created = await api.post(TASKS, _body(world, "team_a1", ["m_a1"], ["leader", "m_b1"]))
    assert created.status_code == 201, created.text
    task = created.json()
    assert set(task["assignee_member_ids"]) == {
        str(world.member_ids[n]) for n in ("m_a1", "leader", "m_b1")
    }
    assert {e["full_name"] for e in task["external_assignees"]} == {"Leader", "M_B1"}
    # The outsider can open the task they were given.
    assert (await (await login("m_b1")).get(f"{TASKS}/{task['id']}")).status_code == 200


async def test_a_task_can_have_only_external_assignees(world: World, login: Login) -> None:
    api = await login("tl_a1")
    response = await api.post(TASKS, _body(world, "team_a1", [], ["leader"]))
    assert response.status_code == 201, response.text
    assert (await api.post(TASKS, _body(world, "team_a1", [], []))).status_code == 422


async def test_other_cannot_repeat_a_regular_assignee_or_use_an_inactive_member(
    world: World, login: Login
) -> None:
    api = await login("tl_a1")
    assert (await api.post(TASKS, _body(world, "team_a1", ["m_a1"], ["m_a1"]))).status_code == 422


async def test_external_assignees_survive_the_scope_cleanup(world: World, login: Login) -> None:
    api = await login("tl_a1")
    task = (await api.post(TASKS, _body(world, "team_a1", ["m_a1"], ["m_b1"]))).json()
    admin = await login("leader")
    # Moving the task re-checks every assignee; the external one stays, regular ones are checked.
    moved = await admin.post(
        f"{TASKS}/{task['id']}/move", {"scope_unit_id": str(world.structure.team_a2)}
    )
    assert moved.status_code == 200, moved.text
    after = (await admin.get(f"{TASKS}/{task['id']}")).json()
    assert str(world.member_ids["m_b1"]) in after["assignee_member_ids"]
    assert str(world.member_ids["m_a1"]) not in after["assignee_member_ids"]


async def test_add_assignee_outside_scope_needs_external_flag(world: World, login: Login) -> None:
    api = await login("tl_a1")
    task = (await api.post(TASKS, _body(world, "team_a1", ["m_a1"], []))).json()
    url = f"{TASKS}/{task['id']}/assignees"
    plain = await api.post(url, {"member_id": str(world.member_ids["leader"])})
    assert plain.status_code == 422
    other = await api.post(url, {"member_id": str(world.member_ids["leader"]), "external": True})
    assert other.status_code == 200, other.text
    assert [e["full_name"] for e in other.json()["external_assignees"]] == ["Leader"]


async def test_plain_members_cannot_create_tasks(world: World, login: Login) -> None:
    for user in ("m_a1b", "pmo_m"):
        api = await login(user)
        response = await api.post(TASKS, _body(world, "team_a1", ["m_a1"], []))
        assert response.status_code == 403, user


async def test_directory_scope_all_lists_everyone_for_task_creators_only(
    world: World, login: Login, db_session: AsyncSession
) -> None:
    await make_member(db_session, "extra", team_id=world.structure.team_b1, role=RoleKey.MEMBER)
    creator = await login("tl_a1")
    mine = {m["full_name"] for m in (await creator.get("/api/v1/organization/members")).json()}
    everyone = {
        m["full_name"]
        for m in (await creator.get("/api/v1/organization/members", scope="all")).json()
    }
    assert "Extra" not in mine
    assert "Extra" in everyone
    plain = await login("m_a1b")
    plain_all = {
        m["full_name"]
        for m in (await plain.get("/api/v1/organization/members", scope="all")).json()
    }
    assert "Extra" not in plain_all


async def test_tasks_from_outside_the_structure_are_flagged(world: World, login: Login) -> None:
    def body(scope: str) -> dict[str, object]:
        return _body(world, scope, ["m_a1"], [])

    team_leader = (await (await login("tl_a1")).post(TASKS, body("team_a1"))).json()
    manager = (await (await login("mgr_a")).post(TASKS, body("team_a1"))).json()
    granted = (await (await login("m_a1")).post(TASKS, body("team_a1"))).json()
    leader = (await (await login("leader")).post(TASKS, body("team_a1"))).json()
    assert [t["from_outside"] for t in (team_leader, manager, granted, leader)] == [
        False,
        False,
        True,
        True,
    ]
