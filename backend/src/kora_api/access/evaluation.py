"""Pure effective-access evaluation (no I/O).

Precedence for a permission on a unit, walking from the unit up to the root:
1. The most specific unit on that chain carrying an override for the permission decides;
   if it carries a deny, the answer is deny (deny wins over grant at the same scope).
2. Otherwise the role default applies when the role grants the permission and the role's
   unit is on the chain (a broader scope covers its descendants).
3. Otherwise access is denied.
"""

import enum
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime

from kora_api.access.permissions import OverrideEffect


class AccessDeniedError(Exception):
    def __init__(self, permission: str, unit_id: uuid.UUID | None) -> None:
        super().__init__(f"{permission} denied on {unit_id}")
        self.permission = permission
        self.unit_id = unit_id


class DecisionSource(enum.StrEnum):
    OVERRIDE_DENY = "override_deny"
    OVERRIDE_GRANT = "override_grant"
    ROLE_DEFAULT = "role_default"
    NONE = "none"


@dataclass(frozen=True)
class Decision:
    allowed: bool
    source: DecisionSource
    decided_at_unit_id: uuid.UUID | None


@dataclass(frozen=True)
class OverrideRule:
    permission: str
    unit_id: uuid.UUID
    effect: OverrideEffect


@dataclass(frozen=True)
class AccessSnapshot:
    at: datetime
    # Every unit in the structure at `at` mapped to its parent (the root maps to None).
    parents: Mapping[uuid.UUID, uuid.UUID | None]
    role_unit_id: uuid.UUID | None = None
    role_permissions: frozenset[str] = frozenset()
    overrides: tuple[OverrideRule, ...] = ()
    _effects: dict[tuple[str, uuid.UUID], set[OverrideEffect]] = field(
        init=False, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        effects: dict[tuple[str, uuid.UUID], set[OverrideEffect]] = {}
        for rule in self.overrides:
            effects.setdefault((rule.permission, rule.unit_id), set()).add(rule.effect)
        object.__setattr__(self, "_effects", effects)

    def chain(self, unit_id: uuid.UUID) -> list[uuid.UUID]:
        """The unit followed by its ancestors up to the root; empty if the unit is unknown."""
        chain: list[uuid.UUID] = []
        current: uuid.UUID | None = unit_id
        while current is not None and current in self.parents and current not in chain:
            chain.append(current)
            current = self.parents[current]
        return chain

    def decide(self, permission: str, unit_id: uuid.UUID) -> Decision:
        chain = self.chain(unit_id)
        for unit in chain:
            effects = self._effects.get((permission, unit))
            if effects:
                if OverrideEffect.DENY in effects:
                    return Decision(False, DecisionSource.OVERRIDE_DENY, unit)
                return Decision(True, DecisionSource.OVERRIDE_GRANT, unit)
        if (
            permission in self.role_permissions
            and self.role_unit_id is not None
            and self.role_unit_id in chain
        ):
            return Decision(True, DecisionSource.ROLE_DEFAULT, self.role_unit_id)
        return Decision(False, DecisionSource.NONE, None)

    def allows(self, permission: str, unit_id: uuid.UUID) -> bool:
        return self.decide(permission, unit_id).allowed

    def require(self, permission: str, unit_id: uuid.UUID) -> None:
        if not self.allows(permission, unit_id):
            raise AccessDeniedError(permission, unit_id)

    def units_with(self, permission: str) -> frozenset[uuid.UUID]:
        """All units on which the permission is allowed; use it to filter queries."""
        return frozenset(unit for unit in self.parents if self.allows(permission, unit))
