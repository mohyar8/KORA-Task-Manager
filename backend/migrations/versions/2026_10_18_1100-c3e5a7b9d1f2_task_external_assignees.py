"""Mark task assignments given through 'Other' (outside the task's scope).

Existing open assignments of the Event Leader, Deputy and PMO Leader become external: they were
assigned before these roles were kept out of the regular assignee list, and must stay assigned.

Revision ID: c3e5a7b9d1f2
Revises: b2d4f6a8c0e1
Create Date: 2026-10-18 11:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c3e5a7b9d1f2"
down_revision: str | Sequence[str] | None = "b2d4f6a8c0e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TOP_ROLES = ["event_project_leader", "deputy_leader", "pmo_leader"]


def upgrade() -> None:
    op.add_column(
        "task_assignments",
        sa.Column("is_external", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.execute(
        sa.text(
            "UPDATE task_assignments SET is_external = true "
            "WHERE valid_to IS NULL AND member_id IN "
            "(SELECT member_id FROM role_assignments WHERE valid_to IS NULL AND role_key IN :roles)"
        ).bindparams(sa.bindparam("roles", value=TOP_ROLES, expanding=True))
    )


def downgrade() -> None:
    op.drop_column("task_assignments", "is_external")
