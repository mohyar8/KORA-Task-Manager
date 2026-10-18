"""League rules. Everyone signed in can read; changing points needs `league.manage`."""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kora_api.access.dependencies import AccessContext
from kora_api.access.evaluation import AccessDeniedError
from kora_api.access.permissions import Permission
from kora_api.audit import service as audit
from kora_api.core import clock
from kora_api.league import audit_actions
from kora_api.league.models import LeagueEntry, LeagueSettings
from kora_api.organization import queries as org
from kora_api.organization.constants import PMO_UNIT_ID

MANAGE = Permission.LEAGUE_MANAGE
# One audit resource for the whole league.
LEAGUE_RESOURCE_ID = uuid.UUID("6b0a0000-0000-4000-8000-0000000000a1")
MAX_POINTS = 9999


class InvalidLeagueError(Exception):
    """The update breaks a league rule (422)."""


@dataclass(frozen=True)
class Standing:
    rank: int
    team_id: uuid.UUID
    team_name: str
    administration_name: str | None
    points: int


@dataclass(frozen=True)
class League:
    round_title: str | None
    updated_at: datetime | None
    standings: list[Standing]


async def get_league(db: AsyncSession) -> League:
    """Every active Team, best first (points, then name). Teams without an entry have 0."""
    units = await org.current_units(db)
    points = {e.team_id: e.points for e in await db.scalars(select(LeagueEntry))}
    settings = await db.get(LeagueSettings, 1)
    teams = [u for u in units.values() if u.kind == "team" and u.active]
    ordered = sorted(teams, key=lambda u: (-points.get(u.id, 0), u.name))
    standings = [
        Standing(
            rank=i + 1,
            team_id=u.id,
            team_name=u.name,
            administration_name=next(
                (
                    units[a].name
                    for a in org.unit_chain(u.id, units)
                    if units[a].kind == "administration"
                ),
                None,
            ),
            points=points.get(u.id, 0),
        )
        for i, u in enumerate(ordered)
    ]
    return League(
        settings.round_title if settings else None,
        settings.updated_at if settings else None,
        standings,
    )


async def update_league(
    db: AsyncSession,
    access: AccessContext,
    *,
    round_title: str | None,
    points: dict[uuid.UUID, int],
) -> League:
    if not access.snapshot.units_with(MANAGE):
        raise AccessDeniedError(MANAGE, None)
    units = await org.current_units(db)
    for team_id, value in points.items():
        unit = units.get(team_id)
        if unit is None or unit.kind != "team" or not unit.active:
            raise InvalidLeagueError(f"Unknown or inactive Team: {team_id}.")
        if not 0 <= value <= MAX_POINTS:
            raise InvalidLeagueError(f"Points must be between 0 and {MAX_POINTS}.")
    now = clock.utcnow()
    existing = {e.team_id: e for e in await db.scalars(select(LeagueEntry))}
    changed: list[uuid.UUID] = []
    for team_id, value in points.items():
        entry = existing.get(team_id)
        if entry is None:
            if value == 0:
                continue
            db.add(
                LeagueEntry(
                    team_id=team_id,
                    points=value,
                    updated_at=now,
                    updated_by_account_id=access.account.id,
                )
            )
        elif entry.points != value:
            entry.points = value
            entry.updated_at = now
            entry.updated_by_account_id = access.account.id
        else:
            continue
        changed.append(team_id)
    settings = await db.get(LeagueSettings, 1)
    title = round_title.strip() if round_title else None
    title_changed = (settings.round_title if settings else None) != title
    if title_changed or settings is None:
        if settings is None:
            settings = LeagueSettings(id=1)
            db.add(settings)
        settings.round_title = title
    if changed or title_changed:
        settings.updated_at = now
        settings.updated_by_account_id = access.account.id
        audit.record(
            db,
            audit_actions.LEAGUE_UPDATED,
            actor_account_id=access.account.id,
            resource_id=LEAGUE_RESOURCE_ID,
            scope_unit_id=PMO_UNIT_ID,
            after={
                "round_title": title,
                "changed_team_ids": sorted(changed, key=str),
                "points": [f"{t}:{points[t]}" for t in sorted(changed, key=str)],
            },
        )
    await db.commit()
    return await get_league(db)
