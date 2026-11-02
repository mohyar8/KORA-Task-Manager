"""Chat: private direct chats, derived unit channels, cursors, unread counts, moderation."""

import uuid
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kora_api.audit.models import AuditRecord
from tests.tasks.conftest import Api, Login, World

pytestmark = pytest.mark.anyio

CHAT = "/api/v1/chat"
NOTIFICATIONS = "/api/v1/notifications"
SECRET = "a very private sentence"


async def _direct(api: Api, world: World, other: str) -> dict[str, Any]:
    response = await api.post(
        f"{CHAT}/conversations/direct", {"member_id": str(world.member_ids[other])}
    )
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


async def _say(api: Api, conversation: str, text: str = "hi") -> dict[str, Any]:
    response = await api.post(f"{CHAT}/conversations/{conversation}/messages", {"body": text})
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


async def _team_channel(api: Api, world: World) -> dict[str, Any]:
    rows = (await api.get(f"{CHAT}/conversations")).json()
    return next(c for c in rows if c["unit_id"] == str(world.unit("team_a1")))


async def _mine(api: Api, chat_id: str) -> dict[str, Any]:
    rows = (await api.get(f"{CHAT}/conversations")).json()
    return next(c for c in rows if c["id"] == chat_id)


async def _channels(api: Api) -> list[tuple[str, str | None]]:
    rows = (await api.get(f"{CHAT}/conversations")).json()
    return sorted((r["kind"], r["unit_id"]) for r in rows if r["kind"] != "direct")


async def test_channels_follow_the_organization(world: World, login: Login) -> None:
    s = world.structure
    org = ("organization", None)
    kinds = {c for c in await _channels(await login("m_a1"))}
    assert kinds == {org, ("unit", str(s.team_a1)), ("unit", str(s.admin_a))}
    assert {c for c in await _channels(await login("m_b1"))} == {
        org,
        ("unit", str(s.team_b1)),
        ("unit", str(s.admin_b)),
    }
    # A PMO Member (placed in Team A2) also has the PMO channel.
    pmo = {c for c in await _channels(await login("pmo_m"))}
    assert ("unit", str(world.unit("pmo"))) in pmo
    # An account that is not an active Member does not chat.
    assert (await (await login("sysadmin")).get(f"{CHAT}/conversations")).status_code == 403


async def test_direct_chat_is_private_and_unread_counts_work(world: World, login: Login) -> None:
    ann, bob = await login("m_a1"), await login("m_a1b")
    chat = await _direct(ann, world, "m_a1b")
    assert (await _direct(bob, world, "m_a1"))["id"] == chat["id"]  # same chat from both sides
    assert chat["other_member_id"] == str(world.member_ids["m_a1b"])
    assert (
        await ann.post(f"{CHAT}/conversations/direct", {"member_id": str(world.member_ids["m_a1"])})
    ).status_code == 422

    first = await _say(ann, chat["id"], SECRET)
    await _say(ann, chat["id"], "two")
    await _say(ann, chat["id"], "three")
    mine = await _mine(ann, chat["id"])
    assert mine["unread"] == 0  # your own messages are not unread
    theirs = await _mine(bob, chat["id"])
    assert theirs["unread"] == 3
    assert theirs["last_message"]["body"] == "three"

    # Cursors: oldest first; `after` for polling, `before` for history.
    url = f"{CHAT}/conversations/{chat['id']}/messages"
    assert [m["body"] for m in (await bob.get(url)).json()] == [SECRET, "two", "three"]
    assert [m["body"] for m in (await bob.get(url, after=first["id"])).json()] == ["two", "three"]
    assert [m["body"] for m in (await bob.get(url, limit=2)).json()] == ["two", "three"]
    older = await bob.get(url, before=first["id"] + 2)
    assert [m["body"] for m in older.json()] == [SECRET, "two"]

    assert (await bob.post(f"{CHAT}/conversations/{chat['id']}/read", {})).status_code == 204
    after = await _mine(bob, chat["id"])
    assert after["unread"] == 0

    # Nobody else can read it or write in it, not even a System Admin or the leaders; it looks
    # like it does not exist.
    for user in ("tl_a1", "leader", "m_b1"):
        other = await login(user)
        assert (await other.get(url)).status_code == 404, user
        assert (await other.post(url, {"body": "hi"})).status_code == 404, user
        assert chat["id"] not in [
            c["id"] for c in (await other.get(f"{CHAT}/conversations")).json()
        ]
    assert (await bob.get(f"{CHAT}/conversations/{uuid.uuid4()}/messages")).status_code == 404


async def test_a_direct_chat_notifies_once_until_read_and_never_shows_the_text(
    world: World, login: Login, db_session: AsyncSession
) -> None:
    ann, bob = await login("m_a1"), await login("m_a1b")
    chat = await _direct(ann, world, "m_a1b")
    await _say(ann, chat["id"], SECRET)
    await _say(ann, chat["id"], "again")
    notes = (await bob.get(NOTIFICATIONS)).json()
    chat_notes = [n for n in notes if n["category"] == "chat_message"]
    assert len(chat_notes) == 1
    assert SECRET not in str(notes)
    await bob.post(f"{NOTIFICATIONS}/{chat_notes[0]['id']}/read", None)
    await _say(ann, chat["id"], "after the read")
    count = len(
        [n for n in (await bob.get(NOTIFICATIONS)).json() if n["category"] == "chat_message"]
    )
    assert count == 2
    # Unit channels never notify; nothing about chat text is audited.
    team = await _team_channel(ann, world)
    await _say(ann, team["id"], "team news")
    assert (
        len([n for n in (await bob.get(NOTIFICATIONS)).json() if n["category"] == "chat_message"])
        == 2
    )
    records = (await db_session.scalars(select(AuditRecord))).all()
    assert all(SECRET not in f"{r.before}{r.after}" for r in records)


async def test_unit_channels_belong_to_the_unit_and_leaders_moderate(
    world: World, login: Login, db_session: AsyncSession
) -> None:
    ann, bob, lead = await login("m_a1"), await login("m_a1b"), await login("tl_a1")
    team = await _team_channel(ann, world)
    message = await _say(ann, team["id"], SECRET)
    url = f"{CHAT}/conversations/{team['id']}/messages"
    # Teammates and the Team Leader read it; another Team's Member does not.
    assert (await bob.get(url)).status_code == 200
    assert (await lead.get(url)).status_code == 200
    assert (await (await login("m_b1")).get(url)).status_code == 404
    # Only the author edits.
    assert (await bob.patch(f"{CHAT}/messages/{message['id']}", {"body": "x"})).status_code == 403
    edited = await ann.patch(f"{CHAT}/messages/{message['id']}", {"body": "fixed"})
    assert edited.json()["body"] == "fixed"
    assert edited.json()["edited_at"] is not None
    # A teammate cannot delete it; the Team Leader can, which blanks it and is audited by ids.
    assert (await bob.delete(f"{CHAT}/messages/{message['id']}")).status_code == 403
    gone = await lead.delete(f"{CHAT}/messages/{message['id']}")
    assert gone.status_code == 200
    assert gone.json()["deleted"] is True
    assert gone.json()["body"] == ""
    assert (await ann.patch(f"{CHAT}/messages/{message['id']}", {"body": "y"})).status_code == 409
    rows = (await bob.get(url)).json()
    assert [(m["id"], m["deleted"], m["body"]) for m in rows] == [(message["id"], True, "")]
    records = [
        r
        for r in (await db_session.scalars(select(AuditRecord))).all()
        if r.action == "message.moderated_deleted"
    ]
    assert len(records) == 1
    assert "fixed" not in f"{records[0].after}"
    # The author may delete their own message without moderation rights.
    mine = await _say(bob, team["id"], "mine")
    assert (await bob.delete(f"{CHAT}/messages/{mine['id']}")).status_code == 200
    # Direct chats have no moderators: the other person cannot delete.
    chat = await _direct(ann, world, "m_a1b")
    private = await _say(ann, chat["id"], "p")
    assert (await bob.delete(f"{CHAT}/messages/{private['id']}")).status_code == 403
    assert (await lead.delete(f"{CHAT}/messages/{private['id']}")).status_code == 404


async def test_messages_are_rate_limited(world: World, login: Login) -> None:
    ann = await login("m_a1")
    chat = await _direct(ann, world, "m_a1b")
    for _ in range(30):
        await _say(ann, chat["id"])
    too_many = await ann.post(f"{CHAT}/conversations/{chat['id']}/messages", {"body": "31"})
    assert too_many.status_code == 429
    assert (
        await ann.post(f"{CHAT}/conversations/{chat['id']}/messages", {"body": " "})
    ).status_code == 422
