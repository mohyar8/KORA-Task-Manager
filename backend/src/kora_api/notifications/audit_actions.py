"""Audited notification actions. Only preference changes are audited (never reads/deletes)."""

from kora_api.audit.service import action
from kora_api.notifications.models import NotificationCategory

PREFERENCES_UPDATED = action(
    "notification_preferences.updated",
    "notification_preferences",
    *(category.value for category in NotificationCategory),
)
