"""Alembic migration environment configuration.

This module configures Alembic to use our SQLAlchemy models and database connection.
Supports both SQLite (development) and PostgreSQL (production).
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

# Default database URL for development
DEFAULT_DATABASE_URL = "sqlite:///./data/security.db"


def get_database_url() -> str:
    """Get database URL from environment or config.

    Priority:
    1. DATABASE_URL environment variable
    2. alembic.ini sqlalchemy.url setting
    """
    url = os.getenv("DATABASE_URL")
    if url:
        # Convert async URLs to sync for Alembic
        # asyncpg -> psycopg2 (or just postgresql)
        # aiosqlite -> sqlite
        if "+asyncpg" in url:
            url = url.replace("+asyncpg", "")
        elif "+aiosqlite" in url:
            url = url.replace("+aiosqlite", "")
        return url
    ini_url = config.get_main_option("sqlalchemy.url")
    return ini_url if ini_url else DEFAULT_DATABASE_URL


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine.
    Useful for generating SQL scripts without a database connection.
    """
    url = get_database_url()
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
    url = get_database_url()

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
