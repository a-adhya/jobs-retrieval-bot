from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Integer, Numeric, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from jobbot.models.base import Base, created_at, uuid_pk


class Run(Base):
    __tablename__ = "runs"
    __table_args__ = (
        CheckConstraint("status IN ('running', 'ok', 'partial', 'failed', 'noop')", name="status"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    command: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    args: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    env: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="running")
    stats: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    error: Mapped[str | None] = mapped_column(Text)
    llm_cost_usd: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False, server_default="0")
    paid_lookups: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    started_at: Mapped[datetime] = created_at()
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
