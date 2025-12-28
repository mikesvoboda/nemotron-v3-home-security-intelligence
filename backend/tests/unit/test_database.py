"""Unit tests for database connection and session management."""

import contextlib
import os
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import Column, Integer, String, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import get_settings
from backend.core.database import (
    Base,
    close_db,
    get_db,
    get_engine,
    get_session,
    get_session_factory,
    init_db,
)


# Test model for database operations
class TestModel(Base):
    """Simple test model for database testing."""

    __tablename__ = "test_models"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    value = Column(String(255))


@pytest.fixture
async def test_db(isolated_db):
    """Fixture to set up test model in the isolated database."""
    # Register test model table
    async with get_engine().begin() as conn:
        await conn.run_sync(TestModel.__table__.create, checkfirst=True)

    yield


@pytest.mark.asyncio
async def test_init_db():
    """Test database initialization."""
    # Save original state
    original_db_url = os.environ.get("DATABASE_URL")
    get_settings.cache_clear()

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_init.db"
        test_db_url = f"sqlite+aiosqlite:///{db_path}"

        os.environ["DATABASE_URL"] = test_db_url
        get_settings.cache_clear()

        try:
            # Ensure clean state
            await close_db()

            await init_db()

            # Verify engine was created
            engine = get_engine()
            assert engine is not None
            assert str(engine.url) == test_db_url

            # Verify session factory was created
            factory = get_session_factory()
            assert factory is not None

        finally:
            await close_db()
            if original_db_url:
                os.environ["DATABASE_URL"] = original_db_url
            else:
                os.environ.pop("DATABASE_URL", None)
            get_settings.cache_clear()


@pytest.mark.asyncio
async def test_engine_without_init():
    """Test that accessing engine before init raises RuntimeError."""
    # Close any existing database connection
    await close_db()

    with pytest.raises(RuntimeError, match="Database not initialized"):
        get_engine()


@pytest.mark.asyncio
async def test_session_factory_without_init():
    """Test that accessing session factory before init raises RuntimeError."""
    # Close any existing database connection
    await close_db()

    with pytest.raises(RuntimeError, match="Database not initialized"):
        get_session_factory()


@pytest.mark.asyncio
async def test_get_session_context_manager(test_db):
    """Test get_session context manager for database operations."""
    # Create a test record
    async with get_session() as session:
        test_obj = TestModel(name="test1", value="value1")
        session.add(test_obj)
        # Commit happens automatically on context exit

    # Verify the record was created
    async with get_session() as session:
        result = await session.execute(select(TestModel).where(TestModel.name == "test1"))
        obj = result.scalar_one_or_none()
        assert obj is not None
        assert obj.name == "test1"
        assert obj.value == "value1"


@pytest.mark.asyncio
async def test_get_session_rollback_on_error(test_db):
    """Test that get_session rolls back on exceptions."""
    # Attempt to create a record but raise an exception
    with pytest.raises(ValueError):
        async with get_session() as session:
            test_obj = TestModel(name="test_rollback", value="value")
            session.add(test_obj)
            raise ValueError("Test error")

    # Verify the record was not created
    async with get_session() as session:
        result = await session.execute(select(TestModel).where(TestModel.name == "test_rollback"))
        obj = result.scalar_one_or_none()
        assert obj is None


@pytest.mark.asyncio
async def test_get_db_dependency(test_db):
    """Test get_db FastAPI dependency function."""
    # Simulate FastAPI dependency injection
    db_generator = get_db()
    session = await anext(db_generator)

    try:
        assert isinstance(session, AsyncSession)

        # Test database operation
        test_obj = TestModel(name="test_dependency", value="dep_value")
        session.add(test_obj)
        await session.flush()

        # Verify object is in session
        result = await session.execute(select(TestModel).where(TestModel.name == "test_dependency"))
        obj = result.scalar_one_or_none()
        assert obj is not None
        assert obj.name == "test_dependency"

    finally:
        # Cleanup - simulate FastAPI cleanup
        with contextlib.suppress(StopAsyncIteration):
            await db_generator.asend(None)


@pytest.mark.asyncio
async def test_multiple_sessions(test_db):
    """Test that multiple sessions can operate independently."""
    # Create records in separate sessions
    async with get_session() as session1:
        test_obj1 = TestModel(name="test_session1", value="value1")
        session1.add(test_obj1)

    async with get_session() as session2:
        test_obj2 = TestModel(name="test_session2", value="value2")
        session2.add(test_obj2)

    # Verify both records exist
    async with get_session() as session3:
        result = await session3.execute(select(TestModel))
        all_objs = result.scalars().all()
        names = {obj.name for obj in all_objs}
        assert "test_session1" in names
        assert "test_session2" in names


@pytest.mark.asyncio
async def test_session_isolation(test_db):
    """Test that changes in one session don't affect another until committed."""
    # Session 1: Add a record but don't commit yet
    factory = get_session_factory()
    session1 = factory()

    try:
        test_obj = TestModel(name="test_isolation", value="value")
        session1.add(test_obj)
        await session1.flush()

        # Session 2: Should not see the uncommitted record
        async with get_session() as session2:
            result = await session2.execute(
                select(TestModel).where(TestModel.name == "test_isolation")
            )
            obj = result.scalar_one_or_none()
            assert obj is None

        # Commit session1
        await session1.commit()

    finally:
        await session1.close()

    # Session 3: Should now see the committed record
    async with get_session() as session3:
        result = await session3.execute(select(TestModel).where(TestModel.name == "test_isolation"))
        obj = result.scalar_one_or_none()
        assert obj is not None


@pytest.mark.asyncio
async def test_table_creation(test_db):
    """Test that tables are created successfully."""
    # Verify TestModel table exists by querying it
    async with get_session() as session:
        result = await session.execute(select(TestModel))
        # If table doesn't exist, this would raise an error
        result.scalars().all()  # Should not raise


@pytest.mark.asyncio
async def test_close_db():
    """Test database cleanup and resource disposal."""
    # Save original state
    original_db_url = os.environ.get("DATABASE_URL")
    get_settings.cache_clear()

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_close.db"
        test_db_url = f"sqlite+aiosqlite:///{db_path}"

        os.environ["DATABASE_URL"] = test_db_url
        get_settings.cache_clear()

        try:
            # Ensure clean state
            await close_db()

            await init_db()
            engine = get_engine()
            assert engine is not None

            await close_db()

            # After closing, accessing engine should raise error
            with pytest.raises(RuntimeError, match="Database not initialized"):
                get_engine()

        finally:
            if original_db_url:
                os.environ["DATABASE_URL"] = original_db_url
            else:
                os.environ.pop("DATABASE_URL", None)
            get_settings.cache_clear()


@pytest.mark.asyncio
async def test_sqlite_pragmas_configured(isolated_db):
    """Test that SQLite PRAGMAs are properly configured for concurrency.

    Verifies:
    - busy_timeout is set to 30000ms (30 seconds) to prevent lock errors
    - journal_mode is WAL for better concurrent access
    - foreign_keys is enabled for referential integrity
    - synchronous is NORMAL for balance of safety and speed
    """
    async with get_session() as session:
        # Check busy_timeout (should be 30000ms = 30 seconds)
        result = await session.execute(text("PRAGMA busy_timeout"))
        busy_timeout = result.scalar()
        assert busy_timeout == 30000, f"Expected busy_timeout=30000, got {busy_timeout}"

        # Check journal_mode (should be WAL)
        result = await session.execute(text("PRAGMA journal_mode"))
        journal_mode = result.scalar()
        assert journal_mode.lower() == "wal", f"Expected journal_mode=wal, got {journal_mode}"

        # Check foreign_keys (should be enabled)
        result = await session.execute(text("PRAGMA foreign_keys"))
        foreign_keys = result.scalar()
        assert foreign_keys == 1, f"Expected foreign_keys=1, got {foreign_keys}"

        # Check synchronous (should be NORMAL = 1)
        result = await session.execute(text("PRAGMA synchronous"))
        synchronous = result.scalar()
        assert synchronous == 1, f"Expected synchronous=1 (NORMAL), got {synchronous}"
