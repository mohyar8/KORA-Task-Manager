"""File rules for tasks.

- Who sees the files: whoever can view the task.
- `brief` files: added by the creator or a scoped manager (`can_administer`).
- `delivery` files: added by an assignee.
- Both only while the task is open (new / in progress); after that the files are read-only.
- Removing: the uploader, or whoever administers the task; also only while the task is open.
Flow: `start_upload` (validates, returns a presigned PUT URL) -> the client uploads straight to the
bucket -> `complete_upload` (checks the stored size) makes the file visible.
"""

import uuid
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from kora_api.access.evaluation import AccessDeniedError
from kora_api.audit import service as audit
from kora_api.core import clock
from kora_api.core.storage import ObjectStorage
from kora_api.notifications import service as notifications
from kora_api.notifications.models import NotificationCategory as Category
from kora_api.organization import queries as org
from kora_api.task_files import audit_actions
from kora_api.task_files.models import FileKind, FileStatus, TaskFile
from kora_api.tasks import service as tasks
from kora_api.tasks.constants import OPEN_STATUSES, TaskKind
from kora_api.tasks.models import Task
from kora_api.tasks.service import TaskActor

MAX_SIZE = 10 * 1024 * 1024
MAX_PER_KIND = 10
PENDING_LIFETIME = timedelta(hours=1)
BLOCKED_EXTENSIONS = frozenset(
    {"exe", "bat", "cmd", "com", "scr", "msi", "vbs", "ps1", "sh", "js", "jar", "dll"}
)


class FileMissingError(Exception):
    pass


class InvalidFileError(Exception):
    """The file breaks a rule (422)."""


class FileConflictError(Exception):
    """The state prevents the operation (409)."""


class StorageUnavailableError(Exception):
    """Object storage is not configured (503)."""


@dataclass(frozen=True)
class UploadTicket:
    file: TaskFile
    url: str


def clean_name(name: str) -> str:
    """Only the file's own name: no folders, no control characters."""
    last = name.replace("\\", "/").rsplit("/", 1)[-1]
    return "".join(ch for ch in last if ch.isprintable()).strip()[:200]


def _require_storage(storage: ObjectStorage | None) -> ObjectStorage:
    if storage is None:
        raise StorageUnavailableError
    return storage


async def _open_task(db: AsyncSession, actor: TaskActor, task_id: uuid.UUID) -> tasks.TaskView:
    view = await tasks.load_visible(db, actor, task_id)
    if view.task.kind == TaskKind.REVIEW:
        raise FileConflictError("Review tasks have no files.")
    return view


def _require_open(task: Task) -> None:
    if task.status not in OPEN_STATUSES:
        raise FileConflictError("Files can only change while the task is open.")


async def start_upload(
    db: AsyncSession,
    actor: TaskActor,
    storage: ObjectStorage | None,
    task_id: uuid.UUID,
    *,
    kind: FileKind,
    name: str,
    size: int,
    content_type: str | None,
) -> UploadTicket:
    store = _require_storage(storage)
    view = await _open_task(db, actor, task_id)
    task = view.task
    allowed = (
        tasks.can_administer(actor, task)
        if kind == FileKind.BRIEF
        else tasks.is_assignee(actor, view.assignee_member_ids)
    )
    if actor.member_id is None or not allowed:
        raise AccessDeniedError(tasks.MANAGE, task.scope_unit_id)
    _require_open(task)
    cleaned = clean_name(name)
    extension = cleaned.rsplit(".", 1)[-1].lower() if "." in cleaned else ""
    if not cleaned:
        raise InvalidFileError("The file needs a name.")
    if extension in BLOCKED_EXTENSIONS:
        raise InvalidFileError(f"Files of type .{extension} are not allowed.")
    if not 0 < size <= MAX_SIZE:
        raise InvalidFileError("A file must be between 1 byte and 10 MB.")
    now = clock.utcnow()
    count = await db.scalar(
        select(func.count())
        .select_from(TaskFile)
        .where(
            TaskFile.task_id == task_id,
            TaskFile.kind == kind,
            TaskFile.deleted_at.is_(None),
            (TaskFile.status == FileStatus.READY) | (TaskFile.created_at > now - PENDING_LIFETIME),
        )
    )
    if (count or 0) >= MAX_PER_KIND:
        raise InvalidFileError(f"At most {MAX_PER_KIND} files per section.")
    file_id = uuid.uuid4()
    file = TaskFile(
        id=file_id,
        task_id=task_id,
        kind=kind,
        name=cleaned,
        size=size,
        content_type=(content_type or None) and content_type[:100],
        storage_key=f"tasks/{task_id}/{file_id}",
        uploaded_by_member_id=actor.member_id,
        status=FileStatus.PENDING,
        created_at=now,
    )
    db.add(file)
    await db.commit()
    return UploadTicket(file, store.upload_url(file.storage_key))


async def _file(db: AsyncSession, task_id: uuid.UUID, file_id: uuid.UUID) -> TaskFile:
    file = await db.get(TaskFile, file_id)
    if file is None or file.task_id != task_id or file.deleted_at is not None:
        raise FileMissingError
    return file


async def complete_upload(
    db: AsyncSession,
    actor: TaskActor,
    storage: ObjectStorage | None,
    task_id: uuid.UUID,
    file_id: uuid.UUID,
) -> TaskFile:
    store = _require_storage(storage)
    view = await _open_task(db, actor, task_id)
    file = await _file(db, task_id, file_id)
    if actor.member_id != file.uploaded_by_member_id:
        raise AccessDeniedError(tasks.MANAGE, view.task.scope_unit_id)
    if file.status == FileStatus.READY:
        return file  # idempotent
    stored = await store.size_of(file.storage_key)
    if stored is None:
        raise FileConflictError("The file has not been uploaded yet.")
    if stored != file.size or stored > MAX_SIZE:
        file.deleted_at = clock.utcnow()
        await db.commit()
        raise InvalidFileError("The uploaded file does not match its declared size.")
    file.status = FileStatus.READY
    audit.record(
        db,
        audit_actions.FILE_ADDED,
        actor_account_id=actor.account_id,
        resource_id=file.id,
        scope_unit_id=view.task.scope_unit_id,
        after={"task_id": task_id, "kind": file.kind.value, "size": file.size},
    )
    # Tell the people running the task: the creator (for a delivery) or the assignees (a brief).
    recipients = {view.task.created_by_account_id}
    if file.kind == FileKind.BRIEF:
        positions = await org.member_positions(db, view.assignee_member_ids)
        recipients = {p.account_id for p in positions.values()}
    await notifications.notify(
        db,
        recipient_account_ids=recipients,
        actor_account_id=actor.account_id,
        category=Category.TASK_UPDATE,
        source_type=tasks.NOTIFICATION_SOURCE,
        source_id=task_id,
        kind="delivery_added" if file.kind == FileKind.DELIVERY else "file_added",
        summary=view.task.title,
    )
    await db.commit()
    return file


async def list_files(db: AsyncSession, actor: TaskActor, task_id: uuid.UUID) -> list[TaskFile]:
    await tasks.load_visible(db, actor, task_id)
    return list(
        await db.scalars(
            select(TaskFile)
            .where(
                TaskFile.task_id == task_id,
                TaskFile.status == FileStatus.READY,
                TaskFile.deleted_at.is_(None),
            )
            .order_by(TaskFile.created_at)
        )
    )


async def download_url(
    db: AsyncSession,
    actor: TaskActor,
    storage: ObjectStorage | None,
    task_id: uuid.UUID,
    file_id: uuid.UUID,
) -> str:
    store = _require_storage(storage)
    await tasks.load_visible(db, actor, task_id)
    file = await _file(db, task_id, file_id)
    if file.status != FileStatus.READY:
        raise FileMissingError
    return store.download_url(file.storage_key, filename=file.name)


async def remove_file(
    db: AsyncSession, actor: TaskActor, task_id: uuid.UUID, file_id: uuid.UUID
) -> None:
    view = await _open_task(db, actor, task_id)
    file = await _file(db, task_id, file_id)
    is_owner = actor.member_id == file.uploaded_by_member_id
    if not (is_owner or tasks.can_administer(actor, view.task)):
        raise AccessDeniedError(tasks.MANAGE, view.task.scope_unit_id)
    _require_open(view.task)
    file.deleted_at = clock.utcnow()
    if file.status == FileStatus.READY:
        audit.record(
            db,
            audit_actions.FILE_REMOVED,
            actor_account_id=actor.account_id,
            resource_id=file.id,
            scope_unit_id=view.task.scope_unit_id,
            after={"task_id": task_id, "kind": file.kind.value, "size": file.size},
        )
    await db.commit()
