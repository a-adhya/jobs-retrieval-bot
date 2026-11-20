from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from jobbot.models.base import Base, created_at, uuid_pk

_ONE_TARGET = "(match_id IS NULL) <> (prospect_id IS NULL)"


class Digest(Base):
    __tablename__ = "digests"
    __table_args__ = (CheckConstraint("kind IN ('calibration', 'weekly')", name="kind"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resend_id: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at()


class DigestItem(Base):
    __tablename__ = "digest_items"
    __table_args__ = (
        CheckConstraint("item_type IN ('role', 'prospect')", name="item_type"),
        CheckConstraint(_ONE_TARGET, name="one_target"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    digest_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("digests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    item_type: Mapped[str] = mapped_column(Text, nullable=False)
    match_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"))
    prospect_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("prospects.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer, nullable=False)


class Feedback(Base):
    __tablename__ = "feedback"
    __table_args__ = (
        CheckConstraint(
            "verdict IN ('good', 'not_fit', 'applied', 'interested', 'contacted')", name="verdict"
        ),
        CheckConstraint(_ONE_TARGET, name="one_target"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    match_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"))
    prospect_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("prospects.id", ondelete="CASCADE"))
    verdict: Mapped[str] = mapped_column(Text, nullable=False)
    reasons: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    created_at: Mapped[datetime] = created_at()
