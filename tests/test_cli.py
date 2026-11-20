from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from typer.testing import CliRunner

from conftest import row_counts
from jobbot.cli import app
from jobbot.context import build_context
from jobbot.runs import track_run
from jobbot.settings import load_settings

runner = CliRunner()

PIPELINE_COMMANDS: list[list[str]] = [
    ["discover"],
    ["ingest"],
    ["match"],
    ["prospects"],
    ["contacts"],
    ["digest"],
    ["run-all"],
    ["seed-companies", "companies.csv"],
    ["eval", "ranking"],
]
ALL_HELP = [
    *PIPELINE_COMMANDS,
    ["admin", "allow-email"],
    ["admin", "test-email"],
    ["profile", "show"],
    ["runs", "list"],
]


def runs(url: str) -> list[tuple[str, str]]:
    engine = create_engine(url)
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT command, status FROM app.runs ORDER BY started_at")).all()
    engine.dispose()
    return [(r[0], r[1]) for r in rows]


@pytest.mark.parametrize("cmd", ALL_HELP, ids=lambda c: " ".join(c))
def test_help(cmd: list[str]) -> None:
    words = cmd[:2] if cmd[0] in ("admin", "profile", "runs") else cmd[:1]
    result = runner.invoke(app, [*words, "--help"])
    assert result.exit_code == 0, result.output


@pytest.mark.parametrize("cmd", PIPELINE_COMMANDS, ids=lambda c: c[0])
def test_shared_flags_accepted_and_dry_run_writes_nothing(cmd: list[str], db: str) -> None:
    before = row_counts(db)
    result = runner.invoke(
        app,
        [*cmd, "--dry-run", "--no-llm", "--llm-budget", "0.5", "--max-paid-lookups", "3", "--output", "json"],
    )
    assert result.exit_code == 0, result.output
    assert "Not built yet" in result.output
    assert row_counts(db) == before


def test_limit_flags_parse(db: str) -> None:
    result = runner.invoke(
        app,
        [
            "ingest",
            "--dry-run",
            "--limit-companies",
            "5",
            "--jobs-per-company",
            "2",
            "--company",
            "ramp.com",
            "--company",
            "modal.com",
        ],
    )
    assert result.exit_code == 0, result.output


def test_stub_run_is_recorded_as_noop(db: str) -> None:
    result = runner.invoke(app, ["ingest", "--limit-companies", "1"])
    assert result.exit_code == 0, result.output
    assert runs(db) == [("ingest", "noop")]


def test_fixtures_and_record_conflict(db: str) -> None:
    result = runner.invoke(app, ["ingest", "--fixtures", "a", "--record-fixtures", "b"])
    assert result.exit_code != 0
    assert runs(db) == []


def test_allow_email_adds_once(db: str) -> None:
    first = runner.invoke(app, ["admin", "allow-email", "New.Person@Example.com"])
    second = runner.invoke(app, ["admin", "allow-email", "new.person@example.com"])
    assert "Added: new.person@example.com" in first.output
    assert "Already allowed" in second.output
    assert row_counts(db)["allowed_emails"] == 1


def test_allow_email_dry_run(db: str) -> None:
    result = runner.invoke(app, ["admin", "allow-email", "x@example.com", "--dry-run"])
    assert "(dry run)" in result.output
    assert row_counts(db)["allowed_emails"] == 0


def test_failed_command_recorded(db: str) -> None:
    result = runner.invoke(app, ["admin", "test-email"])
    assert result.exit_code != 0
    assert runs(db) == [("admin-test-email", "failed")]


def test_test_email_preview(db: str, tmp_path: Path) -> None:
    out = tmp_path / "p.html"
    result = runner.invoke(
        app, ["admin", "test-email", "--recipient", "me@example.com", "--preview", str(out)]
    )
    assert result.exit_code == 0, result.output
    assert "Resend and your sending domain work" in out.read_text()


def test_runs_list(db: str) -> None:
    runner.invoke(app, ["ingest"])
    result = runner.invoke(app, ["runs", "list", "--output", "json"])
    assert result.exit_code == 0, result.output
    assert '"command": "ingest"' in result.output


def test_budget_exceeded_marks_partial(db: str) -> None:
    ctx = build_context(load_settings(), llm_budget=0.01)
    with track_run(ctx, "match") as run:
        run.inc("ranked")
        ctx.budget.charge_llm(0.02)
    assert runs(db) == [("match", "partial")]


def test_non_local_db_asks_for_confirmation(db: str) -> None:
    result = runner.invoke(
        app,
        ["ingest", "--database-url", "postgresql://u:p@db.example.supabase.co:5432/postgres"],
        input="n\n",
    )
    assert result.exit_code != 0
    assert "Continue?" in result.output
