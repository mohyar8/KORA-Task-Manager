"""Seed task.follow and its role defaults.

task.follow lets the PMO Leader and PMO Members read every team's tasks on the follow-up page.
It is read-only (no create, edit or comment) and a System Admin can grant it to anyone.

Revision ID: a7c9e1f3b5d6
Revises: f6b8d0e2a4c5
Create Date: 2026-10-19 10:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a7c9e1f3b5d6"
down_revision: str | Sequence[str] | None = "f6b8d0e2a4c5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KEY = "task.follow"
DESCRIPTION = "Follow up every task of every team (read-only)."
ROLES = ["pmo_leader", "pmo_member"]


def upgrade() -> None:
    op.execute(
        sa.text(
            "INSERT INTO permissions (key, description) VALUES (:key, :description)"
        ).bindparams(key=KEY, description=DESCRIPTION)
    )
    for role in ROLES:
        op.execute(
            sa.text(
                "INSERT INTO role_permission_defaults (id, role_key, permission_key, valid_from) "
                "VALUES (gen_random_uuid(), :role, :key, now())"
            ).bindparams(role=role, key=KEY)
        )


def downgrade() -> None:
    for table, column in (
        ("permission_overrides", "permission_key"),
        ("role_permission_defaults", "permission_key"),
        ("permissions", "key"),
    ):
        op.execute(sa.text(f"DELETE FROM {table} WHERE {column} = :key").bindparams(key=KEY))
