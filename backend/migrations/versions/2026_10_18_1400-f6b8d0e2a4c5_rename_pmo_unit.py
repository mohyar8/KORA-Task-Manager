"""Use the organization's own name for the PMO unit.

Revision ID: f6b8d0e2a4c5
Revises: e5a7c9d1f3b4
Create Date: 2026-10-18 14:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f6b8d0e2a4c5"
down_revision: str | Sequence[str] | None = "e5a7c9d1f3b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PMO_UNIT_ID = "6b0a0000-0000-4000-8000-000000000002"
NEW_NAME = "مكتب إدارة المشروع (PMO)"


def upgrade() -> None:
    op.execute(
        sa.text("UPDATE org_units SET name = :name WHERE id = CAST(:id AS uuid)").bindparams(
            name=NEW_NAME, id=PMO_UNIT_ID
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text("UPDATE org_units SET name = 'PMO' WHERE id = CAST(:id AS uuid)").bindparams(
            id=PMO_UNIT_ID
        )
    )
