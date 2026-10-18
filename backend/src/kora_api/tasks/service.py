"""Task rules. Every operation checks the caller's access itself; routes stay thin.

Who may do what (scope = the task's organizational unit):
- view: `task.view` at the scope; or `task.manage` there, or being the task's creator or an
  assignee - unless an explicit deny override on `task.view` decides the scope.
- create: an active Member with `task.create` at the scope (subtasks: at the parent's scope).
- assignee: move the task to `in_progress` or `completed`.
- administer (edit, cancel, reopen, manage assignees, move): the active creator, or anyone with
  `task.manage` at the scope. Moving needs `task.create` at the destination (creator) or
  `task.manage` at source and destination (manager).
- comment: the creator, an assignee or a scoped task manager.
"""

import enum
import uuid
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import ColumnElement, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from kora_api.access.dependencies import AccessContext
from kora_api.access.evaluation import AccessDeniedError, AccessSnapshot, DecisionSource
from kora_api.access.org_facts import UnitInfo
from kora_api.access.permissions import Permission
from kora_api.audit import service as audit
from kora_api.core import clock
from kora_api.notifications import service as notifications
from kora_api.notifications.models import NotificationCategory as Category
from kora_api.organization import queries as org
from kora_api.tasks import audit_actions
from kora_api.tasks.constants import (
    OPEN_STATUSES,
    AssignmentEndReason,
    EventKind,
    TaskPriority,
    TaskStatus,
)
from kora_api.tasks.models import (
    Task,
    TaskAssignment,
    TaskComment,
    TaskEvent,
    TaskScopeChange,
    TaskSeries,
)

VIEW, CREATE, MANAGE = Permission.TASK_VIEW, Permission.TASK_CREATE, Permission.TASK_MANAGE


class TaskNotFoundError(Exception):
    pass


class InvalidTaskError(Exception):
    """The request breaks a task rule (422)."""


class TaskConflictError(Exception):
    """The task's current state prevents the operation (409)."""


@dataclass(frozen=True)
class TaskActor:
    account_id: uuid.UUID
    member: org.MemberPosition | None  # set only for an active Member
    snapshot: AccessSnapshot

    @property
    def member_id(self) -> uuid.UUID | None:
        return self.member.member_id if self.member else None


async def actor_for(db: AsyncSession, access: AccessContext) -> TaskActor:
    position = await org.member_for_account(db, access.account.id)
    active = position if position is not None and position.active else None
    return TaskActor(access.account.id, active, access.snapshot)


@dataclass(frozen=True)
class TaskView:
    task: Task
    assignee_member_ids: frozenset[uuid.UUID]
    # Assignees given through 'Other' (outside the scope), id -> full name.
    external: Mapping[uuid.UUID, str] = dataclass_field(default_factory=lambda: {})


@dataclass(frozen=True)
class TaskFields:
    title: str
    description: str | None = None
    priority: TaskPriority | None = None
    due_at: datetime | None = None


# --- Permission predicates ----------------------------------------------------------------------


def is_creator(actor: TaskActor, task: Task) -> bool:
    return actor.member_id is not None and actor.member_id == task.created_by_member_id


def is_manager(actor: TaskActor, task: Task) -> bool:
    return actor.snapshot.allows(MANAGE, task.scope_unit_id)


def is_assignee(actor: TaskActor, assignees: frozenset[uuid.UUID]) -> bool:
    return actor.member_id is not None and actor.member_id in assignees


def can_view(actor: TaskActor, task: Task, assignees: frozenset[uuid.UUID]) -> bool:
    decision = actor.snapshot.decide(VIEW, task.scope_unit_id)
    if decision.allowed:
        return True
    if decision.source == DecisionSource.OVERRIDE_DENY:
        return False
    return is_manager(actor, task) or is_creator(actor, task) or is_assignee(actor, assignees)


def can_administer(actor: TaskActor, task: Task) -> bool:
    return is_creator(actor, task) or is_manager(actor, task)


def can_comment(actor: TaskActor, task: Task, assignees: frozenset[uuid.UUID]) -> bool:
    return is_creator(actor, task) or is_assignee(actor, assignees) or is_manager(actor, task)


def _deny(permission: Permission, task: Task) -> AccessDeniedError:
    return AccessDeniedError(permission, task.scope_unit_id)


# --- Loading ------------------------------------------------------------------------------------


async def assignees_of(
    db: AsyncSession, task_ids: Iterable[uuid.UUID]
) -> dict[uuid.UUID, frozenset[uuid.UUID]]:
    ids = set(task_ids)
    result: dict[uuid.UUID, set[uuid.UUID]] = {task_id: set() for task_id in ids}
    if ids:
        rows = await db.execute(
            select(TaskAssignment.task_id, TaskAssignment.member_id).where(
                TaskAssignment.task_id.in_(ids), TaskAssignment.valid_to.is_(None)
            )
        )
        for task_id, member_id in rows:
            result[task_id].add(member_id)
    return {task_id: frozenset(members) for task_id, members in result.items()}


async def externals_of(
    db: AsyncSession, task_ids: Iterable[uuid.UUID]
) -> dict[uuid.UUID, dict[uuid.UUID, str]]:
    ids = set(task_ids)
    result: dict[uuid.UUID, dict[uuid.UUID, str]] = {task_id: {} for task_id in ids}
    if not ids:
        return result
    rows = (
        await db.execute(
            select(TaskAssignment.task_id, TaskAssignment.member_id).where(
                TaskAssignment.task_id.in_(ids),
                TaskAssignment.valid_to.is_(None),
                TaskAssignment.is_external.is_(True),
            )
        )
    ).all()
    names = await org.member_names(db, {member_id for _, member_id in rows})
    for task_id, member_id in rows:
        result[task_id][member_id] = names.get(member_id, "")
    return result


async def _load(db: AsyncSession, task_id: uuid.UUID, *, lock: bool = False) -> TaskView:
    task = await db.get(Task, task_id, with_for_update=lock)
    if task is None:
        raise TaskNotFoundError
    return TaskView(
        task,
        (await assignees_of(db, [task_id]))[task_id],
        (await externals_of(db, [task_id]))[task_id],
    )


async def load_visible(
    db: AsyncSession, actor: TaskActor, task_id: uuid.UUID, *, lock: bool = False
) -> TaskView:
    view = await _load(db, task_id, lock=lock)
    if not can_view(actor, view.task, view.assignee_member_ids):
        raise _deny(VIEW, view.task)
    return view


async def get_task(db: AsyncSession, actor: TaskActor, task_id: uuid.UUID) -> TaskView:
    return await load_visible(db, actor, task_id)


async def list_tasks(
    db: AsyncSession,
    actor: TaskActor,
    *,
    status: TaskStatus | None = None,
    scope_unit_id: uuid.UUID | None = None,
    parent_id: uuid.UUID | None = None,
) -> list[TaskView]:
    """Visible tasks only (top-level unless `parent_id` is given); inaccessible ones are omitted."""
    participant_ids: set[uuid.UUID] = set()
    if actor.member_id is not None:
        participant_ids = set(
            await db.scalars(
                select(TaskAssignment.task_id).where(
                    TaskAssignment.member_id == actor.member_id, TaskAssignment.valid_to.is_(None)
                )
            )
        )
    conditions: list[ColumnElement[bool]] = [
        Task.scope_unit_id.in_(actor.snapshot.units_with(VIEW) | actor.snapshot.units_with(MANAGE))
    ]
    if participant_ids:
        conditions.append(Task.id.in_(participant_ids))
    if actor.member_id is not None:
        conditions.append(Task.created_by_member_id == actor.member_id)
    stmt = select(Task).where(or_(*conditions))
    stmt = stmt.where(Task.parent_id == parent_id if parent_id else Task.parent_id.is_(None))
    if status is not None:
        stmt = stmt.where(Task.status == status)
    if scope_unit_id is not None:
        stmt = stmt.where(Task.scope_unit_id == scope_unit_id)
    tasks = list(await db.scalars(stmt.order_by(Task.due_at.nulls_last(), Task.created_at)))
    assignees = await assignees_of(db, (t.id for t in tasks))
    externals = await externals_of(db, (t.id for t in tasks))
    return [
        TaskView(t, assignees[t.id], externals[t.id])
        for t in tasks
        if can_view(actor, t, assignees[t.id])
    ]


async def due_tasks(
    db: AsyncSession, access: AccessContext, starts_at: datetime, ends_at: datetime
) -> list[TaskView]:
    """Open (`new`/`in_progress`) tasks due in [starts_at, ends_at) that the caller created or is
    currently assigned to, re-checked for normal task visibility. Read-only (calendar view)."""
    actor = await actor_for(db, access)
    if actor.member_id is None:
        return []
    assigned = select(TaskAssignment.task_id).where(
        TaskAssignment.member_id == actor.member_id, TaskAssignment.valid_to.is_(None)
    )
    tasks = list(
        await db.scalars(
            select(Task)
            .where(
                or_(Task.created_by_member_id == actor.member_id, Task.id.in_(assigned)),
                Task.status.in_(OPEN_STATUSES),
                Task.due_at.is_not(None),
                Task.due_at >= starts_at,
                Task.due_at < ends_at,
            )
            .order_by(Task.due_at)
        )
    )
    assignees = await assignees_of(db, (t.id for t in tasks))
    externals = await externals_of(db, (t.id for t in tasks))
    return [
        TaskView(t, assignees[t.id], externals[t.id])
        for t in tasks
        if can_view(actor, t, assignees[t.id])
    ]


async def tasks_due_in_units(
    db: AsyncSession, unit_ids: Iterable[uuid.UUID], starts_at: datetime, ends_at: datetime
) -> list[Task]:
    """Top-level tasks scoped to any of the units and due in [starts_at, ends_at), any status.
    Read-only (broad calendar views); callers decide who may see them."""
    ids = set(unit_ids)
    if not ids:
        return []
    return list(
        await db.scalars(
            select(Task)
            .where(
                Task.scope_unit_id.in_(ids),
                Task.parent_id.is_(None),
                Task.due_at.is_not(None),
                Task.due_at >= starts_at,
                Task.due_at < ends_at,
            )
            .order_by(Task.due_at, Task.created_at)
        )
    )


# --- Creation -----------------------------------------------------------------------------------


async def create_task(
    db: AsyncSession,
    actor: TaskActor,
    *,
    scope_unit_id: uuid.UUID,
    fields: TaskFields,
    assignee_member_ids: Sequence[uuid.UUID],
    external_member_ids: Sequence[uuid.UUID] = (),
) -> TaskView:
    await require_creator(db, actor, scope_unit_id)
    units = await org.current_units(db)
    await _require_assignees(db, assignee_member_ids, external_member_ids, scope_unit_id, units)
    view = await insert_task(
        db,
        scope_unit_id=scope_unit_id,
        fields=fields,
        creator=actor,
        assignee_member_ids=assignee_member_ids,
        external_member_ids=external_member_ids,
    )
    _audit_created(db, view, actor.account_id)
    await db.commit()
    return view


async def create_subtask(
    db: AsyncSession,
    actor: TaskActor,
    parent_id: uuid.UUID,
    *,
    fields: TaskFields,
    assignee_member_ids: Sequence[uuid.UUID],
    external_member_ids: Sequence[uuid.UUID] = (),
) -> TaskView:
    parent = (await load_visible(db, actor, parent_id, lock=True)).task
    if parent.parent_id is not None:
        raise InvalidTaskError("Subtasks cannot have subtasks.")
    await require_creator(db, actor, parent.scope_unit_id)
    units = await org.current_units(db)
    await _require_assignees(
        db, assignee_member_ids, external_member_ids, parent.scope_unit_id, units
    )
    view = await insert_task(
        db,
        scope_unit_id=parent.scope_unit_id,
        fields=fields,
        creator=actor,
        assignee_member_ids=assignee_member_ids,
        external_member_ids=external_member_ids,
        parent_id=parent.id,
    )
    record(db, parent.id, EventKind.SUBTASK_CREATED, actor.account_id, subtask_id=view.task.id)
    _audit_created(db, view, actor.account_id)
    await db.commit()
    return view


def _audit_created(db: AsyncSession, view: TaskView, actor_account_id: uuid.UUID) -> None:
    task = view.task
    audit.record(
        db,
        audit_actions.TASK_CREATED,
        actor_account_id=actor_account_id,
        resource_id=task.id,
        scope_unit_id=task.scope_unit_id,
        after={
            "title": task.title,
            "status": task.status,
            "priority": task.priority,
            "due_at": task.due_at,
            "parent_id": task.parent_id,
            "assignee_member_ids": sorted(view.assignee_member_ids, key=str),
        },
    )


async def require_creator(db: AsyncSession, actor: TaskActor, scope_unit_id: uuid.UUID) -> None:
    if actor.member is None:
        raise AccessDeniedError(CREATE, scope_unit_id)  # only active Members create tasks
    actor.snapshot.require(CREATE, scope_unit_id)
    unit = (await org.current_units(db)).get(scope_unit_id)
    if unit is None or not unit.active:
        raise InvalidTaskError("Scope unit not found or not active.")


async def require_eligible(
    db: AsyncSession,
    member_ids: Sequence[uuid.UUID],
    scope_unit_id: uuid.UUID,
    units: Mapping[uuid.UUID, UnitInfo],
) -> None:
    if not member_ids:
        raise InvalidTaskError("A task needs at least one assignee.")
    if len(set(member_ids)) != len(member_ids):
        raise InvalidTaskError("Assignees must be distinct.")
    positions = await org.member_positions(db, member_ids)
    if any(m in positions and org.is_top_role(positions[m]) for m in member_ids):
        raise InvalidTaskError(
            "The Event Leader, Deputy and PMO Leader can only be assigned through 'Other'."
        )
    invalid = [
        str(m)
        for m in member_ids
        if m not in positions
        or not org.member_within_task_scope(positions[m], scope_unit_id, units)
    ]
    if invalid:
        raise InvalidTaskError(
            f"Assignees must be active Members within the task scope: {', '.join(invalid)}."
        )


async def require_external(
    db: AsyncSession, member_ids: Sequence[uuid.UUID], regular: Sequence[uuid.UUID] = ()
) -> None:
    """'Other' assignees: any active Member, in or outside the scope, never also a regular one."""
    if len(set(member_ids)) != len(member_ids) or set(member_ids) & set(regular):
        raise InvalidTaskError("Assignees must be distinct.")
    positions = await org.member_positions(db, member_ids)
    invalid = [str(m) for m in member_ids if m not in positions or not positions[m].active]
    if invalid:
        raise InvalidTaskError(f"Assignees must be active Members: {', '.join(invalid)}.")


async def _require_assignees(
    db: AsyncSession,
    regular: Sequence[uuid.UUID],
    external: Sequence[uuid.UUID],
    scope_unit_id: uuid.UUID,
    units: Mapping[uuid.UUID, UnitInfo],
) -> None:
    if not regular and not external:
        raise InvalidTaskError("A task needs at least one assignee.")
    if regular:
        await require_eligible(db, regular, scope_unit_id, units)
    if external:
        await require_external(db, external, regular)


async def insert_task(
    db: AsyncSession,
    *,
    scope_unit_id: uuid.UUID,
    fields: TaskFields,
    creator: TaskActor,
    assignee_member_ids: Iterable[uuid.UUID],
    external_member_ids: Iterable[uuid.UUID] = (),
    parent_id: uuid.UUID | None = None,
    series_id: uuid.UUID | None = None,
    series_template_key: uuid.UUID | None = None,
    event_data: Mapping[str, Any] | None = None,
    actor_account_id: uuid.UUID | None = None,
    notify_assignees: bool = True,
) -> TaskView:
    """Insert a task with its scope history, assignees and creation event. Does not commit.

    `creator` is recorded as the task's creator; `actor_account_id` (default: the creator) is
    who performed the change, e.g. an editor adding a subtask to series occurrences.
    """
    assert creator.member_id is not None
    actor_id = actor_account_id or creator.account_id
    now = clock.utcnow()
    from_outside = not org.owns_scope(creator.member, scope_unit_id, await org.current_units(db))
    task = Task(
        title=fields.title,
        description=fields.description,
        priority=fields.priority,
        due_at=fields.due_at,
        status=TaskStatus.NEW,
        scope_unit_id=scope_unit_id,
        parent_id=parent_id,
        series_id=series_id,
        series_template_key=series_template_key,
        created_by_account_id=creator.account_id,
        created_by_member_id=creator.member_id,
        from_outside=from_outside,
        created_at=now,
        updated_at=now,
    )
    db.add(task)
    await db.flush()
    db.add(
        TaskScopeChange(
            task_id=task.id,
            unit_id=scope_unit_id,
            valid_from=now,
            created_by_account_id=actor_id,
        )
    )
    regular = frozenset(assignee_member_ids)
    external = frozenset(external_member_ids)
    members = regular | external
    for member_id in members:
        await open_assignment(
            db,
            task.id,
            member_id,
            actor_id,
            notify=notify_assignees,
            external=member_id in external,
        )
    record(
        db,
        task.id,
        EventKind.CREATED,
        actor_id,
        scope_unit_id=scope_unit_id,
        assignee_member_ids=sorted(members, key=str),
        **dict(event_data or {}),
    )
    return TaskView(task, members, await org.member_names(db, external))


# --- Editing and status -------------------------------------------------------------------------


EDITABLE = ("title", "description", "priority", "due_at")


async def update_task(
    db: AsyncSession, actor: TaskActor, task_id: uuid.UUID, changes: Mapping[str, Any]
) -> TaskView:
    view = await load_visible(db, actor, task_id, lock=True)
    task = view.task
    if not can_administer(actor, task):
        raise _deny(MANAGE, task)
    previous = {field: getattr(task, field) for field in EDITABLE}
    if await apply_changes(db, task, changes, actor.account_id):
        changed = [field for field in EDITABLE if getattr(task, field) != previous[field]]
        # The description is never audited, only that it changed.
        shown = [field for field in changed if field != "description"]
        audit.record(
            db,
            audit_actions.TASK_UPDATED,
            actor_account_id=actor.account_id,
            resource_id=task.id,
            scope_unit_id=task.scope_unit_id,
            before={field: previous[field] for field in shown},
            after={"changed_fields": changed} | {field: getattr(task, field) for field in shown},
        )
        await db.commit()
    return view


async def apply_changes(
    db: AsyncSession,
    task: Task,
    changes: Mapping[str, Any],
    actor_account_id: uuid.UUID,
    *,
    notify: bool = True,
    **event_data: Any,
) -> bool:
    """Apply field changes and record one `updated` event. Returns whether anything changed.

    `notify=False` is for series operations, which send one consolidated notification instead.
    """
    diff: dict[str, list[Any]] = {}
    for field in EDITABLE:
        if field in changes and getattr(task, field) != changes[field]:
            diff[field] = [_jsonable(getattr(task, field)), _jsonable(changes[field])]
            setattr(task, field, changes[field])
    if not diff:
        return False
    task.updated_at = clock.utcnow()
    record(db, task.id, EventKind.UPDATED, actor_account_id, changes=diff, **event_data)
    if notify:
        await _notify_watchers(db, task, Category.TASK_UPDATE, "updated", actor_account_id)
    return True


# Allowed transitions and who may make them.
_ASSIGNEE_TARGETS = frozenset({TaskStatus.IN_PROGRESS, TaskStatus.COMPLETED})
_TRANSITIONS: dict[TaskStatus, frozenset[TaskStatus]] = {
    TaskStatus.NEW: frozenset({TaskStatus.IN_PROGRESS, TaskStatus.COMPLETED, TaskStatus.CANCELLED}),
    TaskStatus.IN_PROGRESS: frozenset({TaskStatus.COMPLETED, TaskStatus.CANCELLED}),
    TaskStatus.COMPLETED: frozenset({TaskStatus.NEW}),  # reopen
    TaskStatus.CANCELLED: frozenset({TaskStatus.NEW}),  # reopen
}


async def change_status(
    db: AsyncSession, actor: TaskActor, task_id: uuid.UUID, target: TaskStatus
) -> TaskView:
    """Assignees: in_progress/completed. Creator: cancel/reopen. Managers: any valid move."""
    view = await load_visible(db, actor, task_id, lock=True)
    task = view.task
    if target not in _TRANSITIONS[task.status]:
        raise TaskConflictError(f"Cannot change status from {task.status} to {target}.")
    if target in _ASSIGNEE_TARGETS:
        allowed = is_assignee(actor, view.assignee_member_ids) or is_manager(actor, task)
    else:  # cancel or reopen
        allowed = can_administer(actor, task)
    if not allowed:
        raise _deny(MANAGE, task)
    previous = task.status
    await set_status(db, task, target, actor.account_id)
    if target == TaskStatus.CANCELLED:
        audit_action = audit_actions.TASK_CANCELLED
    elif target == TaskStatus.NEW:
        audit_action = audit_actions.TASK_REOPENED
    else:
        audit_action = audit_actions.TASK_STATUS_CHANGED
    audit.record(
        db,
        audit_action,
        actor_account_id=actor.account_id,
        resource_id=task.id,
        scope_unit_id=task.scope_unit_id,
        before={"status": previous},
        after={"status": target},
    )
    await db.commit()
    return view


async def set_status(
    db: AsyncSession,
    task: Task,
    target: TaskStatus,
    actor_account_id: uuid.UUID,
    *,
    notify: bool = True,
    **event_data: Any,
) -> None:
    now = clock.utcnow()
    previous = task.status
    task.status = target
    task.updated_at = now
    if target in _ASSIGNEE_TARGETS and task.started_at is None:
        task.started_at = now
    record(
        db,
        task.id,
        EventKind.STATUS_CHANGED,
        actor_account_id,
        previous=previous.value,
        status=target.value,
        **event_data,
    )
    if notify:
        await _notify_watchers(db, task, Category.TASK_UPDATE, "status_changed", actor_account_id)


# --- Assignees ----------------------------------------------------------------------------------


async def add_assignee(
    db: AsyncSession,
    actor: TaskActor,
    task_id: uuid.UUID,
    member_id: uuid.UUID,
    external: bool = False,
) -> TaskView:
    view = await load_visible(db, actor, task_id, lock=True)
    if not can_administer(actor, view.task):
        raise _deny(MANAGE, view.task)
    if member_id in view.assignee_member_ids:
        raise TaskConflictError("Already an assignee.")
    if external:
        await require_external(db, [member_id])
    else:
        units = await org.current_units(db)
        await require_eligible(db, [member_id], view.task.scope_unit_id, units)
    await open_assignment(db, task_id, member_id, actor.account_id, external=external)
    record(db, task_id, EventKind.ASSIGNEE_ADDED, actor.account_id, member_id=member_id)
    audit.record(
        db,
        audit_actions.TASK_ASSIGNEE_ADDED,
        actor_account_id=actor.account_id,
        resource_id=task_id,
        scope_unit_id=view.task.scope_unit_id,
        after={"member_id": member_id},
    )
    await db.commit()
    names = dict(view.external)
    if external:
        names.update(await org.member_names(db, [member_id]))
    return TaskView(view.task, view.assignee_member_ids | {member_id}, names)


async def remove_assignee(
    db: AsyncSession, actor: TaskActor, task_id: uuid.UUID, member_id: uuid.UUID
) -> TaskView:
    view = await load_visible(db, actor, task_id, lock=True)
    if not can_administer(actor, view.task):
        raise _deny(MANAGE, view.task)
    if member_id not in view.assignee_member_ids:
        raise TaskNotFoundError
    if len(view.assignee_member_ids) == 1:
        raise InvalidTaskError("A task needs at least one assignee.")
    await end_assignment(db, task_id, member_id, AssignmentEndReason.REMOVED, actor.account_id)
    _audit_assignee_removed(db, view.task, member_id, AssignmentEndReason.REMOVED, actor.account_id)
    await db.commit()
    names = {k: v for k, v in view.external.items() if k != member_id}
    return TaskView(view.task, view.assignee_member_ids - {member_id}, names)


async def open_assignment(
    db: AsyncSession,
    task_id: uuid.UUID,
    member_id: uuid.UUID,
    actor_account_id: uuid.UUID,
    *,
    notify: bool = True,
    external: bool = False,
) -> None:
    """Assign a Member. `notify=False` is for series-wide changes, which send one consolidated
    notification per Member (`notify_series_assignment`) instead of one per occurrence."""
    db.add(
        TaskAssignment(
            task_id=task_id,
            member_id=member_id,
            valid_from=clock.utcnow(),
            created_by_account_id=actor_account_id,
            is_external=external,
        )
    )
    if notify:
        await _notify_member(db, task_id, member_id, "assigned", actor_account_id)


async def end_assignment(
    db: AsyncSession,
    task_id: uuid.UUID,
    member_id: uuid.UUID,
    reason: AssignmentEndReason,
    actor_account_id: uuid.UUID,
    *,
    notify: bool = True,
) -> bool:
    """End an open assignment; returns whether one was ended. See `open_assignment` on notify."""
    assignment = await db.scalar(
        select(TaskAssignment)
        .where(
            TaskAssignment.task_id == task_id,
            TaskAssignment.member_id == member_id,
            TaskAssignment.valid_to.is_(None),
        )
        .with_for_update()
    )
    if assignment is None:
        return False
    assignment.valid_to = clock.utcnow()
    assignment.ended_by_account_id = actor_account_id
    assignment.end_reason = reason
    record(
        db,
        task_id,
        EventKind.ASSIGNEE_REMOVED,
        actor_account_id,
        member_id=member_id,
        reason=reason,
    )
    if notify:
        await _notify_member(db, task_id, member_id, "unassigned", actor_account_id)
    return True


async def remove_ineligible_assignees(
    db: AsyncSession,
    task: Task,
    actor_account_id: uuid.UUID,
    units: Mapping[uuid.UUID, UnitInfo],
    member_ids: Iterable[uuid.UUID] | None = None,
    *,
    notify: bool = True,
    audit_removals: bool = False,
) -> set[uuid.UUID]:
    """End assignments of Members who are inactive or outside the task's current scope.

    Returns the Members removed. `audit_removals` writes one audit record per removal; callers
    whose own audit record already covers the removals (moves, series operations) leave it off.
    """
    assignees = (await assignees_of(db, [task.id]))[task.id]
    candidates = assignees if member_ids is None else assignees & set(member_ids)
    positions = await org.member_positions(db, candidates)
    external = set((await externals_of(db, [task.id]))[task.id])
    removed: set[uuid.UUID] = set()
    for member_id in candidates:
        position = positions.get(member_id)
        if position is not None and (
            org.member_within_task_scope(position, task.scope_unit_id, units)
            or (member_id in external and position.active)
        ):
            continue
        reason = (
            AssignmentEndReason.MEMBER_INACTIVE
            if position is None or not position.active
            else AssignmentEndReason.OUT_OF_SCOPE
        )
        if await end_assignment(db, task.id, member_id, reason, actor_account_id, notify=notify):
            removed.add(member_id)
            if audit_removals:
                _audit_assignee_removed(db, task, member_id, reason, actor_account_id)
    return removed


def _audit_assignee_removed(
    db: AsyncSession,
    task: Task,
    member_id: uuid.UUID,
    reason: AssignmentEndReason,
    actor_account_id: uuid.UUID,
) -> None:
    audit.record(
        db,
        audit_actions.TASK_ASSIGNEE_REMOVED,
        actor_account_id=actor_account_id,
        resource_id=task.id,
        scope_unit_id=task.scope_unit_id,
        before={"member_id": member_id},
        after={"member_id": None, "end_reason": reason},
    )


async def on_membership_changed(
    db: AsyncSession, member_ids: frozenset[uuid.UUID], actor_account_id: uuid.UUID
) -> None:
    """Organization listener: drop assignees of open tasks who became inactive or left scope.

    The task stays open and the removal is recorded. Runs inside the organization transaction.
    """
    task_ids = set(
        await db.scalars(
            select(TaskAssignment.task_id)
            .join(Task, Task.id == TaskAssignment.task_id)
            .where(
                TaskAssignment.member_id.in_(member_ids),
                TaskAssignment.valid_to.is_(None),
                Task.status.in_(OPEN_STATUSES),
            )
        )
    )
    if not task_ids:
        return
    units = await org.current_units(db)
    series_removals: dict[uuid.UUID, set[uuid.UUID]] = {}
    series_occurrences: dict[uuid.UUID, int] = {}
    for task in await db.scalars(select(Task).where(Task.id.in_(task_ids)).with_for_update()):
        if task.series_id is None:
            await remove_ineligible_assignees(
                db, task, actor_account_id, units, member_ids, audit_removals=True
            )
            continue
        # Series tasks: one consolidated notification per Member and one audit record per
        # series, not one per occurrence.
        removed = await remove_ineligible_assignees(
            db, task, actor_account_id, units, member_ids, notify=False
        )
        series_removals.setdefault(task.series_id, set()).update(removed)
        if removed:
            series_occurrences[task.series_id] = series_occurrences.get(task.series_id, 0) + 1
    for series_id, removed in series_removals.items():
        await notify_series_assignment(
            db, series_id, removed, "series_unassigned", actor_account_id
        )
        if removed:
            series = await db.get_one(TaskSeries, series_id)
            audit.record(
                db,
                audit_actions.SERIES_ASSIGNEES_REMOVED,
                actor_account_id=actor_account_id,
                resource_id=series_id,
                scope_unit_id=series.scope_unit_id,
                after={
                    "member_ids": sorted(removed, key=str),
                    "occurrence_count": series_occurrences[series_id],
                },
            )


# --- Moving -------------------------------------------------------------------------------------


async def move_task(
    db: AsyncSession, actor: TaskActor, task_id: uuid.UUID, destination_id: uuid.UUID
) -> TaskView:
    """Move a top-level task (and its subtasks) to another scope, keeping scope history."""
    view = await load_visible(db, actor, task_id, lock=True)
    task = view.task
    if task.parent_id is not None:
        raise InvalidTaskError("Subtasks move with their parent task.")
    snapshot = actor.snapshot
    as_creator = is_creator(actor, task) and snapshot.allows(CREATE, destination_id)
    as_manager = snapshot.allows(MANAGE, task.scope_unit_id) and snapshot.allows(
        MANAGE, destination_id
    )
    if not (as_creator or as_manager):
        raise AccessDeniedError(MANAGE, destination_id)
    units = await org.current_units(db)
    destination = units.get(destination_id)
    if destination is None or not destination.active:
        raise InvalidTaskError("Destination unit not found or not active.")
    if destination_id == task.scope_unit_id:
        raise InvalidTaskError("The task is already in that scope.")

    subtasks = list(
        await db.scalars(select(Task).where(Task.parent_id == task.id).with_for_update())
    )
    source_id = task.scope_unit_id
    removed: set[uuid.UUID] = set()
    for item in (task, *subtasks):
        await rescope(db, item, destination_id, actor.account_id)
        removed |= await remove_ineligible_assignees(db, item, actor.account_id, units)
    audit.record(
        db,
        audit_actions.TASK_MOVED,
        actor_account_id=actor.account_id,
        resource_id=task.id,
        scope_unit_id=destination_id,
        before={"scope_unit_id": source_id},
        after={
            "scope_unit_id": destination_id,
            "subtask_count": len(subtasks),
            "removed_assignee_member_ids": sorted(removed, key=str),
        },
    )
    await db.commit()
    return await _load(db, task.id)


async def rescope(
    db: AsyncSession,
    task: Task,
    unit_id: uuid.UUID,
    actor_account_id: uuid.UUID,
    *,
    notify: bool = True,
) -> None:
    now = clock.utcnow()
    current = await db.scalar(
        select(TaskScopeChange)
        .where(TaskScopeChange.task_id == task.id, TaskScopeChange.valid_to.is_(None))
        .with_for_update()
    )
    if current is not None:
        current.valid_to = now
        current.ended_by_account_id = actor_account_id
        await db.flush()
    db.add(
        TaskScopeChange(
            task_id=task.id, unit_id=unit_id, valid_from=now, created_by_account_id=actor_account_id
        )
    )
    record(
        db,
        task.id,
        EventKind.SCOPE_CHANGED,
        actor_account_id,
        previous=task.scope_unit_id,
        scope_unit_id=unit_id,
    )
    task.scope_unit_id = unit_id
    task.updated_at = now
    if notify:
        await _notify_watchers(db, task, Category.TASK_UPDATE, "moved", actor_account_id)


# --- Comments -----------------------------------------------------------------------------------


async def list_comments(
    db: AsyncSession, actor: TaskActor, task_id: uuid.UUID
) -> list[TaskComment]:
    await load_visible(db, actor, task_id)
    return list(
        await db.scalars(
            select(TaskComment)
            .where(TaskComment.task_id == task_id)
            .order_by(TaskComment.created_at)
        )
    )


async def add_comment(
    db: AsyncSession, actor: TaskActor, task_id: uuid.UUID, body: str
) -> TaskComment:
    view = await load_visible(db, actor, task_id)
    if not can_comment(actor, view.task, view.assignee_member_ids):
        raise _deny(MANAGE, view.task)
    comment = TaskComment(
        task_id=task_id, author_account_id=actor.account_id, body=body, created_at=clock.utcnow()
    )
    db.add(comment)
    await db.flush()
    record(db, task_id, EventKind.COMMENT_ADDED, actor.account_id, comment_id=comment.id)
    await _notify_watchers(db, view.task, Category.TASK_COMMENT, "commented", actor.account_id)
    _audit_comment(db, audit_actions.COMMENT_CREATED, comment, view.task, {"task_id": task_id})
    await db.commit()
    return comment


async def edit_comment(
    db: AsyncSession, actor: TaskActor, task_id: uuid.UUID, comment_id: uuid.UUID, body: str
) -> TaskComment:
    task, comment = await _own_comment(db, actor, task_id, comment_id)
    if comment.body != body:
        record(
            db,
            task_id,
            EventKind.COMMENT_EDITED,
            actor.account_id,
            comment_id=comment.id,
            previous_body=comment.body,
        )
        comment.body = body
        comment.edited_at = clock.utcnow()
        _audit_comment(
            db,
            audit_actions.COMMENT_EDITED,
            comment,
            task,
            {"task_id": task_id, "edited_at": comment.edited_at},
        )
        await db.commit()
    return comment


async def delete_comment(
    db: AsyncSession, actor: TaskActor, task_id: uuid.UUID, comment_id: uuid.UUID
) -> TaskComment:
    """Soft delete: the comment stays listed as deleted and the history keeps a trace."""
    task, comment = await _own_comment(db, actor, task_id, comment_id)
    comment.deleted_at = clock.utcnow()
    record(db, task_id, EventKind.COMMENT_DELETED, actor.account_id, comment_id=comment.id)
    _audit_comment(
        db,
        audit_actions.COMMENT_DELETED,
        comment,
        task,
        {"task_id": task_id, "deleted_at": comment.deleted_at},
        before={"task_id": task_id, "deleted_at": None},
    )
    await db.commit()
    return comment


def _audit_comment(
    db: AsyncSession,
    audit_action: audit.AuditAction,
    comment: TaskComment,
    task: Task,
    after: audit.Metadata,
    before: audit.Metadata | None = None,
) -> None:
    """Comment bodies are never audited."""
    audit.record(
        db,
        audit_action,
        actor_account_id=comment.author_account_id,
        resource_id=comment.id,
        scope_unit_id=task.scope_unit_id,
        before=before,
        after=after,
    )


async def _own_comment(
    db: AsyncSession, actor: TaskActor, task_id: uuid.UUID, comment_id: uuid.UUID
) -> tuple[Task, TaskComment]:
    view = await load_visible(db, actor, task_id)
    comment = await db.get(TaskComment, comment_id, with_for_update=True)
    if comment is None or comment.task_id != task_id:
        raise TaskNotFoundError
    if comment.author_account_id != actor.account_id:
        raise _deny(VIEW, view.task)
    if comment.deleted_at is not None:
        raise TaskConflictError("The comment has been deleted.")
    return view.task, comment


# --- History ------------------------------------------------------------------------------------


@dataclass(frozen=True)
class HistoryEntry:
    kind: str
    actor_account_id: uuid.UUID | None
    data: dict[str, Any]
    created_at: datetime


# Event data keys that hold comment text. Events are append-only, so for a deleted comment the
# text is removed when history is read, never by rewriting the stored event.
COMMENT_CONTENT_KEYS = frozenset({"previous_body"})


async def history(db: AsyncSession, actor: TaskActor, task_id: uuid.UUID) -> list[HistoryEntry]:
    """Task-local events in order. Content of deleted comments (including earlier edited
    versions) is removed; the event itself (kind, actor, time, comment id) stays."""
    await load_visible(db, actor, task_id)
    events = await db.scalars(
        select(TaskEvent).where(TaskEvent.task_id == task_id).order_by(TaskEvent.seq)
    )
    deleted = {
        str(comment_id)
        for comment_id in await db.scalars(
            select(TaskComment.id).where(
                TaskComment.task_id == task_id, TaskComment.deleted_at.is_not(None)
            )
        )
    }
    return [_history_entry(event, deleted) for event in events]


def _history_entry(event: TaskEvent, deleted_comment_ids: set[str]) -> HistoryEntry:
    data = dict(event.data)
    if data.get("comment_id") in deleted_comment_ids and COMMENT_CONTENT_KEYS & data.keys():
        data = {k: v for k, v in data.items() if k not in COMMENT_CONTENT_KEYS}
        data["content_removed"] = True
    return HistoryEntry(event.kind, event.actor_account_id, data, event.created_at)


def record(
    db: AsyncSession,
    task_id: uuid.UUID,
    kind: EventKind,
    actor_account_id: uuid.UUID | None,
    **data: Any,
) -> None:
    db.add(
        TaskEvent(
            task_id=task_id,
            kind=kind.value,
            actor_account_id=actor_account_id,
            data={key: _jsonable(value) for key, value in data.items()},
            created_at=clock.utcnow(),
        )
    )


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, list):
        return [_jsonable(item) for item in value]  # pyright: ignore[reportUnknownVariableType]
    return value


# --- Notifications ------------------------------------------------------------------------------

NOTIFICATION_SOURCE = "task"


async def _notify_member(
    db: AsyncSession,
    task_id: uuid.UUID,
    member_id: uuid.UUID,
    kind: str,
    actor_account_id: uuid.UUID,
) -> None:
    """Assignment added or removed: notify the affected assignee."""
    task = await db.get_one(Task, task_id)
    position = (await org.member_positions(db, [member_id])).get(member_id)
    if position is not None:
        await notifications.notify(
            db,
            recipient_account_ids=[position.account_id],
            actor_account_id=actor_account_id,
            category=Category.TASK_ASSIGNMENT,
            source_type=NOTIFICATION_SOURCE,
            source_id=task.id,
            kind=kind,
            summary=task.title,
        )


async def _notify_watchers(
    db: AsyncSession, task: Task, category: Category, kind: str, actor_account_id: uuid.UUID
) -> None:
    """Notify the task's creator and current assignees (never the actor)."""
    assignees = (await assignees_of(db, [task.id]))[task.id]
    positions = await org.member_positions(db, assignees)
    await notifications.notify(
        db,
        recipient_account_ids={
            task.created_by_account_id,
            *(p.account_id for p in positions.values()),
        },
        actor_account_id=actor_account_id,
        category=category,
        source_type=NOTIFICATION_SOURCE,
        source_id=task.id,
        kind=kind,
        summary=task.title,
    )


SERIES_NOTIFICATION_SOURCE = "task_series"


async def notify_series_assignment(
    db: AsyncSession,
    series_id: uuid.UUID,
    member_ids: Iterable[uuid.UUID],
    kind: str,
    actor_account_id: uuid.UUID,
) -> None:
    """One consolidated task-assignment notification per Member for a weekly series.

    Used instead of per-occurrence notifications when a series is created, edited or moved, or
    when Members are removed from its occurrences. Identifies the series and its end date.
    """
    members = set(member_ids)
    if not members:
        return
    series = await db.get_one(TaskSeries, series_id)
    positions = await org.member_positions(db, members)
    await notifications.notify(
        db,
        recipient_account_ids={p.account_id for p in positions.values()},
        actor_account_id=actor_account_id,
        category=Category.TASK_ASSIGNMENT,
        source_type=SERIES_NOTIFICATION_SOURCE,
        source_id=series.id,
        kind=kind,
        summary=series_summary(series),
    )


def series_summary(series: TaskSeries) -> str:
    return f"{series.title} (repeats weekly until {series.ends_at.date().isoformat()})"


async def notify_series_update(
    db: AsyncSession,
    series: TaskSeries,
    recipient_account_ids: Iterable[uuid.UUID],
    actor_account_id: uuid.UUID,
) -> None:
    """One consolidated `series_updated` notification per recipient for a series operation."""
    await notifications.notify(
        db,
        recipient_account_ids=recipient_account_ids,
        actor_account_id=actor_account_id,
        category=Category.TASK_UPDATE,
        source_type=SERIES_NOTIFICATION_SOURCE,
        source_id=series.id,
        kind="series_updated",
        summary=series_summary(series),
    )


async def visible_task_ids(
    db: AsyncSession, access: AccessContext, source_ids: set[uuid.UUID]
) -> set[uuid.UUID]:
    """Notification source checker: the tasks among `source_ids` the caller can view now."""
    actor = await actor_for(db, access)
    tasks = list(await db.scalars(select(Task).where(Task.id.in_(source_ids))))
    assignees = await assignees_of(db, (t.id for t in tasks))
    return {t.id for t in tasks if can_view(actor, t, assignees[t.id])}
