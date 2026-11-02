"""One call for the sidebar badges, instead of polling four endpoints. Counts only."""

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import and_, exists, func, select

from kora_api.access.dependencies import CurrentAccess
from kora_api.announcements.models import (
    Announcement,
    AnnouncementRead,
    AnnouncementRecipient,
    AnnouncementState,
)
from kora_api.core.database import DbSession
from kora_api.core.errors import AUTHENTICATED
from kora_api.messaging import service as chat
from kora_api.notifications.models import Notification
from kora_api.organization import queries as org
from kora_api.task_requests.models import RequestStatus, TaskRequest
from kora_api.task_requests.service import RESPOND
from kora_api.tasks.constants import OPEN_STATUSES, TaskKind
from kora_api.tasks.models import Task, TaskAssignment

router = APIRouter(prefix="/me/summary", tags=["summary"], responses=AUTHENTICATED)


class SummaryResponse(BaseModel):
    notifications_unread: int
    # Unread messages across the caller's chats; 0 for an account that is not an active Member.
    chat_unread: int
    # Task requests waiting for the caller's answer (as the target Administration's manager).
    requests_pending: int
    # Published announcements sent to the caller that they have not opened in their current version.
    announcements_unread: int
    # Open review tasks assigned to the caller.
    reviews_open: int


@router.get("")
async def get_summary(access: CurrentAccess, db: DbSession) -> SummaryResponse:
    """Badge counts for the signed-in account. Counts only; no content."""
    account_id = access.account.id
    notifications_unread = await db.scalar(
        select(func.count())
        .select_from(Notification)
        .where(
            Notification.recipient_account_id == account_id,
            Notification.read_at.is_(None),
            Notification.deleted_at.is_(None),
        )
    )
    announcements_unread = await db.scalar(
        select(func.count())
        .select_from(Announcement)
        .join(
            AnnouncementRecipient,
            and_(
                AnnouncementRecipient.announcement_id == Announcement.id,
                AnnouncementRecipient.account_id == account_id,
            ),
        )
        .where(
            Announcement.state == AnnouncementState.PUBLISHED,
            ~exists().where(
                AnnouncementRead.announcement_id == Announcement.id,
                AnnouncementRead.account_id == account_id,
                AnnouncementRead.version == Announcement.current_version,
            ),
        )
    )
    requests_pending = await db.scalar(
        select(func.count())
        .select_from(TaskRequest)
        .where(
            TaskRequest.status == RequestStatus.PENDING,
            TaskRequest.to_unit_id.in_(access.snapshot.units_with(RESPOND)),
        )
    )
    chat_unread = 0
    reviews_open = 0
    position = await org.member_for_account(db, account_id)
    if position is not None and position.active:
        actor = chat.ChatActor(account_id, position, access.snapshot)
        chat_unread = sum(v.unread for v in await chat.list_conversations(db, actor))
        reviews_open = (
            await db.scalar(
                select(func.count())
                .select_from(Task)
                .join(TaskAssignment, TaskAssignment.task_id == Task.id)
                .where(
                    Task.kind == TaskKind.REVIEW,
                    Task.status.in_(OPEN_STATUSES),
                    TaskAssignment.member_id == position.member_id,
                    TaskAssignment.valid_to.is_(None),
                )
            )
            or 0
        )
    return SummaryResponse(
        notifications_unread=notifications_unread or 0,
        chat_unread=chat_unread,
        requests_pending=requests_pending or 0,
        announcements_unread=announcements_unread or 0,
        reviews_open=reviews_open,
    )
