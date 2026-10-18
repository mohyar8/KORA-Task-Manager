import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, StringConstraints

from kora_api.access.dependencies import CurrentAccess
from kora_api.core.database import DbSession
from kora_api.core.errors import AUTHENTICATED, errors
from kora_api.league import service

router = APIRouter(prefix="/league", tags=["league"], responses=AUTHENTICATED)

RoundTitle = Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)]


class StandingResponse(BaseModel):
    rank: int
    team_id: uuid.UUID
    team_name: str
    administration_name: str | None
    points: int


class LeagueResponse(BaseModel):
    round_title: str | None
    updated_at: datetime | None
    standings: list[StandingResponse]


class TeamPoints(BaseModel):
    team_id: uuid.UUID
    points: Annotated[int, Field(ge=0, le=service.MAX_POINTS)]


class UpdateLeagueRequest(BaseModel):
    round_title: RoundTitle | None = None
    points: list[TeamPoints]


def _response(league: service.League) -> LeagueResponse:
    return LeagueResponse(
        round_title=league.round_title,
        updated_at=league.updated_at,
        standings=[StandingResponse(**vars(s)) for s in league.standings],
    )


@router.get("")
async def get_league(access: CurrentAccess, db: DbSession) -> LeagueResponse:
    """The standings of every active Team. Every signed-in account may read them."""
    del access  # authentication only
    return _response(await service.get_league(db))


@router.put("", responses=errors(422))
async def update_league(
    body: UpdateLeagueRequest, access: CurrentAccess, db: DbSession
) -> LeagueResponse:
    """Set points and the round title (`league.manage`: the PMO Leader by default)."""
    try:
        league = await service.update_league(
            db,
            access,
            round_title=body.round_title,
            points={p.team_id: p.points for p in body.points},
        )
    except service.InvalidLeagueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    return _response(league)
