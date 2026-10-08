"""Seed task permissions and their role defaults.

task.view and task.create: every organizational role (at its assigned unit).
task.manage: Event/Project Leader and Deputy Leader (KORA), PMO Leader (PMO), Administration
Manager (its Administration), Team Leader (its Team). Not PMO Member or Member.

Values are literal so this migration never changes meaning; tests compare them with the code.

Revision ID: d7e3a1c9b5f2
Revises: 7eb2d45fba99
Create Date: 2026-10-07 23:40:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d7e3a1c9b5f2"
down_revision: str | Sequence[str] | None = "7eb2d45fba99"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERMISSIONS = [
    ("task.view", "See tasks within scope."),
    ("task.create", "Create tasks within scope (active Members only)."),
    ("task.manage", "Manage any task within scope."),
]

ALL_ROLES = [
    "event_project_leader",
    "deputy_leader",
    "pmo_leader",
    "pmo_member",
    "administration_manager",
    "team_leader",
    "member",
]
MANAGERS = [
    "event_project_leader",
    "deputy_leader",
    "pmo_leader",
    "administration_manager",
    "team_leader",
]

ROLE_DEFAULTS = (
    [(role, "task.view") for role in ALL_ROLES]
    + [(role, "task.create") for role in ALL_ROLES]
    + [(role, "task.manage") for role in MANAGERS]
)


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
