from pathlib import Path

import pytest

from jobbot.budget import Budget
from jobbot.context import build_context, is_remote_db
from jobbot.errors import BudgetExceeded, UsageError
from jobbot.settings import load_settings


def test_replay_and_record_conflict() -> None:
    with pytest.raises(UsageError):
        build_context(load_settings(), fixtures=Path("a"), record_fixtures=Path("b"))


def test_dry_run_with_to_conflicts() -> None:
    with pytest.raises(UsageError):
        build_context(load_settings(), dry_run=True, to="x@example.com")


def test_dry_run_forces_zero_paid_lookups() -> None:
    ctx = build_context(load_settings(), dry_run=True, max_paid_lookups=50)
    assert ctx.budget.paid_lookup_limit == 0
    assert not ctx.paid_calls_allowed


def test_no_llm_means_zero_ai_budget() -> None:
    ctx = build_context(load_settings(), no_llm=True, llm_budget=10)
    assert ctx.budget.llm_limit_usd == 0
    assert not ctx.llm_enabled


def test_flags_override_settings_and_limits() -> None:
    ctx = build_context(
        load_settings(),
        llm_budget=0.5,
        max_paid_lookups=3,
        limit_overrides={"companies": 7, "max_roles": 5, "jobs": None},
    )
    assert ctx.budget.llm_limit_usd == 0.5
    assert ctx.budget.paid_lookup_limit == 3
    assert ctx.limits.companies == 7
    assert ctx.limits.max_roles == 5
    assert ctx.limits.jobs is None
    assert ctx.limits.max_prospects == 5


def test_http_mode() -> None:
    s = load_settings()
    assert build_context(s).http_mode == "live"
    assert build_context(s, fixtures=Path("f")).http_mode == "replay"
    assert build_context(s, record_fixtures=Path("f")).http_mode == "record"


@pytest.mark.parametrize(
    ("url", "remote"),
    [
        ("postgresql+psycopg://postgres:postgres@localhost:5432/x", False),
        ("postgresql+psycopg://postgres:postgres@127.0.0.1/x", False),
        ("postgresql+psycopg://u:p@aws-0-us-west-1.pooler.supabase.com:6543/postgres", True),
    ],
)
def test_remote_db_detection(url: str, remote: bool) -> None:
    assert is_remote_db(url) is remote


def test_budget_llm_cap() -> None:
    b = Budget(llm_limit_usd=0.10, paid_lookup_limit=0)
    b.charge_llm(0.06)
    with pytest.raises(BudgetExceeded):
        b.charge_llm(0.06)


def test_budget_paid_lookup_cap() -> None:
    b = Budget(llm_limit_usd=0, paid_lookup_limit=2)
    b.take_paid_lookup()
    b.take_paid_lookup()
    with pytest.raises(BudgetExceeded):
        b.take_paid_lookup()
    assert b.paid_lookups_used == 2
