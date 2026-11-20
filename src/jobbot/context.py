from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

from jobbot.budget import Budget
from jobbot.errors import UsageError
from jobbot.settings import Limits, Settings

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "db", ""}


@dataclass
class RunContext:
    """Everything a command needs: merged settings plus the shared flags for this invocation."""

    settings: Settings
    dry_run: bool = False
    llm_enabled: bool = True
    fixtures_dir: Path | None = None
    record_dir: Path | None = None
    output: Literal["table", "json"] = "table"
    sample: int | None = None
    seed: int | None = None
    email_to: str | None = None
    preview_path: Path | None = None
    limits: Limits = field(default_factory=Limits)
    budget: Budget = field(default_factory=lambda: Budget(0, 0))
    args: dict[str, Any] = field(default_factory=dict)

    @property
    def database_url(self) -> str:
        return self.settings.database_url

    @property
    def http_mode(self) -> Literal["live", "record", "replay"]:
        if self.fixtures_dir:
            return "replay"
        if self.record_dir:
            return "record"
        return "live"

    @property
    def paid_calls_allowed(self) -> bool:
        return not self.dry_run and self.budget.paid_lookup_limit > 0


def db_host(url: str) -> str:
    return urlsplit(url).hostname or ""


def build_context(
    settings: Settings,
    *,
    dry_run: bool = False,
    no_llm: bool = False,
    fixtures: Path | None = None,
    record_fixtures: Path | None = None,
    llm_budget: float | None = None,
    max_paid_lookups: int | None = None,
    output: Literal["table", "json"] = "table",
    sample: int | None = None,
    seed: int | None = None,
    to: str | None = None,
    preview: Path | None = None,
    limit_overrides: dict[str, int | None] | None = None,
    args: dict[str, Any] | None = None,
) -> RunContext:
    if fixtures and record_fixtures:
        raise UsageError("--fixtures (replay) and --record-fixtures (record) can't be used together")
    if dry_run and to:
        raise UsageError("--dry-run sends nothing, so --to has no effect; drop one of them")

    limits = settings.limits.model_copy(
        update={k: v for k, v in (limit_overrides or {}).items() if v is not None}
    )
    llm_limit = 0.0 if no_llm else (llm_budget if llm_budget is not None else settings.llm_budget_usd_per_run)
    paid_limit = max_paid_lookups if max_paid_lookups is not None else settings.max_paid_lookups_per_run
    if dry_run:
        paid_limit = 0

    return RunContext(
        settings=settings,
        dry_run=dry_run,
        llm_enabled=not no_llm,
        fixtures_dir=fixtures,
        record_dir=record_fixtures,
        output=output,
        sample=sample,
        seed=seed,
        email_to=to,
        preview_path=preview,
        limits=limits,
        budget=Budget(llm_limit_usd=llm_limit, paid_lookup_limit=paid_limit),
        args=args or {},
    )


def is_remote_db(url: str) -> bool:
    return db_host(url) not in LOCAL_HOSTS
