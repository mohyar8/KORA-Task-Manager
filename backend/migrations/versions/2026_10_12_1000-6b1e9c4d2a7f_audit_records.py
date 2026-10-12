"""Central append-only audit log (`audit_records`).

A trigger rejects UPDATE, DELETE and TRUNCATE, so records can only be inserted. Nothing is
backfilled: the log starts with changes made after this migration.

Revision ID: 6b1e9c4d2a7f
Revises: a3c7e5f9d2b4
Create Date: 2026-10-12 10:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "6b1e9c4d2a7f"
down_revision: str | Sequence[str] | None = "a3c7e5f9d2b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("actor_account_id", sa.Uuid(), nullable=True),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("scope_unit_id", sa.Uuid(), nullable=True),
        sa.Column("before", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.CheckConstraint("length(action) > 0", name=op.f("ck_audit_records_action_required")),
        sa.CheckConstraint(
            "length(resource_type) > 0", name=op.f("ck_audit_records_resource_type_required")
        ),
        sa.ForeignKeyConstraint(
            ["actor_account_id"],
            ["user_accounts.id"],
            name=op.f("fk_audit_records_actor_account_id_user_accounts"),
        ),
        sa.ForeignKeyConstraint(
            ["scope_unit_id"],
            ["org_units.id"],
            name=op.f("fk_audit_records_scope_unit_id_org_units"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_records")),
        sa.UniqueConstraint("sequence", name=op.f("uq_audit_records_sequence")),
    )
    op.create_index(op.f("ix_audit_records_action"), "audit_records", ["action"])
    op.create_index(
        op.f("ix_audit_records_actor_account_id"), "audit_records", ["actor_account_id"]
    )
    op.create_index(op.f("ix_audit_records_occurred_at"), "audit_records", ["occurred_at"])
    op.create_index(op.f("ix_audit_records_scope_unit_id"), "audit_records", ["scope_unit_id"])
    op.create_index("ix_audit_records_resource", "audit_records", ["resource_type", "resource_id"])
    op.execute(
        """
        CREATE FUNCTION audit_records_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'audit_records is append-only';
        END;
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER audit_records_no_update_delete BEFORE UPDATE OR DELETE ON audit_records "
        "FOR EACH ROW EXECUTE FUNCTION audit_records_append_only()"
    )
    op.execute(
        "CREATE TRIGGER audit_records_no_truncate BEFORE TRUNCATE ON audit_records "
        "FOR EACH STATEMENT EXECUTE FUNCTION audit_records_append_only()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER audit_records_no_truncate ON audit_records")
    op.execute("DROP TRIGGER audit_records_no_update_delete ON audit_records")
    op.execute("DROP FUNCTION audit_records_append_only()")
    op.drop_index("ix_audit_records_resource", table_name="audit_records")
    op.drop_index(op.f("ix_audit_records_scope_unit_id"), table_name="audit_records")
    op.drop_index(op.f("ix_audit_records_occurred_at"), table_name="audit_records")
    op.drop_index(op.f("ix_audit_records_actor_account_id"), table_name="audit_records")
    op.drop_index(op.f("ix_audit_records_action"), table_name="audit_records")
    op.drop_table("audit_records")
