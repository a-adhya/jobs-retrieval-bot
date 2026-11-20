from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    REAL,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from jobbot.models.base import EMBEDDING_DIM, Base, created_at, uuid_pk


class AllowedEmail(Base):
    __tablename__ = "allowed_emails"
    __table_args__ = (CheckConstraint("email = lower(email)", name="lowercase"),)

    email: Mapped[str] = mapped_column(Text, primary_key=True)
    added_at: Mapped[datetime] = created_at()


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("email = lower(email)", name="lowercase"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    first_name: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at()


class MagicLink(Base):
    __tablename__ = "magic_links"

    id: Mapped[uuid.UUID] = uuid_pk()
    token_hash: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    email: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at()


class FormSubmission(Base):
    __tablename__ = "form_submissions"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    resume_filename: Mapped[str | None] = mapped_column(Text)
    resume_mime: Mapped[str | None] = mapped_column(Text)
    resume_bytes: Mapped[bytes | None] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = created_at()


class Profile(Base):
    __tablename__ = "profiles"
    __table_args__ = (
        UniqueConstraint("user_id", "version"),
        CheckConstraint("status IN ('calibrating', 'active', 'paused')", name="status"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="calibrating")
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    query_embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
    threshold: Mapped[float] = mapped_column(REAL, nullable=False, server_default="70")
    prospect_threshold: Mapped[float] = mapped_column(REAL, nullable=False, server_default="70")
    created_at: Mapped[datetime] = created_at()
