"""Seed the broad calendar view permissions and their role defaults.

calendar.view_administration: Team Leader (its Team's Administration) and Administration Manager
(its Administration). calendar.view_all: Event/Project Leader, Deputy Leader, PMO Leader and PMO
Member. A System Admin can grant either to anyone through overrides.

Revision ID: e5a7c9d1f3b4
Revises: d4f6b8c0e2a3
Create Date: 2026-10-18 13:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e5a7c9d1f3b4"
down_revision: str | Sequence[str] | None = "d4f6b8c0e2a3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERMISSIONS = [
    (
        "calendar.view_administration",
        "See the task calendar of the whole Administration that contains the unit.",
    ),
    ("calendar.view_all", "See the task calendar of every Administration."),
]
ROLE_DEFAULTS = [
    ("team_leader", "calendar.view_administration"),
    ("administration_manager", "calendar.view_administration"),
    ("event_project_leader", "calendar.view_all"),
    ("deputy_leader", "calendar.view_all"),
    ("pmo_leader", "calendar.view_all"),
    ("pmo_member", "calendar.view_all"),
]


def upgrade() -> None:
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
    keys = [key for key, _ in PERMISSIONS]
    for table, column in (
        ("permission_overrides", "permission_key"),
        ("role_permission_defaults", "permission_key"),
        ("permissions", "key"),
    ):
        op.execute(
            sa.text(f"DELETE FROM {table} WHERE {column} IN :keys").bindparams(
                sa.bindparam("keys", value=keys, expanding=True)
            )
        )
