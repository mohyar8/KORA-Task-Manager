from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kora_api.access.models import AccountStatus, AuthSession, SessionRevokeReason, UserAccount
from kora_api.organization.constants import KORA_UNIT_ID, PMO_UNIT_ID, RoleKey
from kora_api.organization.models import MemberTeamPlacement, RoleAssignment
from tests.access.helpers import ME, create_account, csrf_headers, sign_in, signed_in
from tests.conftest import ClientFactory
from tests.organization.helpers import MEMBERS, Structure, make_member, make_structure

pytestmark = pytest.mark.anyio

PROFILE = {
    "full_name": "Sara Ahmed",
    "university_id": "202212345",
    "phone": "0551234567",
    "email": "sara@example.test",
    "major": "Software Engineering",
    "academic_year": "3",
}


@pytest.fixture
async def structure(db_session: AsyncSession) -> Structure:
    return await make_structure(db_session)


@pytest.fixture
async def admin_csrf(db_client: AsyncClient, db_session: AsyncSession) -> str:
    """A System Admin who is not a Member, signed in on db_client."""
    await create_account(db_session, "sysadmin", system_admin=True)
    return await signed_in(db_client, "sysadmin")


async def _post(client: AsyncClient, csrf: str, path: str, body: Any = None) -> Response:
    return await client.post(path, json=body, headers=csrf_headers(csrf))


async def _create(
    client: AsyncClient, csrf: str, structure: Structure, **overrides: Any
) -> Response:
    body = {
        **PROFILE,
        "username": "sara",
        "team_id": str(structure.team_a1),
        "role_key": "member",
        **overrides,
    }
    return await _post(client, csrf, MEMBERS, body)


async def _open_rows(db: AsyncSession, member_id: str) -> tuple[list[Any], list[Any]]:
    placements = (
        await db.scalars(
            select(MemberTeamPlacement)
            .where(MemberTeamPlacement.member_id == member_id)
            .order_by(MemberTeamPlacement.valid_from)
        )
    ).all()
    roles = (
        await db.scalars(
            select(RoleAssignment)
            .where(RoleAssignment.member_id == member_id)
            .order_by(RoleAssignment.valid_from)
        )
    ).all()
    return list(placements), list(roles)


# --- Provisioning ---------------------------------------------------------------------------------


async def test_provisioning_creates_member_account_placement_and_role(
    client_factory: ClientFactory,
    db_client: AsyncClient,
    db_session: AsyncSession,
    structure: Structure,
    admin_csrf: str,
) -> None:
    response = await _create(db_client, admin_csrf, structure)

    assert response.status_code == 201
    body = response.json()
    member = body["member"]
    assert {k: member[k] for k in PROFILE} == PROFILE
    assert member["username"] == "sara"
    assert member["status"] == "active"
    assert member["team_id"] == str(structure.team_a1)
    assert member["role_key"] == "member"
    assert member["role_unit_id"] == str(structure.team_a1)

    newcomer = client_factory()
    signed = await sign_in(newcomer, "sara", body["temporary_password"])
    assert signed.status_code == 200
    assert signed.json()["account"]["must_change_password"] is True


@pytest.mark.parametrize(
    ("role", "extra", "expected_unit"),
    [
        ("event_project_leader", {}, "kora"),
        ("deputy_leader", {}, "kora"),
        ("pmo_leader", {}, "pmo"),
        ("pmo_member", {}, "pmo"),
        ("administration_manager", {"administration_id": "admin_b"}, "admin_b"),
        ("team_leader", {}, "team_a1"),
        ("member", {}, "team_a1"),
    ],
)
async def test_each_role_is_scoped_to_its_unit(
    db_client: AsyncClient,
    structure: Structure,
    admin_csrf: str,
    role: str,
    extra: dict[str, str],
    expected_unit: str,
) -> None:
    extra = {key: str(getattr(structure, value)) for key, value in extra.items()}

    response = await _create(db_client, admin_csrf, structure, role_key=role, **extra)

    assert response.status_code == 201, response.text
    assert response.json()["member"]["role_unit_id"] == str(getattr(structure, expected_unit))
    assert response.json()["member"]["team_id"] == str(structure.team_a1)


@pytest.mark.parametrize(
    "overrides",
    [
        {"role_key": "administration_manager"},  # Administration required
        {"role_key": "team_leader", "administration_id": "admin_a"},  # no Administration allowed
        {"role_key": "administration_manager", "administration_id": "team_a1"},
        {"team_id": "admin_a"},  # placement must be a Team
        {"team_id": "pmo"},
        {"username": "x"},  # invalid username
        {"full_name": "   "},  # full name is required
        {"full_name": None},
    ],
)
async def test_invalid_provisioning_is_rejected_without_side_effects(
    db_client: AsyncClient,
    db_session: AsyncSession,
    structure: Structure,
    admin_csrf: str,
    overrides: dict[str, str],
) -> None:
    resolved = {
        k: str(getattr(structure, v)) if k in ("team_id", "administration_id") else v
        for k, v in overrides.items()
    }

    response = await _create(db_client, admin_csrf, structure, **resolved)

    assert response.status_code == 422
    assert (
        await db_session.scalar(select(UserAccount).where(UserAccount.username == "sara")) is None
    )


OPTIONAL_FIELDS = ("university_id", "phone", "email", "major", "academic_year")


async def test_only_full_name_is_required_in_the_profile(
    db_client: AsyncClient, structure: Structure, admin_csrf: str
) -> None:
    body = {
        "full_name": "Minimal Person",
        "username": "minimal",
        "team_id": str(structure.team_a1),
        "role_key": "member",
        "phone": "   ",  # blank optional values are stored as null
    }

    response = await _post(db_client, admin_csrf, MEMBERS, body)

    assert response.status_code == 201, response.text
    member = response.json()["member"]
    assert member["full_name"] == "Minimal Person"
    assert {field: member[field] for field in OPTIONAL_FIELDS} == dict.fromkeys(OPTIONAL_FIELDS)


async def test_optional_profile_fields_need_not_be_unique_and_can_be_cleared(
    db_client: AsyncClient, structure: Structure, admin_csrf: str
) -> None:
    first = await _create(db_client, admin_csrf, structure, username="first")
    second = await _create(db_client, admin_csrf, structure, username="second")
    assert first.status_code == second.status_code == 201  # same ID, phone, email: allowed

    member_id = first.json()["member"]["id"]
    cleared = await db_client.put(
        f"{MEMBERS}/{member_id}",
        json={"full_name": "Sara Ahmed", "email": None},
        headers=csrf_headers(admin_csrf),
    )

    assert cleared.status_code == 200
    assert {field: cleared.json()[field] for field in OPTIONAL_FIELDS} == dict.fromkeys(
        OPTIONAL_FIELDS
    )


async def test_several_team_leaders_may_share_a_team(
    db_client: AsyncClient, structure: Structure, admin_csrf: str
) -> None:
    for username in ("lead1", "lead2"):
        response = await _create(
            db_client, admin_csrf, structure, username=username, role_key="team_leader"
        )
        assert response.status_code == 201


async def test_profile_update_keeps_account_link(
    db_client: AsyncClient, structure: Structure, admin_csrf: str
) -> None:
    created = (await _create(db_client, admin_csrf, structure)).json()["member"]

    response = await db_client.put(
        f"{MEMBERS}/{created['id']}",
        json={**PROFILE, "phone": "0559999999"},
        headers=csrf_headers(admin_csrf),
    )

    assert response.status_code == 200
    assert response.json()["phone"] == "0559999999"
    assert response.json()["account_id"] == created["account_id"]


# --- Team and role consistency --------------------------------------------------------------------


async def test_team_change_moves_team_level_role_with_member(
    db_client: AsyncClient, db_session: AsyncSession, structure: Structure, admin_csrf: str
) -> None:
    member = (await _create(db_client, admin_csrf, structure, role_key="team_leader")).json()[
        "member"
    ]

    response = await _post(
        db_client, admin_csrf, f"{MEMBERS}/{member['id']}/team", {"team_id": str(structure.team_b1)}
    )

    assert response.status_code == 200
    assert response.json()["team_id"] == str(structure.team_b1)
    assert response.json()["role_key"] == "team_leader"
    assert response.json()["role_unit_id"] == str(structure.team_b1)
    placements, roles = await _open_rows(db_session, member["id"])
    assert [(p.team_id, p.valid_to is None) for p in placements] == [
        (structure.team_a1, False),
        (structure.team_b1, True),
    ]
    assert [(r.unit_id, r.valid_to is None) for r in roles] == [
        (structure.team_a1, False),
        (structure.team_b1, True),
    ]


async def test_team_change_keeps_non_team_role_scope(
    db_client: AsyncClient, db_session: AsyncSession, structure: Structure, admin_csrf: str
) -> None:
    member = (
        await _create(
            db_client,
            admin_csrf,
            structure,
            role_key="administration_manager",
            administration_id=str(structure.admin_a),
        )
    ).json()["member"]

    response = await _post(
        db_client, admin_csrf, f"{MEMBERS}/{member['id']}/team", {"team_id": str(structure.team_b1)}
    )

    assert response.json()["role_unit_id"] == str(structure.admin_a)
    _, roles = await _open_rows(db_session, member["id"])
    assert len(roles) == 1


async def test_role_change_to_team_role_uses_current_team(
    db_client: AsyncClient, structure: Structure, admin_csrf: str
) -> None:
    member = (await _create(db_client, admin_csrf, structure, role_key="pmo_member")).json()[
        "member"
    ]
    url = f"{MEMBERS}/{member['id']}/role"

    changed = await _post(db_client, admin_csrf, url, {"role_key": "team_leader"})
    assert changed.json()["role_unit_id"] == str(structure.team_a1)

    # A Team-level role can never point at a different Team or an Administration.
    wrong = await _post(
        db_client,
        admin_csrf,
        url,
        {"role_key": "team_leader", "administration_id": str(structure.admin_b)},
    )
    assert wrong.status_code == 422
    same = await _post(db_client, admin_csrf, url, {"role_key": "team_leader"})
    assert same.status_code == 422


async def test_one_open_placement_and_role_are_enforced_by_the_database(
    db_session: AsyncSession, structure: Structure
) -> None:
    member, account = await make_member(db_session, "solo", team_id=structure.team_a1)
    db_session.add(
        RoleAssignment(
            member_id=member.id,
            role_key=RoleKey.MEMBER,
            unit_id=structure.team_a2,
            valid_from=member.created_at,
            created_by_account_id=account.id,
        )
    )
    with pytest.raises(Exception, match="uq_role_assignments_open"):
        await db_session.flush()


# --- Deactivation and reactivation ----------------------------------------------------------------


async def test_deactivation_ends_placement_role_account_and_sessions(
    client_factory: ClientFactory,
    db_client: AsyncClient,
    db_session: AsyncSession,
    structure: Structure,
    admin_csrf: str,
) -> None:
    member, account = await make_member(db_session, "leaving", team_id=structure.team_a1)
    their_client = client_factory()
    await signed_in(their_client, "leaving")

    response = await _post(db_client, admin_csrf, f"{MEMBERS}/{member.id}/deactivate")

    assert response.status_code == 200
    assert response.json()["status"] == "deactivated"
    assert response.json()["team_id"] is None
    assert response.json()["role_key"] is None
    placements, roles = await _open_rows(db_session, str(member.id))
    assert [p.valid_to is not None for p in placements] == [True]  # history kept, closed
    assert [r.valid_to is not None for r in roles] == [True]
    await db_session.refresh(account)
    assert account.status == AccountStatus.DEACTIVATED
    assert (await their_client.get(ME)).status_code == 401
    reasons = (
        await db_session.scalars(
            select(AuthSession.revoke_reason).where(AuthSession.account_id == account.id)
        )
    ).all()
    assert reasons == [SessionRevokeReason.ACCOUNT_DEACTIVATED]
    again = await _post(db_client, admin_csrf, f"{MEMBERS}/{member.id}/deactivate")
    assert again.status_code == 409


async def test_final_system_admin_member_cannot_be_deactivated(
    db_client: AsyncClient, db_session: AsyncSession, structure: Structure
) -> None:
    member, account = await make_member(
        db_session, "onlyadmin", team_id=structure.team_a1, system_admin=True
    )
    csrf = await signed_in(db_client, "onlyadmin")

    response = await _post(db_client, csrf, f"{MEMBERS}/{member.id}/deactivate")

    assert response.status_code == 409
    placements, roles = await _open_rows(db_session, str(member.id))
    assert placements[-1].valid_to is None
    assert roles[-1].valid_to is None
    await db_session.refresh(account)
    assert account.status == AccountStatus.ACTIVE


async def test_reactivation_requires_new_placement_and_role(
    client_factory: ClientFactory,
    db_client: AsyncClient,
    db_session: AsyncSession,
    structure: Structure,
    admin_csrf: str,
) -> None:
    member, _ = await make_member(db_session, "returning", team_id=structure.team_a1)
    await _post(db_client, admin_csrf, f"{MEMBERS}/{member.id}/deactivate")
    url = f"{MEMBERS}/{member.id}/reactivate"

    assert (await _post(db_client, admin_csrf, url, {})).status_code == 422
    assert (await _post(db_client, admin_csrf, url, {"role_key": "member"})).status_code == 422

    response = await _post(
        db_client,
        admin_csrf,
        url,
        {"team_id": str(structure.team_b1), "role_key": "team_leader"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "active"
    assert response.json()["team_id"] == str(structure.team_b1)
    assert response.json()["role_unit_id"] == str(structure.team_b1)
    placements, roles = await _open_rows(db_session, str(member.id))
    assert len(placements) == 2 and len(roles) == 2
    assert await signed_in(client_factory(), "returning")
    assert (
        await _post(
            db_client, admin_csrf, url, {"team_id": str(structure.team_b1), "role_key": "member"}
        )
    ).status_code == 409


async def test_deactivated_member_cannot_change_team_or_role(
    db_client: AsyncClient, db_session: AsyncSession, structure: Structure, admin_csrf: str
) -> None:
    member, _ = await make_member(db_session, "gone", team_id=structure.team_a1)
    await _post(db_client, admin_csrf, f"{MEMBERS}/{member.id}/deactivate")

    team = await _post(
        db_client, admin_csrf, f"{MEMBERS}/{member.id}/team", {"team_id": str(structure.team_b1)}
    )
    role = await _post(db_client, admin_csrf, f"{MEMBERS}/{member.id}/role", {"role_key": "member"})

    assert team.status_code == role.status_code == 409


async def test_password_reset_issues_temporary_password_and_ends_sessions(
    client_factory: ClientFactory,
    db_client: AsyncClient,
    db_session: AsyncSession,
    structure: Structure,
    admin_csrf: str,
) -> None:
    member, _ = await make_member(db_session, "forgetful", team_id=structure.team_a1)
    their_client = client_factory()
    await signed_in(their_client, "forgetful")

    response = await _post(db_client, admin_csrf, f"{MEMBERS}/{member.id}/reset-password")

    assert response.status_code == 200
    assert (await their_client.get(ME)).status_code == 401
    fresh = await sign_in(client_factory(), "forgetful", response.json()["temporary_password"])
    assert fresh.json()["account"]["must_change_password"] is True


# --- System Admin only ----------------------------------------------------------------------------


async def test_member_routes_require_system_admin(
    db_client: AsyncClient, db_session: AsyncSession, structure: Structure
) -> None:
    await make_member(
        db_session,
        "leader",
        team_id=structure.team_a1,
        role=RoleKey.EVENT_PROJECT_LEADER,
        role_unit_id=KORA_UNIT_ID,
    )
    csrf = await signed_in(db_client, "leader")

    assert (await db_client.get(MEMBERS)).status_code == 403
    assert (await _create(db_client, csrf, structure, username="other")).status_code == 403


async def test_member_listing_shows_current_team_and_role(
    db_client: AsyncClient, db_session: AsyncSession, structure: Structure, admin_csrf: str
) -> None:
    await make_member(
        db_session,
        "pmo",
        team_id=structure.team_a2,
        role=RoleKey.PMO_LEADER,
        role_unit_id=PMO_UNIT_ID,
    )

    listed = (await db_client.get(MEMBERS)).json()

    assert [(m["username"], m["team_id"], m["role_key"]) for m in listed] == [
        ("pmo", str(structure.team_a2), "pmo_leader")
    ]
