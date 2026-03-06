"""Shared test fixtures."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture(scope="session")
def engine():
    """In-memory SQLite engine for tests.

    Note: Models use PostgreSQL-specific types (JSONB, ARRAY, Geometry).
    For unit tests we mock the DB layer; this engine is only used for
    basic integration tests that don't touch PG-specific columns.
    """
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    return eng


@pytest.fixture
def db_session(engine):
    """Yields a transactional session that rolls back after each test."""
    connection = engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()
    yield session
    session.close()
    transaction.rollback()
    connection.close()
