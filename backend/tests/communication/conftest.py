"""Announcement and notification tests reuse the populated organization from the task tests."""

from typing import Any

from tests.tasks.conftest import Api, World
from tests.tasks.conftest import login as login  # re-exported fixture
from tests.tasks.conftest import new_task as new_task  # re-exported fixture
from tests.tasks.conftest import world as world  # re-exported fixture

ANNOUNCEMENTS = "/api/v1/announcements"
NOTIFICATIONS = "/api/v1/notifications"


async def draft(api: Api, org: World, scope: str = "team_a1", **fields: Any) -> dict[str, Any]:
    response = await api.post(
        ANNOUNCEMENTS,
        {
            "scope_unit_id": str(org.unit(scope)),
            "title": fields.get("title", "Meeting moved"),
            "body": fields.get("body", "The meeting is now at 5pm."),
        },
    )
    assert response.status_code == 201, response.text
    result: dict[str, Any] = response.json()
    return result


async def publish(api: Api, org: World, announcement_id: str, recipients: list[str]) -> Any:
    return await api.post(
        f"{ANNOUNCEMENTS}/{announcement_id}/publish",
        {"recipient_member_ids": [str(org.member_ids[r]) for r in recipients]},
    )


async def notifications_of(api: Api) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = (await api.get(NOTIFICATIONS)).json()
    return result
