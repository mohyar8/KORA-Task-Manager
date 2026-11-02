"""The whole-organization structure: open to every active Member, names and roles only."""

from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from kora_api.organization.constants import RoleKey
from tests.access.helpers import create_account, signed_in
from tests.conftest import ClientFactory
from tests.organization.helpers import make_member, make_structure

pytestmark = pytest.mark.anyio

STRUCTURE = "/api/v1/organization/structure"


def _find(node: dict[str, Any], unit_id: Any) -> dict[str, Any]:
    if node["unit_id"] == str(unit_id):
        return node
    children: list[dict[str, Any]] = node["children"]
    for child in children:
        try:
            return _find(child, unit_id)
        except KeyError:
            continue
    raise KeyError(unit_id)


async def test_every_member_sees_the_same_full_tree(
    client_factory: ClientFactory, db_session: AsyncSession
) -> None:
    s = await make_structure(db_session)
    await make_member(db_session, "lead", team_id=s.team_a1, role=RoleKey.TEAM_LEADER)
    await make_member(db_session, "lead2", team_id=s.team_a1, role=RoleKey.TEAM_LEADER)
    await make_member(db_session, "mia", team_id=s.team_a1)
    await make_member(
        db_session,
        "mgr",
        team_id=s.team_a1,
        role=RoleKey.ADMINISTRATION_MANAGER,
        role_unit_id=s.admin_a,
    )
    await make_member(db_session, "bob", team_id=s.team_b1)

    bodies: list[dict[str, Any]] = []
    for user in ("mia", "bob", "mgr"):
        client = client_factory()
        await signed_in(client, user)
        response = await client.get(STRUCTURE)
        assert response.status_code == 200
        bodies.append(response.json())
    assert bodies[0] == bodies[1] == bodies[2]

    tree: dict[str, Any] = bodies[0]
    assert tree["kind"] == "organization"
    kinds: set[str] = {c["kind"] for c in tree["children"]}
    assert kinds == {"pmo", "administration"}
    team = _find(tree, s.team_a1)
    assert {m["full_name"] for m in team["members"]} == {"Lead", "Lead2", "Mia"}
    assert len(team["leader_ids"]) == 2
    admin = _find(tree, s.admin_a)
    assert [m["full_name"] for m in admin["members"]] == ["Mgr"]
    assert len(admin["leader_ids"]) == 1
    assert {c["name"] for c in admin["children"]} == {"Team A1", "Team A2"}


async def test_the_response_has_no_contact_data(
    client_factory: ClientFactory, db_session: AsyncSession
) -> None:
    s = await make_structure(db_session)
    await make_member(db_session, "mia", team_id=s.team_a1)
    client = client_factory()
    await signed_in(client, "mia")
    text = (await client.get(STRUCTURE)).text
    for secret in ("example.test", "0500000000", "U-mia", "Engineering"):
        assert secret not in text


async def test_inactive_members_and_archived_units_are_left_out(
    client_factory: ClientFactory, db_session: AsyncSession
) -> None:
    s = await make_structure(db_session)
    await make_member(db_session, "mia", team_id=s.team_a1)
    gone, _ = await make_member(db_session, "gone", team_id=s.team_a1)
    from kora_api.core import clock
    from kora_api.organization.constants import MemberStatus
    from kora_api.organization.models import OrgUnit

    gone.status = MemberStatus.DEACTIVATED
    unit = await db_session.get(OrgUnit, s.team_a2)
    assert unit is not None
    unit.archived_at = clock.utcnow()
    await db_session.commit()

    client = client_factory()
    await signed_in(client, "mia")
    tree: dict[str, Any] = (await client.get(STRUCTURE)).json()
    assert [m["full_name"] for m in _find(tree, s.team_a1)["members"]] == ["Mia"]
    with pytest.raises(KeyError):
        _find(tree, s.team_a2)


async def test_an_account_without_a_member_is_refused(
    client_factory: ClientFactory, db_session: AsyncSession
) -> None:
    await make_structure(db_session)
    await create_account(db_session, "root", system_admin=True)
    client = client_factory()
    await signed_in(client, "root")
    assert (await client.get(STRUCTURE)).status_code == 403
    assert (await client_factory().get(STRUCTURE)).status_code == 401
