from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
TEST_DB_URL = os.environ.get(
    "JOBBOT_TEST_DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/jobbot_test"
)


def ensure_database(url: str) -> None:
    target = make_url(url)
    admin = create_engine(target.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": target.database}
        ).scalar()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{target.database}"'))
    admin.dispose()


def alembic_config(url: str) -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return cfg


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    """Every test sees only the repo's toml files plus the variables it sets itself; a developer's
    `.env` and shell variables are ignored."""
    for key in list(os.environ):
        if key.startswith("JOBBOT_"):
            monkeypatch.delenv(key)
    monkeypatch.setenv("JOBBOT_ENV", "test")
    monkeypatch.setenv("JOBBOT_CONFIG_DIR", str(ROOT))
    monkeypatch.setenv("JOBBOT_DATABASE_URL", TEST_DB_URL)
    monkeypatch.chdir(tmp_path)
    yield


@pytest.fixture(scope="session")
def migrated_db() -> str:
    ensure_database(TEST_DB_URL)
    cfg = alembic_config(TEST_DB_URL)
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    return TEST_DB_URL


@pytest.fixture
def db(migrated_db: str) -> Iterator[str]:
    engine = create_engine(migrated_db)
    with engine.begin() as conn:
        tables = conn.execute(
            text(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'app' AND tablename <> 'alembic_version'"
            )
        ).scalars()
        conn.execute(text("TRUNCATE " + ", ".join(f"app.{t}" for t in tables) + " CASCADE"))
    engine.dispose()
    yield migrated_db


def row_counts(url: str) -> dict[str, int]:
    engine = create_engine(url)
    with engine.connect() as conn:
        tables = (
            conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'app' ORDER BY tablename"))
            .scalars()
            .all()
        )
        counts = {t: conn.execute(text(f"SELECT count(*) FROM app.{t}")).scalar_one() for t in tables}
    engine.dispose()
    return counts
