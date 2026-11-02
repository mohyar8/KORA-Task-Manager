"""Audited file actions. File names are free text about content, so they are never stored."""

from kora_api.audit.service import action

FILE = "task_file"
FILE_ADDED = action("task_file.added", FILE, "task_id", "kind", "size")
FILE_REMOVED = action("task_file.removed", FILE, "task_id", "kind", "size")
