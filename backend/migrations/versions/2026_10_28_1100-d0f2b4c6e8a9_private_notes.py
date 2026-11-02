"""Private notes (one per account).

Revision ID: d0f2b4c6e8a9
Revises: c9e1a3b5d7f8
Create Date: 2026-10-28 11:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d0f2b4c6e8a9"
down_revision: str | Sequence[str] | None = "c9e1a3b5d7f8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "private_notes",
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("body", sa.String(length=5000), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("char_length(body) <= 5000", name=op.f("ck_private_notes_body_length")),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["user_accounts.id"],
            name=op.f("fk_private_notes_account_id_user_accounts"),
        ),
        sa.PrimaryKeyConstraint("account_id", name=op.f("pk_private_notes")),
    )


def downgrade() -> None:
    op.drop_table("private_notes")
