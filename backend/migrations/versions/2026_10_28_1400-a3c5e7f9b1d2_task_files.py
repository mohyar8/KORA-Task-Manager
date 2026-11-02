"""Task files (metadata; the bytes live in the object store).

Revision ID: a3c5e7f9b1d2
Revises: f2b4d6e8a0c1
Create Date: 2026-10-28 14:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a3c5e7f9b1d2"
down_revision: str | Sequence[str] | None = "f2b4d6e8a0c1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    sa.Enum("brief", "delivery", name="task_file_kind").create(op.get_bind(), checkfirst=False)
    sa.Enum("pending", "ready", name="task_file_status").create(op.get_bind(), checkfirst=False)
    op.create_table(
        "task_files",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum("brief", "delivery", name="task_file_kind", create_type=False),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=True),
        sa.Column("storage_key", sa.String(length=200), nullable=False),
        sa.Column("uploaded_by_member_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "ready", name="task_file_status", create_type=False),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["task_id"], ["tasks.id"], name=op.f("fk_task_files_task_id_tasks")
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by_member_id"],
            ["members.id"],
            name=op.f("fk_task_files_uploaded_by_member_id_members"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_task_files")),
        sa.UniqueConstraint("storage_key", name=op.f("uq_task_files_storage_key")),
    )
    op.create_index("ix_task_files_task_kind", "task_files", ["task_id", "kind"])


def downgrade() -> None:
    op.drop_index("ix_task_files_task_kind", table_name="task_files")
    op.drop_table("task_files")
    sa.Enum(name="task_file_status").drop(op.get_bind(), checkfirst=False)
    sa.Enum(name="task_file_kind").drop(op.get_bind(), checkfirst=False)
