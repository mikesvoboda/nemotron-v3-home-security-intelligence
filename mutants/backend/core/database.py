"""Database connection and session management using SQLAlchemy 2.0 async patterns.

This module provides PostgreSQL database connectivity using asyncpg,
along with SQL utility functions like ILIKE pattern escaping.
"""

import hashlib
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from backend.core.config import get_settings

# Advisory lock key for database schema initialization
# This is a stable key derived from a namespace string to ensure all workers
# attempting to initialize the same database use the same lock.
# We use SHA256 truncated to 63 bits (PostgreSQL bigint safe) for the lock key.
_INIT_DB_LOCK_NAMESPACE = "home_security_intelligence.init_db"
_INIT_DB_LOCK_KEY = int(hashlib.sha256(_INIT_DB_LOCK_NAMESPACE.encode()).hexdigest()[:15], 16)


def escape_ilike_pattern(value: str | None) -> str:
    """Escape special characters in a string for safe use in ILIKE patterns.

    PostgreSQL ILIKE uses '%' and '_' as wildcards and '\\' as escape character.
    This function escapes these characters to prevent pattern injection attacks
    where user input containing these characters could cause unexpected matching.

    Args:
        value: The user-provided string to escape. If None, returns empty string.
               If not a string, converts to string first.

    Returns:
        The escaped string safe for use in ILIKE patterns

    Example:
        >>> escape_ilike_pattern("100% complete")
        '100\\\\% complete'
        >>> escape_ilike_pattern("file_name")
        'file\\\\_name'
        >>> escape_ilike_pattern("path\\\\to\\\\file")
        'path\\\\\\\\to\\\\\\\\file'
        >>> escape_ilike_pattern(None)
        ''
        >>> escape_ilike_pattern(123)
        '123'
    """
    # Handle None input - return empty string
    if value is None:
        return ""

    # Handle non-string input - convert to string
    if not isinstance(value, str):
        value = str(value)

    # Escape backslash first (it's the escape character itself)
    # Then escape % and _ wildcards
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


# Global engine and session factory
_engine: AsyncEngine | None = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Get or create the global async database engine.

    Returns:
        AsyncEngine: The SQLAlchemy async engine instance.

    Raises:
        RuntimeError: If database has not been initialized.
    """
    if _engine is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get the global async session factory.

    Returns:
        async_sessionmaker: Factory for creating async database sessions.

    Raises:
        RuntimeError: If database has not been initialized.
    """
    if _async_session_factory is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _async_session_factory


async def init_db() -> None:
    """Initialize the database engine and create all tables.

    This function should be called once during application startup.
    It creates the async engine with PostgreSQL connection pooling,
    and creates all tables defined in the Base metadata.

    Uses a PostgreSQL advisory lock to prevent deadlocks when multiple
    workers start simultaneously and all try to create indexes on the
    same tables. Only one worker will actually create the schema; others
    will skip schema creation if they cannot acquire the lock.

    Requires PostgreSQL with asyncpg driver (postgresql+asyncpg://).
    """
    global _engine, _async_session_factory  # noqa: PLW0603

    settings = get_settings()
    db_url = settings.database_url

    # Validate PostgreSQL URL format
    if not db_url.startswith("postgresql+asyncpg://"):
        raise ValueError(
            f"Invalid database URL. Expected postgresql+asyncpg:// format, got: {db_url}"
        )

    # PostgreSQL connection pooling configuration
    # These settings optimize for concurrent access and are configurable via Settings
    # Default: pool_size=20, max_overflow=30 (50 max connections)
    # Previous default: pool_size=10, max_overflow=20 (30 max connections)
    # Increased to handle multiple background workers (detection, analysis, timeout,
    # metrics, GPU monitor, system broadcaster) plus API requests
    engine_kwargs: dict[str, Any] = {
        "echo": settings.debug,
        "future": True,
        "pool_size": settings.database_pool_size,
        "max_overflow": settings.database_pool_overflow,
        "pool_timeout": settings.database_pool_timeout,
        "pool_recycle": settings.database_pool_recycle,
        "pool_pre_ping": True,  # Verify connections before use
    }

    # Create async engine
    _engine = create_async_engine(db_url, **engine_kwargs)

    # Create session factory
    _async_session_factory = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    # Import all models to ensure they're registered with Base.metadata
    from backend.models import Camera, Detection, Event, GPUStats, Zone  # noqa: F401

    # Create all tables with advisory lock to prevent deadlock on concurrent index creation
    # Use the Base from models, not the one defined in this module
    from backend.models.camera import Base as ModelsBase

    async with _engine.begin() as conn:
        # Try to acquire advisory lock - if another worker is already creating schema,
        # this will return False and we skip schema creation.
        # pg_try_advisory_lock returns true if lock was acquired, false otherwise.
        # Note: _INIT_DB_LOCK_KEY is a module-level constant, not user input (safe from SQL injection)
        lock_sql = text(f"SELECT pg_try_advisory_lock({_INIT_DB_LOCK_KEY})")  # nosemgrep
        result = await conn.execute(lock_sql)
        lock_acquired = result.scalar()

        if lock_acquired:
            try:
                # We have the lock - proceed with schema creation
                await conn.run_sync(ModelsBase.metadata.create_all)
            finally:
                # Always release the lock, even if schema creation fails
                unlock_sql = text(f"SELECT pg_advisory_unlock({_INIT_DB_LOCK_KEY})")  # nosemgrep
                await conn.execute(unlock_sql)
        # If lock not acquired, another worker is handling schema creation
        # The tables will be available after that worker completes


async def close_db() -> None:
    """Close the database engine and cleanup resources.

    This function should be called during application shutdown.
    """
    global _engine, _async_session_factory  # noqa: PLW0603

    if _engine is not None:
        try:
            await _engine.dispose()
        except ValueError as e:
            # Handle the case where greenlet is not available (e.g., Python 3.14+)
            # This can happen when the engine was created in a different context
            # or when greenlet is not installed. We still need to reset the globals.
            if "greenlet" in str(e):
                pass  # Gracefully handle missing greenlet
            else:
                raise
        finally:
            _engine = None
            _async_session_factory = None


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession]:
    """Get an async database session as a context manager.

    Usage:
        async with get_session() as session:
            result = await session.execute(select(Model))
            models = result.scalars().all()

    Yields:
        AsyncSession: An async SQLAlchemy session.

    Raises:
        RuntimeError: If database has not been initialized.
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_db() -> AsyncGenerator[AsyncSession]:
    """FastAPI dependency for database sessions.

    This function is designed to be used with FastAPI's Depends():

    Usage:
        @app.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(Item))
            return result.scalars().all()

    Yields:
        AsyncSession: An async SQLAlchemy session.
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
