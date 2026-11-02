"""`/me/summary`: the badge counts match their sources."""

import pytest

from tests.tasks.conftest import Login, World

pytestmark = pytest.mark.anyio

SUMMARY = "/api/v1/me/summary"
ZEROS = {
    "notifications_unread": 0,
    "chat_unread": 0,
    "requests_pending": 0,
    "announcements_unread": 0,
    "reviews_open": 0,
}


async def test_counts_follow_their_sources(world: World, login: Login) -> None:
    ann, bob, lead = await login("m_a1"), await login("m_a1b"), await login("tl_a1")
    assert (await bob.get(SUMMARY)).json() == ZEROS

    # Chat: two unread messages for Bob, none for the sender.
    chat = (
        await ann.post(
            "/api/v1/chat/conversations/direct", {"member_id": str(world.member_ids["m_a1b"])}
        )
    ).json()
    for text in ("one", "two"):
        await ann.post(f"/api/v1/chat/conversations/{chat['id']}/messages", {"body": text})
    summary = (await bob.get(SUMMARY)).json()
    assert summary["chat_unread"] == 2
    assert summary["notifications_unread"] == 1  # one notification per chat until read
    assert (await ann.get(SUMMARY)).json()["chat_unread"] == 0
    await bob.post(f"/api/v1/chat/conversations/{chat['id']}/read", {})
    assert (await bob.get(SUMMARY)).json()["chat_unread"] == 0

    # A finished part opens a review task for the leaders: counted until it is closed.
    task = (
        await lead.post(
            "/api/v1/tasks",
            {
                "title": "Prepare",
                "scope_unit_id": str(world.unit("team_a1")),
                "assignee_member_ids": [str(world.member_ids["m_a1b"])],
            },
        )
    ).json()
    await bob.put(f"/api/v1/tasks/{task['id']}/progress", {"finished": True})
    assert (await lead.get(SUMMARY)).json()["reviews_open"] == 1
    assert (await bob.get(SUMMARY)).json()["reviews_open"] == 0
    await lead.post(f"/api/v1/tasks/{task['id']}/status", {"status": "completed"})
    assert (await lead.get(SUMMARY)).json()["reviews_open"] == 0


async def test_requests_pending_counts_only_for_those_who_can_answer(
    world: World, login: Login
) -> None:
    mgr_a = await login("mgr_a")
    sent = await mgr_a.post(
        "/api/v1/task-requests",
        {
            "title": "Banner",
            "from_unit_id": str(world.unit("admin_a")),
            "to_unit_id": str(world.unit("admin_b")),
        },
    )
    assert sent.status_code == 201
    assert (await (await login("leader")).get(SUMMARY)).json()["requests_pending"] == 1
    for user in ("mgr_a", "tl_a1", "m_b1"):
        assert (await (await login(user)).get(SUMMARY)).json()["requests_pending"] == 0, user


async def test_an_account_without_a_member_gets_zeros(world: World, login: Login) -> None:
    assert (await (await login("sysadmin")).get(SUMMARY)).json() == ZEROS
    assert (await (await login("outsider")).get(SUMMARY)).json() == ZEROS
