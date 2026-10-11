"""Calendar tests reuse the populated organization from the task tests."""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from tests.tasks.conftest import Api, World
from tests.tasks.conftest import login as login  # re-exported fixture
from tests.tasks.conftest import new_task as new_task  # re-exported fixture
from tests.tasks.conftest import world as world  # re-exported fixture

EVENTS = "/api/v1/calendar/events"
CALENDAR = "/api/v1/calendar"
START = datetime(2030, 3, 10, 9, 0, tzinfo=UTC)

NewEvent = Callable[..., Awaitable[dict[str, Any]]]


def event_body(org: World, scope: str, invitees: list[str], **fields: Any) -> dict[str, Any]:
    return {
        "type": "meeting",
        "title": "Planning",
        "starts_at": START.isoformat(),
        "ends_at": (START + timedelta(hours=1)).isoformat(),
        "scope_unit_id": str(org.unit(scope)),
        "invitee_member_ids": [str(org.member_ids[i]) for i in invitees],
        **fields,
    }


@pytest.fixture
def new_event(world: World) -> NewEvent:
    async def _create(api: Api, scope: str, invitees: list[str], **fields: Any) -> dict[str, Any]:
        response = await api.post(EVENTS, event_body(world, scope, invitees, **fields))
        assert response.status_code == 201, response.text
        result: dict[str, Any] = response.json()
        return result

    return _create
