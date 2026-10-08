"""A small populated organization and per-user API sessions for task tests.

KORA -> Admin A (Team A1, Team A2), Admin B (Team B1); PMO.
Members (role @ role unit, Team):
  leader      Event/Project Leader @ KORA,          Team A1
  mgr_a       Administration Manager @ Admin A,     Team A1
  pmo_lead    PMO Leader @ PMO,                     Team A2
  pmo_m       PMO Member @ PMO,                     Team A2
  tl_a1       Team Leader @ Team A1
  m_a1, m_a1b Member @ Team A1
  m_a2        Member @ Team A2
  m_b1        Member @ Team B1
Accounts without a Member: sysadmin (System Admin), outsider.
"""

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from kora_api.organization.constants import KORA_UNIT_ID, PMO_UNIT_ID, RoleKey
from tests.access.helpers import create_account, csrf_headers, signed_in
from tests.conftest import ClientFactory
from tests.organization.helpers import Structure, make_member, make_structure

TASKS = "/api/v1/tasks"
SERIES = "/api/v1/task-series"


@dataclass
class World:
    structure: Structure
    member_ids: dict[str, uuid.UUID]
    account_ids: dict[str, uuid.UUID]

    def unit(self, name: str) -> uuid.UUID:
        return {"kora": KORA_UNIT_ID, "pmo": PMO_UNIT_ID}.get(name) or getattr(self.structure, name)


@pytest.fixture
async def world(db_session: AsyncSession) -> World:
    s = await make_structure(db_session)
    people: list[tuple[str, uuid.UUID, RoleKey, uuid.UUID | None]] = [
        ("leader", s.team_a1, RoleKey.EVENT_PROJECT_LEADER, KORA_UNIT_ID),
        ("mgr_a", s.team_a1, RoleKey.ADMINISTRATION_MANAGER, s.admin_a),
        ("pmo_lead", s.team_a2, RoleKey.PMO_LEADER, PMO_UNIT_ID),
        ("pmo_m", s.team_a2, RoleKey.PMO_MEMBER, PMO_UNIT_ID),
        ("tl_a1", s.team_a1, RoleKey.TEAM_LEADER, None),
        ("m_a1", s.team_a1, RoleKey.MEMBER, None),
        ("m_a1b", s.team_a1, RoleKey.MEMBER, None),
        ("m_a2", s.team_a2, RoleKey.MEMBER, None),
        ("m_b1", s.team_b1, RoleKey.MEMBER, None),
    ]
    member_ids: dict[str, uuid.UUID] = {}
    account_ids: dict[str, uuid.UUID] = {}
    for name, team, role, role_unit in people:
        member, account = await make_member(
            db_session, name, team_id=team, role=role, role_unit_id=role_unit
        )
        member_ids[name] = member.id
        account_ids[name] = account.id
    account_ids["sysadmin"] = (await create_account(db_session, "sysadmin", system_admin=True)).id
    account_ids["outsider"] = (await create_account(db_session, "outsider")).id
    return World(s, member_ids, account_ids)


@dataclass
class Api:
    """A signed-in user's client; unsafe requests carry the CSRF header."""

    client: AsyncClient
    csrf: str

    async def get(self, path: str, **params: Any) -> Response:
        return await self.client.get(path, params=params or None)

    async def post(self, path: str, body: Any = None) -> Response:
        return await self.client.post(path, json=body, headers=csrf_headers(self.csrf))

    async def patch(self, path: str, body: Any) -> Response:
        return await self.client.patch(path, json=body, headers=csrf_headers(self.csrf))


Login = Callable[[str], Awaitable[Api]]


@pytest.fixture
def login(client_factory: ClientFactory) -> Login:
    async def _login(username: str) -> Api:
        client = client_factory()
        return Api(client, await signed_in(client, username))

    return _login


@pytest.fixture
def new_task(world: World) -> Callable[..., Awaitable[dict[str, Any]]]:
    """Create a task through the API and return its JSON (asserts 201)."""

    async def _create(api: Api, scope: str, assignees: list[str], **fields: Any) -> dict[str, Any]:
        response = await api.post(
            TASKS,
            {
                "title": fields.pop("title", "Prepare venue"),
                "scope_unit_id": str(world.unit(scope)),
                "assignee_member_ids": [str(world.member_ids[a]) for a in assignees],
                **fields,
            },
        )
        assert response.status_code == 201, response.text
        result: dict[str, Any] = response.json()
        return result

    return _create
