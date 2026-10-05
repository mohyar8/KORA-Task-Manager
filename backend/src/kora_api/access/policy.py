"""Approved account-security policy values."""

import re
from datetime import timedelta

USERNAME_PATTERN = re.compile(r"^[a-z0-9._-]{3,64}$")

PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128
TEMPORARY_PASSWORD_LIFETIME = timedelta(days=7)

SESSION_IDLE_TIMEOUT = timedelta(hours=8)
SESSION_ABSOLUTE_LIFETIME = timedelta(days=7)
# last_seen_at is refreshed at most this often, to avoid a write on every request.
SESSION_TOUCH_INTERVAL = timedelta(minutes=1)

LOGIN_MAX_FAILURES = 5
LOGIN_FAILURE_WINDOW = timedelta(minutes=15)
LOGIN_LOCKOUT_DURATION = timedelta(minutes=15)
