from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    REAL,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from jobbot.models.base import EMBEDDING_DIM, Base, created_at, uuid_pk


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("company_id", "ats_job_id"),
        CheckConstraint("sponsorship IS NULL OR sponsorship IN ('yes', 'no', 'unknown')", name="sponsorship"),
        Index(None, "embedding", postgresql_using="hnsw", postgresql_ops={"embedding": "vector_cosine_ops"}),
        Index(None, "search_tsv", postgresql_using="gin"),
        Index(None, "closed_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    ats_job_id: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    raw_text: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)

    metros: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    remote_us_ok: Mapped[bool | None] = mapped_column(Boolean)
    work_type: Mapped[str | None] = mapped_column(Text)
    role_family: Mapped[str | None] = mapped_column(Text)
    seniority: Mapped[str | None] = mapped_column(Text)
    yoe_min: Mapped[int | None] = mapped_column(Integer)
    yoe_max: Mapped[int | None] = mapped_column(Integer)
    salary_min: Mapped[int | None] = mapped_column(Integer)
    salary_max: Mapped[int | None] = mapped_column(Integer)
    salary_source: Mapped[str | None] = mapped_column(Text)
    sponsorship: Mapped[str | None] = mapped_column(Text)
    required_skills: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    preferred_skills: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    benefits: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    hiring_contact_text: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    field_confidence: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
    search_tsv: Mapped[Any | None] = mapped_column(TSVECTOR)

    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_seen_at: Mapped[datetime] = created_at()
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Match(Base):
    __tablename__ = "matches"
    __table_args__ = (
        UniqueConstraint("user_id", "job_id"),
        CheckConstraint("quality IS NULL OR quality IN ('high', 'borderline', 'low')", name="quality"),
        CheckConstraint("status IN ('pending', 'sent_calibration', 'sent_weekly', 'skipped')", name="status"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    profile_version: Mapped[int] = mapped_column(Integer, nullable=False)
    retrieval_rank: Mapped[int | None] = mapped_column(Integer)
    feature_score: Mapped[float | None] = mapped_column(REAL)
    feature_breakdown: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    ai_score: Mapped[float | None] = mapped_column(REAL)
    ai_reasons: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    ai_concerns: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    hard_mismatch: Mapped[bool | None] = mapped_column(Boolean)
    final_score: Mapped[float | None] = mapped_column(REAL)
    quality: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="pending")
    created_at: Mapped[datetime] = created_at()


class RoleContact(Base):
    __tablename__ = "role_contacts"

    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True)
    contact_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contacts.id", ondelete="CASCADE"), primary_key=True
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)


class Prospect(Base):
    __tablename__ = "prospects"
    __table_args__ = (
        UniqueConstraint("user_id", "company_id"),
        CheckConstraint("quality IS NULL OR quality IN ('high', 'borderline', 'low')", name="quality"),
        CheckConstraint("status IN ('pending', 'sent', 'interested', 'not_fit', 'contacted')", name="status"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    profile_version: Mapped[int] = mapped_column(Integer, nullable=False)
    alignment_score: Mapped[float | None] = mapped_column(REAL)
    evidence: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, server_default="[]")
    why_now: Mapped[str | None] = mapped_column(Text)
    primary_contact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("contacts.id", ondelete="SET NULL")
    )
    backup_contact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("contacts.id", ondelete="SET NULL")
    )
    shared_background: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    outreach_draft: Mapped[str | None] = mapped_column(Text)
    quality: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="pending")
    created_at: Mapped[datetime] = created_at()
