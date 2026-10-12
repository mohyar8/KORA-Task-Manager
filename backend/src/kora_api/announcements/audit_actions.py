"""Audited announcement actions. Bodies are never stored; titles only as short summaries."""

from kora_api.audit.service import action

ANNOUNCEMENT = "announcement"
DRAFT_CREATED = action("announcement.draft_created", ANNOUNCEMENT, "state", "version", "title")
PUBLISHED = action("announcement.published", ANNOUNCEMENT, "state", "version", "recipient_count")
EDITED = action("announcement.edited", ANNOUNCEMENT, "state", "version", "title", "body_changed")
WITHDRAWN = action("announcement.withdrawn", ANNOUNCEMENT, "state")
