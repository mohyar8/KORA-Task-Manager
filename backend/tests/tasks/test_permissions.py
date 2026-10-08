"""Task permission defaults, overrides, visibility, System Admin, CSRF and password gates."""

from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from kora_api.access.permissions import OverrideEffect, Permission
from tests.access.helpers import create_account, signed_in
from tests.conftest import ClientFactory
from tests.organization.helpers import add_override
from tests.tasks.conftest import TASKS, Login, World

pytestmark = pytest.mark.anyio

NewTask = Callable[..., Awaitable[dict[str, Any]]]


def _body(world: World, scope: str, assignees: list[str]) -> dict[str, Any]:
    return {
        "title": "T",
        "scope_unit_id": str(world.unit(scope)),
        "assignee_member_ids": [str(world.member_ids[a]) for a in assignees],
    }


# --- Defaults -------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("user", "allowed", "denied"),
    [
        ("leader", ["kora", "admin_b", "team_b1", "pmo"], []),
        ("mgr_a", ["admin_a", "team_a2"], ["kora", "admin_b", "pmo"]),
        ("pmo_lead", ["pmo"], ["kora", "team_a2"]),
        ("pmo_m", ["pmo"], ["kora", "team_a2"]),
        ("tl_a1", ["team_a1"], ["admin_a", "team_a2"]),
        ("m_a1", ["team_a1"], ["admin_a", "team_a2", "kora"]),
    ],
)
async def test_every_role_creates_within_its_assigned_scope(
    world: World, login: Login, user: str, allowed: list[str], denied: list[str]
) -> None:
    api = await login(user)
    for scope in allowed:
        assignee = (
            "pmo_m"
            if scope == "pmo"
            else {"team_a2": "m_a2", "team_b1": "m_b1", "admin_b": "m_b1"}.get(scope, "m_a1")
        )
        response = await api.post(TASKS, _body(world, scope, [assignee]))
        assert response.status_code == 201, (user, scope, response.text)
    for scope in denied:
        response = await api.post(TASKS, _body(world, scope, ["m_a1"]))
        assert response.status_code == 403, (user, scope)


@pytest.mark.parametrize(
    ("user", "scope", "assignee", "can_manage"),
    [
        ("leader", "team_b1", "m_b1", True),
        ("mgr_a", "team_a2", "m_a2", True),
        ("mgr_a", "team_b1", "m_b1", False),
        ("pmo_lead", "pmo", "pmo_m", True),
        ("tl_a1", "team_a1", "m_a1", True),
        ("tl_a1", "team_a2", "m_a2", False),
        ("pmo_m", "pmo", "pmo_m", False),
        ("m_a1b", "team_a1", "m_a1", False),
    ],
)
async def test_task_manage_defaults(
    world: World,
    login: Login,
    new_task: NewTask,
    user: str,
    scope: str,
    assignee: str,
    can_manage: bool,
) -> None:
    owner = "leader"
    task = await new_task(await login(owner), scope, [assignee])
    api = await login(user)

    response = await api.patch(f"{TASKS}/{task['id']}", {"title": "Renamed"})

    assert response.status_code == (200 if can_manage else 403)


async def test_visibility_follows_task_view_scope(
    world: World, login: Login, new_task: NewTask
) -> None:
    leader = await login("leader")
    in_a1 = await new_task(leader, "team_a1", ["m_a1"], title="A1 task")
    in_a2 = await new_task(leader, "team_a2", ["m_a2"], title="A2 task")
    in_kora = await new_task(leader, "kora", ["m_b1"], title="KORA task")

    viewer = await login("m_a1b")  # Member: task.view at Team A1 only, not a participant
    listed = {t["title"] for t in (await viewer.get(TASKS)).json()}

    assert listed == {"A1 task"}
    assert (await viewer.get(f"{TASKS}/{in_a1['id']}")).status_code == 200
    assert (await viewer.get(f"{TASKS}/{in_a2['id']}")).json() == {"detail": "Not permitted."}
    assert (await viewer.get(f"{TASKS}/{in_kora['id']}")).status_code == 403
    all_titles = {t["title"] for t in (await leader.get(TASKS)).json()}
    assert all_titles == {"A1 task", "A2 task", "KORA task"}


async def test_participants_see_their_tasks_outside_their_view_scope(
    world: World, login: Login, new_task: NewTask, db_session: AsyncSession
) -> None:
    leader = await login("leader")
    task = await new_task(leader, "admin_a", ["m_a1"])  # m_a1 views Team A1 only
    assignee = await login("m_a1")

    assert (await assignee.get(f"{TASKS}/{task['id']}")).status_code == 200
    assert [t["id"] for t in (await assignee.get(TASKS)).json()] == [task["id"]]

    # An explicit deny on task.view still wins.
    await add_override(
        db_session,
        world.account_ids["m_a1"],
        world.structure.admin_a,
        OverrideEffect.DENY,
        Permission.TASK_VIEW,
    )
    assert (await assignee.get(f"{TASKS}/{task['id']}")).status_code == 403
    assert (await assignee.get(TASKS)).json() == []


async def test_overrides_grant_and_deny_task_permissions(
    world: World, login: Login, new_task: NewTask, db_session: AsyncSession
) -> None:
    task = await new_task(await login("leader"), "team_a1", ["m_a1"])
    accounts = world.account_ids

    # Grant: a Member manages a task outside their defaults.
    await add_override(
        db_session, accounts["m_a2"], world.structure.team_a1, permission=Permission.TASK_MANAGE
    )
    m_a2 = await login("m_a2")
    assert (await m_a2.patch(f"{TASKS}/{task['id']}", {"priority": "high"})).status_code == 200

    # Deny: the Team Leader loses manage and create in their own Team.
    for permission in (Permission.TASK_MANAGE, Permission.TASK_CREATE):
        await add_override(
            db_session, accounts["tl_a1"], world.structure.team_a1, OverrideEffect.DENY, permission
        )
    tl = await login("tl_a1")
    assert (await tl.patch(f"{TASKS}/{task['id']}", {"priority": "low"})).status_code == 403
    assert (await tl.post(TASKS, _body(world, "team_a1", ["m_a1"]))).status_code == 403


# --- System Admin and non-Members -----------------------------------------------------------------


async def test_system_admin_has_no_implicit_task_access(
    world: World, login: Login, new_task: NewTask
) -> None:
    task = await new_task(await login("leader"), "kora", ["m_a1"])
    admin = await login("sysadmin")

    assert (await admin.get(TASKS)).json() == []
    assert (await admin.get(f"{TASKS}/{task['id']}")).status_code == 403
    assert (await admin.patch(f"{TASKS}/{task['id']}", {"title": "x"})).status_code == 403
    assert (await admin.post(TASKS, _body(world, "kora", ["m_a1"]))).status_code == 403


async def test_only_active_members_create_but_non_members_can_manage_by_override(
    world: World, login: Login, new_task: NewTask, db_session: AsyncSession
) -> None:
    task = await new_task(await login("leader"), "team_b1", ["m_b1"])
    outsider = world.account_ids["outsider"]
    for permission in Permission:
        await add_override(db_session, outsider, world.unit("kora"), permission=permission)
    api = await login("outsider")

    assert (await api.post(TASKS, _body(world, "kora", ["m_a1"]))).status_code == 403
    assert (await api.get(f"{TASKS}/{task['id']}")).status_code == 200
    assert (await api.patch(f"{TASKS}/{task['id']}", {"title": "Managed"})).status_code == 200
    assert (await api.post(f"{TASKS}/{task['id']}/comments", {"body": "ok"})).status_code == 201


# --- Gates ----------------------------------------------------------------------------------------


async def test_task_routes_enforce_csrf_and_temporary_password_gate(
    world: World, client_factory: ClientFactory, db_session: AsyncSession
) -> None:
    client = client_factory()
    await signed_in(client, "leader")
    no_csrf = await client.post(TASKS, json=_body(world, "kora", ["m_a1"]))
    assert no_csrf.json() == {"detail": "CSRF token missing or invalid."}

    await create_account(db_session, "fresh", temporary=True)
    gated = client_factory()
    await signed_in(gated, "fresh")
    assert (await gated.get(TASKS)).json() == {"detail": "Password change required."}
