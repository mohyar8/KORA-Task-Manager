"""Task files: presigned upload flow, who may add what, and the limits."""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kora_api.audit.models import AuditRecord
from kora_api.core.storage import S3Storage
from tests.tasks.conftest import TASKS, Api, Login, World

pytestmark = pytest.mark.anyio

NewTask = Callable[..., Awaitable[dict[str, Any]]]


class FakeStorage:
    """An in-memory bucket: `objects` maps key -> uploaded size."""

    def __init__(self) -> None:
        self.objects: dict[str, int] = {}

    def upload_url(self, key: str) -> str:
        return f"https://bucket.test/{key}?signed=put"

    def download_url(self, key: str, *, filename: str) -> str:
        return f"https://bucket.test/{key}?signed=get&name={filename}"

    async def size_of(self, key: str) -> int | None:
        return self.objects.get(key)


@pytest.fixture
def storage(db_app: FastAPI) -> FakeStorage:
    fake = FakeStorage()
    db_app.state.storage = fake
    return fake


async def _upload(
    api: Api,
    storage: FakeStorage,
    task_id: str,
    kind: str,
    name: str = "plan.pdf",
    size: int = 1000,
    stored: int | None = None,
) -> dict[str, Any]:
    started = await api.post(f"{TASKS}/{task_id}/files", {"kind": kind, "name": name, "size": size})
    assert started.status_code == 201, started.text
    ticket: dict[str, Any] = started.json()
    key = ticket["upload_url"].split("bucket.test/")[1].split("?")[0]
    storage.objects[key] = size if stored is None else stored
    return ticket


async def _setup(world: World, login: Login, new_task: NewTask) -> tuple[Api, Api, dict[str, Any]]:
    lead, member = await login("tl_a1"), await login("m_a1b")
    return lead, member, await new_task(lead, "team_a1", ["m_a1b"])


async def test_a_brief_is_hidden_until_the_upload_is_confirmed(
    world: World, login: Login, new_task: NewTask, storage: FakeStorage
) -> None:
    lead, member, task = await _setup(world, login, new_task)
    url = f"{TASKS}/{task['id']}/files"
    started = await lead.post(url, {"kind": "brief", "name": "../etc/plan.pdf", "size": 1000})
    ticket = started.json()
    assert started.status_code == 201
    assert ticket["file"]["name"] == "plan.pdf"  # folders are stripped
    assert "storage_key" not in ticket["file"]
    assert (await lead.get(url)).json() == []  # pending files are invisible
    complete = f"{url}/{ticket['file']['id']}/complete"
    assert (await lead.post(complete)).status_code == 409  # nothing uploaded yet

    key = ticket["upload_url"].split("bucket.test/")[1].split("?")[0]
    storage.objects[key] = 1000
    assert (await member.post(complete)).status_code == 403  # only the uploader confirms
    assert (await lead.post(complete)).status_code == 200
    assert (await lead.post(complete)).status_code == 200  # idempotent
    for api in (lead, member):
        listed = (await api.get(url)).json()
        assert [f["name"] for f in listed] == ["plan.pdf"]
    assert (await (await login("m_b1")).get(url)).status_code == 403  # not their task

    link = (await member.get(f"{url}/{ticket['file']['id']}/download")).json()
    assert "signed=get" in link["url"]
    assert (
        await (await login("m_b1")).get(f"{url}/{ticket['file']['id']}/download")
    ).status_code == 403
    notes = (await member.get("/api/v1/notifications")).json()
    assert any(n["kind"] == "file_added" for n in notes)


async def test_who_may_add_which_kind(
    world: World, login: Login, new_task: NewTask, storage: FakeStorage
) -> None:
    lead, member, task = await _setup(world, login, new_task)
    url = f"{TASKS}/{task['id']}/files"
    brief = {"kind": "brief", "name": "a.txt", "size": 10}
    delivery = {"kind": "delivery", "name": "a.txt", "size": 10}
    assert (await member.post(url, brief)).status_code == 403  # an assignee cannot add the brief
    assert (await lead.post(url, delivery)).status_code == 403  # the creator did not do the work
    assert (await (await login("m_a1")).post(url, delivery)).status_code == 403  # nor a bystander
    ticket = await _upload(member, storage, task["id"], "delivery")
    assert (await member.post(f"{url}/{ticket['file']['id']}/complete")).status_code == 200
    notes = (await lead.get("/api/v1/notifications")).json()
    assert any(n["kind"] == "delivery_added" for n in notes)


async def test_limits_and_rejected_files(
    world: World, login: Login, new_task: NewTask, storage: FakeStorage
) -> None:
    lead, _, task = await _setup(world, login, new_task)
    url = f"{TASKS}/{task['id']}/files"
    for bad in (
        {"name": "run.EXE", "size": 10},
        {"name": "tool.sh", "size": 10},
        {"name": "big.zip", "size": 10 * 1024 * 1024 + 1},
        {"name": "///", "size": 10},
    ):
        assert (await lead.post(url, {"kind": "brief", **bad})).status_code == 422, bad
    assert (await lead.post(url, {"kind": "brief", "name": "empty", "size": 0})).status_code == 422

    # A file whose stored size differs from what was declared is refused and hidden.
    ticket = await _upload(lead, storage, task["id"], "brief", size=500, stored=900)
    assert (await lead.post(f"{url}/{ticket['file']['id']}/complete")).status_code == 422
    assert (await lead.get(url)).json() == []

    for i in range(10):
        made = await _upload(lead, storage, task["id"], "brief", name=f"f{i}.txt")
        assert (await lead.post(f"{url}/{made['file']['id']}/complete")).status_code == 200
    assert (await lead.post(url, {"kind": "brief", "name": "11.txt", "size": 5})).status_code == 422


async def test_removing_and_closed_tasks(
    world: World, login: Login, new_task: NewTask, storage: FakeStorage, db_session: AsyncSession
) -> None:
    lead, member, task = await _setup(world, login, new_task)
    other = await login("m_a1")
    url = f"{TASKS}/{task['id']}/files"
    mine = await _upload(member, storage, task["id"], "delivery", name="secret-plan.pdf")
    await member.post(f"{url}/{mine['file']['id']}/complete")
    assert (await other.delete(f"{url}/{mine['file']['id']}")).status_code == 403
    brief = await _upload(lead, storage, task["id"], "brief")
    await lead.post(f"{url}/{brief['file']['id']}/complete")
    assert (await member.delete(f"{url}/{brief['file']['id']}")).status_code == 403
    assert (await lead.delete(f"{url}/{mine['file']['id']}")).status_code == 204  # the creator may
    assert (await member.delete(f"{url}/{brief['file']['id']}")).status_code == 403
    assert (await lead.delete(f"{url}/{brief['file']['id']}")).status_code == 204
    assert (await lead.get(url)).json() == []
    assert (await lead.delete(f"{url}/{brief['file']['id']}")).status_code == 404

    # No file names in the audit trail.
    records = (await db_session.scalars(select(AuditRecord))).all()
    actions = {r.action for r in records}
    assert {"task_file.added", "task_file.removed"} <= actions
    assert all("secret-plan" not in f"{r.before}{r.after}" for r in records)

    # A closed task is read-only for files.
    await lead.post(f"{TASKS}/{task['id']}/status", {"status": "completed"})
    assert (
        await lead.post(url, {"kind": "brief", "name": "late.txt", "size": 5})
    ).status_code == 409


async def test_unconfigured_storage_and_review_tasks(
    world: World, login: Login, new_task: NewTask, db_app: FastAPI
) -> None:
    lead, member, task = await _setup(world, login, new_task)
    db_app.state.storage = None
    url = f"{TASKS}/{task['id']}/files"
    assert (await lead.post(url, {"kind": "brief", "name": "a.txt", "size": 5})).status_code == 503
    assert (await lead.get(url)).status_code == 200  # reading needs no storage
    # Review tasks carry no files.
    await member.put(f"{TASKS}/{task['id']}/progress", {"finished": True})
    review = next(t for t in (await lead.get(TASKS)).json() if t["kind"] == "review")
    db_app.state.storage = FakeStorage()
    started = await lead.post(
        f"{TASKS}/{review['id']}/files", {"kind": "brief", "name": "a.txt", "size": 5}
    )
    assert started.status_code == 409


def test_presigned_urls_are_signed_and_never_expose_the_secret() -> None:
    store = S3Storage(
        endpoint="https://acct.r2.example.com",
        bucket="kora-files",
        region="auto",
        access_key_id="AKIDEXAMPLE",
        secret_access_key="super-secret",
    )
    at = datetime(2026, 10, 28, 12, 0, tzinfo=UTC)
    url = store._presign("PUT", "tasks/t1/f1", 600, at=at)  # type: ignore[reportPrivateUsage]
    assert url.startswith("https://acct.r2.example.com/kora-files/tasks/t1/f1?")
    assert "X-Amz-Credential=AKIDEXAMPLE%2F20261028%2Fauto%2Fs3%2Faws4_request" in url
    assert "X-Amz-Expires=600" in url
    assert "super-secret" not in url
    signature = url.rsplit("X-Amz-Signature=", 1)[1]
    assert len(signature) == 64
    assert url == store._presign("PUT", "tasks/t1/f1", 600, at=at)  # type: ignore[reportPrivateUsage]
    download = store.download_url("tasks/t1/f1", filename='a"b.pdf')
    assert "response-content-disposition=attachment" in download
    assert "response-content-type=application%2Foctet-stream" in download
