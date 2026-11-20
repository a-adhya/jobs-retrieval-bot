from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import REAL, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from jobbot.models.base import EMBEDDING_DIM, Base, created_at, uuid_pk


class Company(Base):
    __tablename__ = "companies"
    __table_args__ = (
        CheckConstraint("ats IN ('greenhouse', 'lever', 'ashby', 'unknown')", name="ats"),
        CheckConstraint("status IN ('candidate', 'active', 'paused', 'rejected', 'archived')", name="status"),
        CheckConstraint("track IN ('hiring', 'prospect', 'both')", name="track"),
        CheckConstraint("crawl_tier IN ('hot', 'warm', 'cold')", name="crawl_tier"),
        CheckConstraint(
            "size_bucket IS NULL OR size_bucket IN "
            "('seed_lt_50', 'early_50_500', 'mid_500_5000', 'large_5000_plus')",
            name="size_bucket",
        ),
        Index(
            None,
            "desc_embedding",
            postgresql_using="hnsw",
            postgresql_ops={"desc_embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    ats: Mapped[str] = mapped_column(Text, nullable=False, server_default="unknown")
    ats_slug: Mapped[str | None] = mapped_column(Text)
    ats_confidence: Mapped[float | None] = mapped_column(REAL)
    track: Mapped[str] = mapped_column(Text, nullable=False, server_default="hiring")
    size_bucket: Mapped[str | None] = mapped_column(Text)
    size_source: Mapped[str | None] = mapped_column(Text)
    employee_count: Mapped[int | None] = mapped_column(Integer)
    headcount_growth_12m: Mapped[float | None] = mapped_column(REAL)
    last_funding_at: Mapped[date | None] = mapped_column(Date)
    last_funding_round: Mapped[str | None] = mapped_column(Text)
    metros: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    office_metros: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    industry_tags: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    github_org: Mapped[str | None] = mapped_column(Text)
    blog_feed_url: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    desc_embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
    fit_score: Mapped[float | None] = mapped_column(REAL)
    fit_reason: Mapped[str | None] = mapped_column(Text)
    alignment_score: Mapped[float | None] = mapped_column(REAL)
    open_matching_roles: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="candidate")
    crawl_tier: Mapped[str] = mapped_column(Text, nullable=False, server_default="hot")
    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_match_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetch_failures: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = created_at()


class CompanySource(Base):
    __tablename__ = "company_sources"

    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), primary_key=True
    )
    source: Mapped[str] = mapped_column(Text, primary_key=True)
    source_ref: Mapped[str] = mapped_column(Text, primary_key=True)
    found_at: Mapped[datetime] = created_at()


class CompanySignal(Base):
    __tablename__ = "company_signals"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('product', 'blog_post', 'repo', 'paper', 'aligned_people', 'funding', 'headcount')",
            name="kind",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    ref_url: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
    observed_at: Mapped[datetime] = created_at()


class Contact(Base):
    __tablename__ = "contacts"
    __table_args__ = (
        CheckConstraint(
            "role_type IS NULL OR role_type IN ('hiring_manager', 'founder', 'peer', 'recruiter')",
            name="role_type",
        ),
        CheckConstraint(
            "email_status IS NULL OR email_status IN ('verified', 'risky', 'unknown')", name="email_status"
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    role_type: Mapped[str | None] = mapped_column(Text)
    seniority: Mapped[str | None] = mapped_column(Text)
    metro: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[date | None] = mapped_column(Date)
    education: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    past_companies: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    email: Mapped[str | None] = mapped_column(Text)
    email_status: Mapped[str | None] = mapped_column(Text)
    linkedin_url: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    alignment_reason: Mapped[str | None] = mapped_column(Text)
    fetched_at: Mapped[datetime] = created_at()
