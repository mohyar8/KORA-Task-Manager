"""Audited task-request actions. Titles are cut short and the rejection reason is never stored."""

from kora_api.audit.service import action

REQUEST = "task_request"
REQUEST_CREATED = action(
    "task_request.created", REQUEST, "title", "priority", "due_at", "from_unit_id", "to_unit_id"
)
REQUEST_ACCEPTED = action(
    "task_request.accepted", REQUEST, "status", "resulting_task_id", "assignee_member_ids"
)
REQUEST_REJECTED = action("task_request.rejected", REQUEST, "status")
REQUEST_WITHDRAWN = action("task_request.withdrawn", REQUEST, "status")
