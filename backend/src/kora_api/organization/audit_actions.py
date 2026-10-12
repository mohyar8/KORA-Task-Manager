"""Audited organization actions and the only metadata each may store.

Member records never include profile values (name, contact details, IDs, studies): a profile
change stores only the names of the changed fields.
"""

from kora_api.audit.service import action

UNIT = "org_unit"
UNIT_CREATED = action("org_unit.created", UNIT, "kind", "name", "parent_id", "status")
UNIT_MOVED = action("org_unit.moved", UNIT, "parent_id")
UNIT_ARCHIVED = action("org_unit.archived", UNIT, "status")

MEMBER = "member"
_POSITION = ("status", "team_id", "role_key", "role_unit_id")
MEMBER_PROVISIONED = action(
    "member.provisioned", MEMBER, *_POSITION, "account_id", "password_is_temporary"
)
MEMBER_PROFILE_UPDATED = action("member.profile_updated", MEMBER, "changed_fields")
MEMBER_TEAM_CHANGED = action("member.team_changed", MEMBER, "team_id", "role_key", "role_unit_id")
MEMBER_ROLE_CHANGED = action("member.role_changed", MEMBER, "role_key", "role_unit_id")
MEMBER_DEACTIVATED = action(
    "member.deactivated", MEMBER, *_POSITION, "account_id", "account_status", "sessions_revoked"
)
MEMBER_REACTIVATED = action(
    "member.reactivated", MEMBER, *_POSITION, "account_id", "account_status"
)
