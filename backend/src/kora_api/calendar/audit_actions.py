"""Audited calendar actions. Descriptions, locations and online URLs (which may carry meeting
passcodes) are never stored; an edit records only that they changed."""

from kora_api.audit.service import action

EVENT = "calendar_event"
EVENT_CREATED = action(
    "calendar_event.created",
    EVENT,
    "type",
    "title",
    "starts_at",
    "ends_at",
    "state",
    "invitee_member_ids",
)
EVENT_UPDATED = action(
    "calendar_event.updated", EVENT, "changed_fields", "type", "title", "starts_at", "ends_at"
)
EVENT_CANCELLED = action("calendar_event.cancelled", EVENT, "state")
INVITEE_ADDED = action("calendar_event.invitee_added", EVENT, "member_id")
INVITEE_REMOVED = action("calendar_event.invitee_removed", EVENT, "member_id")
