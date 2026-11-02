import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from kora_api.core import clock
from kora_api.notes.models import PrivateNote


class NoteConflictError(Exception):
    """The note was saved elsewhere since the caller read it."""


@dataclass(frozen=True)
class Note:
    body: str
    version: int
    updated_at: datetime | None


async def get_note(db: AsyncSession, account_id: uuid.UUID) -> Note:
    row = await db.scalar(select(PrivateNote).where(PrivateNote.account_id == account_id))
    return Note(row.body, row.version, row.updated_at) if row else Note("", 0, None)


async def save_note(db: AsyncSession, account_id: uuid.UUID, body: str, version: int) -> Note:
    """Save when `version` is the one the caller last read (0 = no note yet), else conflict."""
    now = clock.utcnow()
    if version == 0:
        db.add(PrivateNote(account_id=account_id, body=body, version=1, updated_at=now))
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            raise NoteConflictError from None
        return Note(body, 1, now)
    result = await db.execute(
        update(PrivateNote)
        .where(PrivateNote.account_id == account_id, PrivateNote.version == version)
        .values(body=body, version=version + 1, updated_at=now)
    )
    if result.rowcount == 0:  # type: ignore[attr-defined]
        await db.rollback()
        raise NoteConflictError
    await db.commit()
    return Note(body, version + 1, now)
