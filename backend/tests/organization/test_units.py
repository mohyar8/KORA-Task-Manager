from datetime import timedelta

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kora_api.access.permissions import OverrideEffect
from kora_api.organization.constants import KORA_UNIT_ID, PMO_UNIT_ID, RoleKey, UnitKind
from kora_api.organization.models import OrgUnitPlacement
from tests.access.helpers import create_account, csrf_headers, signed_in
from tests.conftest import ClientFactory, FrozenClock
from tests.organization.helpers import (
    MANAGE,
    UNITS,
    add_override,
    make_member,
    make_structure,
    make_unit,
    snapshot,
)

pytestmark = pytest.mark.anyio

DENIED = {"detail": "Not permitted."}


async def _post(client: AsyncClient, csrf: str, path: str, body: object | None = None) -> Response:
    return await client.post(path, json=body, headers=csrf_headers(csrf))


# --- First structure and System Admin -------------------------------------------------------------


async def test_first_structure_via_explicit_override_for_non_member_account(
    client_factory: ClientFactory, db_session: AsyncSession
) -> None:
    sysadmin = await create_account(db_session, "sysadmin", system_admin=True)
    await create_account(db_session, "builder")
    admin_client, builder = client_factory(), client_factory()
    admin_csrf = await signed_in(admin_client, "sysadmin")
    builder_csrf = await signed_in(builder, "builder")
    builder_id = (await builder.get("/api/v1/auth/me")).json()["id"]

    # No access yet, for either account.
    body = {"kind": "administration", "name": "Admin A", "parent_id": str(KORA_UNIT_ID)}
    assert (await _post(builder, builder_csrf, UNITS, body)).status_code == 403
    assert (await _post(admin_client, admin_csrf, UNITS, body)).status_code == 403

    granted = await _post(
        admin_client,
        admin_csrf,
        f"/api/v1/admin/accounts/{builder_id}/overrides",
        {"permission": MANAGE, "unit_id": str(KORA_UNIT_ID), "effect": "grant", "reason": "setup"},
    )
    assert granted.status_code == 201

    administration = await _post(builder, builder_csrf, UNITS, body)
    assert administration.status_code == 201
    team = await _post(
        builder,
        builder_csrf,
        UNITS,
        {"kind": "team", "name": "Team A1", "parent_id": administration.json()["id"]},
    )
    assert team.status_code == 201
    assert team.json()["parent_id"] == administration.json()["id"]
    assert sysadmin.id  # the System Admin itself still has no organization access
    assert (await admin_client.get(UNITS)).json() == []


async def test_system_admin_can_grant_itself_explicit_access(
    db_client: AsyncClient, db_session: AsyncSession
) -> None:
    sysadmin = await create_account(db_session, "sysadmin", system_admin=True)
    csrf = await signed_in(db_client, "sysadmin")
    await _post(
        db_client,
        csrf,
        f"/api/v1/admin/accounts/{sysadmin.id}/overrides",
        {"permission": MANAGE, "unit_id": str(KORA_UNIT_ID), "effect": "grant", "reason": "setup"},
    )

    body = {"kind": "administration", "name": "Admin A", "parent_id": str(KORA_UNIT_ID)}
    assert (await _post(db_client, csrf, UNITS, body)).status_code == 201


async def test_system_admin_has_no_implicit_unit_access(
    db_client: AsyncClient, db_session: AsyncSession
) -> None:
    structure = await make_structure(db_session)
    await create_account(db_session, "sysadmin", system_admin=True)
    csrf = await signed_in(db_client, "sysadmin")

    assert (await db_client.get(UNITS)).json() == []
    assert (await db_client.get(f"{UNITS}/{structure.team_a1}")).status_code == 403
    archived = await _post(db_client, csrf, f"{UNITS}/{structure.team_a1}/archive")
    assert archived.status_code == 403


# --- Role defaults and scope ----------------------------------------------------------------------


@pytest.mark.parametrize("role", [RoleKey.EVENT_PROJECT_LEADER, RoleKey.DEPUTY_LEADER])
async def test_leaders_manage_the_whole_organization_by_default(
    db_client: AsyncClient, db_session: AsyncSession, role: RoleKey
) -> None:
    structure = await make_structure(db_session)
    await make_member(
        db_session, "leader", team_id=structure.team_a1, role=role, role_unit_id=KORA_UNIT_ID
    )
    await signed_in(db_client, "leader")

    listed = {unit["id"] for unit in (await db_client.get(UNITS)).json()}

    assert listed == {
        str(u)
        for u in (
            KORA_UNIT_ID,
            PMO_UNIT_ID,
            structure.admin_a,
            structure.admin_b,
            structure.team_a1,
            structure.team_a2,
            structure.team_b1,
        )
    }


@pytest.mark.parametrize(
    ("role", "unit_attr"),
    [
        (RoleKey.PMO_LEADER, "pmo"),
        (RoleKey.PMO_MEMBER, "pmo"),
        (RoleKey.ADMINISTRATION_MANAGER, "admin_a"),
        (RoleKey.TEAM_LEADER, "team_a1"),
        (RoleKey.MEMBER, "team_a1"),
    ],
)
async def test_other_roles_have_no_default_access(
    db_client: AsyncClient, db_session: AsyncSession, role: RoleKey, unit_attr: str
) -> None:
    structure = await make_structure(db_session)
    await make_member(
        db_session,
        "someone",
        team_id=structure.team_a1,
        role=role,
        role_unit_id=getattr(structure, unit_attr),
    )
    csrf = await signed_in(db_client, "someone")

    assert (await db_client.get(UNITS)).json() == []
    assert (await db_client.get(f"{UNITS}/{structure.team_a1}")).json() == DENIED
    body = {"kind": "team", "name": "New", "parent_id": str(structure.admin_a)}
    assert (await _post(db_client, csrf, UNITS, body)).status_code == 403


async def test_deny_override_restricts_a_leader_at_a_narrower_scope(
    db_client: AsyncClient, db_session: AsyncSession
) -> None:
    structure = await make_structure(db_session)
    _, leader = await make_member(
        db_session,
        "leader",
        team_id=structure.team_a1,
        role=RoleKey.EVENT_PROJECT_LEADER,
        role_unit_id=KORA_UNIT_ID,
    )
    await add_override(db_session, leader.id, structure.admin_a, OverrideEffect.DENY)
    await signed_in(db_client, "leader")

    listed = {unit["id"] for unit in (await db_client.get(UNITS)).json()}

    assert str(structure.admin_b) in listed
    assert not {str(structure.admin_a), str(structure.team_a1), str(structure.team_a2)} & listed
    assert (await db_client.get(f"{UNITS}/{structure.team_a2}")).status_code == 403


async def test_scoped_grant_lists_only_the_scope_and_descendants(
    db_client: AsyncClient, db_session: AsyncSession
) -> None:
    structure = await make_structure(db_session)
    _, manager = await make_member(
        db_session,
        "manager",
        team_id=structure.team_a1,
        role=RoleKey.ADMINISTRATION_MANAGER,
        role_unit_id=structure.admin_a,
    )
    await add_override(db_session, manager.id, structure.admin_a)
    await signed_in(db_client, "manager")

    listed = {unit["id"] for unit in (await db_client.get(UNITS)).json()}

    assert listed == {str(structure.admin_a), str(structure.team_a1), str(structure.team_a2)}
    assert (await db_client.get(f"{UNITS}/{structure.team_a2}")).status_code == 200
    assert (await db_client.get(f"{UNITS}/{structure.team_b1}")).status_code == 403


# --- Structural rules -----------------------------------------------------------------------------


@pytest.fixture
async def org_admin(db_client: AsyncClient, db_session: AsyncSession) -> str:
    """Signs in an account with organization-wide organization.manage; returns its CSRF token."""
    account = await create_account(db_session, "orgadmin")
    await add_override(db_session, account.id, KORA_UNIT_ID)
    return await signed_in(db_client, "orgadmin")


@pytest.mark.parametrize(
    ("kind", "parent"),
    [
        ("administration", "admin_a"),  # Administrations only directly under KORA
        ("team", "kora"),  # Teams only under an Administration
        ("team", "pmo"),  # the PMO contains no Teams
        ("team", "team_a1"),
        ("pmo", "kora"),  # only one PMO, seeded
        ("organization", "kora"),
    ],
)
async def test_invalid_structures_are_rejected(
    db_client: AsyncClient, db_session: AsyncSession, org_admin: str, kind: str, parent: str
) -> None:
    structure = await make_structure(db_session)
    body = {"kind": kind, "name": "X", "parent_id": str(getattr(structure, parent))}

    assert (await _post(db_client, org_admin, UNITS, body)).status_code == 422


async def test_team_cannot_be_created_in_archived_administration(
    db_client: AsyncClient, db_session: AsyncSession, org_admin: str
) -> None:
    administration = await make_unit(db_session, UnitKind.ADMINISTRATION, "Old")
    assert (await _post(db_client, org_admin, f"{UNITS}/{administration.id}/archive")).is_success

    body = {"kind": "team", "name": "T", "parent_id": str(administration.id)}
    assert (await _post(db_client, org_admin, UNITS, body)).status_code == 422


# --- Team moves -----------------------------------------------------------------------------------


async def test_move_requires_access_to_team_and_destination(
    db_client: AsyncClient, db_session: AsyncSession
) -> None:
    structure = await make_structure(db_session)
    account = await create_account(db_session, "mover")
    await add_override(db_session, account.id, structure.admin_a)
    csrf = await signed_in(db_client, "mover")
    move = f"{UNITS}/{structure.team_a1}/move"

    denied = await _post(db_client, csrf, move, {"administration_id": str(structure.admin_b)})
    assert denied.status_code == 403

    await add_override(db_session, account.id, structure.admin_b)
    moved = await _post(db_client, csrf, move, {"administration_id": str(structure.admin_b)})
    assert moved.status_code == 200
    assert moved.json()["parent_id"] == str(structure.admin_b)


async def test_team_move_preserves_history_and_time_aware_scope(
    db_client: AsyncClient,
    db_session: AsyncSession,
    org_admin: str,
    frozen_clock: FrozenClock,
) -> None:
    structure = await make_structure(db_session)
    _, manager = await make_member(
        db_session,
        "manager",
        team_id=structure.team_b1,
        role=RoleKey.ADMINISTRATION_MANAGER,
        role_unit_id=structure.admin_a,
    )
    await add_override(db_session, manager.id, structure.admin_a)
    before_move = frozen_clock.now
    frozen_clock.advance(timedelta(minutes=5))

    response = await _post(
        db_client,
        org_admin,
        f"{UNITS}/{structure.team_a1}/move",
        {"administration_id": str(structure.admin_b)},
    )
    assert response.status_code == 200

    placements = (
        await db_session.scalars(
            select(OrgUnitPlacement)
            .where(OrgUnitPlacement.unit_id == structure.team_a1)
            .order_by(OrgUnitPlacement.valid_from)
        )
    ).all()
    assert [(p.parent_id, p.valid_to is None) for p in placements] == [
        (structure.admin_a, False),
        (structure.admin_b, True),
    ]
    # Scope follows the structure at each point in time.
    assert (await snapshot(db_session, manager.id, before_move)).allows(MANAGE, structure.team_a1)
    assert not (await snapshot(db_session, manager.id)).allows(MANAGE, structure.team_a1)


@pytest.mark.parametrize(
    ("unit", "destination"),
    [
        ("admin_a", "admin_b"),  # only Teams move
        ("team_a1", "admin_a"),  # already there
        ("team_a1", "team_b1"),  # destination must be an Administration
        ("team_a1", "pmo"),
    ],
)
async def test_invalid_moves_are_rejected(
    db_client: AsyncClient, db_session: AsyncSession, org_admin: str, unit: str, destination: str
) -> None:
    structure = await make_structure(db_session)

    response = await _post(
        db_client,
        org_admin,
        f"{UNITS}/{getattr(structure, unit)}/move",
        {"administration_id": str(getattr(structure, destination))},
    )

    assert response.status_code == 422


async def test_moving_a_team_keeps_member_assignments(
    db_client: AsyncClient, db_session: AsyncSession, org_admin: str
) -> None:
    structure = await make_structure(db_session)
    _, leader_account = await make_member(
        db_session, "leader", team_id=structure.team_a1, role=RoleKey.TEAM_LEADER
    )

    await _post(
        db_client,
        org_admin,
        f"{UNITS}/{structure.team_a1}/move",
        {"administration_id": str(structure.admin_b)},
    )

    access = await snapshot(db_session, leader_account.id)
    assert access.role_unit_id == structure.team_a1
    assert access.chain(structure.team_a1) == [structure.team_a1, structure.admin_b, KORA_UNIT_ID]


# --- Archiving ------------------------------------------------------------------------------------


async def test_archive_is_refused_while_dependents_are_active(
    db_client: AsyncClient, db_session: AsyncSession, org_admin: str
) -> None:
    structure = await make_structure(db_session)
    admin_c = await make_unit(db_session, UnitKind.ADMINISTRATION, "Admin C")  # no Teams
    await make_member(db_session, "member", team_id=structure.team_b1)
    await make_member(
        db_session,
        "manager",
        team_id=structure.team_a1,
        role=RoleKey.ADMINISTRATION_MANAGER,
        role_unit_id=admin_c.id,
    )

    # Admin A: active Teams. Team B1 and Team A1: active Members. Admin C: a role scoped to it.
    for unit in (structure.admin_a, structure.team_b1, structure.team_a1, admin_c.id):
        response = await _post(db_client, org_admin, f"{UNITS}/{unit}/archive")
        assert response.status_code == 409, unit

    empty_team = await _post(db_client, org_admin, f"{UNITS}/{structure.team_a2}/archive")
    assert empty_team.status_code == 200
    assert empty_team.json()["status"] == "archived"


async def test_administration_can_be_archived_once_its_teams_are(
    db_client: AsyncClient, db_session: AsyncSession, org_admin: str
) -> None:
    administration = await make_unit(db_session, UnitKind.ADMINISTRATION, "Temp")
    team = await make_unit(db_session, UnitKind.TEAM, "Temp team", administration.id)

    assert (
        await _post(db_client, org_admin, f"{UNITS}/{administration.id}/archive")
    ).status_code == 409
    assert (await _post(db_client, org_admin, f"{UNITS}/{team.id}/archive")).status_code == 200
    assert (
        await _post(db_client, org_admin, f"{UNITS}/{administration.id}/archive")
    ).status_code == 200
    assert (
        await _post(db_client, org_admin, f"{UNITS}/{administration.id}/archive")
    ).status_code == 409


@pytest.mark.parametrize("unit_id", [KORA_UNIT_ID, PMO_UNIT_ID])
async def test_kora_and_pmo_cannot_be_archived(
    db_client: AsyncClient, org_admin: str, unit_id: object
) -> None:
    assert (await _post(db_client, org_admin, f"{UNITS}/{unit_id}/archive")).status_code == 422


async def test_archived_team_cannot_be_moved(
    db_client: AsyncClient, db_session: AsyncSession, org_admin: str
) -> None:
    structure = await make_structure(db_session)
    await _post(db_client, org_admin, f"{UNITS}/{structure.team_a2}/archive")

    response = await _post(
        db_client,
        org_admin,
        f"{UNITS}/{structure.team_a2}/move",
        {"administration_id": str(structure.admin_b)},
    )

    assert response.status_code == 409


# --- Gates ----------------------------------------------------------------------------------------


async def test_unit_routes_enforce_csrf_and_temporary_password_gate(
    client_factory: ClientFactory, db_session: AsyncSession
) -> None:
    account = await create_account(db_session, "orgadmin")
    await add_override(db_session, account.id, KORA_UNIT_ID)
    temp = await create_account(db_session, "newbie", temporary=True)
    await add_override(db_session, temp.id, KORA_UNIT_ID)
    body = {"kind": "administration", "name": "A", "parent_id": str(KORA_UNIT_ID)}

    client = client_factory()
    await signed_in(client, "orgadmin")
    no_csrf = await client.post(UNITS, json=body)
    assert no_csrf.json() == {"detail": "CSRF token missing or invalid."}

    gated = client_factory()
    csrf = await signed_in(gated, "newbie")
    assert (await gated.get(UNITS)).json() == {"detail": "Password change required."}
    assert (await _post(gated, csrf, UNITS, body)).status_code == 403
