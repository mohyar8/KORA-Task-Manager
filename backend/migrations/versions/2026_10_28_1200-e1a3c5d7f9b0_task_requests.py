"""Task requests between Administrations; `task_request` notification category; permissions.

`task_request.create` and `task_request.respond` go to the Administration Manager (at their
Administration) and to the Event/Project Leader and Deputy Leader (at KORA).

Revision ID: e1a3c5d7f9b0
Revises: d0f2b4c6e8a9
Create Date: 2026-10-28 12:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e1a3c5d7f9b0"
down_revision: str | Sequence[str] | None = "d0f2b4c6e8a9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERMISSIONS = (
    ("task_request.create", "Ask another Administration for a task (from the unit)."),
    ("task_request.respond", "Accept or reject task requests sent to the Administration."),
)
ROLES = ("administration_manager", "event_project_leader", "deputy_leader")
OLD_CATEGORIES = (
    "task_assignment",
    "task_update",
    "task_comment",
    "announcement_new",
    "announcement_change",
    "calendar_event",
    "task_review",
)


def upgrade() -> None:
    # A new enum value cannot be used in the transaction that adds it; nothing here uses it.
    op.execute("ALTER TYPE notification_category ADD VALUE IF NOT EXISTS 'task_request'")
    op.add_column("tasks", sa.Column("requested_by_member_id", sa.Uuid(), nullable=True))
    op.add_column("tasks", sa.Column("requested_from_unit_id", sa.Uuid(), nullable=True))
    op.create_index(
        op.f("ix_tasks_requested_by_member_id"), "tasks", ["requested_by_member_id"], unique=False
    )
    op.create_foreign_key(
        op.f("fk_tasks_requested_by_member_id_members"),
        "tasks",
        "members",
        ["requested_by_member_id"],
        ["id"],
    )
    op.create_foreign_key(
        op.f("fk_tasks_requested_from_unit_id_org_units"),
        "tasks",
        "org_units",
        ["requested_from_unit_id"],
        ["id"],
    )

    status = sa.Enum("pending", "accepted", "rejected", "withdrawn", name="task_request_status")
    status.create(op.get_bind(), checkfirst=False)
    op.create_table(
        "task_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "priority",
            sa.Enum("low", "normal", "high", "urgent", name="task_priority", create_type=False),
            nullable=True,
        ),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("from_unit_id", sa.Uuid(), nullable=False),
        sa.Column("to_unit_id", sa.Uuid(), nullable=False),
        sa.Column("requested_by_member_id", sa.Uuid(), nullable=False),
        sa.Column("requested_by_account_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "accepted",
                "rejected",
                "withdrawn",
                name="task_request_status",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("decided_by_member_id", sa.Uuid(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.String(length=1000), nullable=True),
        sa.Column("resulting_task_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "from_unit_id <> to_unit_id", name=op.f("ck_task_requests_different_units")
        ),
        sa.ForeignKeyConstraint(
            ["from_unit_id"], ["org_units.id"], name=op.f("fk_task_requests_from_unit_id_org_units")
        ),
        sa.ForeignKeyConstraint(
            ["to_unit_id"], ["org_units.id"], name=op.f("fk_task_requests_to_unit_id_org_units")
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_member_id"],
            ["members.id"],
            name=op.f("fk_task_requests_requested_by_member_id_members"),
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_account_id"],
            ["user_accounts.id"],
            name=op.f("fk_task_requests_requested_by_account_id_user_accounts"),
        ),
        sa.ForeignKeyConstraint(
            ["decided_by_member_id"],
            ["members.id"],
            name=op.f("fk_task_requests_decided_by_member_id_members"),
        ),
        sa.ForeignKeyConstraint(
            ["resulting_task_id"],
            ["tasks.id"],
            name=op.f("fk_task_requests_resulting_task_id_tasks"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_task_requests")),
    )
    op.create_index(op.f("ix_task_requests_from_unit_id"), "task_requests", ["from_unit_id"])
    op.create_index(
        op.f("ix_task_requests_requested_by_member_id"), "task_requests", ["requested_by_member_id"]
    )
    op.create_index("ix_task_requests_to_unit_status", "task_requests", ["to_unit_id", "status"])

    for key, description in PERMISSIONS:
        op.execute(
            sa.text(
                "INSERT INTO permissions (key, description) VALUES (:key, :description)"
            ).bindparams(key=key, description=description)
        )
        for role in ROLES:
            op.execute(
                sa.text(
                    "INSERT INTO role_permission_defaults "
                    "(id, role_key, permission_key, valid_from) "
                    "VALUES (gen_random_uuid(), :role, :key, now())"
                ).bindparams(role=role, key=key)
            )


def downgrade() -> None:
    for key, _ in PERMISSIONS:
        for table in ("permission_overrides", "role_permission_defaults"):
            op.execute(
                sa.text(f"DELETE FROM {table} WHERE permission_key = :key").bindparams(key=key)
            )
        op.execute(sa.text("DELETE FROM permissions WHERE key = :key").bindparams(key=key))
    op.drop_index("ix_task_requests_to_unit_status", table_name="task_requests")
    op.drop_index(op.f("ix_task_requests_requested_by_member_id"), table_name="task_requests")
    op.drop_index(op.f("ix_task_requests_from_unit_id"), table_name="task_requests")
    op.drop_table("task_requests")
    sa.Enum(name="task_request_status").drop(op.get_bind(), checkfirst=False)
    op.drop_constraint(
        op.f("fk_tasks_requested_from_unit_id_org_units"), "tasks", type_="foreignkey"
    )
    op.drop_constraint(op.f("fk_tasks_requested_by_member_id_members"), "tasks", type_="foreignkey")
    op.drop_index(op.f("ix_tasks_requested_by_member_id"), table_name="tasks")
    op.drop_column("tasks", "requested_from_unit_id")
    op.drop_column("tasks", "requested_by_member_id")
    # Postgres cannot drop an enum value: rebuild the type without `task_request`.
    op.execute("DELETE FROM notifications WHERE category = 'task_request'")
    op.execute("DELETE FROM notification_preferences WHERE category = 'task_request'")
    op.execute("ALTER TYPE notification_category RENAME TO notification_category_old")
    values = ", ".join(f"'{c}'" for c in OLD_CATEGORIES)
    op.execute(f"CREATE TYPE notification_category AS ENUM ({values})")
    for table in ("notifications", "notification_preferences"):
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN category TYPE notification_category "
            "USING category::text::notification_category"
        )
    op.execute("DROP TYPE notification_category_old")
