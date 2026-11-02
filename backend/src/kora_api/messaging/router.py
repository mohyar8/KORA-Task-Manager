import uuid
from collections.abc import Awaitable
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import BaseModel, Field, StringConstraints

from kora_api.access.dependencies import CurrentAccess
from kora_api.core.database import DbSession
from kora_api.core.errors import AUTHENTICATED, errors
from kora_api.messaging import service
from kora_api.messaging.models import MAX_BODY, ConversationKind, Message

router = APIRouter(prefix="/chat", tags=["chat"], responses=AUTHENTICATED)

Body = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_BODY)]


class MessageRequest(BaseModel):
    body: Body


class DirectRequest(BaseModel):
    member_id: uuid.UUID


class ReadRequest(BaseModel):
    # Default: everything in the conversation.
    last_read_message_id: Annotated[int, Field(ge=1)] | None = None


class MessageResponse(BaseModel):
    id: int
    conversation_id: uuid.UUID
    author_member_id: uuid.UUID
    # Empty once deleted.
    body: str
    created_at: datetime
    edited_at: datetime | None
    deleted: bool


class ConversationResponse(BaseModel):
    id: uuid.UUID
    kind: ConversationKind
    # For a unit channel.
    unit_id: uuid.UUID | None
    # For a direct chat: the other person.
    other_member_id: uuid.UUID | None
    last_message: MessageResponse | None
    unread: int


def _message(m: Message) -> MessageResponse:
    return MessageResponse(
        id=m.id,
        conversation_id=m.conversation_id,
        author_member_id=m.author_member_id,
        body=m.body,
        created_at=m.created_at,
        edited_at=m.edited_at,
        deleted=m.deleted_at is not None,
    )


def _conversation(view: service.ConversationView, me: uuid.UUID) -> ConversationResponse:
    c = view.conversation
    other = None
    if c.kind == ConversationKind.DIRECT:
        other = c.direct_b_id if c.direct_a_id == me else c.direct_a_id
    return ConversationResponse(
        id=c.id,
        kind=c.kind,
        unit_id=c.unit_id,
        other_member_id=other,
        last_message=_message(view.last_message) if view.last_message else None,
        unread=view.unread,
    )


async def _call[T](call: Awaitable[T]) -> T:
    try:
        return await call
    except service.ChatNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found.") from None
    except service.InvalidChatError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    except service.ChatConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None
    except service.RateLimitedError:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "Too many messages; slow down."
        ) from None


@router.get("/conversations")
async def list_conversations(access: CurrentAccess, db: DbSession) -> list[ConversationResponse]:
    """The caller's channels (organization, their Team, Administration, PMO) and direct chats,
    newest activity first, with the last message and the unread count."""
    actor = await service.actor_for(db, access)
    views = await service.list_conversations(db, actor)
    return [_conversation(v, actor.member_id) for v in views]


@router.post("/conversations/direct", responses=errors(422))
async def open_direct(
    body: DirectRequest, access: CurrentAccess, db: DbSession
) -> ConversationResponse:
    """The direct chat with another active Member (created on first use)."""
    actor = await service.actor_for(db, access)
    view = await _call(service.open_direct(db, actor, body.member_id))
    return _conversation(view, actor.member_id)


@router.get("/conversations/{conversation_id}/messages", responses=errors(404))
async def list_messages(
    conversation_id: uuid.UUID,
    access: CurrentAccess,
    db: DbSession,
    after: Annotated[int | None, Query(ge=0)] = None,
    before: Annotated[int | None, Query(ge=1)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[MessageResponse]:
    """Oldest first. No cursor: the latest `limit`. `after=<id>`: newer than the id (polling).
    `before=<id>`: the page before the id (history)."""
    actor = await service.actor_for(db, access)
    rows = await _call(
        service.list_messages(db, actor, conversation_id, after=after, before=before, limit=limit)
    )
    return [_message(m) for m in rows]


@router.post(
    "/conversations/{conversation_id}/messages",
    status_code=status.HTTP_201_CREATED,
    responses=errors(404, (429, "Too many messages in a minute."), 422),
)
async def send_message(
    conversation_id: uuid.UUID, body: MessageRequest, access: CurrentAccess, db: DbSession
) -> MessageResponse:
    actor = await service.actor_for(db, access)
    return _message(await _call(service.send_message(db, actor, conversation_id, body.body)))


@router.post(
    "/conversations/{conversation_id}/read",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=errors(404),
)
async def mark_read(
    conversation_id: uuid.UUID, body: ReadRequest, access: CurrentAccess, db: DbSession
) -> Response:
    actor = await service.actor_for(db, access)
    await _call(service.mark_read(db, actor, conversation_id, body.last_read_message_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/messages/{message_id}", responses=errors(404, 409, 422))
async def edit_message(
    message_id: int, body: MessageRequest, access: CurrentAccess, db: DbSession
) -> MessageResponse:
    """Only the author edits their own message."""
    actor = await service.actor_for(db, access)
    return _message(await _call(service.edit_message(db, actor, message_id, body.body)))


@router.delete("/messages/{message_id}", responses=errors(404))
async def delete_message(message_id: int, access: CurrentAccess, db: DbSession) -> MessageResponse:
    """The author, or a holder of `chat.moderate` at the channel's unit. The text is blanked."""
    actor = await service.actor_for(db, access)
    return _message(await _call(service.delete_message(db, actor, message_id)))
