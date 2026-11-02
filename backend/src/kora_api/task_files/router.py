import uuid
from collections.abc import Awaitable
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field, StringConstraints

from kora_api.access.dependencies import CurrentAccess
from kora_api.core.database import DbSession
from kora_api.core.errors import AUTHENTICATED, errors
from kora_api.core.storage import (
    DOWNLOAD_URL_SECONDS,
    UPLOAD_URL_SECONDS,
    ObjectStorage,
    get_storage,
)
from kora_api.task_files import service
from kora_api.task_files.models import FileKind, TaskFile
from kora_api.tasks import service as tasks

router = APIRouter(prefix="/tasks/{task_id}/files", tags=["task-files"], responses=AUTHENTICATED)
Storage = Annotated[ObjectStorage | None, Depends(get_storage)]

UNAVAILABLE = (503, "File storage is not configured.")


class StartUploadRequest(BaseModel):
    kind: FileKind
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
    size: Annotated[int, Field(ge=1)]
    content_type: Annotated[str, StringConstraints(max_length=100)] | None = None


class FileResponse(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    kind: FileKind
    name: str
    size: int
    content_type: str | None
    uploaded_by_member_id: uuid.UUID
    created_at: datetime


class UploadResponse(BaseModel):
    file: FileResponse
    # PUT the raw bytes here (no other headers needed), then call `complete`.
    upload_url: str
    expires_in: int


class DownloadResponse(BaseModel):
    url: str
    expires_in: int


def _file(f: TaskFile) -> FileResponse:
    return FileResponse(
        id=f.id,
        task_id=f.task_id,
        kind=f.kind,
        name=f.name,
        size=f.size,
        content_type=f.content_type,
        uploaded_by_member_id=f.uploaded_by_member_id,
        created_at=f.created_at,
    )


async def _call[T](call: Awaitable[T]) -> T:
    try:
        return await call
    except (service.FileMissingError, tasks.TaskNotFoundError):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found.") from None
    except service.InvalidFileError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    except service.FileConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None
    except service.StorageUnavailableError:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "File storage is not configured."
        ) from None


@router.get("", responses=errors(404))
async def list_files(
    task_id: uuid.UUID, access: CurrentAccess, db: DbSession
) -> list[FileResponse]:
    """Ready files of a task, oldest first. Whoever can see the task sees them."""
    actor = await tasks.actor_for(db, access)
    return [_file(f) for f in await _call(service.list_files(db, actor, task_id))]


@router.post("", status_code=status.HTTP_201_CREATED, responses=errors(404, 409, 422, UNAVAILABLE))
async def start_upload(
    task_id: uuid.UUID,
    body: StartUploadRequest,
    access: CurrentAccess,
    db: DbSession,
    storage: Storage,
) -> UploadResponse:
    """Register a file and get a presigned URL to upload it to. The file stays hidden until
    `complete` confirms the upload. Max 10 MB and 10 files per section."""
    actor = await tasks.actor_for(db, access)
    ticket = await _call(
        service.start_upload(
            db,
            actor,
            storage,
            task_id,
            kind=body.kind,
            name=body.name,
            size=body.size,
            content_type=body.content_type,
        )
    )
    return UploadResponse(
        file=_file(ticket.file), upload_url=ticket.url, expires_in=UPLOAD_URL_SECONDS
    )


@router.post("/{file_id}/complete", responses=errors(404, 409, 422, UNAVAILABLE))
async def complete_upload(
    task_id: uuid.UUID, file_id: uuid.UUID, access: CurrentAccess, db: DbSession, storage: Storage
) -> FileResponse:
    """Confirm the upload: the stored size must match. Only the uploader; idempotent."""
    actor = await tasks.actor_for(db, access)
    return _file(await _call(service.complete_upload(db, actor, storage, task_id, file_id)))


@router.get("/{file_id}/download", responses=errors(404, UNAVAILABLE))
async def download_file(
    task_id: uuid.UUID, file_id: uuid.UUID, access: CurrentAccess, db: DbSession, storage: Storage
) -> DownloadResponse:
    """A short-lived link that forces a download. Access is checked on every call."""
    actor = await tasks.actor_for(db, access)
    url = await _call(service.download_url(db, actor, storage, task_id, file_id))
    return DownloadResponse(url=url, expires_in=DOWNLOAD_URL_SECONDS)


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT, responses=errors(404, 409))
async def remove_file(
    task_id: uuid.UUID, file_id: uuid.UUID, access: CurrentAccess, db: DbSession
) -> Response:
    """Hide a file: the uploader or whoever administers the task, while the task is open."""
    actor = await tasks.actor_for(db, access)
    await _call(service.remove_file(db, actor, task_id, file_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
