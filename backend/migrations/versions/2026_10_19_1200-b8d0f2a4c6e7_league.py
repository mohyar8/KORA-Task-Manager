"""The KORA league: tables and the league.manage permission (PMO Leader by default).

Revision ID: b8d0f2a4c6e7
Revises: a7c9e1f3b5d6
Create Date: 2026-10-19 12:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b8d0f2a4c6e7"
down_revision: str | Sequence[str] | None = "a7c9e1f3b5d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KEY = "league.manage"
DESCRIPTION = "Set the points and round title of the KORA league."


def upgrade() -> None:
    op.create_table(
        "league_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("round_title", sa.String(length=100), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_by_account_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint("id = 1", name=op.f("ck_league_settings_single_row")),
        sa.ForeignKeyConstraint(
            ["updated_by_account_id"],
            ["user_accounts.id"],
            name=op.f("fk_league_settings_updated_by_account_id_user_accounts"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_league_settings")),
    )
    op.create_table(
        "league_entries",
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by_account_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "points >= 0 AND points <= 9999", name=op.f("ck_league_entries_points_range")
        ),
        sa.ForeignKeyConstraint(
            ["team_id"], ["org_units.id"], name=op.f("fk_league_entries_team_id_org_units")
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_account_id"],
            ["user_accounts.id"],
            name=op.f("fk_league_entries_updated_by_account_id_user_accounts"),
        ),
        sa.PrimaryKeyConstraint("team_id", name=op.f("pk_league_entries")),
    )
    op.execute(
        sa.text(
            "INSERT INTO permissions (key, description) VALUES (:key, :description)"
        ).bindparams(key=KEY, description=DESCRIPTION)
    )
    op.execute(
        sa.text(
            "INSERT INTO role_permission_defaults (id, role_key, permission_key, valid_from) "
            "VALUES (gen_random_uuid(), 'pmo_leader', :key, now())"
        ).bindparams(key=KEY)
    )


def downgrade() -> None:
    for table in ("permission_overrides", "role_permission_defaults"):
        op.execute(sa.text(f"DELETE FROM {table} WHERE permission_key = :key").bindparams(key=KEY))
    op.execute(sa.text("DELETE FROM permissions WHERE key = :key").bindparams(key=KEY))
    op.drop_table("league_entries")
    op.drop_table("league_settings")
