import json
from datetime import UTC, datetime
from typing import Annotated

import typer
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from jobbot.cli.options import command
from jobbot.context import RunContext
from jobbot.db import session_scope
from jobbot.email import send_email
from jobbot.errors import UsageError
from jobbot.models import AllowedEmail, Run
from jobbot.runs import RunTracker


@command("admin-allow-email")
def allow_email(
    ctx: RunContext,
    run: RunTracker,
    email: Annotated[str, typer.Argument(help="Email address allowed to log in.")],
) -> None:
    """Add an email to the login allowlist."""
    address = email.strip().lower()
    if "@" not in address:
        raise UsageError(f"{email!r} is not an email address")
    with session_scope(ctx.database_url, dry_run=ctx.dry_run) as s:
        added = (
            s.execute(
                insert(AllowedEmail)
                .values(email=address)
                .on_conflict_do_nothing()
                .returning(AllowedEmail.email)
            ).scalar_one_or_none()
            is not None
        )
    run.set("added", added)
    typer.echo(
        f"{'Added' if added else 'Already allowed'}: {address}" + (" (dry run)" if ctx.dry_run else "")
    )


@command("admin-test-email", email=True)
async def test_email(
    ctx: RunContext,
    run: RunTracker,
    recipient: Annotated[
        str | None,
        typer.Option("--recipient", help="Intended recipient; defaults to the first allowed email."),
    ] = None,
) -> None:
    """Send one email through Resend to check the domain setup."""
    intended = recipient or (ctx.settings.allowed_emails[0] if ctx.settings.allowed_emails else None)
    intended = intended or ctx.settings.email_test_to
    if not intended:
        raise UsageError("No recipient: pass --recipient or set JOBBOT_ALLOWED_EMAILS / JOBBOT_EMAIL_TEST_TO")
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    delivery = await send_email(
        ctx,
        to=intended,
        subject="jobbot test email",
        html=f"<p>If you can read this, Resend and your sending domain work.</p><p>Sent {now}.</p>",
        text=f"If you can read this, Resend and your sending domain work. Sent {now}.",
    )
    run.set("sent", delivery.sent)
    if delivery.sent:
        typer.echo(f"Sent to {delivery.to} (Resend id {delivery.provider_id}).")
    elif delivery.preview_path:
        typer.echo(f"Wrote preview to {delivery.preview_path}.")
    else:
        typer.echo(f"Dry run: would send '{delivery.subject}' to {delivery.to}.")


@command("runs-list", track=False)
def runs_list(
    ctx: RunContext,
    run: None,
    last: Annotated[int, typer.Option(help="How many recent runs to show.")] = 10,
    name: Annotated[str | None, typer.Option("--command", help="Only runs of this command.")] = None,
) -> None:
    """Show recent runs from app.runs."""
    query = select(Run).order_by(Run.started_at.desc()).limit(last)
    if name:
        query = query.where(Run.command == name)
    with session_scope(ctx.database_url, dry_run=True) as s:
        records = [
            {
                "started_at": r.started_at.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S UTC"),
                "command": r.command,
                "status": r.status,
                "llm_cost_usd": float(r.llm_cost_usd),
                "paid_lookups": r.paid_lookups,
                "stats": r.stats,
            }
            for r in s.scalars(query)
        ]
    if ctx.output == "json":
        typer.echo(json.dumps(records, indent=2))
        return
    if not records:
        typer.echo("No runs recorded yet.")
        return
    for rec in records:
        stats = ", ".join(f"{k}={v}" for k, v in rec["stats"].items())
        typer.echo(
            f"{rec['started_at']}  {rec['command']:<18} {rec['status']:<8} "
            f"${rec['llm_cost_usd']:.2f}  lookups={rec['paid_lookups']}  {stats}"
        )
