"""PMO follow-up: read every team's tasks, change nothing."""

import pytest

from tests.tasks.conftest import TASKS, Login, World

pytestmark = pytest.mark.anyio


async def _seed(world: World, login: Login) -> dict[str, str]:
    leader = await login("leader")
    ids: dict[str, str] = {}
    for scope, assignee in (("team_a1", "m_a1"), ("team_b1", "m_b1")):
        response = await leader.post(
            TASKS,
            {
                "title": f"{scope} task",
                "scope_unit_id": str(world.unit(scope)),
                "assignee_member_ids": [str(world.member_ids[assignee])],
            },
        )
        ids[scope] = response.json()["id"]
    return ids


async def test_pmo_follows_every_team_but_not_through_the_normal_list(
    world: World, login: Login
) -> None:
    ids = await _seed(world, login)
    for user in ("pmo_lead", "pmo_m"):
        api = await login(user)
        followed = (await api.get(f"{TASKS}/follow")).json()
        assert {t["title"] for t in followed} == {"team_a1 task", "team_b1 task"}
        assert {t["unit_name"] for t in followed} == {"Team A1", "Team B1"}
        assert all(t["administration_name"] for t in followed)
        # The normal list stays the PMO's own tasks; other teams' tasks are not mixed into it.
        assert (await api.get(TASKS)).json() == []
        # They can open a followed task, but not change or comment on it.
        assert (await api.get(f"{TASKS}/{ids['team_a1']}")).status_code == 200
        assert (await api.patch(f"{TASKS}/{ids['team_a1']}", {"title": "x"})).status_code == 403
        status = await api.post(f"{TASKS}/{ids['team_a1']}/status", {"status": "completed"})
        assert status.status_code == 403


async def test_follow_needs_the_permission(world: World, login: Login) -> None:
    await _seed(world, login)
    for user in ("m_a1", "tl_a1", "mgr_a"):
        assert (await (await login(user)).get(f"{TASKS}/follow")).status_code == 403, user
