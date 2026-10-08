"""Seeded catalog consistency and module dependency direction."""

import ast
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kora_api.access.models import PermissionDefinition, RolePermissionDefault
from kora_api.access.permissions import PERMISSION_DESCRIPTIONS, Permission
from kora_api.organization.constants import (
    KORA_UNIT_ID,
    PMO_UNIT_ID,
    ROLES,
    UnitKind,
    UnitStatus,
)
from kora_api.organization.models import OrgRole, OrgUnit, OrgUnitPlacement

PACKAGE_DIR = Path(__file__).resolve().parents[1] / "src" / "kora_api"


def _imports(package: str) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for path in (PACKAGE_DIR / package).rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                found += [(path.name, alias.name) for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                found.append((path.name, node.module))
    return found


@pytest.mark.parametrize(
    ("package", "forbidden"),
    [
        ("access", ("kora_api.organization", "kora_api.tasks")),
        ("organization", ("kora_api.tasks", "kora_api.announcements", "kora_api.notifications")),
        ("notifications", ("kora_api.tasks", "kora_api.announcements", "kora_api.organization")),
        ("tasks", ("kora_api.announcements",)),
        ("announcements", ("kora_api.tasks",)),
    ],
)
def test_dependency_direction(package: str, forbidden: tuple[str, ...]) -> None:
    """access <- organization <- tasks/announcements -> notifications -> access."""
    offenders = [(f, m) for f, m in _imports(package) if m.startswith(forbidden)]
    assert offenders == []


@pytest.mark.anyio
async def test_seeded_catalog_matches_code(db_session: AsyncSession) -> None:
    permissions = {
        p.key: p.description for p in await db_session.scalars(select(PermissionDefinition))
    }
    assert permissions == {str(k): v for k, v in PERMISSION_DESCRIPTIONS.items()}
    assert set(permissions) == {str(p) for p in Permission}
    assert set(permissions) == {
        "organization.manage",
        "task.view",
        "task.create",
        "task.manage",
        "announcement.publish",
        "announcement.manage",
    }

    roles = {r.key: (r.name, r.unit_kind) for r in await db_session.scalars(select(OrgRole))}
    assert roles == {str(k): v for k, v in ROLES.items()}

    defaults = {
        (d.role_key, d.permission_key)
        for d in await db_session.scalars(
            select(RolePermissionDefault).where(RolePermissionDefault.valid_to.is_(None))
        )
    }
    every_role = {str(role) for role in ROLES}
    task_managers = every_role - {"pmo_member", "member"}
    assert defaults == (
        {("event_project_leader", "organization.manage"), ("deputy_leader", "organization.manage")}
        | {(role, "task.view") for role in every_role}
        | {(role, "task.create") for role in every_role}
        | {(role, "task.manage") for role in task_managers}
        | {(role, "announcement.publish") for role in task_managers}
        | {(role, "announcement.manage") for role in task_managers}
    )


@pytest.mark.anyio
async def test_seeded_kora_root_and_single_pmo(db_session: AsyncSession) -> None:
    kora = await db_session.get_one(OrgUnit, KORA_UNIT_ID)
    pmo = await db_session.get_one(OrgUnit, PMO_UNIT_ID)
    assert (kora.kind, kora.name, kora.status) == (UnitKind.ORGANIZATION, "KORA", UnitStatus.ACTIVE)
    assert (pmo.kind, pmo.name, pmo.status) == (UnitKind.PMO, "PMO", UnitStatus.ACTIVE)
    pmo_parent = await db_session.scalar(
        select(OrgUnitPlacement.parent_id).where(
            OrgUnitPlacement.unit_id == PMO_UNIT_ID, OrgUnitPlacement.valid_to.is_(None)
        )
    )
    assert pmo_parent == KORA_UNIT_ID
