"""Fixed organization facts. The KORA root and the PMO are seeded by migration with these ids."""

import enum
import uuid

KORA_UNIT_ID = uuid.UUID("6b0a0000-0000-4000-8000-000000000001")
PMO_UNIT_ID = uuid.UUID("6b0a0000-0000-4000-8000-000000000002")


class UnitKind(enum.StrEnum):
    ORGANIZATION = "organization"
    PMO = "pmo"
    ADMINISTRATION = "administration"
    TEAM = "team"


class UnitStatus(enum.StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class MemberStatus(enum.StrEnum):
    ACTIVE = "active"
    DEACTIVATED = "deactivated"


class RoleKey(enum.StrEnum):
    EVENT_PROJECT_LEADER = "event_project_leader"
    DEPUTY_LEADER = "deputy_leader"
    PMO_LEADER = "pmo_leader"
    PMO_MEMBER = "pmo_member"
    ADMINISTRATION_MANAGER = "administration_manager"
    TEAM_LEADER = "team_leader"
    MEMBER = "member"


# Display name and the unit kind each role is held at. Team-kind roles are always held at the
# Member's current Team.
ROLES: dict[RoleKey, tuple[str, UnitKind]] = {
    RoleKey.EVENT_PROJECT_LEADER: ("Event/Project Leader", UnitKind.ORGANIZATION),
    RoleKey.DEPUTY_LEADER: ("Deputy Leader", UnitKind.ORGANIZATION),
    RoleKey.PMO_LEADER: ("PMO Leader", UnitKind.PMO),
    RoleKey.PMO_MEMBER: ("PMO Member", UnitKind.PMO),
    RoleKey.ADMINISTRATION_MANAGER: ("Administration Manager", UnitKind.ADMINISTRATION),
    RoleKey.TEAM_LEADER: ("Team Leader", UnitKind.TEAM),
    RoleKey.MEMBER: ("Member", UnitKind.TEAM),
}
