from pathlib import Path
from typing import Annotated, Literal

import typer

from jobbot.cli.options import command
from jobbot.context import RunContext
from jobbot.runs import RunTracker

Track = Literal["hiring", "prospect", "both"]
DigestKind = Literal["calibration", "weekly"]

Companies = Annotated[
    list[str] | None, typer.Option("--company", help="Only these company domains (repeatable).")
]
User = Annotated[str | None, typer.Option("--user", help="User email; defaults to the only user.")]


def not_built(run: RunTracker | None, phase: str) -> None:
    message = f"Not built yet: arrives in {phase}."
    typer.echo(message)
    if run is not None:
        run.noop(message)


@command("discover", limits=("companies",))
def discover(
    ctx: RunContext,
    run: RunTracker,
    track: Annotated[Track, typer.Option(help="Which company track to search for.")] = "both",
    sources: Annotated[
        str | None,
        typer.Option(help="Comma-separated: yc,brave,pdl,people,simplify,common_crawl,lookalike."),
    ] = None,
    company: Companies = None,
) -> None:
    """Find companies and add them to the company list."""
    not_built(run, "Phase 5 (hiring track) and Phase 6 (prospect track)")


@command("ingest", limits=("companies", "jobs", "jobs_per_company"))
def ingest(
    ctx: RunContext,
    run: RunTracker,
    company: Companies = None,
    ats: Annotated[str | None, typer.Option(help="Comma-separated: greenhouse,lever,ashby.")] = None,
    then_match: Annotated[bool, typer.Option("--then-match", help="Run matching afterwards.")] = False,
) -> None:
    """Fetch job postings from the active companies' job boards."""
    not_built(run, "Phase 1")


@command("match", limits=("jobs", "max_roles"))
def match(
    ctx: RunContext,
    run: RunTracker,
    user: User = None,
    threshold: Annotated[float | None, typer.Option(help="Override the profile's quality cutoff.")] = None,
    rerank_top: Annotated[int | None, typer.Option(help="How many candidates the AI ranks.")] = None,
) -> None:
    """Rank open jobs for a user."""
    not_built(run, "Phase 3")


@command("prospects", limits=("companies", "max_prospects"))
def prospects(ctx: RunContext, run: RunTracker, user: User = None, company: Companies = None) -> None:
    """Score prospect companies (no open role) and find their contacts."""
    not_built(run, "Phase 6")


@command("contacts")
def contacts(
    ctx: RunContext,
    run: RunTracker,
    job: Annotated[str | None, typer.Option(help="Job id.")] = None,
    company: Companies = None,
) -> None:
    """Find points of contact for a role or company."""
    not_built(run, "Phase 4")


@command("digest", limits=("max_roles", "max_prospects"), email=True)
def digest(
    ctx: RunContext,
    run: RunTracker,
    kind: Annotated[DigestKind, typer.Option(help="calibration or weekly.")] = "weekly",
    user: User = None,
) -> None:
    """Build and send the calibration or weekly email."""
    not_built(run, "Phase 3 (calibration) and Phase 4 (weekly)")


@command(
    "run-all",
    limits=tuple(["companies", "jobs", "jobs_per_company", "max_roles", "max_prospects"]),
    email=True,
)
def run_all(ctx: RunContext, run: RunTracker) -> None:
    """discover → ingest → match → prospects → digest, with the same limits throughout."""
    not_built(run, "Phase 4 (end-to-end once matching and the digest exist)")


@command("seed-companies", limits=("companies",))
def seed_companies(
    ctx: RunContext,
    run: RunTracker,
    path: Annotated[Path, typer.Argument(help="CSV with name,domain[,ats,ats_slug].")],
) -> None:
    """Load a hand-picked company list."""
    not_built(run, "Phase 1")


@command("eval")
def eval_(
    ctx: RunContext,
    run: RunTracker,
    suite: Annotated[
        Literal["extraction", "ranking", "prospects", "contacts"], typer.Argument(help="Which eval to run.")
    ],
) -> None:
    """Score extraction, ranking, prospect or contact quality against hand-labeled sets."""
    not_built(run, "Phase 1 (extraction) onwards")


@command("profile-show", track=False)
def profile_show(ctx: RunContext, run: None, user: User = None) -> None:
    """Print the generated profile."""
    not_built(run, "Phase 2")
