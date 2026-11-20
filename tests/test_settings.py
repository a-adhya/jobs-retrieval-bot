from pathlib import Path

import pytest

from jobbot.settings import load_settings, normalize_db_url


def test_toml_defaults_apply() -> None:
    s = load_settings()
    assert s.env == "test"
    assert s.llm_budget_usd_per_run == 1.00
    assert s.max_paid_lookups_per_run == 0
    assert s.limits.max_roles == 25
    assert s.http.requests_per_second_per_host == 5


def test_prod_toml_overrides_base(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JOBBOT_ENV", "prod")
    s = load_settings()
    assert s.llm_budget_usd_per_run == 5.00
    assert s.max_paid_lookups_per_run == 60
    assert s.log_format == "json"
    assert s.limits.max_roles == 25, "deep merge keeps base keys the prod file doesn't mention"


def test_env_var_beats_toml_and_flag_beats_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JOBBOT_LLM_BUDGET_USD_PER_RUN", "2.5")
    monkeypatch.setenv("JOBBOT_LIMITS__MAX_ROLES", "10")
    assert load_settings().llm_budget_usd_per_run == 2.5
    assert load_settings().limits.max_roles == 10
    assert load_settings(llm_budget_usd_per_run=0.25).llm_budget_usd_per_run == 0.25


def test_dotenv_is_read_but_env_wins(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("JOBBOT_EMAIL_TEST_TO=dotenv@example.com\nJOBBOT_EMAIL_FROM=x <a@b.c>\n")
    monkeypatch.setenv("JOBBOT_EMAIL_FROM", "env <e@b.c>")
    s = load_settings()
    assert s.email_test_to == "dotenv@example.com"
    assert s.email_from == "env <e@b.c>"


def test_allowed_emails_split_and_lowercased(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JOBBOT_ALLOWED_EMAILS", " Me@Example.com , ,other@x.com")
    assert load_settings().allowed_emails == ["me@example.com", "other@x.com"]


def test_bad_env_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JOBBOT_ENV", "staging")
    with pytest.raises(ValueError, match="dev, test or prod"):
        load_settings()


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("postgresql://u:p@h:6543/db", "postgresql+psycopg://u:p@h:6543/db"),
        ("postgres://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
        ("postgresql+psycopg://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
    ],
)
def test_supabase_urls_get_psycopg_driver(raw: str, expected: str) -> None:
    assert normalize_db_url(raw) == expected


def test_migration_url_prefers_direct(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JOBBOT_DATABASE_URL_DIRECT", "postgresql://u:p@direct:5432/db")
    assert load_settings().migration_url == "postgresql+psycopg://u:p@direct:5432/db"
