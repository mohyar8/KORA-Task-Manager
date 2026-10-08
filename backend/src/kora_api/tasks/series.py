"""Weekly recurrence. All occurrences (with duplicated subtasks) are generated up front; there is
no scheduler. Editing, moving or stopping a series touches only future, unstarted occurrences
(and their direct subtasks); past, started, completed and cancelled occurrences never change."""

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from kora_api.access.dependencies import AccessContext
from kora_api.access.evaluation import AccessDeniedError
from kora_api.access.org_facts import UnitInfo
from kora_api.core import clock
from kora_api.organization import queries as org
from kora_api.tasks import service
from kora_api.tasks.constants import (
    MAX_SERIES_OCCURRENCES,
    RECURRENCE_INTERVAL,
    AssignmentEndReason,
    EventKind,
    SeriesStatus,
    TaskPriority,
    TaskStatus,
)
from kora_api.tasks.models import Task, TaskAssignment, TaskSeries
from kora_api.tasks.service import (
    CREATE,
    MANAGE,
    VIEW,
    InvalidTaskError,
    TaskActor,
    TaskConflictError,
    TaskFields,
    TaskNotFoundError,
)


@dataclass(frozen=True)
class SubtaskTemplate:
    title: str
    assignee_member_ids: tuple[uuid.UUID, ...]
    description: str | None = None
    priority: TaskPriority | None = None
    # Identifies the template across edits; generated subtasks carry it. None for a new template.
    key: uuid.UUID | None = None

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> "SubtaskTemplate":
        return cls(
            title=data["title"],
            assignee_member_ids=tuple(uuid.UUID(m) for m in data["assignee_member_ids"]),
            description=data.get("description"),
            priority=TaskPriority(data["priority"]) if data.get("priority") else None,
            key=uuid.UUID(data["key"]) if data.get("key") else None,
        )

    def as_json(self) -> dict[str, Any]:
        return {
            "key": str(self.key) if self.key else None,
            "title": self.title,
            "description": self.description,
            "priority": self.priority.value if self.priority else None,
            "assignee_member_ids": [str(m) for m in self.assignee_member_ids],
        }


@dataclass(frozen=True)
class SeriesView:
    series: TaskSeries
    occurrence_ids: list[uuid.UUID]


def occurrence_due_times(first_due_at: datetime, ends_at: datetime) -> list[datetime]:
    if ends_at < first_due_at:
        raise InvalidTaskError("The series must end at or after the first due time.")
    times: list[datetime] = []
    due = first_due_at
    while due <= ends_at:
        times.append(due)
        if len(times) > MAX_SERIES_OCCURRENCES:
            raise InvalidTaskError(
                f"A series may have at most {MAX_SERIES_OCCURRENCES} weekly occurrences."
            )
        due += RECURRENCE_INTERVAL
    return times


async def create_series(
    db: AsyncSession,
    actor: TaskActor,
    *,
    scope_unit_id: uuid.UUID,
    fields: TaskFields,
    ends_at: datetime,
    assignee_member_ids: Sequence[uuid.UUID],
    subtasks: Sequence[SubtaskTemplate] = (),
) -> SeriesView:
    if fields.due_at is None:
        raise InvalidTaskError("A weekly series needs the first occurrence's due time.")
    due_times = occurrence_due_times(fields.due_at, ends_at)
    await service.require_creator(db, actor, scope_unit_id)
    units = await org.current_units(db)
    await service.require_eligible(db, assignee_member_ids, scope_unit_id, units)
    for template in subtasks:
        await service.require_eligible(db, template.assignee_member_ids, scope_unit_id, units)

    assert actor.member_id is not None
    subtasks = [replace(template, key=uuid.uuid4()) for template in subtasks]
    now = clock.utcnow()
    series = TaskSeries(
        scope_unit_id=scope_unit_id,
        title=fields.title,
        description=fields.description,
        priority=fields.priority,
        assignee_member_ids=list(assignee_member_ids),
        subtask_templates=[template.as_json() for template in subtasks],
        first_due_at=fields.due_at,
        ends_at=ends_at,
        status=SeriesStatus.ACTIVE,
        created_by_account_id=actor.account_id,
        created_by_member_id=actor.member_id,
        created_at=now,
        updated_at=now,
    )
    db.add(series)
    await db.flush()

    occurrence_ids: list[uuid.UUID] = []
    for index, due_at in enumerate(due_times, start=1):
        occurrence = await service.insert_task(
            db,
            scope_unit_id=scope_unit_id,
            fields=replace(fields, due_at=due_at),
            creator=actor,
            assignee_member_ids=assignee_member_ids,
            series_id=series.id,
            event_data={"series_id": series.id, "occurrence": index},
            notify_assignees=False,
        )
        occurrence_ids.append(occurrence.task.id)
        for template in subtasks:
            subtask = await service.insert_task(
                db,
                scope_unit_id=scope_unit_id,
                fields=TaskFields(template.title, template.description, template.priority),
                creator=actor,
                assignee_member_ids=template.assignee_member_ids,
                parent_id=occurrence.task.id,
                series_id=series.id,
                series_template_key=template.key,
                notify_assignees=False,
            )
            service.record(
                db,
                occurrence.task.id,
                EventKind.SUBTASK_CREATED,
                actor.account_id,
                subtask_id=subtask.task.id,
            )
    assigned = set(assignee_member_ids).union(*(t.assignee_member_ids for t in subtasks))
    await service.notify_series_assignment(
        db, series.id, assigned, "series_assigned", actor.account_id
    )
    await db.commit()
    return SeriesView(series, occurrence_ids)


async def get_series(db: AsyncSession, actor: TaskActor, series_id: uuid.UUID) -> SeriesView:
    series = await _load(db, series_id)
    if not (_is_creator(actor, series) or actor.snapshot.allows(VIEW, series.scope_unit_id)):
        raise AccessDeniedError(VIEW, series.scope_unit_id)
    return await _view(db, series)


async def update_series(
    db: AsyncSession,
    actor: TaskActor,
    series_id: uuid.UUID,
    changes: Mapping[str, Any],
    assignee_member_ids: Sequence[uuid.UUID] | None,
    subtasks: Sequence[SubtaskTemplate] | None = None,
) -> SeriesView:
    """Change the series and its future, unstarted occurrences only.

    `subtasks`, when given, replaces the subtask templates: templates with a known `key` are
    updated, ones without a key are added, and missing ones are removed. Future unstarted
    occurrences get matching subtasks created, updated or (soft-)removed by cancelling them.
    """
    series = await _load_administrable(db, actor, series_id)
    units = await org.current_units(db)
    if assignee_member_ids is not None:
        await service.require_eligible(db, assignee_member_ids, series.scope_unit_id, units)
        series.assignee_member_ids = list(assignee_member_ids)
    templates: list[SubtaskTemplate] | None = None
    previous_templates = list(series.subtask_templates)
    if subtasks is not None:
        templates = await _replace_templates(db, series, subtasks, units)
    content_changed = series.subtask_templates != previous_templates or any(
        getattr(series, name) != changes[name]
        for name in ("title", "description", "priority")
        if name in changes
    )
    for name in ("title", "description", "priority"):
        if name in changes:
            setattr(series, name, changes[name])
    series.updated_at = clock.utcnow()

    wanted = set(series.assignee_member_ids)
    assignment_changes = _AssignmentChanges()
    for occurrence in await _future_unstarted(db, series.id):
        await service.apply_changes(
            db, occurrence, changes, actor.account_id, notify=False, series_id=series.id
        )
        if assignee_member_ids is not None:
            await _sync_assignees(
                db, occurrence, wanted, actor.account_id, units, assignment_changes
            )
        # Drop any future assignee who is no longer valid, recording why.
        assignment_changes.removed |= await service.remove_ineligible_assignees(
            db, occurrence, actor.account_id, units, notify=False
        )
        if templates is not None:
            await _sync_subtasks(
                db, series, occurrence, templates, actor, units, assignment_changes
            )
    await _notify_assignment_changes(db, series, assignment_changes, actor.account_id)
    if content_changed:
        removed_only = assignment_changes.removed - assignment_changes.added
        await _notify_series_updated(db, series, actor.account_id, units, removed_only)
    await db.commit()
    return await _view(db, series)


async def move_series(
    db: AsyncSession, actor: TaskActor, series_id: uuid.UUID, destination_id: uuid.UUID
) -> SeriesView:
    """Move the series and its future, unstarted occurrences (with their subtasks).

    Same rules as moving a task: the creator needs `task.create` at the destination; a manager
    needs `task.manage` at the destination and at every affected source scope.
    """
    series = await _load(db, series_id, lock=True)
    if series.status != SeriesStatus.ACTIVE:
        raise TaskConflictError("The series has been stopped.")
    occurrences = await _future_unstarted(db, series.id)
    snapshot = actor.snapshot
    sources = {series.scope_unit_id, *(o.scope_unit_id for o in occurrences)}
    as_creator = _is_creator(actor, series) and snapshot.allows(CREATE, destination_id)
    as_manager = snapshot.allows(MANAGE, destination_id) and all(
        snapshot.allows(MANAGE, source) for source in sources
    )
    if not (as_creator or as_manager):
        raise AccessDeniedError(MANAGE, destination_id)
    units = await org.current_units(db)
    destination = units.get(destination_id)
    if destination is None or not destination.active:
        raise InvalidTaskError("Destination unit not found or not active.")
    if destination_id == series.scope_unit_id:
        raise InvalidTaskError("The series is already in that scope.")

    # Keep the templates valid at the new scope.
    templates = [SubtaskTemplate.from_json(t) for t in series.subtask_templates]
    member_ids = set(series.assignee_member_ids).union(*(t.assignee_member_ids for t in templates))
    positions = await org.member_positions(db, member_ids)

    def eligible(member_id: uuid.UUID) -> bool:
        position = positions.get(member_id)
        return position is not None and org.member_within_scope(position, destination_id, units)

    series.scope_unit_id = destination_id
    series.assignee_member_ids = [m for m in series.assignee_member_ids if eligible(m)]
    series.subtask_templates = [
        replace(
            t, assignee_member_ids=tuple(m for m in t.assignee_member_ids if eligible(m))
        ).as_json()
        for t in templates
    ]
    series.updated_at = clock.utcnow()

    removed: set[uuid.UUID] = set()
    for occurrence in occurrences:
        if occurrence.scope_unit_id == destination_id:
            continue
        subtasks = list(
            await db.scalars(select(Task).where(Task.parent_id == occurrence.id).with_for_update())
        )
        for item in (occurrence, *subtasks):
            await service.rescope(db, item, destination_id, actor.account_id, notify=False)
            removed |= await service.remove_ineligible_assignees(
                db, item, actor.account_id, units, notify=False
            )
    await service.notify_series_assignment(
        db, series.id, removed, "series_unassigned", actor.account_id
    )
    await _notify_series_updated(db, series, actor.account_id, units, removed)
    await db.commit()
    return await _view(db, series)


async def _replace_templates(
    db: AsyncSession,
    series: TaskSeries,
    subtasks: Sequence[SubtaskTemplate],
    units: Mapping[uuid.UUID, UnitInfo],
) -> list[SubtaskTemplate]:
    known = {t.key for t in map(SubtaskTemplate.from_json, series.subtask_templates) if t.key}
    keys = [t.key for t in subtasks if t.key is not None]
    if len(keys) != len(set(keys)) or not set(keys) <= known:
        raise InvalidTaskError("Unknown or repeated subtask template key.")
    for template in subtasks:
        await service.require_eligible(
            db, template.assignee_member_ids, series.scope_unit_id, units
        )
    templates = [t if t.key else replace(t, key=uuid.uuid4()) for t in subtasks]
    series.subtask_templates = [t.as_json() for t in templates]
    return templates


async def _sync_subtasks(
    db: AsyncSession,
    series: TaskSeries,
    occurrence: Task,
    templates: Sequence[SubtaskTemplate],
    actor: TaskActor,
    units: Mapping[uuid.UUID, UnitInfo],
    assignment_changes: "_AssignmentChanges",
) -> None:
    """Make one future occurrence's subtasks match the templates. Started subtasks are kept."""
    existing = {
        sub.series_template_key: sub
        for sub in await db.scalars(
            select(Task).where(Task.parent_id == occurrence.id).with_for_update()
        )
        if sub.series_template_key is not None
    }
    creator = await _series_creator(db, series, actor)
    for template in templates:
        assert template.key is not None
        wanted = set(template.assignee_member_ids)
        subtask = existing.get(template.key)
        if subtask is None:
            created = await service.insert_task(
                db,
                scope_unit_id=occurrence.scope_unit_id,
                fields=TaskFields(template.title, template.description, template.priority),
                creator=creator,
                assignee_member_ids=(),
                parent_id=occurrence.id,
                series_id=series.id,
                series_template_key=template.key,
                event_data={"series_id": series.id},
                actor_account_id=actor.account_id,
                notify_assignees=False,
            )
            await _sync_assignees(
                db, created.task, wanted, actor.account_id, units, assignment_changes
            )
            service.record(
                db,
                occurrence.id,
                EventKind.SUBTASK_CREATED,
                actor.account_id,
                subtask_id=created.task.id,
            )
        elif _unstarted(subtask):
            fields = {
                "title": template.title,
                "description": template.description,
                "priority": template.priority,
            }
            await service.apply_changes(
                db, subtask, fields, actor.account_id, notify=False, series_id=series.id
            )
            await _sync_assignees(db, subtask, wanted, actor.account_id, units, assignment_changes)
            assignment_changes.removed |= await service.remove_ineligible_assignees(
                db, subtask, actor.account_id, units, notify=False
            )
    removed = set(existing) - {t.key for t in templates}
    for key in removed:
        subtask = existing[key]
        if _unstarted(subtask):
            await service.set_status(
                db,
                subtask,
                TaskStatus.CANCELLED,
                actor.account_id,
                notify=False,
                reason="series_template_removed",
            )


@dataclass
class _AssignmentChanges:
    """Members assigned to / removed from any task of a series during one series operation."""

    added: set[uuid.UUID] = field(default_factory=set[uuid.UUID])
    removed: set[uuid.UUID] = field(default_factory=set[uuid.UUID])


async def _notify_assignment_changes(
    db: AsyncSession, series: TaskSeries, changes: _AssignmentChanges, actor_account_id: uuid.UUID
) -> None:
    """At most one consolidated notification per affected Member."""
    both = changes.added & changes.removed
    for members, kind in (
        (changes.added - both, "series_assigned"),
        (changes.removed - both, "series_unassigned"),
        (both, "series_assignment_changed"),
    ):
        await service.notify_series_assignment(db, series.id, members, kind, actor_account_id)


async def visible_series_ids(
    db: AsyncSession, access: AccessContext, source_ids: set[uuid.UUID]
) -> set[uuid.UUID]:
    """Notification source checker: series the caller may see (creator, `task.view` at the
    series scope, or a current assignee of any of its tasks)."""
    actor = await service.actor_for(db, access)
    visible: set[uuid.UUID] = set()
    for series in await db.scalars(select(TaskSeries).where(TaskSeries.id.in_(source_ids))):
        if (
            _is_creator(actor, series)
            or actor.snapshot.allows(VIEW, series.scope_unit_id)
            or (
                actor.member_id is not None
                and await db.scalar(
                    select(
                        exists().where(
                            TaskAssignment.member_id == actor.member_id,
                            TaskAssignment.valid_to.is_(None),
                            TaskAssignment.task_id == Task.id,
                            Task.series_id == series.id,
                        )
                    )
                )
            )
        ):
            visible.add(series.id)
    return visible


async def _notify_series_updated(
    db: AsyncSession,
    series: TaskSeries,
    actor_account_id: uuid.UUID,
    units: Mapping[uuid.UUID, UnitInfo],
    removed_member_ids: set[uuid.UUID] | frozenset[uuid.UUID] = frozenset(),
) -> None:
    """One `series_updated` per recipient: the series creator and its currently eligible
    (occurrence and subtask-template) assignees. Members removed in this operation get only
    their assignment-removal notification; the actor gets nothing."""
    templates = [SubtaskTemplate.from_json(t) for t in series.subtask_templates]
    members = set(series.assignee_member_ids).union(*(t.assignee_member_ids for t in templates))
    positions = await org.member_positions(db, members | set(removed_member_ids))
    removed_accounts = {positions[m].account_id for m in removed_member_ids if m in positions}
    eligible = {
        positions[m].account_id
        for m in members - set(removed_member_ids)
        if m in positions and org.member_within_scope(positions[m], series.scope_unit_id, units)
    }
    recipients = ({series.created_by_account_id} | eligible) - removed_accounts
    await service.notify_series_update(db, series, recipients, actor_account_id)


def _unstarted(task: Task) -> bool:
    return task.status == TaskStatus.NEW and task.started_at is None


async def _series_creator(db: AsyncSession, series: TaskSeries, actor: TaskActor) -> TaskActor:
    """The series creator, recorded as creator of subtasks added to its occurrences."""
    positions = await org.member_positions(db, [series.created_by_member_id])
    return TaskActor(
        series.created_by_account_id, positions[series.created_by_member_id], actor.snapshot
    )


async def stop_series(db: AsyncSession, actor: TaskActor, series_id: uuid.UUID) -> SeriesView:
    """Stop the series: cancel future, unstarted occurrences (and their unstarted subtasks)."""
    series = await _load_administrable(db, actor, series_id)
    now = clock.utcnow()
    series.status = SeriesStatus.STOPPED
    series.stopped_at = now
    series.stopped_by_account_id = actor.account_id
    series.updated_at = now
    for occurrence in await _future_unstarted(db, series.id):
        await service.set_status(
            db,
            occurrence,
            TaskStatus.CANCELLED,
            actor.account_id,
            notify=False,
            reason="series_stopped",
        )
        subtasks = await db.scalars(
            select(Task)
            .where(
                Task.parent_id == occurrence.id,
                Task.status == TaskStatus.NEW,
                Task.started_at.is_(None),
            )
            .with_for_update()
        )
        for subtask in subtasks:
            await service.set_status(
                db,
                subtask,
                TaskStatus.CANCELLED,
                actor.account_id,
                notify=False,
                reason="series_stopped",
            )
    await _notify_series_updated(db, series, actor.account_id, await org.current_units(db))
    await db.commit()
    return await _view(db, series)


async def _sync_assignees(
    db: AsyncSession,
    occurrence: Task,
    wanted: set[uuid.UUID],
    actor_account_id: uuid.UUID,
    units: Mapping[uuid.UUID, UnitInfo],
    assignment_changes: "_AssignmentChanges",
) -> None:
    current = (await service.assignees_of(db, [occurrence.id]))[occurrence.id]
    for member_id in current - wanted:
        if await service.end_assignment(
            db,
            occurrence.id,
            member_id,
            AssignmentEndReason.SERIES_UPDATE,
            actor_account_id,
            notify=False,
        ):
            assignment_changes.removed.add(member_id)
    positions = await org.member_positions(db, wanted - current)
    for member_id in wanted - current:
        position = positions.get(member_id)
        if position is None or not org.member_within_scope(
            position, occurrence.scope_unit_id, units
        ):
            # e.g. the Member became inactive, or the occurrence moved out of their scope.
            service.record(
                db,
                occurrence.id,
                EventKind.ASSIGNEE_NOT_ADDED,
                actor_account_id,
                member_id=member_id,
                reason=AssignmentEndReason.MEMBER_INACTIVE
                if position is None or not position.active
                else AssignmentEndReason.OUT_OF_SCOPE,
            )
            continue
        await service.open_assignment(db, occurrence.id, member_id, actor_account_id, notify=False)
        assignment_changes.added.add(member_id)
        service.record(
            db, occurrence.id, EventKind.ASSIGNEE_ADDED, actor_account_id, member_id=member_id
        )


async def _future_unstarted(db: AsyncSession, series_id: uuid.UUID) -> list[Task]:
    return list(
        await db.scalars(
            select(Task)
            .where(
                Task.series_id == series_id,
                Task.parent_id.is_(None),
                Task.status == TaskStatus.NEW,
                Task.started_at.is_(None),
                Task.due_at > clock.utcnow(),
            )
            .order_by(Task.due_at)
            .with_for_update()
        )
    )


def _is_creator(actor: TaskActor, series: TaskSeries) -> bool:
    return actor.member_id is not None and actor.member_id == series.created_by_member_id


async def _load(db: AsyncSession, series_id: uuid.UUID, *, lock: bool = False) -> TaskSeries:
    series = await db.get(TaskSeries, series_id, with_for_update=lock)
    if series is None:
        raise TaskNotFoundError
    return series


async def _load_administrable(
    db: AsyncSession, actor: TaskActor, series_id: uuid.UUID
) -> TaskSeries:
    series = await _load(db, series_id, lock=True)
    if not (_is_creator(actor, series) or actor.snapshot.allows(MANAGE, series.scope_unit_id)):
        raise AccessDeniedError(MANAGE, series.scope_unit_id)
    if series.status != SeriesStatus.ACTIVE:
        raise TaskConflictError("The series has been stopped.")
    return series


async def _view(db: AsyncSession, series: TaskSeries) -> SeriesView:
    ids = await db.scalars(
        select(Task.id)
        .where(Task.series_id == series.id, Task.parent_id.is_(None))
        .order_by(Task.due_at)
    )
    return SeriesView(series, list(ids))
