"""End the task.create default for Member and PMO Member.

Tasks are created by Team Leaders, Administration Managers and the leadership roles, each within
their own scope. A System Admin can still grant `task.create` to anyone through an override.
History is kept: the default rows are closed, not deleted.

Revision ID: b2d4f6a8c0e1
Revises: 6b1e9c4d2a7f
Create Date: 2026-10-18 10:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b2d4f6a8c0e1"
down_revision: str | Sequence[str] | None = "6b1e9c4d2a7f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ROLES = ["member", "pmo_member"]


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE role_permission_defaults SET valid_to = now() "
            "WHERE permission_key = 'task.create' AND valid_to IS NULL AND role_key IN :roles"
        ).bindparams(sa.bindparam("roles", value=ROLES, expanding=True))
    )


def downgrade() -> None:
    for role in ROLES:
        op.execute(
            sa.text(
                "INSERT INTO role_permission_defaults (id, role_key, permission_key, valid_from) "
                "VALUES (gen_random_uuid(), :role, 'task.create', now())"
            ).bindparams(role=role)
        )
