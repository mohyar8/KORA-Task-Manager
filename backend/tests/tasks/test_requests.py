"""Task requests between Administrations: send, answer, withdraw, and the task an accepted
request becomes (readable and commentable by the sender, never administered by them)."""

import uuid
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kora_api.audit.models import AuditRecord
from kora_api.organization.constants import RoleKey
from tests.organization.helpers import make_member
from tests.tasks.conftest import TASKS, Api, Login, World

pytestmark = pytest.mark.anyio

REQUESTS = "/api/v1/task-requests"
NOTIFICATIONS = "/api/v1/notifications"
REASON = "we are fully booked this month"


@pytest.fixture(autouse=True)
async def manager_of_b(world: World, db_session: AsyncSession) -> None:
    """Administration B needs a manager to answer for it."""
    member, account = await make_member(
        db_session,
        "mgr_b",
        team_id=world.structure.team_b1,
        role=RoleKey.ADMINISTRATION_MANAGER,
        role_unit_id=world.structure.admin_b,
    )
    world.member_ids["mgr_b"] = member.id
    world.account_ids["mgr_b"] = account.id


async def _send(world: World, api: Api, **fields: Any) -> dict[str, Any]:
    response = await api.post(
        REQUESTS,
        {
            "title": "Need a banner",
            "from_unit_id": str(world.unit("admin_a")),
            "to_unit_id": str(world.unit("admin_b")),
            **fields,
        },
    )
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


async def test_the_administration_manager_sends_and_the_target_manager_is_told(
    world: World, login: Login
) -> None:
    mgr_a, mgr_b = await login("mgr_a"), await login("mgr_b")
    request = await _send(world, mgr_a, priority="high")
    assert request["status"] == "pending"
    assert request["requested_by_member_id"] == str(world.member_ids["mgr_a"])

    notes = (await mgr_b.get(NOTIFICATIONS)).json()
    assert [(n["category"], n["kind"]) for n in notes] == [("task_request", "received")]
    # The sender is not told about their own request.
    assert (await mgr_a.get(NOTIFICATIONS)).json() == []

    assert [r["id"] for r in (await mgr_b.get(REQUESTS, box="incoming")).json()] == [request["id"]]
    assert [r["id"] for r in (await mgr_a.get(REQUESTS, box="outgoing")).json()] == [request["id"]]
    assert (await mgr_a.get(REQUESTS, box="incoming")).json() == []
    assert (await mgr_b.get(REQUESTS, box="outgoing")).json() == []


async def test_who_may_send_and_where(world: World, login: Login) -> None:
    body = {
        "title": "x",
        "from_unit_id": str(world.unit("admin_a")),
        "to_unit_id": str(world.unit("admin_b")),
    }
    for user in ("tl_a1", "m_a1", "pmo_lead", "m_b1"):
        assert (await (await login(user)).post(REQUESTS, body)).status_code == 403, user
    mgr_a = await login("mgr_a")
    # Not for another Administration, and not as KORA.
    other = {
        **body,
        "from_unit_id": str(world.unit("admin_b")),
        "to_unit_id": str(world.unit("admin_a")),
    }
    assert (await mgr_a.post(REQUESTS, other)).status_code == 403
    assert (
        await mgr_a.post(REQUESTS, {**body, "from_unit_id": str(world.unit("kora"))})
    ).status_code == 403
    # Only Administrations can receive, and not the sender itself.
    for target in ("team_b1", "pmo", "kora", "admin_a"):
        bad = {**body, "to_unit_id": str(world.unit(target))}
        assert (await mgr_a.post(REQUESTS, bad)).status_code == 422, target
    assert (
        await mgr_a.post(REQUESTS, {**body, "from_unit_id": str(world.unit("team_a1"))})
    ).status_code == 422
    assert (
        await mgr_a.post(REQUESTS, {**body, "to_unit_id": str(uuid.uuid4())})
    ).status_code == 422
    assert (await mgr_a.post(REQUESTS, {**body, "title": "  "})).status_code == 422
    # The leadership may ask from KORA.
    leader = await login("leader")
    assert (
        await leader.post(REQUESTS, {**body, "from_unit_id": str(world.unit("kora"))})
    ).status_code == 201


async def test_accepting_creates_a_real_task_the_sender_can_read_and_comment_on(
    world: World, login: Login
) -> None:
    mgr_a, mgr_b = await login("mgr_a"), await login("mgr_b")
    request = await _send(world, mgr_a, description="Two metres wide")
    url = f"{REQUESTS}/{request['id']}"

    accepted = await mgr_b.post(
        f"{url}/accept", {"assignee_member_ids": [str(world.member_ids["m_b1"])]}
    )
    assert accepted.status_code == 200, accepted.text
    body = accepted.json()
    assert body["status"] == "accepted"
    assert body["decided_by_member_id"] == str(world.member_ids["mgr_b"])

    task = (await mgr_b.get(f"{TASKS}/{body['resulting_task_id']}")).json()
    assert task["title"] == "Need a banner"
    assert task["description"] == "Two metres wide"
    assert task["scope_unit_id"] == str(world.unit("admin_b"))
    assert task["created_by_member_id"] == str(world.member_ids["mgr_b"])
    assert task["assignee_member_ids"] == [str(world.member_ids["m_b1"])]
    assert task["from_outside"] is True
    assert task["requested_by_member_id"] == str(world.member_ids["mgr_a"])
    assert task["requested_from_unit_id"] == str(world.unit("admin_a"))

    # The sender (outside Administration B) reads and comments, and does nothing else.
    task_url = f"{TASKS}/{task['id']}"
    assert (await mgr_a.get(task_url)).status_code == 200
    assert task["id"] in [t["id"] for t in (await mgr_a.get(TASKS)).json()]
    assert (await mgr_a.post(f"{task_url}/comments", {"body": "thanks"})).status_code == 201
    assert (await mgr_a.patch(task_url, {"title": "mine now"})).status_code == 403
    assert (await mgr_a.post(f"{task_url}/status", {"status": "cancelled"})).status_code == 403
    assert (await mgr_a.post(f"{task_url}/status", {"status": "in_progress"})).status_code == 403
    add = await mgr_a.post(f"{task_url}/assignees", {"member_id": str(world.member_ids["m_b1"])})
    assert add.status_code == 403
    # Other people outside Administration B still cannot see it.
    assert (await (await login("m_a2")).get(task_url)).status_code == 403

    notes = (await mgr_a.get(NOTIFICATIONS)).json()
    assert ("task_request", "accepted") in [(n["category"], n["kind"]) for n in notes]
    member_notes = (await (await login("m_b1")).get(NOTIFICATIONS)).json()
    assert "task_assignment" in [n["category"] for n in member_notes]


async def test_accepting_needs_eligible_assignees_and_the_right_to_answer(
    world: World, login: Login
) -> None:
    mgr_a, mgr_b = await login("mgr_a"), await login("mgr_b")
    request = await _send(world, mgr_a)
    url = f"{REQUESTS}/{request['id']}/accept"
    ids = world.member_ids
    # Outside Administration B, or a top role, or nobody.
    for chosen in (["m_a1"], ["leader"], []):
        body = {"assignee_member_ids": [str(ids[n]) for n in chosen]}
        assert (await mgr_b.post(url, body)).status_code == 422, chosen
    ok = {"assignee_member_ids": [str(ids["m_b1"])]}
    # The sender cannot answer their own request, nor can an unrelated Member.
    assert (await mgr_a.post(url, ok)).status_code == 403
    assert (await (await login("m_b1")).post(url, ok)).status_code == 403
    assert (await (await login("m_a2")).post(url, ok)).status_code == 403
    # Unknown request.
    assert (await mgr_b.post(f"{REQUESTS}/{uuid.uuid4()}/accept", ok)).status_code == 404
    # The Event Leader holds the permission over every Administration.
    assert (await (await login("leader")).post(url, ok)).status_code == 200


async def test_only_the_first_answer_counts(world: World, login: Login) -> None:
    mgr_a, mgr_b = await login("mgr_a"), await login("mgr_b")
    request = await _send(world, mgr_a)
    url = f"{REQUESTS}/{request['id']}"
    ok = {"assignee_member_ids": [str(world.member_ids["m_b1"])]}
    assert (await mgr_b.post(f"{url}/accept", ok)).status_code == 200
    assert (await mgr_b.post(f"{url}/accept", ok)).status_code == 409
    assert (await mgr_b.post(f"{url}/reject", {"reason": REASON})).status_code == 409
    assert (await mgr_a.post(f"{url}/withdraw")).status_code == 409
    tasks = [t for t in (await mgr_b.get(TASKS)).json() if t["title"] == "Need a banner"]
    assert len(tasks) == 1  # one task, however many answers were tried


async def test_rejecting_needs_a_reason_and_tells_the_sender(
    world: World, login: Login, db_session: AsyncSession
) -> None:
    mgr_a, mgr_b = await login("mgr_a"), await login("mgr_b")
    request = await _send(world, mgr_a)
    url = f"{REQUESTS}/{request['id']}"
    assert (await mgr_b.post(f"{url}/reject", {"reason": " "})).status_code == 422
    assert (await mgr_a.post(f"{url}/reject", {"reason": REASON})).status_code == 403
    rejected = await mgr_b.post(f"{url}/reject", {"reason": REASON})
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    assert rejected.json()["rejection_reason"] == REASON
    assert rejected.json()["resulting_task_id"] is None
    assert (await mgr_a.get(url)).json()["rejection_reason"] == REASON
    notes = (await mgr_a.get(NOTIFICATIONS)).json()
    assert ("task_request", "rejected") in [(n["category"], n["kind"]) for n in notes]
    assert REASON not in str(notes)  # the reason is not in the notification
    # Nor in the audit trail.
    records = (await db_session.scalars(select(AuditRecord))).all()
    assert any(r.action == "task_request.rejected" for r in records)
    assert all(REASON not in f"{r.before}{r.after}" for r in records)


async def test_the_sender_can_withdraw_while_pending(world: World, login: Login) -> None:
    mgr_a, mgr_b = await login("mgr_a"), await login("mgr_b")
    request = await _send(world, mgr_a)
    url = f"{REQUESTS}/{request['id']}"
    assert (await mgr_b.post(f"{url}/withdraw")).status_code == 403  # only the sender
    assert (await (await login("tl_a1")).post(f"{url}/withdraw")).status_code == 403
    withdrawn = await mgr_a.post(f"{url}/withdraw")
    assert withdrawn.status_code == 200
    assert withdrawn.json()["status"] == "withdrawn"
    notes = (await mgr_b.get(NOTIFICATIONS)).json()
    assert ("task_request", "withdrawn") in [(n["category"], n["kind"]) for n in notes]
    ok = {"assignee_member_ids": [str(world.member_ids["m_b1"])]}
    assert (await mgr_b.post(f"{url}/accept", ok)).status_code == 409
    assert (await mgr_a.post(f"{url}/withdraw")).status_code == 409


async def test_requests_are_visible_only_to_the_parties(world: World, login: Login) -> None:
    mgr_a = await login("mgr_a")
    request = await _send(world, mgr_a)
    url = f"{REQUESTS}/{request['id']}"
    for user in ("tl_a1", "m_b1", "pmo_lead", "outsider"):
        assert (await (await login(user)).get(url)).status_code == 403, user
    for user in ("mgr_a", "mgr_b", "leader"):
        assert (await (await login(user)).get(url)).status_code == 200, user
    for user in ("tl_a1", "m_b1"):
        api = await login(user)
        assert (await api.get(REQUESTS, box="incoming")).json() == []
        assert (await api.get(REQUESTS, box="outgoing")).json() == []
    assert (await mgr_a.get(REQUESTS, box="outgoing", status="accepted")).json() == []
    assert (await mgr_a.get(REQUESTS, box="sideways")).status_code == 422


async def test_requests_are_audited_without_free_text(
    world: World, login: Login, db_session: AsyncSession
) -> None:
    mgr_a, mgr_b = await login("mgr_a"), await login("mgr_b")
    request = await _send(world, mgr_a, description="a private detail")
    ok = {"assignee_member_ids": [str(world.member_ids["m_b1"])]}
    await mgr_b.post(f"{REQUESTS}/{request['id']}/accept", ok)
    records = (await db_session.scalars(select(AuditRecord))).all()
    actions = [r.action for r in records]
    assert "task_request.created" in actions
    assert "task_request.accepted" in actions
    assert all("a private detail" not in f"{r.before}{r.after}" for r in records)
