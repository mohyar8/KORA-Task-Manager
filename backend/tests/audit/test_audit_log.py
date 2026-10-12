"""Audit log storage rules, privacy, atomicity and the System Admin-only read API."""

import logging
import uuid
from dataclasses import replace
from datetime import timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from kora_api.access.models import UserAccount
from kora_api.audit import service as audit
from kora_api.notifications.models import Notification
from kora_api.organization.models import OrgUnit
from kora_api.tasks.models import Task
from tests.access.helpers import (
    CHANGE_PASSWORD,
    PASSWORD,
    create_account,
    csrf_headers,
    sign_in,
    signed_in,
)
from tests.audit.conftest import AUDIT, audit_records
from tests.calendar.conftest import EVENTS, NewEvent
from tests.communication.conftest import ANNOUNCEMENTS, draft
from tests.conftest import ClientFactory, FrozenClock
from tests.organization.helpers import MEMBERS, UNITS, make_structure
from tests.route_tree import mounted_routes
from tests.tasks.conftest import TASKS, Login, World

pytestmark = pytest.mark.anyio

ALPHA = audit.action("test.alpha", "thing", "n", "title")
BETA = audit.action("test.beta", "widget", "n")


# --- Storage rules --------------------------------------------------------------------------------


async def test_audit_records_are_append_only(db_session: AsyncSession) -> None:
    account = await create_account(db_session, "someone")
    audit.record(
        db_session, ALPHA, actor_account_id=account.id, resource_id=uuid.uuid4(), after={"n": 1}
    )
    await db_session.commit()

    for statement in (
        "UPDATE audit_records SET action = 'test.changed'",
        "DELETE FROM audit_records",
        "TRUNCATE audit_records",
    ):
        with pytest.raises(DBAPIError, match="append-only"):
            async with db_session.begin_nested():
                await db_session.execute(text(statement))

    rows = (await db_session.execute(text("SELECT action FROM audit_records"))).scalars().all()
    assert list(rows) == ["test.alpha"]


async def test_metadata_outside_the_allowlist_is_refused(db_session: AsyncSession) -> None:
    for unsafe in ("password", "password_hash", "session_token", "comment_body", "email"):
        with pytest.raises(audit.UnsafeAuditMetadataError):
            audit.action("test.unsafe", "thing", unsafe)
    with pytest.raises(audit.UnsafeAuditMetadataError):
        audit.record(
            db_session,
            ALPHA,
            actor_account_id=None,
            resource_id=uuid.uuid4(),
            after={"description": "full text"},
        )
    with pytest.raises(audit.UnsafeAuditMetadataError):
        audit.record(
            db_session,
            ALPHA,
            actor_account_id=None,
            resource_id=uuid.uuid4(),
            after={"n": {"nested": "model"}},  # pyright: ignore[reportArgumentType]
        )

    audit.record(
        db_session,
        ALPHA,
        actor_account_id=None,
        resource_id=uuid.uuid4(),
        after={"title": "x" * 500},
    )
    await db_session.commit()
    (record,) = await audit_records(db_session, "test.alpha")
    assert record.after is not None and len(record.after["title"]) == audit.MAX_TEXT_LENGTH


# --- Atomicity ------------------------------------------------------------------------------------


async def test_audit_write_failure_rolls_back_the_change(
    world: World, login: Login, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    leader = await login("leader")
    original = audit.record

    def too_long(db: AsyncSession, audit_action: audit.AuditAction, **kwargs: Any) -> None:
        # The database rejects the record (column too long) when the transaction commits.
        original(db, replace(audit_action, resource_type="x" * 65), **kwargs)

    monkeypatch.setattr(audit, "record", too_long)

    with pytest.raises(DBAPIError):
        await leader.post(
            UNITS, {"kind": "team", "name": "Doomed", "parent_id": str(world.structure.admin_a)}
        )
    await db_session.rollback()

    assert await db_session.scalar(select(OrgUnit).where(OrgUnit.name == "Doomed")) is None
    assert await audit_records(db_session) == []


async def test_audit_failure_rolls_back_task_and_its_notifications(
    world: World, login: Login, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    tl = await login("tl_a1")

    def unavailable(*_: Any, **__: Any) -> None:
        raise RuntimeError("audit store unavailable")

    monkeypatch.setattr(audit, "record", unavailable)

    with pytest.raises(RuntimeError):
        await tl.post(
            TASKS,
            {
                "title": "Never saved",
                "scope_unit_id": str(world.structure.team_a1),
                "assignee_member_ids": [str(world.member_ids["m_a1"])],
            },
        )
    await db_session.rollback()

    assert await db_session.scalar(select(Task).where(Task.title == "Never saved")) is None
    assert list(await db_session.scalars(select(Notification))) == []


# --- Privacy --------------------------------------------------------------------------------------


async def test_secrets_and_content_never_reach_audit_records_or_logs(
    world: World,
    login: Login,
    new_task: Any,
    new_event: NewEvent,
    client_factory: ClientFactory,
    db_session: AsyncSession,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    admin, tl = await login("sysadmin"), await login("tl_a1")
    secrets = [
        PASSWORD,
        "secret.person@example.test",
        "0551112233",
        "U-SECRET-77",
        "Secret Major",
        "SECRET-DESCRIPTION",
        "SECRET-COMMENT",
        "SECRET-COMMENT-EDIT",
        "SECRET-ANNOUNCEMENT-BODY",
        "SECRET-EVENT-DESC",
        "SECRET-PASSCODE",
        "SECRET-REASON",
        "SECRET-new-password",
        "SECRET-WRONG-PASSWORD",
        "secret-typo-user",
    ]

    response = await admin.post(
        MEMBERS,
        {
            "username": "newbie",
            "full_name": "New Person",
            "email": "secret.person@example.test",
            "phone": "0551112233",
            "university_id": "U-SECRET-77",
            "major": "Secret Major",
            "team_id": str(world.structure.team_a1),
            "role_key": "member",
        },
    )
    assert response.status_code == 201, response.text
    member_id = response.json()["member"]["id"]
    secrets.append(response.json()["temporary_password"])
    response = await admin.post(f"{MEMBERS}/{member_id}/reset-password")
    temporary_password = response.json()["temporary_password"]
    secrets.append(temporary_password)
    newbie = client_factory()
    newbie_csrf = await signed_in(newbie, "newbie", temporary_password)
    response = await newbie.post(
        CHANGE_PASSWORD,
        json={"current_password": temporary_password, "new_password": "SECRET-new-password"},
        headers=csrf_headers(newbie_csrf),
    )
    assert response.status_code == 200, response.text
    secrets.append(response.json()["csrf_token"])
    secrets.append(newbie.cookies["kora_session"])

    task = await new_task(tl, "team_a1", ["m_a1"], description="SECRET-DESCRIPTION")
    comment = (await tl.post(f"{TASKS}/{task['id']}/comments", {"body": "SECRET-COMMENT"})).json()
    await tl.patch(
        f"{TASKS}/{task['id']}/comments/{comment['id']}", {"body": "SECRET-COMMENT-EDIT"}
    )
    await draft(tl, world, body="SECRET-ANNOUNCEMENT-BODY")
    await new_event(
        tl,
        "team_a1",
        ["m_a1"],
        description="SECRET-EVENT-DESC",
        online_url="https://meet.example/j/1?pwd=SECRET-PASSCODE",
    )
    response = await admin.post(
        f"/api/v1/admin/accounts/{world.account_ids['m_a2']}/overrides",
        {
            "permission": "task.view",
            "unit_id": str(world.structure.team_b1),
            "effect": "grant",
            "reason": "SECRET-REASON",
        },
    )
    assert response.status_code == 201, response.text
    for _ in range(6):
        await sign_in(client_factory(), "secret-typo-user", "SECRET-WRONG-PASSWORD")
        await sign_in(client_factory(), "m_b1", "SECRET-WRONG-PASSWORD")
    secrets += [admin.csrf, tl.csrf, admin.client.cookies["kora_session"]]
    secrets += list(await db_session.scalars(select(UserAccount.password_hash)))

    listing = await admin.get(AUDIT, limit=200)
    assert listing.status_code == 200
    actions = {item["action"] for item in listing.json()["items"]}
    assert {"member.provisioned", "account.password_reset", "account.password_changed"} <= actions
    assert {"task_comment.edited", "calendar_event.created", "account.locked_out"} <= actions
    for secret in secrets:
        assert secret not in listing.text, secret
        assert secret not in caplog.text, secret


# --- Read API -------------------------------------------------------------------------------------


async def test_system_admin_reads_records_without_source_access(
    world: World, login: Login, new_task: Any, new_event: NewEvent
) -> None:
    tl, admin = await login("tl_a1"), await login("sysadmin")
    task = await new_task(tl, "team_a1", ["m_a1"], title="Original title")
    event = await new_event(tl, "team_a1", ["m_a1"])
    announcement = await draft(tl, world)

    page = (await admin.get(AUDIT)).json()
    by_action = {item["action"]: item for item in page["items"]}
    assert {"task.created", "calendar_event.created", "announcement.draft_created"} <= set(
        by_action
    )
    record = by_action["task.created"]
    assert record["resource_id"] == task["id"]
    assert record["actor_account_id"] == str(world.account_ids["tl_a1"])

    # Only stored metadata: later changes to the task are not reflected in the record.
    assert (await tl.patch(f"{TASKS}/{task['id']}", {"title": "Renamed"})).is_success
    response = await admin.get(f"{AUDIT}/{record['id']}")
    assert response.status_code == 200
    assert response.json() == record
    assert response.json()["after"]["title"] == "Original title"

    # Audit access grants nothing on the underlying resources.
    for path in (
        f"{TASKS}/{task['id']}",
        f"{EVENTS}/{event['id']}",
        f"{ANNOUNCEMENTS}/{announcement['id']}",
    ):
        assert (await admin.get(path)).status_code == 403, path
    assert (await admin.get(TASKS)).json() == []


async def test_audit_api_is_system_admin_only_and_read_only(
    db_app: FastAPI, world: World, login: Login, db_client: AsyncClient
) -> None:
    for name in ("leader", "tl_a1", "m_a1"):
        api = await login(name)
        for path in (AUDIT, f"{AUDIT}/{uuid.uuid4()}"):
            response = await api.get(path)
            assert response.status_code == 403, (name, path)
            assert response.json() == {"detail": "System Admin authority required."}
    assert (await db_client.get(AUDIT)).status_code == 401

    routes = [(methods, path) for methods, path in mounted_routes(db_app) if "audit" in path]
    assert routes and all(methods <= {"GET", "HEAD"} for methods, _ in routes)
    admin = await login("sysadmin")
    for method in ("POST", "PUT", "PATCH", "DELETE"):
        for path in (AUDIT, f"{AUDIT}/{uuid.uuid4()}"):
            response = await admin.client.request(method, path, headers=csrf_headers(admin.csrf))
            assert response.status_code == 405, (method, path)
    assert (await admin.get(f"{AUDIT}/{uuid.uuid4()}")).status_code == 404


async def test_pagination_and_filters(
    client_factory: ClientFactory, db_session: AsyncSession, frozen_clock: FrozenClock
) -> None:
    admin = await create_account(db_session, "sysadmin", system_admin=True)
    other = await create_account(db_session, "other")
    team = (await make_structure(db_session)).team_a1
    start = frozen_clock.now
    resource_ids: list[uuid.UUID] = []
    for n in range(7):
        frozen_clock.advance(timedelta(minutes=1))  # record n occurs at start + (n + 1) minutes
        resource_ids.append(uuid.uuid4())
        audit.record(
            db_session,
            ALPHA if n % 2 == 0 else BETA,
            actor_account_id=admin.id if n < 4 else other.id,
            resource_id=resource_ids[n],
            scope_unit_id=team if n < 3 else None,
            after={"n": n},
        )
    await db_session.commit()
    client = client_factory()
    await signed_in(client, "sysadmin")

    async def numbers(**params: Any) -> list[int]:
        response = await client.get(AUDIT, params=params)
        assert response.status_code == 200, response.text
        return [item["after"]["n"] for item in response.json()["items"]]

    pages: list[list[int]] = []
    cursor: int | None = None
    while True:
        params: dict[str, Any] = {"limit": 3} | ({"cursor": cursor} if cursor else {})
        body = (await client.get(AUDIT, params=params)).json()
        pages.append([item["after"]["n"] for item in body["items"]])
        cursor = body["next_cursor"]
        if cursor is None:
            break
    assert pages == [[6, 5, 4], [3, 2, 1], [0]]

    assert await numbers(action="test.alpha") == [6, 4, 2, 0]
    assert await numbers(actor_account_id=str(other.id)) == [6, 5, 4]
    assert await numbers(resource_type="widget") == [5, 3, 1]
    assert await numbers(resource_id=str(resource_ids[3])) == [3]
    assert await numbers(scope_unit_id=str(team)) == [2, 1, 0]
    assert await numbers(
        occurred_from=(start + timedelta(minutes=2, seconds=30)).isoformat(),
        occurred_to=(start + timedelta(minutes=5)).isoformat(),
    ) == [3, 2]
    assert await numbers(action="test.alpha", actor_account_id=str(admin.id)) == [2, 0]
    assert await numbers(action="test.none") == []

    for params in (
        {"occurred_from": "2030-01-01T00:00:00"},  # no offset
        {"limit": 0},
        {"limit": audit.MAX_PAGE_SIZE + 1},
        {"cursor": "abc"},
    ):
        assert (await client.get(AUDIT, params=params)).status_code == 422, params
