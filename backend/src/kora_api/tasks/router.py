import uuid
from collections.abc import Awaitable
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from kora_api.access.dependencies import CurrentAccess
from kora_api.core.database import DbSession
from kora_api.tasks import series as series_service
from kora_api.tasks import service
from kora_api.tasks.constants import TaskStatus
from kora_api.tasks.models import TaskComment
from kora_api.tasks.schemas import (
    AssigneeRequest,
    CommentRequest,
    CommentResponse,
    CreateSeriesRequest,
    CreateSubtaskRequest,
    CreateTaskRequest,
    MoveTaskRequest,
    SeriesResponse,
    StatusRequest,
    TaskEventResponse,
    TaskFieldsRequest,
    TaskResponse,
    UpdateSeriesRequest,
    UpdateTaskRequest,
)

tasks_router = APIRouter(prefix="/tasks", tags=["tasks"])
series_router = APIRouter(prefix="/task-series", tags=["tasks"])


async def _call[T](call: Awaitable[T]) -> T:
    try:
        return await call
    except service.TaskNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found.") from None
    except service.InvalidTaskError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    except service.TaskConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None


def _fields(body: TaskFieldsRequest) -> service.TaskFields:
    return service.TaskFields(body.title, body.description, body.priority, body.due_at)


# --- Tasks --------------------------------------------------------------------------------------


@tasks_router.get("")
async def list_tasks(
    access: CurrentAccess,
    db: DbSession,
    status_filter: Annotated[TaskStatus | None, Query(alias="status")] = None,
    scope_unit_id: uuid.UUID | None = None,
) -> list[TaskResponse]:
    """Visible top-level tasks; tasks the caller cannot view are omitted."""
    actor = await service.actor_for(db, access)
    views = await service.list_tasks(db, actor, status=status_filter, scope_unit_id=scope_unit_id)
    return [_task(view) for view in views]


@tasks_router.post("", status_code=status.HTTP_201_CREATED)
async def create_task(
    body: CreateTaskRequest, access: CurrentAccess, db: DbSession
) -> TaskResponse:
    actor = await service.actor_for(db, access)
    view = await _call(
        service.create_task(
            db,
            actor,
            scope_unit_id=body.scope_unit_id,
            fields=_fields(body),
            assignee_member_ids=body.assignee_member_ids,
        )
    )
    return _task(view)


@tasks_router.get("/{task_id}")
async def get_task(task_id: uuid.UUID, access: CurrentAccess, db: DbSession) -> TaskResponse:
    actor = await service.actor_for(db, access)
    return _task(await _call(service.get_task(db, actor, task_id)))


@tasks_router.patch("/{task_id}")
async def update_task(
    task_id: uuid.UUID, body: UpdateTaskRequest, access: CurrentAccess, db: DbSession
) -> TaskResponse:
    actor = await service.actor_for(db, access)
    return _task(await _call(service.update_task(db, actor, task_id, body.changes())))


@tasks_router.post("/{task_id}/status")
async def change_status(
    task_id: uuid.UUID, body: StatusRequest, access: CurrentAccess, db: DbSession
) -> TaskResponse:
    actor = await service.actor_for(db, access)
    return _task(await _call(service.change_status(db, actor, task_id, body.status)))


@tasks_router.post("/{task_id}/assignees")
async def add_assignee(
    task_id: uuid.UUID, body: AssigneeRequest, access: CurrentAccess, db: DbSession
) -> TaskResponse:
    actor = await service.actor_for(db, access)
    return _task(await _call(service.add_assignee(db, actor, task_id, body.member_id)))


@tasks_router.post("/{task_id}/assignees/{member_id}/remove")
async def remove_assignee(
    task_id: uuid.UUID, member_id: uuid.UUID, access: CurrentAccess, db: DbSession
) -> TaskResponse:
    actor = await service.actor_for(db, access)
    return _task(await _call(service.remove_assignee(db, actor, task_id, member_id)))


@tasks_router.post("/{task_id}/move")
async def move_task(
    task_id: uuid.UUID, body: MoveTaskRequest, access: CurrentAccess, db: DbSession
) -> TaskResponse:
    actor = await service.actor_for(db, access)
    return _task(await _call(service.move_task(db, actor, task_id, body.scope_unit_id)))


@tasks_router.get("/{task_id}/subtasks")
async def list_subtasks(
    task_id: uuid.UUID, access: CurrentAccess, db: DbSession
) -> list[TaskResponse]:
    actor = await service.actor_for(db, access)
    await _call(service.get_task(db, actor, task_id))
    return [_task(view) for view in await service.list_tasks(db, actor, parent_id=task_id)]


@tasks_router.post("/{task_id}/subtasks", status_code=status.HTTP_201_CREATED)
async def create_subtask(
    task_id: uuid.UUID, body: CreateSubtaskRequest, access: CurrentAccess, db: DbSession
) -> TaskResponse:
    actor = await service.actor_for(db, access)
    view = await _call(
        service.create_subtask(
            db,
            actor,
            task_id,
            fields=_fields(body),
            assignee_member_ids=body.assignee_member_ids,
        )
    )
    return _task(view)


@tasks_router.get("/{task_id}/history")
async def task_history(
    task_id: uuid.UUID, access: CurrentAccess, db: DbSession
) -> list[TaskEventResponse]:
    actor = await service.actor_for(db, access)
    return [
        TaskEventResponse(
            kind=event.kind,
            actor_account_id=event.actor_account_id,
            data=event.data,
            created_at=event.created_at,
        )
        for event in await _call(service.history(db, actor, task_id))
    ]


# --- Comments -----------------------------------------------------------------------------------


@tasks_router.get("/{task_id}/comments")
async def list_comments(
    task_id: uuid.UUID, access: CurrentAccess, db: DbSession
) -> list[CommentResponse]:
    actor = await service.actor_for(db, access)
    return [_comment(c) for c in await _call(service.list_comments(db, actor, task_id))]


@tasks_router.post("/{task_id}/comments", status_code=status.HTTP_201_CREATED)
async def add_comment(
    task_id: uuid.UUID, body: CommentRequest, access: CurrentAccess, db: DbSession
) -> CommentResponse:
    actor = await service.actor_for(db, access)
    return _comment(await _call(service.add_comment(db, actor, task_id, body.body)))


@tasks_router.patch("/{task_id}/comments/{comment_id}")
async def edit_comment(
    task_id: uuid.UUID,
    comment_id: uuid.UUID,
    body: CommentRequest,
    access: CurrentAccess,
    db: DbSession,
) -> CommentResponse:
    actor = await service.actor_for(db, access)
    return _comment(await _call(service.edit_comment(db, actor, task_id, comment_id, body.body)))


@tasks_router.post("/{task_id}/comments/{comment_id}/delete")
async def delete_comment(
    task_id: uuid.UUID, comment_id: uuid.UUID, access: CurrentAccess, db: DbSession
) -> CommentResponse:
    actor = await service.actor_for(db, access)
    return _comment(await _call(service.delete_comment(db, actor, task_id, comment_id)))


# --- Weekly series ------------------------------------------------------------------------------


@series_router.post("", status_code=status.HTTP_201_CREATED)
async def create_series(
    body: CreateSeriesRequest, access: CurrentAccess, db: DbSession
) -> SeriesResponse:
    actor = await service.actor_for(db, access)
    view = await _call(
        series_service.create_series(
            db,
            actor,
            scope_unit_id=body.scope_unit_id,
            fields=service.TaskFields(
                body.title, body.description, body.priority, body.first_due_at
            ),
            ends_at=body.ends_at,
            assignee_member_ids=body.assignee_member_ids,
            subtasks=[
                series_service.SubtaskTemplate(
                    title=s.title,
                    assignee_member_ids=tuple(s.assignee_member_ids),
                    description=s.description,
                    priority=s.priority,
                )
                for s in body.subtasks
            ],
        )
    )
    return _series(view)


@series_router.get("/{series_id}")
async def get_series(series_id: uuid.UUID, access: CurrentAccess, db: DbSession) -> SeriesResponse:
    actor = await service.actor_for(db, access)
    return _series(await _call(series_service.get_series(db, actor, series_id)))


@series_router.patch("/{series_id}")
async def update_series(
    series_id: uuid.UUID, body: UpdateSeriesRequest, access: CurrentAccess, db: DbSession
) -> SeriesResponse:
    actor = await service.actor_for(db, access)
    subtasks = None
    if body.subtasks is not None:
        subtasks = [
            series_service.SubtaskTemplate(
                title=s.title,
                assignee_member_ids=tuple(s.assignee_member_ids),
                description=s.description,
                priority=s.priority,
                key=s.key,
            )
            for s in body.subtasks
        ]
    view = await _call(
        series_service.update_series(
            db, actor, series_id, body.changes(), body.assignee_member_ids, subtasks
        )
    )
    return _series(view)


@series_router.post("/{series_id}/move")
async def move_series(
    series_id: uuid.UUID, body: MoveTaskRequest, access: CurrentAccess, db: DbSession
) -> SeriesResponse:
    actor = await service.actor_for(db, access)
    return _series(
        await _call(series_service.move_series(db, actor, series_id, body.scope_unit_id))
    )


@series_router.post("/{series_id}/stop")
async def stop_series(series_id: uuid.UUID, access: CurrentAccess, db: DbSession) -> SeriesResponse:
    actor = await service.actor_for(db, access)
    return _series(await _call(series_service.stop_series(db, actor, series_id)))


# --- Mapping ------------------------------------------------------------------------------------


def _task(view: service.TaskView) -> TaskResponse:
    t = view.task
    return TaskResponse(
        id=t.id,
        title=t.title,
        description=t.description,
        priority=t.priority,
        due_at=t.due_at,
        status=t.status,
        scope_unit_id=t.scope_unit_id,
        parent_id=t.parent_id,
        series_id=t.series_id,
        created_by_account_id=t.created_by_account_id,
        created_by_member_id=t.created_by_member_id,
        created_at=t.created_at,
        updated_at=t.updated_at,
        started_at=t.started_at,
        assignee_member_ids=sorted(view.assignee_member_ids, key=str),
    )


def _comment(comment: TaskComment) -> CommentResponse:
    return CommentResponse(
        id=comment.id,
        task_id=comment.task_id,
        author_account_id=comment.author_account_id,
        body=None if comment.deleted_at else comment.body,
        created_at=comment.created_at,
        edited_at=comment.edited_at,
        deleted_at=comment.deleted_at,
    )


def _series(view: series_service.SeriesView) -> SeriesResponse:
    s = view.series
    return SeriesResponse(
        id=s.id,
        scope_unit_id=s.scope_unit_id,
        title=s.title,
        description=s.description,
        priority=s.priority,
        assignee_member_ids=s.assignee_member_ids,
        subtask_templates=s.subtask_templates,
        first_due_at=s.first_due_at,
        ends_at=s.ends_at,
        status=s.status.value,
        created_by_account_id=s.created_by_account_id,
        stopped_at=s.stopped_at,
        occurrence_ids=view.occurrence_ids,
    )
