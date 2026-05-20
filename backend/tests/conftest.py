import os
import sys
import uuid

# Make `app` importable from tests/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from sqlalchemy import create_engine, String, JSON
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.types import TypeDecorator, CHAR, Text


# ---------------------------------------------------------------------------
# Compile Postgres-specific types to SQLite-compatible ones
# These hooks fire at DDL (CREATE TABLE) time when the dialect is sqlite.
# ---------------------------------------------------------------------------

@compiles(UUID, "sqlite")
def _uuid_sqlite(element, compiler, **kw):
    return "CHAR(36)"


@compiles(JSONB, "sqlite")
def _jsonb_sqlite(element, compiler, **kw):
    return "JSON"


# ---------------------------------------------------------------------------
# Now import app modules (after the compile hooks are registered)
# ---------------------------------------------------------------------------

from app.db import Base
from app import db as app_db
from app.main import app

try:
    from app.auth.dependencies import current_user  # noqa: F401
except ImportError:
    current_user = None  # filled in by Task 7


# ---------------------------------------------------------------------------
# In-memory SQLite test engine
# ---------------------------------------------------------------------------

test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
)
TestSessionLocal = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)


@pytest.fixture(scope="session", autouse=True)
def _setup_db():
    """Import all models so Base.metadata knows about them, then create tables."""
    from app import models  # noqa: F401
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session():
    """A fresh session per test, rolled back at the end."""
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestSessionLocal(bind=connection)

    # Override the app's get_db to use this session
    def _override_get_db():
        try:
            yield session
        finally:
            pass  # don't close — the fixture handles it

    app.dependency_overrides[app_db.get_db] = _override_get_db

    yield session

    app.dependency_overrides.pop(app_db.get_db, None)
    session.close()
    transaction.rollback()
    connection.close()
