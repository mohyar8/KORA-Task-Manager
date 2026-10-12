"""Release-readiness: one cross-module flow from an organization with no structure.

Bootstrap -> first System Admin -> explicit grant -> first Administration and Team ->
provisioned Members -> task, announcement, calendar event -> notifications (with source-access
redaction) -> audit inspection without operational access. Each module's own rules are covered
by its focused tests; this checks that they work together through the public API.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kora_api.access import service as access_service
from kora_api.access.models import UserAccount
from kora_api.organization.constants import KORA_UNIT_ID
from tests.access.helpers import CHANGE_PASSWORD, csrf_headers, signed_in
from tests.conftest import ClientFactory

pytestmark = pytest.mark.anyio

V1 = "/api/v1"


class User:
    """A signed-in client whose unsafe requests carry the CSRF header."""

    def __init__(self, client: AsyncClient, csrf: str) -> None:
        self.client, self.csrf = client, csrf

    async def get(self, path: str, **params: Any) -> Response:
        return await self.client.get(V1 + path, params=params or None)

    async def post(self, path: str, body: Any = None) -> Response:
        return await self.client.post(V1 + path, json=body, headers=csrf_headers(self.csrf))

    async def ok(self, path: str, body: Any = None, status: int = 200) -> Any:
        response = await self.post(path, body)
        assert response.status_code == status, (path, response.text)
        return response.json()


async def _first_sign_in(
    client_factory: ClientFactory, username: str, temporary: str, secrets: list[str]
) -> User:
    """Sign in with a temporary password, confirm the gate, then set a real password."""
    client = client_factory()
    csrf = await signed_in(client, username, temporary)
    assert (await client.get(f"{V1}/access/me")).json() == {"detail": "Password change required."}
    password = f"{username} chose a long passphrase"
    response = await client.post(
        CHANGE_PASSWORD,
        json={"current_password": temporary, "new_password": password},
        headers=csrf_headers(csrf),
    )
    assert response.status_code == 200, response.text
    secrets += [temporary, password, csrf, response.json()["csrf_token"]]
    secrets.append(client.cookies["kora_session"])
    return User(client, response.json()["csrf_token"])


async def test_platform_flow_from_bootstrap_to_audit(
    client_factory: ClientFactory, db_session: AsyncSession, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    secrets: list[str] = []

    # 1. Bootstrap (CLI-only) and the first System Admin's first sign-in.
    root_account, temporary = await access_service.bootstrap_first_system_admin(db_session, "root")
    root = await _first_sign_in(client_factory, "root", temporary, secrets)
    assert (await root.get("/auth/me")).json()["is_system_admin"] is True

    # 2. System Admin has no implicit operational access, until explicitly granted.
    structure = {"kind": "administration", "name": "Operations", "parent_id": str(KORA_UNIT_ID)}
    assert (await root.post("/organization/units", structure)).status_code == 403
    await root.ok(
        f"/admin/accounts/{root_account.id}/overrides",
        {
            "permission": "organization.manage",
            "unit_id": str(KORA_UNIT_ID),
            "effect": "grant",
            "reason": "Initial structure setup",
        },
        status=201,
    )
    administration = await root.ok("/organization/units", structure, status=201)
    team = await root.ok(
        "/organization/units",
        {"kind": "team", "name": "Logistics", "parent_id": administration["id"]},
        status=201,
    )

    # 3. Provision Members with roles; each must replace the temporary password.
    users: dict[str, User] = {}
    member_ids: dict[str, str] = {}
    for username, role in (("lead", "team_leader"), ("member1", "member"), ("member2", "member")):
        created = await root.ok(
            "/admin/members",
            {
                "username": username,
                "full_name": username.title(),
                "team_id": team["id"],
                "role_key": role,
            },
            status=201,
        )
        member_ids[username] = created["member"]["id"]
        assert created["member"]["role_unit_id"] == team["id"]
        users[username] = await _first_sign_in(
            client_factory, username, created["temporary_password"], secrets
        )
    lead, m1, m2 = users["lead"], users["member1"], users["member2"]

    # 4. A task: assignment, progress, a comment, another assignee.
    task = await lead.ok(
        "/tasks",
        {
            "title": "Book the venue",
            "description": "Confidential venue shortlist",
            "scope_unit_id": team["id"],
            "assignee_member_ids": [member_ids["member1"]],
        },
        status=201,
    )
    task_path = f"/tasks/{task['id']}"
    assert (await m1.ok(f"{task_path}/status", {"status": "in_progress"}))["status"] == (
        "in_progress"
    )
    await m1.ok(f"{task_path}/comments", {"body": "Confidential: called the hotel"}, status=201)
    updated = await lead.ok(f"{task_path}/assignees", {"member_id": member_ids["member2"]})
    assert set(updated["assignee_member_ids"]) == {member_ids["member1"], member_ids["member2"]}
    comments = (await lead.get(f"{task_path}/comments")).json()
    assert [c["body"] for c in comments] == ["Confidential: called the hotel"]

    # 5. An announcement: fixed recipients and per-recipient read state.
    announcement = await lead.ok(
        "/announcements",
        {"scope_unit_id": team["id"], "title": "Venue update", "body": "Confidential body"},
        status=201,
    )
    announcement_path = f"/announcements/{announcement['id']}"
    await lead.ok(
        f"{announcement_path}/publish",
        {"recipient_member_ids": [member_ids["member1"], member_ids["member2"]]},
    )
    opened = (await m1.get(announcement_path)).json()
    assert (opened["body"], opened["my_read_current"]) == ("Confidential body", True)
    statuses = {
        s["member_id"]: s["read_current"]
        for s in (await lead.get(f"{announcement_path}/recipients")).json()
    }
    assert statuses == {member_ids["member1"]: True, member_ids["member2"]: False}
    assert (await m1.get(f"{announcement_path}/recipients")).status_code == 403

    # 6. A calendar event: invitees see it and only their own invitation.
    starts = datetime(2030, 5, 1, 9, tzinfo=UTC)
    event = await lead.ok(
        "/calendar/events",
        {
            "type": "meeting",
            "title": "Venue walkthrough",
            "starts_at": starts.isoformat(),
            "ends_at": (starts + timedelta(hours=1)).isoformat(),
            "online_url": "https://meet.example/j/1?pwd=confidential",
            "scope_unit_id": team["id"],
            "invitee_member_ids": [member_ids["member1"]],
        },
        status=201,
    )
    event_path = f"/calendar/events/{event['id']}"
    seen = (await m1.get(event_path)).json()
    assert seen["invitee_member_ids"] is None
    assert seen["my_invitation"]["member_id"] == member_ids["member1"]
    assert (await m2.get(event_path)).status_code == 403
    invitations = (await lead.get(f"{event_path}/invitations")).json()
    assert [i["member_id"] for i in invitations] == [member_ids["member1"]]

    # 7. Notifications, and redaction once the source is no longer visible to the reader.
    def kinds(notifications: list[dict[str, Any]]) -> set[tuple[str, str]]:
        return {(n["source_type"], n["kind"]) for n in notifications}

    m1_notes = (await m1.get("/notifications")).json()
    assert {
        ("task", "assigned"),
        ("announcement", "published"),
        ("calendar_event", "invited"),
    } <= kinds(m1_notes)
    assert ("task", "commented") not in kinds(m1_notes)  # never notified of one's own action
    assert ("task", "commented") in kinds((await lead.get("/notifications")).json())
    await lead.ok(f"{announcement_path}/withdraw")
    m2_announcement_notes = [
        n for n in (await m2.get("/notifications")).json() if n["source_type"] == "announcement"
    ]
    assert m2_announcement_notes
    assert all(n["redacted"] and n["summary"] is None for n in m2_announcement_notes)
    withdrawn = (await m2.get(announcement_path)).json()
    assert (withdrawn["state"], withdrawn["content_hidden"], withdrawn["body"]) == (
        "withdrawn",
        True,
        None,
    )

    # 8. The System Admin inspects the audit log but gains no operational access from it.
    page = (await root.get("/admin/audit-records", limit=200)).json()
    actions = [item["action"] for item in page["items"]]
    for expected in (
        "account.bootstrapped",
        "permission_override.created",
        "org_unit.created",
        "member.provisioned",
        "task.created",
        "task_comment.created",
        "announcement.published",
        "announcement.withdrawn",
        "calendar_event.created",
    ):
        assert expected in actions, expected
    assert actions.count("member.provisioned") == 3
    for path in (task_path, announcement_path, event_path, f"{task_path}/comments"):
        assert (await root.get(path)).status_code == 403, path
    assert (await root.get("/tasks")).json() == []
    assert (await root.get("/announcements")).json() == []
    assert (await root.get("/calendar/events")).json() == []
    new_task = {
        "title": "x",
        "scope_unit_id": team["id"],
        "assignee_member_ids": [member_ids["member1"]],
    }
    assert (await root.post("/tasks", new_task)).status_code == 403  # not a Member

    # Nothing secret or confidential reached the audit log or the logs.
    hashes = list(await db_session.scalars(select(UserAccount.password_hash)))
    audit_text = (await root.get("/admin/audit-records", limit=200)).text
    for secret in [*secrets, *hashes, "Confidential", "confidential"]:
        assert secret not in audit_text, secret
        assert secret not in caplog.text, secret
