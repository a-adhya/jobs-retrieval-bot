import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from conftest import TEST_DB_URL, alembic_config, ensure_database
from jobbot.models import Base

ROUNDTRIP_URL = (
    make_url(TEST_DB_URL).set(database="jobbot_migrations_test").render_as_string(hide_password=False)
)


@pytest.fixture
def fresh_db(monkeypatch: pytest.MonkeyPatch) -> str:
    ensure_database(ROUNDTRIP_URL)
    monkeypatch.setenv("JOBBOT_ALLOWED_EMAILS", "Owner@Example.com")
    command.downgrade(alembic_config(ROUNDTRIP_URL), "base")
    return ROUNDTRIP_URL


def test_upgrade_downgrade_upgrade(fresh_db: str) -> None:
    cfg = alembic_config(fresh_db)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")

    engine = create_engine(fresh_db)
    with engine.connect() as conn:
        tables = conn.execute(
            text(
                "SELECT tablename, rowsecurity FROM pg_tables "
                "WHERE schemaname = 'app' AND tablename <> 'alembic_version'"
            )
        ).all()
        public = conn.execute(text("SELECT count(*) FROM pg_tables WHERE schemaname = 'public'")).scalar_one()
        emails = conn.execute(text("SELECT email FROM app.allowed_emails")).scalars().all()
        diff = compare_metadata(
            MigrationContext.configure(
                conn,
                opts={
                    "include_schemas": True,
                    "version_table_schema": "app",
                    "include_object": lambda obj, name, type_, reflected, compare_to: (
                        type_ != "table" or obj.schema == "app"
                    ),
                },
            ),
            Base.metadata,
        )
    engine.dispose()

    assert len(tables) == len(Base.metadata.tables) == 17
    assert all(rls for _, rls in tables), "row-level security must be on for every table"
    assert public == 0, "nothing should live in the public schema"
    assert emails == ["owner@example.com"]
    assert not diff, f"models and migrations disagree: {diff}"
