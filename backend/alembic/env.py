"""
Alembic environment configuration for AURA.
Reads DATABASE_URL from environment (Railway / .env).
Uses the same Base metadata as the application.
"""

import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# Add backend to path so we can import our models
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Override sqlalchemy.url from environment — REQUIRED for production
database_url = os.getenv("DATABASE_URL", "")
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

if database_url:
    config.set_main_option("sqlalchemy.url", database_url)
elif not context.is_offline_mode():
    raise RuntimeError(
        "DATABASE_URL environment variable is not set. "
        "Alembic refuses to run online migrations without an explicit database URL. "
        "Set DATABASE_URL or use --sql for offline mode."
    )


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode — emit SQL to stdout."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live database.

    Uses transaction_per_migration=True so each migration script is committed
    in its own transaction. This prevents a single failing migration from
    rolling back all previously-committed migrations.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            transaction_per_migration=True,
        )
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
