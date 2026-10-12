"""Audited access actions and the only metadata each may store."""

from kora_api.audit.service import action

ACCOUNT = "user_account"

ACCOUNT_BOOTSTRAPPED = action(
    "account.bootstrapped", ACCOUNT, "status", "password_is_temporary", "system_admin"
)
ACCOUNT_PASSWORD_CHANGED = action(
    "account.password_changed", ACCOUNT, "password_is_temporary", "password_changed_at"
)
ACCOUNT_PASSWORD_RESET = action(
    "account.password_reset",
    ACCOUNT,
    "password_is_temporary",
    "temporary_password_expires_at",
    "sessions_revoked",
)
ACCOUNT_LOCKED_OUT = action("account.locked_out", ACCOUNT, "failure_count", "locked_until")
SYSTEM_ADMIN_GRANTED = action("system_admin.granted", ACCOUNT, "system_admin")
SYSTEM_ADMIN_REVOKED = action("system_admin.revoked", ACCOUNT, "system_admin")

ROLE_DEFAULT = "role_permission_default"
ROLE_DEFAULT_CREATED = action(
    "role_default.created", ROLE_DEFAULT, "role_key", "permission", "valid_from"
)
ROLE_DEFAULT_ENDED = action(
    "role_default.ended", ROLE_DEFAULT, "role_key", "permission", "valid_to"
)

OVERRIDE = "permission_override"
_OVERRIDE_FIELDS = ("account_id", "permission", "unit_id", "effect")
OVERRIDE_CREATED = action("permission_override.created", OVERRIDE, *_OVERRIDE_FIELDS, "valid_from")
OVERRIDE_ENDED = action("permission_override.ended", OVERRIDE, *_OVERRIDE_FIELDS, "valid_to")
