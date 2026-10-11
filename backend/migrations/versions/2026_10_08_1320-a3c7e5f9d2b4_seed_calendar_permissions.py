"""Seed calendar permissions and their role defaults.

calendar.create: every organizational role (at its assigned unit).
calendar.manage: Event/Project Leader and Deputy Leader (KORA), PMO Leader (PMO), Administration
Manager (its Administration), Team Leader (its Team). Not PMO Member or Member.

Revision ID: a3c7e5f9d2b4
Revises: 9ddea54afcb3
Create Date: 2026-10-08 13:20:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a3c7e5f9d2b4"
down_revision: str | Sequence[str] | None = "9ddea54afcb3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERMISSIONS = [
    ("calendar.create", "Create events and meetings within scope (active Members only)."),
    ("calendar.manage", "See, edit and cancel events and meetings within scope."),
]
MANAGERS = [
    "event_project_leader",
    "deputy_leader",
    "pmo_leader",
    "administration_manager",
    "team_leader",
]
ALL_ROLES = [*MANAGERS, "pmo_member", "member"]
ROLE_DEFAULTS = [(role, "calendar.create") for role in ALL_ROLES] + [
    (role, "calendar.manage") for role in MANAGERS
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
