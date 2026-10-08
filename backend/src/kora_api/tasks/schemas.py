import uuid
from datetime import UTC, datetime
from typing import Annotated, Any, Self

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    Field,
    StringConstraints,
    model_validator,
)

from kora_api.tasks.constants import TaskPriority, TaskStatus


def _to_utc(value: datetime) -> datetime:
    return value.astimezone(UTC)


# Timestamps must carry an offset and are stored in UTC.
UtcDatetime = Annotated[AwareDatetime, AfterValidator(_to_utc)]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
Description = Annotated[str, StringConstraints(max_length=10_000)]
CommentBody = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5_000)
]
Assignees = Annotated[list[uuid.UUID], Field(min_length=1)]


class TaskFieldsRequest(BaseModel):
    title: Title
    description: Description | None = None
    priority: TaskPriority | None = None
    due_at: UtcDatetime | None = None


class CreateSubtaskRequest(TaskFieldsRequest):
    assignee_member_ids: Assignees


class CreateTaskRequest(CreateSubtaskRequest):
    scope_unit_id: uuid.UUID


class UpdateTaskRequest(BaseModel):
    """Only the fields sent are changed; send null to clear an optional field."""

    title: Title | None = None
    description: Description | None = None
    priority: TaskPriority | None = None
    due_at: UtcDatetime | None = None

    @model_validator(mode="after")
    def _title_not_null(self) -> Self:
        if "title" in self.model_fields_set and self.title is None:
            raise ValueError("title cannot be null")
        return self

    def changes(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.model_fields_set}


class StatusRequest(BaseModel):
    status: TaskStatus


class AssigneeRequest(BaseModel):
    member_id: uuid.UUID


class MoveTaskRequest(BaseModel):
    scope_unit_id: uuid.UUID


class CommentRequest(BaseModel):
    body: CommentBody


class TaskResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    priority: TaskPriority | None
    due_at: datetime | None
    status: TaskStatus
    scope_unit_id: uuid.UUID
    parent_id: uuid.UUID | None
    series_id: uuid.UUID | None
    created_by_account_id: uuid.UUID
    created_by_member_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    assignee_member_ids: list[uuid.UUID]


class CommentResponse(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    author_account_id: uuid.UUID
    # Null once deleted; the deletion stays visible through `deleted_at` and the history.
    body: str | None
    created_at: datetime
    edited_at: datetime | None
    deleted_at: datetime | None


class TaskEventResponse(BaseModel):
    kind: str
    actor_account_id: uuid.UUID | None
    data: dict[str, Any]
    created_at: datetime


# --- Weekly series ------------------------------------------------------------------------------


class SubtaskTemplateRequest(BaseModel):
    title: Title
    description: Description | None = None
    priority: TaskPriority | None = None
    assignee_member_ids: Assignees


class CreateSeriesRequest(BaseModel):
    scope_unit_id: uuid.UUID
    title: Title
    description: Description | None = None
    priority: TaskPriority | None = None
    first_due_at: UtcDatetime
    ends_at: UtcDatetime
    assignee_member_ids: Assignees
    subtasks: list[SubtaskTemplateRequest] = []


class SeriesSubtaskTemplateRequest(SubtaskTemplateRequest):
    # Omit for a new template; send an existing template's key to update it.
    key: uuid.UUID | None = None


class UpdateSeriesRequest(BaseModel):
    """Applies to future, unstarted occurrences only. Only the fields sent are changed.

    `subtasks`, when sent, is the complete new list of subtask templates.
    """

    title: Title | None = None
    description: Description | None = None
    priority: TaskPriority | None = None
    assignee_member_ids: Assignees | None = None
    subtasks: list[SeriesSubtaskTemplateRequest] | None = None

    @model_validator(mode="after")
    def _required_not_null(self) -> Self:
        for field in ("title", "assignee_member_ids", "subtasks"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self

    def changes(self) -> dict[str, Any]:
        return {
            field: getattr(self, field)
            for field in self.model_fields_set
            if field in ("title", "description", "priority")
        }


class SeriesResponse(BaseModel):
    id: uuid.UUID
    scope_unit_id: uuid.UUID
    title: str
    description: str | None
    priority: TaskPriority | None
    assignee_member_ids: list[uuid.UUID]
    subtask_templates: list[dict[str, Any]]
    first_due_at: datetime
    ends_at: datetime
    status: str
    created_by_account_id: uuid.UUID
    stopped_at: datetime | None
    occurrence_ids: list[uuid.UUID]
