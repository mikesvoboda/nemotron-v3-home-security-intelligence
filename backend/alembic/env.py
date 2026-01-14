"""Alembic migration environment configuration.

This module configures Alembic to use our SQLAlchemy models and database connection.
PostgreSQL is the only supported database.

Features:
- Automatic transaction management with rollback on failure
- Comprehensive error logging for debugging migration issues
- Pre-migration database state verification
- Post-migration verification hooks
- Uses centralized config system (NEM-2525)

Related Linear issue: NEM-2610
"""

import logging
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import (
    IntegrityError,
    OperationalError,
    ProgrammingError,
    SQLAlchemyError,
)

from alembic import context

# Add the backend directory to the Python path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Import centralized config (NEM-2525) and models
from backend.core.config import get_settings
from backend.models.camera import Base

# Configure logging for migrations
logger = logging.getLogger("alembic.env")

# This is the Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set target metadata from our models
target_metadata = Base.metadata

# Default database URL for development (PostgreSQL only - no SQLite support)
DEFAULT_DATABASE_URL = "postgresql://security:password@localhost:5432/security"


class MigrationFailedError(Exception):
    """Raised when a migration fails and needs manual intervention."""

    pass


def get_database_url() -> str:
    """Get database URL from centralized config or fallback to alembic.ini.

    Priority:
    1. Centralized config (backend.core.config.Settings.database_url)
    2. alembic.ini sqlalchemy.url setting
    3. Default development URL

    Note: Only PostgreSQL is supported. SQLite URLs will cause runtime errors.
    The centralized config uses asyncpg URLs, which are converted to sync
    for Alembic compatibility.

    Related Linear issue: NEM-2525
    """
    # Use centralized config system (NEM-2525)
    try:
        settings = get_settings()
        url = settings.database_url
        if url:
            # Convert async URL (asyncpg) to sync (psycopg2/plain postgresql)
            if "+asyncpg" in url:
                url = url.replace("+asyncpg", "")
            return url
    except Exception as e:
        # Fall back to alembic.ini or default if config fails
        # This can happen during initial setup or testing
        logger.debug(f"Config loading failed, using fallback: {e}")

    ini_url = config.get_main_option("sqlalchemy.url")
    return ini_url if ini_url else DEFAULT_DATABASE_URL


def verify_database_connection(connection: Connection) -> bool:
    """Verify database connection is healthy before migration.

    Args:
        connection: SQLAlchemy connection object.

    Returns:
        True if connection is healthy.

    Raises:
        MigrationFailedError: If connection verification fails.
    """
    try:
        result = connection.execute(text("SELECT 1"))
        result.fetchone()
        logger.debug("Database connection verified successfully")
        return True
    except SQLAlchemyError as e:
        logger.error(f"Database connection verification failed: {e}")
        raise MigrationFailedError(
            f"Cannot proceed with migration - database connection failed: {e}"
        ) from e


def get_current_revision(connection: Connection) -> str | None:
    """Get the current migration revision from alembic_version table.

    Args:
        connection: SQLAlchemy connection object.

    Returns:
        Current revision ID or None if no migrations have been applied.
    """
    try:
        result = connection.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
        row = result.fetchone()
        return row[0] if row else None
    except ProgrammingError:
        # alembic_version table doesn't exist yet
        return None


def log_migration_state(connection: Connection, phase: str) -> None:
    """Log the current migration state for debugging.

    Args:
        connection: SQLAlchemy connection object.
        phase: Phase of migration ('before' or 'after').
    """
    current_rev = get_current_revision(connection)
    logger.info(f"Migration state {phase}: revision={current_rev}")

    # Log table count for verification
    try:
        result = connection.execute(
            text("SELECT COUNT(*) FROM pg_tables WHERE schemaname = 'public'")
        )
        table_count = result.scalar()
        logger.info(f"Migration state {phase}: {table_count} tables in public schema")
    except SQLAlchemyError:
        logger.debug("Could not count tables (this is normal for fresh databases)")


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine.
    Useful for generating SQL scripts without a database connection.
    """
    url = get_database_url()
    logger.info(
        f"Running offline migration with URL: {url[: url.find('@') if '@' in url else len(url)]}"
    )

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode with enhanced error handling.

    Creates an Engine and associates a connection with the context.
    Includes:
    - Pre-migration verification
    - Transaction management with automatic rollback on failure
    - Post-migration verification
    - Detailed error logging for debugging

    Raises:
        MigrationFailedError: If migration fails with details for manual recovery.
    """
    # Get the database URL and configure engine
    url = get_database_url()
    logger.info("Starting online migration")
    masked_url = url[: url.find("@")] if "@" in url else url
    logger.debug(f"Database URL (masked): {masked_url}...")

    # Build configuration dict
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = url

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        # Pre-migration verification
        verify_database_connection(connection)
        log_migration_state(connection, "before")

        context.configure(connection=connection, target_metadata=target_metadata)

        try:
            with context.begin_transaction():
                logger.info("Executing migrations within transaction")
                context.run_migrations()
                logger.info("Migrations executed successfully, committing transaction")

        except IntegrityError as e:
            logger.error(f"Migration failed due to integrity constraint: {e}")
            logger.error(
                "ROLLBACK: Transaction has been rolled back. "
                "Check for duplicate keys, foreign key violations, or constraint conflicts."
            )
            raise MigrationFailedError(
                f"Migration failed due to data integrity issue: {e}\n"
                "The transaction has been automatically rolled back. "
                "Review the error and fix the data before retrying."
            ) from e

        except OperationalError as e:
            logger.error(f"Migration failed due to operational error: {e}")
            logger.error(
                "ROLLBACK: Transaction has been rolled back. "
                "This may indicate a connection issue, timeout, or resource problem."
            )
            raise MigrationFailedError(
                f"Migration failed due to database operational error: {e}\n"
                "The transaction has been automatically rolled back. "
                "Check database connectivity and resources before retrying."
            ) from e

        except ProgrammingError as e:
            logger.error(f"Migration failed due to programming error: {e}")
            logger.error(
                "ROLLBACK: Transaction has been rolled back. "
                "This may indicate invalid SQL, missing objects, or schema issues."
            )
            raise MigrationFailedError(
                f"Migration failed due to SQL/schema error: {e}\n"
                "The transaction has been automatically rolled back. "
                "Review the migration script for SQL errors."
            ) from e

        except SQLAlchemyError as e:
            logger.error(f"Migration failed with database error: {e}")
            logger.error("ROLLBACK: Transaction has been rolled back.")
            raise MigrationFailedError(
                f"Migration failed with unexpected database error: {e}\n"
                "The transaction has been automatically rolled back."
            ) from e

        except Exception as e:
            logger.error(f"Migration failed with unexpected error: {type(e).__name__}: {e}")
            logger.error("ROLLBACK: Transaction has been rolled back.")
            raise MigrationFailedError(
                f"Migration failed with unexpected error: {type(e).__name__}: {e}\n"
                "The transaction has been automatically rolled back."
            ) from e

        # Post-migration verification (only reached on success)
        log_migration_state(connection, "after")
        logger.info("Migration completed successfully")


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
