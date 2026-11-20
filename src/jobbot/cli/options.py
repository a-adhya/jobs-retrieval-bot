import asyncio
import functools
import inspect
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any, Literal

import typer

from jobbot.context import RunContext, build_context, db_host, is_remote_db
from jobbot.runs import RunTracker, track_run
from jobbot.settings import load_settings

KW = inspect.Parameter.KEYWORD_ONLY

SHARED: list[inspect.Parameter] = [
    inspect.Parameter(
        "dry_run",
        KW,
        default=False,
        annotation=Annotated[
            bool, typer.Option("--dry-run", help="No database writes, no emails, no paid lookups.")
        ],
    ),
    inspect.Parameter(
        "no_llm",
        KW,
        default=False,
        annotation=Annotated[bool, typer.Option("--no-llm", help="Rules only; any AI call is refused.")],
    ),
    inspect.Parameter(
        "fixtures",
        KW,
        default=None,
        annotation=Annotated[
            Path | None, typer.Option("--fixtures", help="Replay saved API responses from this directory.")
        ],
    ),
    inspect.Parameter(
        "record_fixtures",
        KW,
        default=None,
        annotation=Annotated[
            Path | None, typer.Option("--record-fixtures", help="Save live API responses to this directory.")
        ],
    ),
    inspect.Parameter(
        "database_url",
        KW,
        default=None,
        annotation=Annotated[
            str | None, typer.Option("--database-url", help="Override JOBBOT_DATABASE_URL.")
        ],
    ),
    inspect.Parameter(
        "llm_budget",
        KW,
        default=None,
        annotation=Annotated[
            float | None, typer.Option("--llm-budget", help="Stop AI calls after this many USD.")
        ],
    ),
    inspect.Parameter(
        "max_paid_lookups",
        KW,
        default=None,
        annotation=Annotated[
            int | None, typer.Option("--max-paid-lookups", help="Cap on paid contact/company lookups.")
        ],
    ),
    inspect.Parameter(
        "sample",
        KW,
        default=None,
        annotation=Annotated[int | None, typer.Option("--sample", help="Random subset of this size.")],
    ),
    inspect.Parameter(
        "seed",
        KW,
        default=None,
        annotation=Annotated[int | None, typer.Option("--seed", help="Seed for --sample.")],
    ),
    inspect.Parameter(
        "output",
        KW,
        default="table",
        annotation=Annotated[Literal["table", "json"], typer.Option("--output", help="table or json.")],
    ),
    inspect.Parameter(
        "yes",
        KW,
        default=False,
        annotation=Annotated[
            bool, typer.Option("--yes", "-y", help="Skip the confirmation for a non-local database.")
        ],
    ),
]

LIMITS: dict[str, tuple[str, str]] = {
    "companies": ("--limit-companies", "Max companies to process."),
    "jobs": ("--limit-jobs", "Max jobs to process."),
    "jobs_per_company": ("--jobs-per-company", "Max jobs per company."),
    "max_roles": ("--max-roles", "Max roles in a digest."),
    "max_prospects": ("--max-prospects", "Max prospect companies in a digest."),
}

EMAIL: list[inspect.Parameter] = [
    inspect.Parameter(
        "to",
        KW,
        default=None,
        annotation=Annotated[
            str | None, typer.Option("--to", help="Send to this address instead; nothing is marked sent.")
        ],
    ),
    inspect.Parameter(
        "preview",
        KW,
        default=None,
        annotation=Annotated[
            Path | None,
            typer.Option("--preview", help="Write the email HTML to this file instead of sending."),
        ],
    ),
]

SHARED_NAMES = {p.name for p in SHARED} | {p.name for p in EMAIL}


def _limit_param(key: str) -> inspect.Parameter:
    flag, help_text = LIMITS[key]
    return inspect.Parameter(
        f"limit__{key}",
        KW,
        default=None,
        annotation=Annotated[int | None, typer.Option(flag, help=help_text)],
    )


def command(
    name: str,
    *,
    limits: tuple[str, ...] = (),
    email: bool = False,
    track: bool = True,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Wraps `fn(ctx, run, **own_options)` into a Typer command that also accepts the shared flags,
    the requested limit flags and (optionally) --to/--preview, builds the RunContext and records the run."""

    def decorate(fn: Callable[..., Any]) -> Callable[..., Any]:
        own = [p for p in inspect.signature(fn).parameters.values() if p.name not in ("ctx", "run")]
        params = own + SHARED + [_limit_param(k) for k in limits] + (EMAIL if email else [])
        params = [p.replace(kind=KW) for p in params]

        @functools.wraps(fn)
        def wrapper(**kwargs: Any) -> Any:
            shared = {k: kwargs.pop(k) for k in list(kwargs) if k in SHARED_NAMES}
            limit_overrides = {
                k.removeprefix("limit__"): kwargs.pop(k) for k in list(kwargs) if k.startswith("limit__")
            }
            ctx = _context(name, shared, limit_overrides, kwargs)
            if not track:
                return _call(fn, ctx, None, kwargs)
            with track_run(ctx, name) as run:
                return _call(fn, ctx, run, kwargs)

        wrapper.__signature__ = inspect.Signature(params)  # type: ignore[attr-defined]
        wrapper.__annotations__ = {p.name: p.annotation for p in params}
        return wrapper

    return decorate


def _call(fn: Callable[..., Any], ctx: RunContext, run: RunTracker | None, kwargs: dict[str, Any]) -> Any:
    result = fn(ctx, run, **kwargs)
    if inspect.iscoroutine(result):
        return asyncio.run(result)
    return result


def _context(
    name: str, shared: dict[str, Any], limit_overrides: dict[str, int | None], own: dict[str, Any]
) -> RunContext:
    overrides = {"database_url": shared["database_url"]} if shared.get("database_url") else {}
    settings = load_settings(**overrides)
    if settings.env != "prod" and is_remote_db(settings.database_url) and not shared.get("yes"):
        typer.confirm(
            f"JOBBOT_ENV={settings.env} but the database is {db_host(settings.database_url)}. Continue?",
            abort=True,
        )
    return build_context(
        settings,
        dry_run=shared.get("dry_run", False),
        no_llm=shared.get("no_llm", False),
        fixtures=shared.get("fixtures"),
        record_fixtures=shared.get("record_fixtures"),
        llm_budget=shared.get("llm_budget"),
        max_paid_lookups=shared.get("max_paid_lookups"),
        output=shared.get("output", "table"),
        sample=shared.get("sample"),
        seed=shared.get("seed"),
        to=shared.get("to"),
        preview=shared.get("preview"),
        limit_overrides=limit_overrides,
        args={
            **own,
            **{k: v for k, v in limit_overrides.items() if v is not None},
            "dry_run": shared.get("dry_run"),
        },
    )
