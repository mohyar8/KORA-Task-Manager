"""The KORA league: everyone reads, only the PMO Leader (or a grantee) changes points."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kora_api.access.permissions import OverrideEffect, Permission
from kora_api.audit.models import AuditRecord
from tests.organization.helpers import add_override
from tests.tasks.conftest import Login, World

pytestmark = pytest.mark.anyio

LEAGUE = "/api/v1/league"


def _points(world: World, **by_team: int) -> list[dict[str, object]]:
    return [{"team_id": str(getattr(world.structure, t)), "points": p} for t, p in by_team.items()]


async def test_everyone_signed_in_reads_the_standings(world: World, login: Login) -> None:
    for user in ("m_a1", "tl_a1", "mgr_a", "pmo_m", "leader"):
        response = await (await login(user)).get(LEAGUE)
        assert response.status_code == 200, user
        body = response.json()
        assert body["round_title"] is None
        assert {s["team_name"] for s in body["standings"]} >= {"Team A1", "Team B1"}
        assert [s["rank"] for s in body["standings"]] == list(range(1, len(body["standings"]) + 1))
        assert all(s["points"] == 0 for s in body["standings"])


async def test_pmo_leader_sets_points_and_the_table_re_sorts(
    world: World, login: Login, db_session: AsyncSession
) -> None:
    api = await login("pmo_lead")
    response = await api.put(
        LEAGUE,
        {
            "round_title": " الجولة الأولى ",
            "points": _points(world, team_b1=6, team_a2=5, team_a1=5),
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["round_title"] == "الجولة الأولى"
    assert [(s["team_name"], s["points"]) for s in body["standings"]][:3] == [
        ("Team B1", 6),
        ("Team A1", 5),
        ("Team A2", 5),
    ]
    # Everybody sees the new table.
    seen = (await (await login("m_a1")).get(LEAGUE)).json()
    assert seen["standings"][0]["team_name"] == "Team B1"
    records = list(
        await db_session.scalars(select(AuditRecord).where(AuditRecord.action == "league.updated"))
    )
    assert len(records) == 1
    # A repeat with the same values changes nothing and records nothing.
    again = await api.put(
        LEAGUE, {"round_title": "الجولة الأولى", "points": _points(world, team_b1=6)}
    )
    assert again.status_code == 200
    records = list(
        await db_session.scalars(select(AuditRecord).where(AuditRecord.action == "league.updated"))
    )
    assert len(records) == 1


async def test_nobody_else_changes_the_result_unless_granted(
    world: World, login: Login, db_session: AsyncSession
) -> None:
    body = {"points": _points(world, team_a1=3)}
    for user in ("m_a1", "tl_a1", "mgr_a", "pmo_m", "leader"):
        assert (await (await login(user)).put(LEAGUE, body)).status_code == 403, user
    await add_override(
        db_session,
        world.account_ids["mgr_a"],
        world.structure.admin_a,
        OverrideEffect.GRANT,
        Permission.LEAGUE_MANAGE,
    )
    assert (await (await login("mgr_a")).put(LEAGUE, body)).status_code == 200


async def test_invalid_points_and_teams_are_rejected(world: World, login: Login) -> None:
    api = await login("pmo_lead")
    assert (await api.put(LEAGUE, {"points": _points(world, team_a1=-1)})).status_code == 422
    assert (await api.put(LEAGUE, {"points": _points(world, team_a1=10000)})).status_code == 422
    not_a_team = [{"team_id": str(world.structure.admin_a), "points": 1}]
    assert (await api.put(LEAGUE, {"points": not_a_team})).status_code == 422
