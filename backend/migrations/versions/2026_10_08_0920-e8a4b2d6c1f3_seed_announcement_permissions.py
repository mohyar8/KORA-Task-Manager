"""Seed announcement permissions and their role defaults.

announcement.publish and announcement.manage: Event/Project Leader, Deputy Leader, PMO Leader,
Administration Manager and Team Leader (each at its assigned unit). Not PMO Member or Member.

Revision ID: e8a4b2d6c1f3
Revises: 01947ff726ab
Create Date: 2026-10-08 09:20:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e8a4b2d6c1f3"
down_revision: str | Sequence[str] | None = "01947ff726ab"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERMISSIONS = [
    ("announcement.publish", "Draft and publish announcements within scope."),
    ("announcement.manage", "See, edit and withdraw announcements within scope."),
]
ROLES = [
    "event_project_leader",
    "deputy_leader",
    "pmo_leader",
    "administration_manager",
    "team_leader",
]


def upgrade() -> None:
    for key, description in PERMISSIONS:
        op.execute(
            sa.text(
                "INSERT INTO permissions (key, description) VALUES (:key, :description)"
            ).bindparams(key=key, description=description)
        )
        for role_key in ROLES:
            op.execute(
                sa.text(
                    "INSERT INTO role_permission_defaults "
                    "(id, role_key, permission_key, valid_from) "
                    "VALUES (gen_random_uuid(), :role_key, :permission_key, now())"
                ).bindparams(role_key=role_key, permission_key=key)
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
