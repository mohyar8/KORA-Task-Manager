"""Per-assignee progress and review tasks; `task_review` notification category.

Revision ID: c9e1a3b5d7f8
Revises: b8d0f2a4c6e7
Create Date: 2026-10-28 10:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c9e1a3b5d7f8"
down_revision: str | Sequence[str] | None = "b8d0f2a4c6e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_CATEGORIES = (
    "task_assignment",
    "task_update",
    "task_comment",
    "announcement_new",
    "announcement_change",
    "calendar_event",
)


def upgrade() -> None:
    op.execute("ALTER TYPE notification_category ADD VALUE IF NOT EXISTS 'task_review'")
    kind = sa.Enum("regular", "review", name="task_kind")
    kind.create(op.get_bind(), checkfirst=False)
    op.add_column(
        "tasks",
        sa.Column(
            "kind",
            sa.Enum("regular", "review", name="task_kind", create_type=False),
            server_default=sa.text("'regular'"),
            nullable=False,
        ),
    )
    op.add_column("tasks", sa.Column("review_of_task_id", sa.Uuid(), nullable=True))
    op.add_column("tasks", sa.Column("review_member_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_tasks_review_of_task_id_tasks"), "tasks", "tasks", ["review_of_task_id"], ["id"]
    )
    op.create_foreign_key(
        op.f("fk_tasks_review_member_id_members"), "tasks", "members", ["review_member_id"], ["id"]
    )
    op.create_check_constraint(
        op.f("ck_tasks_review_fields"),
        "tasks",
        "(kind = 'review') = (review_of_task_id IS NOT NULL AND review_member_id IS NOT NULL)",
    )
    op.create_index(
        "uq_tasks_review",
        "tasks",
        ["review_of_task_id", "review_member_id"],
        unique=True,
        postgresql_where=sa.text("review_of_task_id IS NOT NULL"),
    )
    op.create_table(
        "task_part_progress",
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("member_id", sa.Uuid(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["member_id"], ["members.id"], name=op.f("fk_task_part_progress_member_id_members")
        ),
        sa.ForeignKeyConstraint(
            ["task_id"], ["tasks.id"], name=op.f("fk_task_part_progress_task_id_tasks")
        ),
        sa.PrimaryKeyConstraint("task_id", "member_id", name=op.f("pk_task_part_progress")),
    )


def downgrade() -> None:
    op.drop_table("task_part_progress")
    op.drop_index("uq_tasks_review", table_name="tasks")
    op.drop_constraint(op.f("ck_tasks_review_fields"), "tasks", type_="check")
    op.drop_constraint(op.f("fk_tasks_review_member_id_members"), "tasks", type_="foreignkey")
    op.drop_constraint(op.f("fk_tasks_review_of_task_id_tasks"), "tasks", type_="foreignkey")
    op.drop_column("tasks", "review_member_id")
    op.drop_column("tasks", "review_of_task_id")
    op.drop_column("tasks", "kind")
    sa.Enum(name="task_kind").drop(op.get_bind(), checkfirst=False)
    # PostgreSQL cannot drop an enum value: rebuild notification_category without it.
    op.execute("DELETE FROM notifications WHERE category = 'task_review'")
    op.execute("DELETE FROM notification_preferences WHERE category = 'task_review'")
    op.execute("ALTER TYPE notification_category RENAME TO notification_category_old")
    values = ", ".join(f"'{value}'" for value in OLD_CATEGORIES)
    op.execute(f"CREATE TYPE notification_category AS ENUM ({values})")
    for table in ("notifications", "notification_preferences"):
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN category TYPE notification_category "
            "USING category::text::notification_category"
        )
    op.execute("DROP TYPE notification_category_old")
