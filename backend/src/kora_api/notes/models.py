"""Private notes: one per account, readable only by its owner."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from kora_api.core.database import Base

MAX_LENGTH = 5_000


class PrivateNote(Base):
    """The note's text is never audited, logged or exposed to anyone but the owner (not even a
    System Admin). `version` increases on every save and guards against overwriting a newer save."""

    __tablename__ = "private_notes"
    __table_args__ = (CheckConstraint(f"char_length(body) <= {MAX_LENGTH}", name="body_length"),)

    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_accounts.id"), primary_key=True)
    body: Mapped[str] = mapped_column(String(MAX_LENGTH))
    version: Mapped[int] = mapped_column(Integer)
    updated_at: Mapped[datetime]
