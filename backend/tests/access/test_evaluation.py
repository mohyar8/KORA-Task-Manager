"""Pure tests of the effective-access precedence rules (no database)."""

import random
import uuid
from datetime import UTC, datetime

import pytest

from kora_api.access.evaluation import (
    AccessDeniedError,
    AccessSnapshot,
    DecisionSource,
    OverrideRule,
)
from kora_api.access.permissions import OverrideEffect

P = "organization.manage"
OTHER = "other.permission"
GRANT, DENY = OverrideEffect.GRANT, OverrideEffect.DENY
AT = datetime(2026, 1, 1, tzinfo=UTC)

ROOT, ADMIN_A, ADMIN_B, TEAM_A1, TEAM_A2, TEAM_B1 = (uuid.uuid4() for _ in range(6))
TREE: dict[uuid.UUID, uuid.UUID | None] = {
    ROOT: None,
    ADMIN_A: ROOT,
    ADMIN_B: ROOT,
    TEAM_A1: ADMIN_A,
    TEAM_A2: ADMIN_A,
    TEAM_B1: ADMIN_B,
}


def snap(
    *overrides: tuple[uuid.UUID, OverrideEffect],
    role_unit: uuid.UUID | None = None,
    role_permissions: frozenset[str] = frozenset({P}),
    permission: str = P,
) -> AccessSnapshot:
    return AccessSnapshot(
        at=AT,
        parents=TREE,
        role_unit_id=role_unit,
        role_permissions=role_permissions if role_unit else frozenset(),
        overrides=tuple(OverrideRule(permission, unit, effect) for unit, effect in overrides),
    )


def test_role_default_covers_its_unit_and_descendants_only() -> None:
    access = snap(role_unit=ADMIN_A)

    assert access.units_with(P) == {ADMIN_A, TEAM_A1, TEAM_A2}
    assert access.decide(P, TEAM_A1).source == DecisionSource.ROLE_DEFAULT
    assert not access.allows(P, ROOT)
    assert not access.allows(P, TEAM_B1)


def test_role_default_applies_only_to_permissions_the_role_has() -> None:
    access = snap(role_unit=ROOT)

    assert access.allows(P, TEAM_B1)
    assert not access.allows(OTHER, TEAM_B1)


def test_no_role_and_no_overrides_allows_nothing() -> None:
    assert snap().units_with(P) == frozenset()


def test_unknown_unit_is_denied() -> None:
    access = snap(role_unit=ROOT)

    assert not access.allows(P, uuid.uuid4())
    with pytest.raises(AccessDeniedError):
        access.require(P, uuid.uuid4())


def test_grant_override_expands_beyond_role_default() -> None:
    access = snap((ADMIN_B, GRANT), role_unit=TEAM_A1)

    assert access.units_with(P) == {TEAM_A1, ADMIN_B, TEAM_B1}
    assert access.decide(P, TEAM_B1).source == DecisionSource.OVERRIDE_GRANT


def test_grant_override_works_without_any_role() -> None:
    access = snap((ROOT, GRANT))

    assert access.units_with(P) == set(TREE)


def test_deny_override_restricts_role_default() -> None:
    access = snap((TEAM_A1, DENY), role_unit=ROOT)

    decision = access.decide(P, TEAM_A1)
    assert not decision.allowed
    assert decision.source == DecisionSource.OVERRIDE_DENY
    assert decision.decided_at_unit_id == TEAM_A1
    assert access.allows(P, TEAM_A2)
    assert access.allows(P, ADMIN_A)


def test_most_specific_override_wins() -> None:
    deny_broad_grant_narrow = snap((ROOT, DENY), (TEAM_A1, GRANT))
    assert deny_broad_grant_narrow.allows(P, TEAM_A1)
    assert not deny_broad_grant_narrow.allows(P, TEAM_A2)

    grant_broad_deny_narrow = snap((ROOT, GRANT), (ADMIN_A, DENY))
    assert not grant_broad_deny_narrow.allows(P, TEAM_A2)
    assert grant_broad_deny_narrow.allows(P, TEAM_B1)


def test_deny_wins_over_grant_at_the_same_scope() -> None:
    access = snap((ADMIN_A, GRANT), (ADMIN_A, DENY), role_unit=ROOT)

    assert access.decide(P, TEAM_A1).source == DecisionSource.OVERRIDE_DENY
    assert not access.allows(P, ADMIN_A)


def test_override_for_another_permission_does_not_apply() -> None:
    access = snap((ROOT, GRANT), permission=OTHER)

    assert not access.allows(P, ROOT)
    assert access.allows(OTHER, ROOT)


def test_units_with_matches_decide_on_random_trees() -> None:
    rng = random.Random(4242)
    for _ in range(200):
        units = [uuid.uuid4() for _ in range(rng.randint(1, 12))]
        parents: dict[uuid.UUID, uuid.UUID | None] = {units[0]: None}
        for index, unit in enumerate(units[1:], start=1):
            parents[unit] = units[rng.randrange(index)]
        overrides = tuple(
            OverrideRule(P, rng.choice(units), rng.choice([GRANT, DENY]))
            for _ in range(rng.randint(0, 4))
        )
        access = AccessSnapshot(
            at=AT,
            parents=parents,
            role_unit_id=rng.choice([None, *units]),
            role_permissions=frozenset({P}),
            overrides=overrides,
        )
        expected = {unit for unit in units if access.decide(P, unit).allowed}
        assert access.units_with(P) == expected
        for unit in units:
            chain = access.chain(unit)
            overridden = [u for u in chain if any(o.unit_id == u for o in overrides)]
            if overridden:
                nearest = overridden[0]
                effects = {o.effect for o in overrides if o.unit_id == nearest}
                assert access.allows(P, unit) == (DENY not in effects)
            else:
                assert access.allows(P, unit) == (access.role_unit_id in chain)
