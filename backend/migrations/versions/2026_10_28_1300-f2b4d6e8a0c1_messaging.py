"""Chat: conversations, messages, read markers; `chat_message` category; `chat.moderate`.

`chat.moderate` goes to the Team Leader, Administration Manager, PMO Leader, Event/Project Leader
and Deputy Leader (each at their own unit, so each moderates the channels of their unit).

Revision ID: f2b4d6e8a0c1
Revises: e1a3c5d7f9b0
Create Date: 2026-10-28 13:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f2b4d6e8a0c1"
down_revision: str | Sequence[str] | None = "e1a3c5d7f9b0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KEY = "chat.moderate"
DESCRIPTION = "Delete other people's messages in the chat channels of the unit."
ROLES = (
    "team_leader",
    "administration_manager",
    "pmo_leader",
    "event_project_leader",
    "deputy_leader",
)
OLD_CATEGORIES = (
    "task_assignment",
    "task_update",
    "task_comment",
    "announcement_new",
    "announcement_change",
    "calendar_event",
    "task_review",
    "task_request",
)


def upgrade() -> None:
    op.execute("ALTER TYPE notification_category ADD VALUE IF NOT EXISTS 'chat_message'")
    kind = sa.Enum("direct", "unit", "organization", name="conversation_kind")
    kind.create(op.get_bind(), checkfirst=False)
    op.create_table(
        "conversations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum("direct", "unit", "organization", name="conversation_kind", create_type=False),
            nullable=False,
        ),
        sa.Column("unit_id", sa.Uuid(), nullable=True),
        sa.Column("direct_a_id", sa.Uuid(), nullable=True),
        sa.Column("direct_b_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(kind = 'direct' AND direct_a_id IS NOT NULL AND direct_b_id IS NOT NULL"
            " AND direct_a_id < direct_b_id AND unit_id IS NULL)"
            " OR (kind = 'unit' AND unit_id IS NOT NULL AND direct_a_id IS NULL"
            " AND direct_b_id IS NULL)"
            " OR (kind = 'organization' AND unit_id IS NULL AND direct_a_id IS NULL"
            " AND direct_b_id IS NULL)",
            name=op.f("ck_conversations_shape"),
        ),
        sa.ForeignKeyConstraint(
            ["unit_id"], ["org_units.id"], name=op.f("fk_conversations_unit_id_org_units")
        ),
        sa.ForeignKeyConstraint(
            ["direct_a_id"], ["members.id"], name=op.f("fk_conversations_direct_a_id_members")
        ),
        sa.ForeignKeyConstraint(
            ["direct_b_id"], ["members.id"], name=op.f("fk_conversations_direct_b_id_members")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_conversations")),
    )
    op.create_index(
        "uq_conversations_direct",
        "conversations",
        ["direct_a_id", "direct_b_id"],
        unique=True,
        postgresql_where=sa.text("kind = 'direct'"),
    )
    op.create_index(
        "uq_conversations_unit",
        "conversations",
        ["unit_id"],
        unique=True,
        postgresql_where=sa.text("kind = 'unit'"),
    )
    op.create_index(
        "uq_conversations_organization",
        "conversations",
        ["kind"],
        unique=True,
        postgresql_where=sa.text("kind = 'organization'"),
    )
    op.create_table(
        "messages",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("author_member_id", sa.Uuid(), nullable=False),
        sa.Column("body", sa.String(length=2000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            name=op.f("fk_messages_conversation_id_conversations"),
        ),
        sa.ForeignKeyConstraint(
            ["author_member_id"], ["members.id"], name=op.f("fk_messages_author_member_id_members")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_messages")),
    )
    op.create_index("ix_messages_conversation_id_id", "messages", ["conversation_id", "id"])
    op.create_index("ix_messages_author_created", "messages", ["author_member_id", "created_at"])
    op.create_table(
        "conversation_reads",
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("member_id", sa.Uuid(), nullable=False),
        sa.Column("last_read_message_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            name=op.f("fk_conversation_reads_conversation_id_conversations"),
        ),
        sa.ForeignKeyConstraint(
            ["member_id"], ["members.id"], name=op.f("fk_conversation_reads_member_id_members")
        ),
        sa.PrimaryKeyConstraint("conversation_id", "member_id", name=op.f("pk_conversation_reads")),
    )
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
    for table in ("permission_overrides", "role_permission_defaults"):
        op.execute(sa.text(f"DELETE FROM {table} WHERE permission_key = :key").bindparams(key=KEY))
    op.execute(sa.text("DELETE FROM permissions WHERE key = :key").bindparams(key=KEY))
    op.drop_table("conversation_reads")
    op.drop_index("ix_messages_author_created", table_name="messages")
    op.drop_index("ix_messages_conversation_id_id", table_name="messages")
    op.drop_table("messages")
    op.drop_index("uq_conversations_organization", table_name="conversations")
    op.drop_index("uq_conversations_unit", table_name="conversations")
    op.drop_index("uq_conversations_direct", table_name="conversations")
    op.drop_table("conversations")
    sa.Enum(name="conversation_kind").drop(op.get_bind(), checkfirst=False)
    op.execute("DELETE FROM notifications WHERE category = 'chat_message'")
    op.execute("DELETE FROM notification_preferences WHERE category = 'chat_message'")
    op.execute("ALTER TYPE notification_category RENAME TO notification_category_old")
    values = ", ".join(f"'{c}'" for c in OLD_CATEGORIES)
    op.execute(f"CREATE TYPE notification_category AS ENUM ({values})")
    for table in ("notifications", "notification_preferences"):
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN category TYPE notification_category "
            "USING category::text::notification_category"
        )
    op.execute("DROP TYPE notification_category_old")
