"""Seed fixed data: KORA root and PMO, organizational roles, permission catalog, role defaults.

Values are written literally (not imported from application code) so this migration never
changes meaning. Tests check they match `organization.constants` and `access.permissions`.

Revision ID: c4d2e8f1a7b3
Revises: b89a71a2b1d0
Create Date: 2026-10-07 19:50:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c4d2e8f1a7b3"
down_revision: str | Sequence[str] | None = "b89a71a2b1d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KORA_UNIT_ID = "6b0a0000-0000-4000-8000-000000000001"
PMO_UNIT_ID = "6b0a0000-0000-4000-8000-000000000002"

ROLES = [
    ("event_project_leader", "Event/Project Leader", "organization"),
    ("deputy_leader", "Deputy Leader", "organization"),
    ("pmo_leader", "PMO Leader", "pmo"),
    ("pmo_member", "PMO Member", "pmo"),
    ("administration_manager", "Administration Manager", "administration"),
    ("team_leader", "Team Leader", "team"),
    ("member", "Member", "team"),
]

PERMISSIONS = [
    ("organization.manage", "Create, move and archive organizational units within scope."),
]

ROLE_DEFAULTS = [
    ("event_project_leader", "organization.manage"),
    ("deputy_leader", "organization.manage"),
]


def upgrade() -> None:
    op.execute(
        sa.text(
            "INSERT INTO org_units (id, kind, name, status, created_at) VALUES "
            "(CAST(:kora AS uuid), 'organization', 'KORA', 'active', now()), "
            "(CAST(:pmo AS uuid), 'pmo', 'PMO', 'active', now())"
        ).bindparams(kora=KORA_UNIT_ID, pmo=PMO_UNIT_ID)
    )
    op.execute(
        sa.text(
            "INSERT INTO org_unit_placements (id, unit_id, parent_id, valid_from) "
            "VALUES (gen_random_uuid(), CAST(:pmo AS uuid), CAST(:kora AS uuid), now())"
        ).bindparams(kora=KORA_UNIT_ID, pmo=PMO_UNIT_ID)
    )
    for key, name, unit_kind in ROLES:
        op.execute(
            sa.text(
                "INSERT INTO org_roles (key, name, unit_kind) "
                "VALUES (:key, :name, CAST(:unit_kind AS org_unit_kind))"
            ).bindparams(key=key, name=name, unit_kind=unit_kind)
        )
    for key, description in PERMISSIONS:
        op.execute(
            sa.text(
                "INSERT INTO permissions (key, description) VALUES (:key, :description)"
            ).bindparams(key=key, description=description)
        )
    for role_key, permission_key in ROLE_DEFAULTS:
        op.execute(
            sa.text(
                "INSERT INTO role_permission_defaults (id, role_key, permission_key, valid_from) "
                "VALUES (gen_random_uuid(), :role_key, :permission_key, now())"
            ).bindparams(role_key=role_key, permission_key=permission_key)
        )


def downgrade() -> None:
    op.execute("DELETE FROM role_permission_defaults WHERE created_by_account_id IS NULL")
    op.execute("DELETE FROM permissions")
    op.execute("DELETE FROM org_roles")
    op.execute("DELETE FROM org_unit_placements WHERE created_by_account_id IS NULL")
    op.execute(
        sa.text(
            "DELETE FROM org_units WHERE id IN (CAST(:kora AS uuid), CAST(:pmo AS uuid))"
        ).bindparams(kora=KORA_UNIT_ID, pmo=PMO_UNIT_ID)
    )
