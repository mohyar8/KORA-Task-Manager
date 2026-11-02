"""Private notes: owner-only, versioned, never audited."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kora_api.audit.models import AuditRecord
from tests.access.helpers import create_account, csrf_headers, signed_in
from tests.conftest import ClientFactory

pytestmark = pytest.mark.anyio

NOTE = "/api/v1/me/note"
SECRET = "my very private thought"


async def test_a_new_account_has_an_empty_note(
    client_factory: ClientFactory, db_session: AsyncSession
) -> None:
    await create_account(db_session, "ann")
    client = client_factory()
    await signed_in(client, "ann")
    body = (await client.get(NOTE)).json()
    assert body == {"body": "", "version": 0, "updated_at": None}


async def test_saving_bumps_the_version_and_an_old_version_conflicts(
    client_factory: ClientFactory, db_session: AsyncSession
) -> None:
    await create_account(db_session, "ann")
    client = client_factory()
    csrf = csrf_headers(await signed_in(client, "ann"))
    first = await client.put(NOTE, json={"body": "a\n- b", "version": 0}, headers=csrf)
    assert first.status_code == 200
    assert first.json()["version"] == 1
    second = await client.put(NOTE, json={"body": "c", "version": 1}, headers=csrf)
    assert second.json()["version"] == 2
    # Saved elsewhere meanwhile: both the stale version and a second "first save" conflict.
    assert (
        await client.put(NOTE, json={"body": "x", "version": 1}, headers=csrf)
    ).status_code == 409
    assert (
        await client.put(NOTE, json={"body": "x", "version": 0}, headers=csrf)
    ).status_code == 409
    assert (await client.get(NOTE)).json()["body"] == "c"


async def test_notes_are_isolated_between_accounts(
    client_factory: ClientFactory, db_session: AsyncSession
) -> None:
    await create_account(db_session, "ann")
    await create_account(db_session, "root", system_admin=True)
    ann, root = client_factory(), client_factory()
    ann_csrf = csrf_headers(await signed_in(ann, "ann"))
    await signed_in(root, "root")
    await ann.put(NOTE, json={"body": SECRET, "version": 0}, headers=ann_csrf)
    assert (await root.get(NOTE)).json()["body"] == ""  # not even a System Admin


async def test_length_limit_and_authentication(
    client_factory: ClientFactory, db_session: AsyncSession
) -> None:
    await create_account(db_session, "ann")
    client = client_factory()
    csrf = csrf_headers(await signed_in(client, "ann"))
    ok = await client.put(NOTE, json={"body": "x" * 5000, "version": 0}, headers=csrf)
    assert ok.status_code == 200
    too_long = await client.put(NOTE, json={"body": "x" * 5001, "version": 1}, headers=csrf)
    assert too_long.status_code == 422
    assert SECRET not in too_long.text
    assert (await client_factory().get(NOTE)).status_code == 401


async def test_the_text_never_reaches_the_audit_log(
    client_factory: ClientFactory, db_session: AsyncSession
) -> None:
    await create_account(db_session, "ann")
    client = client_factory()
    csrf = csrf_headers(await signed_in(client, "ann"))
    await client.put(NOTE, json={"body": SECRET, "version": 0}, headers=csrf)
    records = (await db_session.scalars(select(AuditRecord))).all()
    assert all(SECRET not in str(r.before) + str(r.after) for r in records)
    assert all(not r.action.startswith("note") for r in records)
