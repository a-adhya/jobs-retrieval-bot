import sys

import typer

from jobbot.cli.commands import admin, pipeline
from jobbot.errors import JobbotError, UsageError
from jobbot.log import configure_logging
from jobbot.settings import load_settings

app = typer.Typer(
    no_args_is_help=True, add_completion=False, help="Job and company-prospect digest pipeline."
)
admin_app = typer.Typer(no_args_is_help=True, help="Allowlist and email setup.")
profile_app = typer.Typer(no_args_is_help=True, help="Inspect generated profiles.")
runs_app = typer.Typer(no_args_is_help=True, help="Inspect recorded runs.")

for name, fn in [
    ("discover", pipeline.discover),
    ("ingest", pipeline.ingest),
    ("match", pipeline.match),
    ("prospects", pipeline.prospects),
    ("contacts", pipeline.contacts),
    ("digest", pipeline.digest),
    ("run-all", pipeline.run_all),
    ("seed-companies", pipeline.seed_companies),
    ("eval", pipeline.eval_),
]:
    app.command(name)(fn)

admin_app.command("allow-email")(admin.allow_email)
admin_app.command("test-email")(admin.test_email)
profile_app.command("show")(pipeline.profile_show)
runs_app.command("list")(admin.runs_list)

app.add_typer(admin_app, name="admin")
app.add_typer(profile_app, name="profile")
app.add_typer(runs_app, name="runs")


@app.callback()
def _setup() -> None:
    try:
        fmt = load_settings().log_format
    except Exception:
        fmt = "console"
    configure_logging(fmt)


def main() -> None:
    try:
        app()
    except UsageError as exc:
        typer.echo(f"Error: {exc}", err=True)
        sys.exit(2)
    except JobbotError as exc:
        typer.echo(f"Error: {exc}", err=True)
        sys.exit(1)
