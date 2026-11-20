from __future__ import annotations

import traceback
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import update

from jobbot.context import RunContext
from jobbot.db import session_scope
from jobbot.errors import BudgetExceeded
from jobbot.log import get_logger
from jobbot.models import Run

log = get_logger(__name__)


@dataclass
class RunTracker:
    command: str
    stats: dict[str, Any] = field(default_factory=dict)
    status: str = "ok"
    error: str | None = None
    id: uuid.UUID | None = None

    def inc(self, key: str, by: int = 1) -> None:
        self.stats[key] = self.stats.get(key, 0) + by

    def set(self, key: str, value: Any) -> None:
        self.stats[key] = value

    def noop(self, reason: str) -> None:
        """Mark the run as doing nothing on purpose, e.g. a command that is not built yet."""
        self.status = "noop"
        self.stats["note"] = reason


@contextmanager
def track_run(ctx: RunContext, command: str) -> Iterator[RunTracker]:
    """Records one row in app.runs per command invocation, in its own transaction so the record
    survives even when the command's own work is rolled back. Dry runs only log."""
    tracker = RunTracker(command=command)
    if not ctx.dry_run:
        with session_scope(ctx.database_url) as s:
            row = Run(command=command, args=_jsonable(ctx.args), env=ctx.settings.env)
            s.add(row)
            s.flush()
            tracker.id = row.id

    try:
        yield tracker
    except BudgetExceeded as exc:
        tracker.status = "partial"
        tracker.error = str(exc)
        log.warning("run stopped at budget cap", command=command, reason=str(exc))
    except BaseException as exc:
        tracker.status = "failed"
        tracker.error = "".join(traceback.format_exception(exc))
        raise
    finally:
        _finish(ctx, tracker)


def _finish(ctx: RunContext, tracker: RunTracker) -> None:
    summary = {
        "command": tracker.command,
        "status": tracker.status,
        "dry_run": ctx.dry_run,
        "llm_cost_usd": round(ctx.budget.llm_spent_usd, 4),
        "paid_lookups": ctx.budget.paid_lookups_used,
        **tracker.stats,
    }
    log.info("run finished", **summary)
    if ctx.dry_run or tracker.id is None:
        return
    with session_scope(ctx.database_url) as s:
        s.execute(
            update(Run)
            .where(Run.id == tracker.id)
            .values(
                status=tracker.status,
                stats=_jsonable(tracker.stats),
                error=tracker.error,
                llm_cost_usd=ctx.budget.llm_spent_usd,
                paid_lookups=ctx.budget.paid_lookups_used,
                finished_at=datetime.now(UTC),
            )
        )


def _jsonable(d: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in d.items():
        if v is None or isinstance(v, bool | int | float | str):
            out[k] = v
        elif isinstance(v, list | tuple):
            out[k] = [str(x) for x in v]
        else:
            out[k] = str(v)
    return out
