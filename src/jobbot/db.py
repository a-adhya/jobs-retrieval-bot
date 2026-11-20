from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker


@lru_cache(maxsize=8)
def get_engine(url: str) -> Engine:
    # Supabase's transaction pooler (port 6543) rejects prepared statements.
    return create_engine(url, pool_pre_ping=True, connect_args={"prepare_threshold": None})


@contextmanager
def session_scope(url: str, *, dry_run: bool = False) -> Iterator[Session]:
    """Commits on success. In dry-run mode everything is rolled back, so writes can be exercised
    without persisting."""
    session = sessionmaker(get_engine(url), expire_on_commit=False)()
    try:
        yield session
        if dry_run:
            session.rollback()
        else:
            session.commit()
    except BaseException:
        session.rollback()
        raise
    finally:
        session.close()
