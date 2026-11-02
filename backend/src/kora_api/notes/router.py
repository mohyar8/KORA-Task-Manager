from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from kora_api.access.dependencies import CurrentAccount
from kora_api.core.database import DbSession
from kora_api.core.errors import AUTHENTICATED, errors
from kora_api.notes import service
from kora_api.notes.models import MAX_LENGTH

router = APIRouter(prefix="/me/note", tags=["notes"], responses=AUTHENTICATED)


class NoteResponse(BaseModel):
    body: str
    # 0 while the account has never saved a note.
    version: int
    updated_at: datetime | None


class SaveNoteRequest(BaseModel):
    # Whitespace is kept: the note is free-form text with its own line breaks.
    body: Annotated[str, Field(max_length=MAX_LENGTH)]
    # The version this edit is based on (0 for the first save).
    version: Annotated[int, Field(ge=0)]


def _response(note: service.Note) -> NoteResponse:
    return NoteResponse(body=note.body, version=note.version, updated_at=note.updated_at)


@router.get("")
async def get_note(account: CurrentAccount, db: DbSession) -> NoteResponse:
    """The caller's own private note. Nobody else can read it, including System Admins."""
    return _response(await service.get_note(db, account.id))


@router.put("", responses=errors(409, 422))
async def save_note(body: SaveNoteRequest, account: CurrentAccount, db: DbSession) -> NoteResponse:
    """Save the note. 409 when it was saved elsewhere since `version` was read; the client then
    fetches the newer note instead of overwriting it silently."""
    try:
        return _response(await service.save_note(db, account.id, body.body, body.version))
    except service.NoteConflictError:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "The note was changed elsewhere. Reload it first."
        ) from None
