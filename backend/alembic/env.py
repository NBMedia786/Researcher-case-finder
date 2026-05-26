from logging.config import fileConfig
from sqlalchemy import create_engine, pool
from alembic import context

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.db import Base
# NOTE: do NOT import app.models here. When models are loaded, their Enum
# columns register SQLAlchemy 'before_create' hooks that try to CREATE TYPE
# even though our migration creates them explicitly via op.execute().
# We only need Base.metadata for autogenerate; for applying existing
# migration files, target_metadata can be empty.

config = context.config

# Note: we read the database URL from settings (not from alembic.ini) because
# the URL may contain '%' characters (URL-encoded password, query params),
# which configparser would try to interpolate. Bypass configparser entirely
# by creating the engine directly from settings.database_url.

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine, though
    an Engine is acceptable here as well. By skipping the Engine creation
    we don't even need a DBAPI to be available.
    """
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode by creating an engine directly."""
    connectable = create_engine(settings.database_url, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
