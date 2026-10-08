import re
import uuid
from datetime import datetime, timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kora_api.access import service as access_service
from kora_api.access.models import AccountStatus, PermissionOverride, RolePermissionDefault
from kora_api.access.permissions import OverrideEffect
from kora_api.organization.constants import KORA_UNIT_ID, RoleKey
from tests.access.helpers import create_account, csrf_headers, sign_in, signed_in
from tests.conftest import ClientFactory, FrozenClock
from tests.organization.helpers import MANAGE, UNITS, make_member, make_structure, snapshot
from tests.route_tree import mounted_routes

pytestmark = pytest.mark.anyio

ADMIN = "/api/v1/admin"


async def _post(client: AsyncClient, csrf: str, path: str, body: Any = None) -> Response:
    return await client.post(path, json=body, headers=csrf_headers(csrf))


@pytest.fixture
async def admin_csrf(db_client: AsyncClient, db_session: AsyncSession) -> str:
    await create_account(db_session, "sysadmin", system_admin=True)
    return await signed_in(db_client, "sysadmin")


def _override(unit_id: uuid.UUID, effect: str = "grant", **extra: Any) -> dict[str, Any]:
    return {
        "permission": MANAGE,
        "unit_id": str(unit_id),
        "effect": effect,
        "reason": "Needed for setup",
        **extra,
    }


# --- Every System Admin-only route ----------------------------------------------------------------


async def test_every_admin_route_requires_system_admin(
    db_app: FastAPI, db_client: AsyncClient, db_session: AsyncSession
) -> None:
    structure = await make_structure(db_session)
    await make_member(
        db_session,
        "leader",
        team_id=structure.team_a1,
        role=RoleKey.EVENT_PROJECT_LEADER,
        role_unit_id=KORA_UNIT_ID,
    )
    csrf = await signed_in(db_client, "leader")
    # The mounted route tree, so admin routes hidden from OpenAPI are covered too.
    routes = [
        (method, re.sub(r"\{[^}]+\}", str(uuid.uuid4()), path))
        for methods, path in mounted_routes(db_app)
        if path.startswith(ADMIN)
        for method in methods - {"HEAD"}
    ]
    assert len(routes) >= 15

    for method, path in routes:
        response = await db_client.request(method, path, json={}, headers=csrf_headers(csrf))
        assert response.status_code == 403, (method, path)
        assert response.json() == {"detail": "System Admin authority required."}


# --- Overrides ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "body",
    [
        _override(KORA_UNIT_ID, reason=""),
        _override(KORA_UNIT_ID, reason="   "),
        {k: v for k, v in _override(KORA_UNIT_ID).items() if k != "reason"},
        _override(KORA_UNIT_ID, valid_to="2030-01-01T00:00:00Z"),  # no expiry
        _override(KORA_UNIT_ID, permission="tasks.manage"),  # not in the catalog
    ],
)
async def test_override_requires_reason_and_catalog_permission_and_has_no_expiry(
    db_client: AsyncClient, db_session: AsyncSession, admin_csrf: str, body: dict[str, Any]
) -> None:
    target = await create_account(db_session, "target")

    response = await _post(db_client, admin_csrf, f"{ADMIN}/accounts/{target.id}/overrides", body)

    assert response.status_code == 422


async def test_override_validation_of_account_and_unit(
    db_client: AsyncClient, db_session: AsyncSession, admin_csrf: str
) -> None:
    inactive = await create_account(
        db_session,
        "inactive",
        status=AccountStatus.DEACTIVATED,
    )
    active = await create_account(db_session, "active")

    missing_account = await _post(
        db_client, admin_csrf, f"{ADMIN}/accounts/{uuid.uuid4()}/overrides", _override(KORA_UNIT_ID)
    )
    inactive_account = await _post(
        db_client, admin_csrf, f"{ADMIN}/accounts/{inactive.id}/overrides", _override(KORA_UNIT_ID)
    )
    unknown_unit = await _post(
        db_client, admin_csrf, f"{ADMIN}/accounts/{active.id}/overrides", _override(uuid.uuid4())
    )

    assert missing_account.status_code == 404
    assert inactive_account.status_code == 409
    assert unknown_unit.status_code == 422


async def test_ending_an_override_removes_access_and_keeps_history(
    client_factory: ClientFactory,
    db_client: AsyncClient,
    db_session: AsyncSession,
    admin_csrf: str,
    frozen_clock: FrozenClock,
) -> None:
    target = await create_account(db_session, "target")
    created = await _post(
        db_client, admin_csrf, f"{ADMIN}/accounts/{target.id}/overrides", _override(KORA_UNIT_ID)
    )
    duplicate = await _post(
        db_client, admin_csrf, f"{ADMIN}/accounts/{target.id}/overrides", _override(KORA_UNIT_ID)
    )
    assert duplicate.status_code == 409
    granted_at = frozen_clock.now
    frozen_clock.advance(timedelta(minutes=1))

    ended = await _post(db_client, admin_csrf, f"{ADMIN}/overrides/{created.json()['id']}/end")

    assert ended.status_code == 200
    assert ended.json()["valid_to"] is not None
    assert ended.json()["reason"] == "Needed for setup"
    assert (
        await _post(db_client, admin_csrf, f"{ADMIN}/overrides/{created.json()['id']}/end")
    ).status_code == 409
    rows = (await db_session.scalars(select(PermissionOverride))).all()
    assert len(rows) == 1  # ended, not deleted
    assert not (await snapshot(db_session, target.id)).allows(MANAGE, KORA_UNIT_ID)
    assert (await snapshot(db_session, target.id, granted_at)).allows(MANAGE, KORA_UNIT_ID)
    their_client = client_factory()
    await signed_in(their_client, "target")
    assert (await their_client.get(UNITS)).json() == []


# --- Role defaults --------------------------------------------------------------------------------


async def test_role_defaults_can_be_ended_and_re_added_with_history(
    client_factory: ClientFactory,
    db_client: AsyncClient,
    db_session: AsyncSession,
    admin_csrf: str,
    frozen_clock: FrozenClock,
) -> None:
    structure = await make_structure(db_session)
    await make_member(
        db_session,
        "deputy",
        team_id=structure.team_a1,
        role=RoleKey.DEPUTY_LEADER,
        role_unit_id=KORA_UNIT_ID,
    )
    deputy = client_factory()
    await signed_in(deputy, "deputy")
    assert (await deputy.get(f"{UNITS}/{structure.team_b1}")).status_code == 200

    defaults = (await db_client.get(f"{ADMIN}/role-defaults")).json()
    deputy_default = next(
        d for d in defaults if d["role_key"] == "deputy_leader" and d["permission"] == MANAGE
    )
    frozen_clock.advance(timedelta(minutes=1))
    ended = await _post(db_client, admin_csrf, f"{ADMIN}/role-defaults/{deputy_default['id']}/end")
    assert ended.status_code == 200
    assert (await deputy.get(f"{UNITS}/{structure.team_b1}")).status_code == 403

    readded = await _post(
        db_client,
        admin_csrf,
        f"{ADMIN}/role-defaults",
        {"role_key": "deputy_leader", "permission": MANAGE},
    )
    assert readded.status_code == 201
    assert (await deputy.get(f"{UNITS}/{structure.team_b1}")).status_code == 200
    rows = (
        await db_session.scalars(
            select(RolePermissionDefault).where(
                RolePermissionDefault.role_key == "deputy_leader",
                RolePermissionDefault.permission_key == MANAGE,
            )
        )
    ).all()
    assert len(rows) == 2


async def test_role_default_validation(db_client: AsyncClient, admin_csrf: str) -> None:
    unknown_role = await _post(
        db_client,
        admin_csrf,
        f"{ADMIN}/role-defaults",
        {"role_key": "deputy_team_leader", "permission": MANAGE},
    )
    duplicate = await _post(
        db_client,
        admin_csrf,
        f"{ADMIN}/role-defaults",
        {"role_key": "event_project_leader", "permission": MANAGE},
    )

    assert unknown_role.status_code == 422
    assert duplicate.status_code == 409


# --- Effective access -----------------------------------------------------------------------------


async def test_inspection_explains_each_decision(
    db_client: AsyncClient, db_session: AsyncSession, admin_csrf: str
) -> None:
    structure = await make_structure(db_session)
    _, leader = await make_member(
        db_session,
        "leader",
        team_id=structure.team_a1,
        role=RoleKey.EVENT_PROJECT_LEADER,
        role_unit_id=KORA_UNIT_ID,
    )
    await _post(
        db_client,
        admin_csrf,
        f"{ADMIN}/accounts/{leader.id}/overrides",
        _override(structure.admin_b, "deny"),
    )

    response = await db_client.get(f"{ADMIN}/accounts/{leader.id}/effective-access")

    assert response.status_code == 200
    permission = next(p for p in response.json()["permissions"] if p["permission"] == MANAGE)
    decisions = {u["unit_id"]: u for u in permission["units"]}
    assert permission["permission"] == MANAGE
    assert decisions[str(structure.team_a1)]["source"] == "role_default"
    assert decisions[str(structure.team_a1)]["decided_at_unit_id"] == str(KORA_UNIT_ID)
    assert decisions[str(structure.team_b1)]["allowed"] is False
    assert decisions[str(structure.team_b1)]["source"] == "override_deny"
    assert decisions[str(structure.team_b1)]["decided_at_unit_id"] == str(structure.admin_b)


async def test_users_read_only_their_own_effective_access(
    client_factory: ClientFactory, db_session: AsyncSession
) -> None:
    structure = await make_structure(db_session)
    _, member = await make_member(db_session, "plain", team_id=structure.team_a1)
    other = await create_account(db_session, "other")
    client = client_factory()
    await signed_in(client, "plain")

    mine = await client.get("/api/v1/access/me")
    theirs = await client.get(f"{ADMIN}/accounts/{other.id}/effective-access")

    assert mine.status_code == 200
    assert mine.json()["account_id"] == str(member.id)
    assert not any(u["allowed"] for u in mine.json()["permissions"][0]["units"])
    assert theirs.status_code == 403


async def test_system_admin_grant_gives_no_operational_access(
    client_factory: ClientFactory, db_client: AsyncClient, db_session: AsyncSession, admin_csrf: str
) -> None:
    structure = await make_structure(db_session)
    member, account = await make_member(db_session, "promoted", team_id=structure.team_a1)

    granted = await _post(db_client, admin_csrf, f"{ADMIN}/accounts/{account.id}/system-admin")

    assert granted.status_code == 201
    assert (await snapshot(db_session, account.id)).units_with(MANAGE) == frozenset()
    promoted = client_factory()
    await signed_in(promoted, "promoted")
    assert (await promoted.get(f"{ADMIN}/members")).status_code == 200
    assert (await promoted.get(UNITS)).json() == []
    assert member.id


async def test_system_admin_grants_and_revocation(
    db_client: AsyncClient, db_session: AsyncSession, admin_csrf: str
) -> None:
    other = await create_account(db_session, "other")
    me = (await db_client.get("/api/v1/auth/me")).json()["id"]

    assert (
        await _post(db_client, admin_csrf, f"{ADMIN}/accounts/{other.id}/system-admin")
    ).status_code == 201
    assert (
        await _post(db_client, admin_csrf, f"{ADMIN}/accounts/{other.id}/system-admin")
    ).status_code == 409
    listed = {a["username"] for a in (await db_client.get(f"{ADMIN}/system-admins")).json()}
    assert listed == {"sysadmin", "other"}

    revoked = await _post(db_client, admin_csrf, f"{ADMIN}/accounts/{other.id}/system-admin/revoke")
    assert revoked.status_code == 204
    final = await _post(db_client, admin_csrf, f"{ADMIN}/accounts/{me}/system-admin/revoke")
    assert final.status_code == 409


async def test_admin_routes_enforce_csrf_and_temporary_password_gate(
    client_factory: ClientFactory, db_session: AsyncSession
) -> None:
    await create_account(db_session, "sysadmin", system_admin=True)
    await create_account(db_session, "newadmin", system_admin=True, temporary=True)
    target = await create_account(db_session, "target")

    admin = client_factory()
    await signed_in(admin, "sysadmin")
    no_csrf = await admin.post(
        f"{ADMIN}/accounts/{target.id}/overrides", json=_override(KORA_UNIT_ID)
    )
    assert no_csrf.json() == {"detail": "CSRF token missing or invalid."}

    gated = client_factory()
    await signed_in(gated, "newadmin")
    assert (await gated.get(f"{ADMIN}/members")).json() == {"detail": "Password change required."}


# --- Current vs historical access for deactivated accounts ----------------------------------------


def _allowed_units(response: Response) -> set[str]:
    assert response.status_code == 200, response.text
    return {u["unit_id"] for u in response.json()["permissions"][0]["units"] if u["allowed"]}


async def test_deactivated_member_has_no_current_access_but_history_is_reconstructed(
    client_factory: ClientFactory,
    db_client: AsyncClient,
    db_session: AsyncSession,
    frozen_clock: FrozenClock,
    admin_csrf: str,
) -> None:
    structure = await make_structure(db_session)
    member, leader = await make_member(
        db_session,
        "leader",
        team_id=structure.team_a1,
        role=RoleKey.EVENT_PROJECT_LEADER,
        role_unit_id=KORA_UNIT_ID,
    )
    frozen_clock.advance(timedelta(minutes=1))
    while_active = frozen_clock.now
    frozen_clock.advance(timedelta(minutes=1))
    deactivated = await _post(db_client, admin_csrf, f"{ADMIN}/members/{member.id}/deactivate")
    assert deactivated.status_code == 200
    frozen_clock.advance(timedelta(minutes=1))
    inspect = f"{ADMIN}/accounts/{leader.id}/effective-access"

    # Current: no authentication, no access.
    assert (await sign_in(client_factory(), "leader")).status_code == 401
    assert (await snapshot(db_session, leader.id)).units_with(MANAGE) == frozenset()
    assert _allowed_units(await db_client.get(inspect)) == set()

    # Historical: the account was active then, so its access then is reconstructed.
    then = await db_client.get(inspect, params={"as_of": while_active.isoformat()})
    assert str(structure.team_b1) in _allowed_units(then)
    assert {u["source"] for u in then.json()["permissions"][0]["units"]} == {"role_default"}
    assert (await snapshot(db_session, leader.id, while_active)).allows(MANAGE, KORA_UNIT_ID)


async def test_historical_access_follows_deactivation_and_reactivation_periods(
    db_session: AsyncSession, frozen_clock: FrozenClock
) -> None:
    account = await create_account(db_session, "builder")
    db_session.add(
        PermissionOverride(
            account_id=account.id,
            permission_key=MANAGE,
            unit_id=KORA_UNIT_ID,
            effect=OverrideEffect.GRANT,
            reason="setup",
            valid_from=frozen_clock.now,
            created_by_account_id=account.id,
        )
    )
    await db_session.commit()
    times: dict[str, datetime] = {}
    for label, change in (
        ("active", None),
        ("deactivated", access_service.deactivate_account),
        ("reactivated", access_service.reactivate_account),
    ):
        frozen_clock.advance(timedelta(minutes=1))
        if change is not None:
            await change(db_session, account.id)
            await db_session.commit()
        frozen_clock.advance(timedelta(minutes=1))
        times[label] = frozen_clock.now

    allowed = {
        label: (await snapshot(db_session, account.id, at)).allows(MANAGE, KORA_UNIT_ID)
        for label, at in times.items()
    }
    assert allowed == {"active": True, "deactivated": False, "reactivated": True}
    assert (await snapshot(db_session, account.id)).allows(MANAGE, KORA_UNIT_ID)


async def test_as_of_requires_a_time_zone(
    db_client: AsyncClient, db_session: AsyncSession, admin_csrf: str
) -> None:
    target = await create_account(db_session, "target")

    response = await db_client.get(
        f"{ADMIN}/accounts/{target.id}/effective-access", params={"as_of": "2026-01-01T00:00:00"}
    )

    assert response.status_code == 422
