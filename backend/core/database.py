"""Database connection and session management using SQLAlchemy 2.0 async patterns."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import event, pool
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from backend.core.config import get_settings


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
    It creates the async engine, configures connection pooling,
    and creates all tables defined in the Base metadata.
    """
    global _engine, _async_session_factory  # noqa: PLW0603

    settings = get_settings()

    # Configure engine with appropriate pooling for SQLite
    connect_args: dict[str, Any] = {}
    poolclass = None

    if "sqlite" in settings.database_url:
        # SQLite-specific configuration
        connect_args = {
            "check_same_thread": False,  # Required for async SQLite
        }
        # Use NullPool for SQLite to avoid connection reuse issues
        poolclass = pool.NullPool

    # Create async engine
    _engine = create_async_engine(
        settings.database_url,
        echo=settings.debug,
        connect_args=connect_args,
        poolclass=poolclass,
        future=True,
    )

    # Enable SQLite foreign keys if using SQLite
    if "sqlite" in settings.database_url:

        @event.listens_for(_engine.sync_engine, "connect")
        def enable_foreign_keys(dbapi_conn, _connection_record):
            """Enable foreign key constraints for SQLite."""
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    # Create session factory
    _async_session_factory = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    # Create all tables
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close the database engine and cleanup resources.

    This function should be called during application shutdown.
    """
    global _engine, _async_session_factory  # noqa: PLW0603

    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _async_session_factory = None


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
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


async def get_db() -> AsyncGenerator[AsyncSession, None]:
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
