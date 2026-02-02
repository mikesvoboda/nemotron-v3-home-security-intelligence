"""Alembic migration environment configuration.

This module configures Alembic to use our SQLAlchemy models and database connection.
PostgreSQL is the only supported database.
"""

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool

from alembic import context

# Add the backend directory to the Python path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Import our models to get the metadata
from backend.models.camera import Base

# This is the Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set target metadata from our models
target_metadata = Base.metadata


def get_url() -> str:
    """Get database URL from DATABASE_URL environment variable.

    The DATABASE_URL environment variable is required. No fallback is provided
    to prevent accidental use of hardcoded credentials.

    Note: Only PostgreSQL is supported. SQLite URLs will cause runtime errors.

    Returns:
        Database URL with async driver removed (asyncpg -> postgresql).

    Raises:
        ValueError: If DATABASE_URL environment variable is not set.

    Example:
        DATABASE_URL=postgresql://user:pass@localhost:5432/dbname
    """
    url = os.getenv("DATABASE_URL")
    if not url:
        raise ValueError(
            "DATABASE_URL environment variable is required. "
            "Example: postgresql://user:pass@localhost:5432/dbname"
        )
    # Convert async URL (asyncpg) to sync (psycopg2/plain postgresql)
    return url.replace("+asyncpg", "")


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine.
    Useful for generating SQL scripts without a database connection.
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    Creates an Engine and associates a connection with the context.
    """
    # Get the database URL and configure engine
    url = get_url()

    # Build configuration dict
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = url

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
