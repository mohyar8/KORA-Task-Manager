"""Permission catalog. Every key here is seeded into the `permissions` table by migration."""

import enum


class Permission(enum.StrEnum):
    ORGANIZATION_MANAGE = "organization.manage"
    TASK_VIEW = "task.view"
    TASK_CREATE = "task.create"
    TASK_MANAGE = "task.manage"
    TASK_FOLLOW = "task.follow"
    ANNOUNCEMENT_PUBLISH = "announcement.publish"
    ANNOUNCEMENT_MANAGE = "announcement.manage"
    CALENDAR_CREATE = "calendar.create"
    CALENDAR_MANAGE = "calendar.manage"
    CALENDAR_VIEW_ADMINISTRATION = "calendar.view_administration"
    CALENDAR_VIEW_ALL = "calendar.view_all"
    LEAGUE_MANAGE = "league.manage"
    TASK_REQUEST_CREATE = "task_request.create"
    TASK_REQUEST_RESPOND = "task_request.respond"
    CHAT_MODERATE = "chat.moderate"


PERMISSION_DESCRIPTIONS: dict[Permission, str] = {
    Permission.ORGANIZATION_MANAGE: "Create, move and archive organizational units within scope.",
    Permission.TASK_VIEW: "See tasks within scope.",
    Permission.TASK_CREATE: "Create tasks within scope (active Members only).",
    Permission.TASK_MANAGE: "Manage any task within scope.",
    Permission.TASK_FOLLOW: "Follow up every task of every team (read-only).",
    Permission.ANNOUNCEMENT_PUBLISH: "Draft and publish announcements within scope.",
    Permission.ANNOUNCEMENT_MANAGE: "See, edit and withdraw announcements within scope.",
    Permission.CALENDAR_CREATE: "Create events and meetings within scope (active Members only).",
    Permission.CALENDAR_MANAGE: "See, edit and cancel events and meetings within scope.",
    Permission.CALENDAR_VIEW_ADMINISTRATION: (
        "See the task calendar of the whole Administration that contains the unit."
    ),
    Permission.CALENDAR_VIEW_ALL: "See the task calendar of every Administration.",
    Permission.LEAGUE_MANAGE: "Set the points and round title of the KORA league.",
    Permission.TASK_REQUEST_CREATE: "Ask another Administration for a task (from the unit).",
    Permission.TASK_REQUEST_RESPOND: "Accept or reject task requests sent to the Administration.",
    Permission.CHAT_MODERATE: "Delete other people's messages in the chat channels of the unit.",
}


class OverrideEffect(enum.StrEnum):
    GRANT = "grant"
    DENY = "deny"
