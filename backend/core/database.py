"""Database connection and session management using SQLAlchemy 2.0 async patterns.

This module provides PostgreSQL database connectivity using asyncpg.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

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


def _is_postgresql(url: str) -> bool:
    """Check if the database URL is for PostgreSQL."""
    return "postgresql" in url or "postgres" in url


def _is_sqlite(url: str) -> bool:
    """Check if the database URL is for SQLite."""
    return "sqlite" in url


async def init_db() -> None:
    """Initialize the database engine and create all tables.

    This function should be called once during application startup.
    It creates the async engine with PostgreSQL connection pooling,
    and creates all tables defined in the Base metadata.

    Supports both SQLite (development) and PostgreSQL (production).
    """
    global _engine, _async_session_factory  # noqa: PLW0603

    settings = get_settings()

    # Create async engine for PostgreSQL with asyncpg
    # Connection pooling is handled by SQLAlchemy's default QueuePool
    _engine = create_async_engine(
        settings.database_url,
        echo=settings.debug,
        future=True,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,  # Verify connections before use
    )

    # Create session factory
    _async_session_factory = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    # Import all models to ensure they're registered with Base.metadata
    from backend.models import Camera, Detection, Event, GPUStats  # noqa: F401

    # Create all tables
    # Use the Base from models, not the one defined in this module
    from backend.models.camera import Base as ModelsBase

    async with _engine.begin() as conn:
        await conn.run_sync(ModelsBase.metadata.create_all)


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
