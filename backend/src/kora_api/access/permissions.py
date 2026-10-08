"""Permission catalog. Every key here is seeded into the `permissions` table by migration."""

import enum


class Permission(enum.StrEnum):
    ORGANIZATION_MANAGE = "organization.manage"
    TASK_VIEW = "task.view"
    TASK_CREATE = "task.create"
    TASK_MANAGE = "task.manage"
    ANNOUNCEMENT_PUBLISH = "announcement.publish"
    ANNOUNCEMENT_MANAGE = "announcement.manage"


PERMISSION_DESCRIPTIONS: dict[Permission, str] = {
    Permission.ORGANIZATION_MANAGE: "Create, move and archive organizational units within scope.",
    Permission.TASK_VIEW: "See tasks within scope.",
    Permission.TASK_CREATE: "Create tasks within scope (active Members only).",
    Permission.TASK_MANAGE: "Manage any task within scope.",
    Permission.ANNOUNCEMENT_PUBLISH: "Draft and publish announcements within scope.",
    Permission.ANNOUNCEMENT_MANAGE: "See, edit and withdraw announcements within scope.",
}


class OverrideEffect(enum.StrEnum):
    GRANT = "grant"
    DENY = "deny"
