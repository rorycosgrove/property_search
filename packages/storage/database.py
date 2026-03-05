"""
Database engine, session management, and dependency injection.

Provides the SQLAlchemy engine, session factory, and a FastAPI dependency
for injecting database sessions into endpoint handlers.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from packages.shared.config import settings

# ── Engine ────────────────────────────────────────────────────────────────────

engine = create_engine(
    settings.database_url,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,  # Detect stale connections
    echo=False,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


# ── FastAPI Dependency ────────────────────────────────────────────────────────

def get_db_session() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a database session.

    Automatically commits on success, rolls back on exception,
    and closes the session when done.
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """
    Get a standalone session for use outside FastAPI (workers, scripts).

    Use as a context manager: ``with get_session() as session:``
    Commits on success, rolls back on error, closes when done.
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
