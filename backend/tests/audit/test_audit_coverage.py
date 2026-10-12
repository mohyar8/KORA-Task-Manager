"""Every required action family writes exactly one safe audit record per logical change."""

import uuid
from datetime import timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from kora_api.access import service as access_service
from kora_api.access.policy import LOGIN_MAX_FAILURES
from tests.access.helpers import CHANGE_PASSWORD, PASSWORD, csrf_headers, sign_in
from tests.audit.conftest import audit_records, only
from tests.calendar.conftest import EVENTS, NewEvent
from tests.communication.conftest import ANNOUNCEMENTS, NOTIFICATIONS, draft, publish
from tests.conftest import FrozenClock
from tests.organization.helpers import MEMBERS, UNITS
from tests.tasks.conftest import SERIES, TASKS, Login, World

pytestmark = pytest.mark.anyio

ADMIN = "/api/v1/admin"


async def _actions(db: AsyncSession) -> list[str]:
    return [r.action for r in await audit_records(db)]


# --- Access ---------------------------------------------------------------------------------------


async def test_bootstrap_is_audited(db_session: AsyncSession) -> None:
    account, _ = await access_service.bootstrap_first_system_admin(db_session, "first-admin")

    record = await only(db_session, "account.bootstrapped", account.id)
    assert record.actor_account_id is None
    assert record.resource_type == "user_account"
    assert record.after == {"status": "active", "password_is_temporary": True, "system_admin": True}


async def test_access_administration_and_password_change_are_audited(
    world: World, login: Login, db_session: AsyncSession
) -> None:
    admin = await login("sysadmin")
    admin_id, target = world.account_ids["sysadmin"], world.account_ids["m_a1"]

    assert (await admin.post(f"{ADMIN}/accounts/{target}/system-admin")).status_code == 201
    assert (await admin.post(f"{ADMIN}/accounts/{target}/system-admin/revoke")).status_code == 204
    response = await admin.post(
        f"{ADMIN}/role-defaults", {"role_key": "member", "permission": "task.manage"}
    )
    default_id = response.json()["id"]
    assert (await admin.post(f"{ADMIN}/role-defaults/{default_id}/end")).status_code == 200
    response = await admin.post(
        f"{ADMIN}/accounts/{target}/overrides",
        {
            "permission": "task.view",
            "unit_id": str(world.structure.team_b1),
            "effect": "grant",
            "reason": "Covering for a colleague",
        },
    )
    override_id = response.json()["id"]
    assert (await admin.post(f"{ADMIN}/overrides/{override_id}/end")).status_code == 200
    member = await login("m_a2")
    response = await member.post(
        CHANGE_PASSWORD, {"current_password": PASSWORD, "new_password": "another good one"}
    )
    assert response.status_code == 200, response.text

    assert await _actions(db_session) == [
        "system_admin.granted",
        "system_admin.revoked",
        "role_default.created",
        "role_default.ended",
        "permission_override.created",
        "permission_override.ended",
        "account.password_changed",
    ]
    granted = await only(db_session, "system_admin.granted", target)
    assert granted.actor_account_id == admin_id
    assert (granted.before, granted.after) == ({"system_admin": False}, {"system_admin": True})
    created = await only(db_session, "role_default.created", default_id)
    assert created.after is not None
    assert (created.after["role_key"], created.after["permission"]) == ("member", "task.manage")
    override = await only(db_session, "permission_override.created", override_id)
    assert override.scope_unit_id == world.structure.team_b1
    assert override.after is not None and "Covering" not in str(override.after)
    ended = await only(db_session, "permission_override.ended", override_id)
    assert ended.before is not None and ended.before["valid_to"] is None
    changed = await only(db_session, "account.password_changed", world.account_ids["m_a2"])
    assert changed.actor_account_id == world.account_ids["m_a2"]
    assert changed.before == {"password_is_temporary": False}


async def test_lockout_is_audited_only_for_existing_accounts(
    world: World, db_client: AsyncClient, db_session: AsyncSession
) -> None:
    for _ in range(LOGIN_MAX_FAILURES):
        assert (await sign_in(db_client, "m_b1", "wrong password!")).status_code == 401
    assert (await sign_in(db_client, "m_b1", "wrong password!")).status_code == 429
    for _ in range(LOGIN_MAX_FAILURES):
        await sign_in(db_client, "no-such-user", "wrong password!")

    record = await only(db_session, "account.locked_out")
    assert record.resource_id == world.account_ids["m_b1"]
    assert record.actor_account_id is None
    assert record.after is not None and record.after["failure_count"] == LOGIN_MAX_FAILURES
    assert record.after["locked_until"] is not None


# --- Organization ---------------------------------------------------------------------------------


async def test_organization_changes_are_audited(
    world: World, login: Login, db_session: AsyncSession
) -> None:
    s = world.structure
    leader = await login("leader")
    response = await leader.post(
        UNITS, {"kind": "team", "name": "Team A3", "parent_id": str(s.admin_a)}
    )
    team = response.json()["id"]
    assert (
        await leader.post(f"{UNITS}/{team}/move", {"administration_id": str(s.admin_b)})
    ).is_success
    assert (await leader.post(f"{UNITS}/{team}/archive")).is_success

    admin = await login("sysadmin")
    response = await admin.post(
        MEMBERS,
        {
            "username": "newbie",
            "full_name": "New Person",
            "email": "newbie@example.test",
            "team_id": str(s.team_a1),
            "role_key": "member",
        },
    )
    assert response.status_code == 201, response.text
    member_id, account_id = response.json()["member"]["id"], response.json()["member"]["account_id"]
    response = await admin.client.put(
        f"{MEMBERS}/{member_id}",
        json={"full_name": "New Person", "phone": "0559999999"},
        headers=csrf_headers(admin.csrf),
    )
    assert response.status_code == 200, response.text
    assert (await admin.post(f"{MEMBERS}/{member_id}/team", {"team_id": str(s.team_a2)})).is_success
    assert (await admin.post(f"{MEMBERS}/{member_id}/role", {"role_key": "team_leader"})).is_success
    assert (await admin.post(f"{MEMBERS}/{member_id}/reset-password")).is_success
    assert (await admin.post(f"{MEMBERS}/{member_id}/deactivate")).is_success
    response = await admin.post(
        f"{MEMBERS}/{member_id}/reactivate", {"team_id": str(s.team_a1), "role_key": "member"}
    )
    assert response.is_success, response.text

    # One record per logical change: no separate account records for deactivation etc.
    assert await _actions(db_session) == [
        "org_unit.created",
        "org_unit.moved",
        "org_unit.archived",
        "member.provisioned",
        "member.profile_updated",
        "member.team_changed",
        "member.role_changed",
        "account.password_reset",
        "member.deactivated",
        "member.reactivated",
    ]
    created = await only(db_session, "org_unit.created", team)
    assert created.after == {
        "kind": "team",
        "name": "Team A3",
        "parent_id": str(s.admin_a),
        "status": "active",
    }
    moved = await only(db_session, "org_unit.moved", team)
    assert (moved.before, moved.after) == (
        {"parent_id": str(s.admin_a)},
        {"parent_id": str(s.admin_b)},
    )
    provisioned = await only(db_session, "member.provisioned", member_id)
    assert provisioned.actor_account_id == world.account_ids["sysadmin"]
    assert provisioned.scope_unit_id == s.team_a1
    assert provisioned.after is not None
    assert set(provisioned.after) == {
        "account_id",
        "status",
        "team_id",
        "role_key",
        "role_unit_id",
        "password_is_temporary",
    }
    profile = await only(db_session, "member.profile_updated", member_id)
    assert (profile.before, profile.after) == (None, {"changed_fields": ["email", "phone"]})
    team_change = await only(db_session, "member.team_changed", member_id)
    assert team_change.before is not None and team_change.after is not None
    assert (team_change.before["team_id"], team_change.after["team_id"]) == (
        str(s.team_a1),
        str(s.team_a2),
    )
    assert team_change.after["role_unit_id"] == str(s.team_a2)  # a Team role follows the Team
    reset = await only(db_session, "account.password_reset", account_id)
    assert reset.after is not None and reset.after["sessions_revoked"] is True
    deactivated = await only(db_session, "member.deactivated", member_id)
    assert deactivated.after is not None
    assert (deactivated.after["status"], deactivated.after["account_status"]) == (
        "deactivated",
        "deactivated",
    )


# --- Tasks ----------------------------------------------------------------------------------------


async def test_task_changes_are_audited(
    world: World, login: Login, new_task: Any, db_session: AsyncSession
) -> None:
    tl, assignee, leader = await login("tl_a1"), await login("m_a1"), await login("leader")
    task = await new_task(tl, "team_a1", ["m_a1"], title="Book the hall", description="Details")
    path = f"{TASKS}/{task['id']}"
    m_a1, m_a1b = world.member_ids["m_a1"], world.member_ids["m_a1b"]

    assert (await tl.patch(path, {"description": "New details", "priority": "high"})).is_success
    assert (await assignee.post(f"{path}/status", {"status": "in_progress"})).is_success
    assert (await tl.post(f"{path}/status", {"status": "cancelled"})).is_success
    assert (await tl.post(f"{path}/status", {"status": "new"})).is_success
    assert (await tl.post(f"{path}/assignees", {"member_id": str(m_a1b)})).is_success
    assert (await tl.post(f"{path}/assignees/{m_a1b}/remove")).is_success
    response = await tl.post(
        f"{path}/subtasks", {"title": "Call the venue", "assignee_member_ids": [str(m_a1)]}
    )
    subtask_id = response.json()["id"]
    comment = (await assignee.post(f"{path}/comments", {"body": "On it"})).json()
    comment_path = f"{path}/comments/{comment['id']}"
    assert (await assignee.patch(comment_path, {"body": "On it today"})).is_success
    assert (await assignee.post(f"{comment_path}/delete")).is_success
    move = await leader.post(f"{path}/move", {"scope_unit_id": str(world.structure.team_a2)})
    assert move.is_success, move.text

    assert await _actions(db_session) == [
        "task.created",
        "task.updated",
        "task.status_changed",
        "task.cancelled",
        "task.reopened",
        "task.assignee_added",
        "task.assignee_removed",
        "task.created",
        "task_comment.created",
        "task_comment.edited",
        "task_comment.deleted",
        "task.moved",
    ]
    created = await only(db_session, "task.created", task["id"])
    assert created.scope_unit_id == world.structure.team_a1
    assert created.after == {
        "title": "Book the hall",
        "status": "new",
        "priority": None,
        "due_at": None,
        "parent_id": None,
        "assignee_member_ids": [str(m_a1)],
    }
    updated = await only(db_session, "task.updated", task["id"])
    assert updated.before == {"priority": None}
    assert updated.after == {"changed_fields": ["description", "priority"], "priority": "high"}
    status = await only(db_session, "task.status_changed", task["id"])
    assert status.actor_account_id == world.account_ids["m_a1"]
    assert (status.before, status.after) == ({"status": "new"}, {"status": "in_progress"})
    removed = await only(db_session, "task.assignee_removed", task["id"])
    assert removed.after == {"member_id": None, "end_reason": "removed"}
    sub = await only(db_session, "task.created", subtask_id)
    assert sub.after is not None and sub.after["parent_id"] == task["id"]
    comment_record = await only(db_session, "task_comment.created", comment["id"])
    assert comment_record.after == {"task_id": task["id"]}
    moved = await only(db_session, "task.moved", task["id"])
    assert moved.before == {"scope_unit_id": str(world.structure.team_a1)}
    assert moved.after == {
        "scope_unit_id": str(world.structure.team_a2),
        "subtask_count": 1,
        "removed_assignee_member_ids": [str(m_a1)],
    }


async def test_series_operations_are_audited_once_per_series(
    world: World, login: Login, db_session: AsyncSession, frozen_clock: FrozenClock
) -> None:
    tl, leader = await login("tl_a1"), await login("leader")
    first_due = frozen_clock.now + timedelta(days=1)
    response = await tl.post(
        SERIES,
        {
            "scope_unit_id": str(world.structure.team_a1),
            "title": "Weekly report",
            "first_due_at": first_due.isoformat(),
            "ends_at": (first_due + timedelta(weeks=3, hours=1)).isoformat(),
            "assignee_member_ids": [str(world.member_ids["m_a1"])],
            "subtasks": [
                {"title": "Numbers", "assignee_member_ids": [str(world.member_ids["m_a1b"])]}
            ],
        },
    )
    assert response.status_code == 201, response.text
    series_id = response.json()["id"]
    path = f"{SERIES}/{series_id}"
    frozen_clock.advance(timedelta(minutes=1))  # history rows need distinct times
    assert (await tl.patch(path, {"title": "Weekly summary", "description": "Notes"})).is_success
    frozen_clock.advance(timedelta(minutes=1))
    move = await leader.post(f"{path}/move", {"scope_unit_id": str(world.structure.team_a2)})
    assert move.is_success, move.text
    frozen_clock.advance(timedelta(minutes=1))
    assert (await leader.post(f"{path}/stop")).is_success

    # No per-occurrence task records for series-wide operations.
    assert await _actions(db_session) == [
        "task_series.created",
        "task_series.updated",
        "task_series.moved",
        "task_series.stopped",
    ]
    created = await only(db_session, "task_series.created", series_id)
    assert created.after is not None
    assert (created.after["occurrence_count"], created.after["subtask_template_count"]) == (4, 1)
    updated = await only(db_session, "task_series.updated", series_id)
    assert updated.before == {"title": "Weekly report", "subtask_template_count": 1}
    assert updated.after == {
        "title": "Weekly summary",
        "changed_fields": ["description", "title"],
        "subtask_template_count": 1,
        "affected_occurrence_count": 4,
    }
    moved = await only(db_session, "task_series.moved", series_id)
    assert moved.after is not None and moved.after["moved_occurrence_count"] == 4
    assert set(moved.after["removed_assignee_member_ids"]) == {
        str(world.member_ids["m_a1"]),
        str(world.member_ids["m_a1b"]),
    }
    stopped = await only(db_session, "task_series.stopped", series_id)
    assert stopped.after == {"status": "stopped", "cancelled_occurrence_count": 4}


async def test_membership_change_removals_are_audited(
    world: World, login: Login, new_task: Any, db_session: AsyncSession
) -> None:
    tl, admin = await login("tl_a1"), await login("sysadmin")
    task = await new_task(tl, "team_a1", ["m_a1", "m_a1b"])
    m_a1 = world.member_ids["m_a1"]

    response = await admin.post(f"{MEMBERS}/{m_a1}/team", {"team_id": str(world.structure.team_b1)})
    assert response.is_success, response.text

    assert await _actions(db_session) == [
        "task.created",
        "task.assignee_removed",
        "member.team_changed",
    ]
    removed = await only(db_session, "task.assignee_removed", task["id"])
    assert removed.actor_account_id == world.account_ids["sysadmin"]
    assert (removed.before, removed.after) == (
        {"member_id": str(m_a1)},
        {"member_id": None, "end_reason": "out_of_scope"},
    )


# --- Announcements and notifications -------------------------------------------------------------


async def test_announcement_changes_are_audited(
    world: World, login: Login, db_session: AsyncSession
) -> None:
    tl = await login("tl_a1")
    announcement = await draft(tl, world, title="Meeting moved", body="Now at 5pm.")
    path = f"{ANNOUNCEMENTS}/{announcement['id']}"
    assert (await publish(tl, world, announcement["id"], ["m_a1", "m_a1b"])).is_success
    assert (await tl.patch(path, {"body": "Now at 6pm."})).is_success
    assert (await tl.post(f"{path}/withdraw")).is_success

    assert await _actions(db_session) == [
        "announcement.draft_created",
        "announcement.published",
        "announcement.edited",
        "announcement.withdrawn",
    ]
    created = await only(db_session, "announcement.draft_created", announcement["id"])
    assert created.after == {"state": "draft", "version": 1, "title": "Meeting moved"}
    published = await only(db_session, "announcement.published", announcement["id"])
    assert published.after == {"state": "published", "version": 1, "recipient_count": 2}
    edited = await only(db_session, "announcement.edited", announcement["id"])
    assert edited.after == {
        "state": "published",
        "version": 2,
        "title": "Meeting moved",
        "body_changed": True,
    }


async def test_only_notification_preference_changes_are_audited(
    world: World, login: Login, new_task: Any, db_session: AsyncSession
) -> None:
    tl, member = await login("tl_a1"), await login("m_a1")
    await new_task(tl, "team_a1", ["m_a1"])
    account_id = world.account_ids["m_a1"]

    for _ in range(2):  # the second request changes nothing
        response = await member.client.put(
            f"{NOTIFICATIONS}/preferences",
            json={"task_comment": False},
            headers=csrf_headers(member.csrf),
        )
        assert response.status_code == 200, response.text
    notification_id = (await member.get(NOTIFICATIONS)).json()[0]["id"]
    assert (await member.post(f"{NOTIFICATIONS}/{notification_id}/read")).is_success
    assert (await member.post(f"{NOTIFICATIONS}/read-all")).is_success
    assert (await member.post(f"{NOTIFICATIONS}/{notification_id}/delete")).is_success
    assert (await member.post(f"{NOTIFICATIONS}/delete-all")).is_success

    assert await _actions(db_session) == ["task.created", "notification_preferences.updated"]
    record = await only(db_session, "notification_preferences.updated", account_id)
    assert record.actor_account_id == account_id
    assert (record.before, record.after) == ({"task_comment": True}, {"task_comment": False})


# --- Calendar -------------------------------------------------------------------------------------


async def test_calendar_changes_are_audited(
    world: World, login: Login, new_event: NewEvent, db_session: AsyncSession
) -> None:
    tl = await login("tl_a1")
    event = await new_event(tl, "team_a1", ["m_a1"], online_url="https://meet.example/j/1")
    path = f"{EVENTS}/{event['id']}"
    m_a1b = world.member_ids["m_a1b"]
    update = {"title": "Planning v2", "online_url": None, "location_text": "Room 5"}
    assert (await tl.patch(path, update)).is_success
    assert (await tl.post(f"{path}/invitees", {"member_id": str(m_a1b)})).is_success
    assert (await tl.post(f"{path}/invitees/{m_a1b}/remove")).is_success
    assert (await tl.post(f"{path}/cancel")).is_success

    assert await _actions(db_session) == [
        "calendar_event.created",
        "calendar_event.updated",
        "calendar_event.invitee_added",
        "calendar_event.invitee_removed",
        "calendar_event.cancelled",
    ]
    created = await only(db_session, "calendar_event.created", event["id"])
    assert created.scope_unit_id == world.structure.team_a1
    assert created.after is not None and "online_url" not in created.after
    updated = await only(db_session, "calendar_event.updated", event["id"])
    assert updated.before == {"title": "Planning"}
    assert updated.after == {
        "changed_fields": ["title", "location_text", "online_url"],
        "title": "Planning v2",
    }
    removed = await only(db_session, "calendar_event.invitee_removed", event["id"])
    assert removed.before == {"member_id": str(m_a1b)}


# --- Rejected changes ----------------------------------------------------------------------------


async def test_rejected_and_failed_mutations_write_no_records(
    world: World, login: Login, new_task: Any, db_client: AsyncClient, db_session: AsyncSession
) -> None:
    tl, outsider_member, leader = await login("tl_a1"), await login("m_b1"), await login("leader")
    admin = await login("sysadmin")
    task = await new_task(tl, "team_a1", ["m_a1"])
    count = len(await audit_records(db_session))

    rejected = [
        await outsider_member.patch(f"{TASKS}/{task['id']}", {"title": "Hijacked"}),  # 403
        await tl.post(f"{TASKS}/{task['id']}/status", {"status": "new"}),  # 409
        await outsider_member.post(
            UNITS, {"kind": "team", "name": "Rogue", "parent_id": str(world.structure.admin_b)}
        ),  # 403
        await leader.post(f"{UNITS}/{world.structure.kora}/archive"),  # 422
        await admin.post(
            f"{ADMIN}/role-defaults", {"role_key": "member", "permission": "task.view"}
        ),
        await admin.post(f"{ADMIN}/accounts/{uuid.uuid4()}/system-admin"),  # 404
        await tl.post(
            CHANGE_PASSWORD, {"current_password": "not it at all", "new_password": "whatever1"}
        ),  # 400
        await sign_in(db_client, "m_a1", "wrong password!"),  # 401, below the lockout limit
    ]

    assert all(r.status_code >= 400 for r in rejected), [r.status_code for r in rejected]
    assert len(await audit_records(db_session)) == count
