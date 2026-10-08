"""Membership-change notifications for modules that depend on `organization`.

`organization` must not import its dependents, so they register listeners here (at app
composition). Listeners run inside the same transaction as the change, before commit, and see
the new state: e.g. `tasks` removes assignees who became inactive or left a task's scope.
"""

import uuid
from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

MembershipListener = Callable[[AsyncSession, frozenset[uuid.UUID], uuid.UUID], Awaitable[None]]

_listeners: list[MembershipListener] = []


def on_membership_changed(listener: MembershipListener) -> None:
    """Register a listener once (idempotent)."""
    if listener not in _listeners:
        _listeners.append(listener)


async def membership_changed(
    db: AsyncSession, member_ids: frozenset[uuid.UUID], actor_account_id: uuid.UUID
) -> None:
    """Members' status, Team or role (or their Team's position) changed; notify listeners."""
    if not member_ids:
        return
    await db.flush()
    for listener in _listeners:
        await listener(db, member_ids, actor_account_id)
