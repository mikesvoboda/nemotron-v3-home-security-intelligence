"""Unit tests for database connection and session management.

Tests use PostgreSQL. Set TEST_DATABASE_URL environment variable or
use the default test database.
"""

import contextlib

import pytest
from sqlalchemy import Column, Integer, String, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import (
    Base,
    close_db,
    get_db,
    get_engine,
    get_session,
    get_session_factory,
    init_db,
)
from backend.tests.conftest import unique_id

# Mark as integration since these tests require real PostgreSQL database
# NOTE: This file should be moved to backend/tests/integration/ in a future cleanup
pytestmark = pytest.mark.integration


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
async def test_init_db(isolated_db):
    """Test database initialization."""
    # isolated_db fixture already initializes the database
    # Verify engine was created
    engine = get_engine()
    assert engine is not None
    assert "postgresql" in str(engine.url)
    assert "asyncpg" in str(engine.url)

    # Verify session factory was created
    factory = get_session_factory()
    assert factory is not None


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
    # Use unique name to avoid conflicts with parallel tests
    test_name = unique_id("test")
    test_value = unique_id("value")

    # Create a test record
    async with get_session() as session:
        test_obj = TestModel(name=test_name, value=test_value)
        session.add(test_obj)
        # Commit happens automatically on context exit

    # Verify the record was created
    async with get_session() as session:
        result = await session.execute(select(TestModel).where(TestModel.name == test_name))
        obj = result.scalar_one_or_none()
        assert obj is not None
        assert obj.name == test_name
        assert obj.value == test_value


@pytest.mark.asyncio
async def test_get_session_rollback_on_error(test_db):
    """Test that get_session rolls back on exceptions."""
    # Use unique name to avoid conflicts with parallel tests
    test_name = unique_id("rollback")

    # Attempt to create a record but raise an exception
    with pytest.raises(ValueError):
        async with get_session() as session:
            test_obj = TestModel(name=test_name, value="value")
            session.add(test_obj)
            raise ValueError("Test error")

    # Verify the record was not created
    async with get_session() as session:
        result = await session.execute(select(TestModel).where(TestModel.name == test_name))
        obj = result.scalar_one_or_none()
        assert obj is None


@pytest.mark.asyncio
async def test_get_db_dependency(test_db):
    """Test get_db FastAPI dependency function."""
    # Use unique name to avoid conflicts with parallel tests
    test_name = unique_id("dependency")
    test_value = unique_id("dep_value")

    # Simulate FastAPI dependency injection
    db_generator = get_db()
    session = await anext(db_generator)

    try:
        assert isinstance(session, AsyncSession)

        # Test database operation
        test_obj = TestModel(name=test_name, value=test_value)
        session.add(test_obj)
        await session.flush()

        # Verify object is in session
        result = await session.execute(select(TestModel).where(TestModel.name == test_name))
        obj = result.scalar_one_or_none()
        assert obj is not None
        assert obj.name == test_name

    finally:
        # Cleanup - simulate FastAPI cleanup
        with contextlib.suppress(StopAsyncIteration):
            await db_generator.asend(None)


@pytest.mark.asyncio
async def test_multiple_sessions(test_db):
    """Test that multiple sessions can operate independently."""
    # Use unique names to avoid conflicts with parallel tests
    name1 = unique_id("session1")
    name2 = unique_id("session2")

    # Create records in separate sessions
    async with get_session() as session1:
        test_obj1 = TestModel(name=name1, value="value1")
        session1.add(test_obj1)

    async with get_session() as session2:
        test_obj2 = TestModel(name=name2, value="value2")
        session2.add(test_obj2)

    # Verify both records exist
    async with get_session() as session3:
        result = await session3.execute(select(TestModel))
        all_objs = result.scalars().all()
        names = {obj.name for obj in all_objs}
        assert name1 in names
        assert name2 in names


@pytest.mark.asyncio
async def test_session_isolation(test_db):
    """Test that changes in one session don't affect another until committed."""
    # Use unique name to avoid conflicts with parallel tests
    test_name = unique_id("isolation")

    # Session 1: Add a record but don't commit yet
    factory = get_session_factory()
    session1 = factory()

    try:
        test_obj = TestModel(name=test_name, value="value")
        session1.add(test_obj)
        await session1.flush()

        # Session 2: Should not see the uncommitted record
        async with get_session() as session2:
            result = await session2.execute(select(TestModel).where(TestModel.name == test_name))
            obj = result.scalar_one_or_none()
            assert obj is None

        # Commit session1
        await session1.commit()

    finally:
        await session1.close()

    # Session 3: Should now see the committed record
    async with get_session() as session3:
        result = await session3.execute(select(TestModel).where(TestModel.name == test_name))
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
async def test_close_db(isolated_db):
    """Test database cleanup and resource disposal."""
    # isolated_db fixture already initializes the database
    engine = get_engine()
    assert engine is not None

    await close_db()

    # After closing, accessing engine should raise error
    with pytest.raises(RuntimeError, match="Database not initialized"):
        get_engine()

    # Re-initialize for cleanup by isolated_db fixture
    await init_db()


@pytest.mark.asyncio
async def test_postgresql_connection(isolated_db):
    """Test that PostgreSQL connection is properly configured.

    Verifies:
    - Connection to PostgreSQL works
    - Can execute basic queries
    """
    async with get_session() as session:
        # Verify we can execute a simple query
        from sqlalchemy import text

        result = await session.execute(text("SELECT 1"))
        value = result.scalar()
        assert value == 1, f"Expected SELECT 1 to return 1, got {value}"
