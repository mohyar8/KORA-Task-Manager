"""The KORA league: points per Team, and the title of the round being shown."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from kora_api.core.database import Base


class LeagueSettings(Base):
    """A single row (id = 1)."""

    __tablename__ = "league_settings"
    __table_args__ = (CheckConstraint("id = 1", name="single_row"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    round_title: Mapped[str | None] = mapped_column(String(100))
    updated_at: Mapped[datetime | None]
    updated_by_account_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_accounts.id"))


class LeagueEntry(Base):
    """Current points of one Team; changes are recorded in the audit log."""

    __tablename__ = "league_entries"
    __table_args__ = (CheckConstraint("points >= 0 AND points <= 9999", name="points_range"),)

    team_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("org_units.id"), primary_key=True)
    points: Mapped[int] = mapped_column(Integer)
    updated_at: Mapped[datetime]
    updated_by_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_accounts.id"))
