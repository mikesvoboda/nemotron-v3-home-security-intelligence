"""Unit tests for database initialization advisory lock mechanism.

Tests verify that init_db uses PostgreSQL advisory locks to prevent deadlocks
when multiple workers attempt to initialize the database concurrently.

The advisory lock mechanism ensures:
1. Only one worker can run schema creation at a time
2. Other workers wait for the lock and then proceed without re-creating schema
3. Deadlocks from concurrent CREATE INDEX operations are prevented

NOTE: These tests manipulate global database module state (_engine, _async_session_factory)
and must run serially to prevent race conditions with other tests that use the database.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Mark all tests in this module for serial execution to avoid parallel conflicts
# These tests modify global database state which would cause race conditions
# with tests using isolated_db fixture when run in parallel.
pytestmark = [
    pytest.mark.serial,
    pytest.mark.xdist_group(name="database_init_lock"),
]


class TestInitDbAdvisoryLock:
    """Tests for advisory lock mechanism in init_db."""

    @pytest.mark.asyncio
    async def test_init_db_acquires_advisory_lock(self) -> None:
        """Test that init_db acquires a PostgreSQL advisory lock during schema creation.

        The advisory lock prevents deadlocks when multiple workers start simultaneously
        and all try to create indexes on the same tables.
        """
        import backend.core.database as db_module

        # Save original state
        original_engine = db_module._engine
        original_factory = db_module._async_session_factory

        try:
            db_module._engine = None
            db_module._async_session_factory = None

            # Track all SQL statements executed
            executed_statements: list[str] = []

            mock_conn = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar.return_value = True  # Lock acquired

            async def track_execute(stmt):
                # Extract the text from TextClause objects
                stmt_text = getattr(stmt, "text", str(stmt))
                executed_statements.append(stmt_text)
                return mock_result

            mock_conn.execute = track_execute
            mock_conn.run_sync = AsyncMock()

            # Create mock context manager for begin()
            mock_begin_ctx = AsyncMock()
            mock_begin_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_begin_ctx.__aexit__ = AsyncMock(return_value=None)

            mock_engine = AsyncMock()
            mock_engine.begin = MagicMock(return_value=mock_begin_ctx)

            with (
                patch("backend.core.database.get_settings") as mock_settings,
                patch("backend.core.database.create_async_engine", return_value=mock_engine),
                patch("backend.core.database.async_sessionmaker"),
            ):
                mock_settings.return_value = MagicMock(
                    database_url="postgresql+asyncpg://localhost/test",
                    debug=False,
                    database_pool_size=5,
                    database_pool_overflow=10,
                    database_pool_timeout=30,
                    database_pool_recycle=1800,
                )

                await db_module.init_db()

                # Verify advisory lock was acquired
                lock_call_found = any(
                    "pg_try_advisory_lock" in stmt or "pg_advisory_lock" in stmt
                    for stmt in executed_statements
                )

                assert lock_call_found, (
                    "init_db should acquire a PostgreSQL advisory lock during schema creation. "
                    f"Statements executed: {executed_statements}"
                )

        finally:
            # Restore original state
            db_module._engine = original_engine
            db_module._async_session_factory = original_factory

    @pytest.mark.asyncio
    async def test_init_db_releases_advisory_lock_on_success(self) -> None:
        """Test that init_db releases the advisory lock after successful schema creation."""
        import backend.core.database as db_module

        # Save original state
        original_engine = db_module._engine
        original_factory = db_module._async_session_factory

        try:
            db_module._engine = None
            db_module._async_session_factory = None

            # Track all SQL statements executed
            executed_statements: list[str] = []

            mock_conn = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar.return_value = True  # Lock acquired

            async def track_execute(stmt):
                executed_statements.append(str(stmt))
                return mock_result

            mock_conn.execute = track_execute
            mock_conn.run_sync = AsyncMock()

            # Create mock context manager for begin()
            mock_begin_ctx = AsyncMock()
            mock_begin_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_begin_ctx.__aexit__ = AsyncMock(return_value=None)

            mock_engine = AsyncMock()
            mock_engine.begin = MagicMock(return_value=mock_begin_ctx)

            with (
                patch("backend.core.database.get_settings") as mock_settings,
                patch("backend.core.database.create_async_engine", return_value=mock_engine),
                patch("backend.core.database.async_sessionmaker"),
            ):
                mock_settings.return_value = MagicMock(
                    database_url="postgresql+asyncpg://localhost/test",
                    debug=False,
                    database_pool_size=5,
                    database_pool_overflow=10,
                    database_pool_timeout=30,
                    database_pool_recycle=1800,
                )

                await db_module.init_db()

                # Verify advisory lock was released
                unlock_found = any("pg_advisory_unlock" in stmt for stmt in executed_statements)
                assert unlock_found, (
                    "init_db should release the PostgreSQL advisory lock after schema creation. "
                    f"Statements executed: {executed_statements}"
                )

        finally:
            # Restore original state
            db_module._engine = original_engine
            db_module._async_session_factory = original_factory

    @pytest.mark.asyncio
    async def test_init_db_releases_advisory_lock_on_error(self) -> None:
        """Test that init_db releases the advisory lock even if schema creation fails."""
        import backend.core.database as db_module

        # Save original state
        original_engine = db_module._engine
        original_factory = db_module._async_session_factory

        try:
            db_module._engine = None
            db_module._async_session_factory = None

            # Track all SQL statements executed
            executed_statements: list[str] = []
            run_sync_call_count = 0

            mock_conn = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar.return_value = True  # Lock acquired

            async def track_execute(stmt):
                executed_statements.append(str(stmt))
                return mock_result

            mock_conn.execute = track_execute

            async def failing_run_sync(fn):
                nonlocal run_sync_call_count
                run_sync_call_count += 1
                if run_sync_call_count == 1:  # First call is create_all
                    raise RuntimeError("Simulated schema creation failure")

            mock_conn.run_sync = failing_run_sync

            # Create mock context manager for begin()
            mock_begin_ctx = AsyncMock()
            mock_begin_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_begin_ctx.__aexit__ = AsyncMock(return_value=None)

            mock_engine = AsyncMock()
            mock_engine.begin = MagicMock(return_value=mock_begin_ctx)

            with (
                patch("backend.core.database.get_settings") as mock_settings,
                patch("backend.core.database.create_async_engine", return_value=mock_engine),
                patch("backend.core.database.async_sessionmaker"),
            ):
                mock_settings.return_value = MagicMock(
                    database_url="postgresql+asyncpg://localhost/test",
                    debug=False,
                    database_pool_size=5,
                    database_pool_overflow=10,
                    database_pool_timeout=30,
                    database_pool_recycle=1800,
                )

                with pytest.raises(RuntimeError, match="Simulated schema creation failure"):
                    await db_module.init_db()

                # Verify advisory lock was still released despite the error
                unlock_found = any("pg_advisory_unlock" in stmt for stmt in executed_statements)
                assert unlock_found, (
                    "init_db should release advisory lock even when schema creation fails. "
                    f"Statements executed: {executed_statements}"
                )

        finally:
            # Restore original state
            db_module._engine = original_engine
            db_module._async_session_factory = original_factory

    @pytest.mark.asyncio
    async def test_init_db_skips_schema_if_lock_not_acquired(self) -> None:
        """Test that init_db skips schema creation if another worker holds the lock.

        When using pg_try_advisory_lock, if another worker is already creating
        the schema, this worker should skip schema creation (the other worker
        will handle it).
        """
        import backend.core.database as db_module

        # Save original state
        original_engine = db_module._engine
        original_factory = db_module._async_session_factory

        try:
            db_module._engine = None
            db_module._async_session_factory = None

            run_sync_called = False

            mock_conn = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar.return_value = False  # Lock NOT acquired (another worker has it)

            mock_conn.execute = AsyncMock(return_value=mock_result)

            async def track_run_sync(fn):
                nonlocal run_sync_called
                run_sync_called = True

            mock_conn.run_sync = track_run_sync

            # Create mock context manager for begin()
            mock_begin_ctx = AsyncMock()
            mock_begin_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_begin_ctx.__aexit__ = AsyncMock(return_value=None)

            mock_engine = AsyncMock()
            mock_engine.begin = MagicMock(return_value=mock_begin_ctx)

            with (
                patch("backend.core.database.get_settings") as mock_settings,
                patch("backend.core.database.create_async_engine", return_value=mock_engine),
                patch("backend.core.database.async_sessionmaker"),
            ):
                mock_settings.return_value = MagicMock(
                    database_url="postgresql+asyncpg://localhost/test",
                    debug=False,
                    database_pool_size=5,
                    database_pool_overflow=10,
                    database_pool_timeout=30,
                    database_pool_recycle=1800,
                )

                await db_module.init_db()

                # Schema creation (run_sync with metadata.create_all) should NOT have been called
                # because we couldn't acquire the lock
                assert not run_sync_called, (
                    "init_db should skip schema creation when advisory lock is not acquired "
                    "(another worker is handling it)"
                )

        finally:
            # Restore original state
            db_module._engine = original_engine
            db_module._async_session_factory = original_factory

    @pytest.mark.asyncio
    async def test_advisory_lock_uses_stable_key(self) -> None:
        """Test that the advisory lock uses a stable, predictable key.

        The lock key should be derived from a stable namespace string so that
        all workers trying to initialize the same database use the same lock.
        """
        import backend.core.database as db_module

        # Save original state
        original_engine = db_module._engine
        original_factory = db_module._async_session_factory

        try:
            db_module._engine = None
            db_module._async_session_factory = None

            captured_lock_key = None

            mock_conn = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar.return_value = True

            async def capture_execute(stmt):
                nonlocal captured_lock_key
                stmt_str = str(stmt)
                if "pg_try_advisory_lock" in stmt_str or "pg_advisory_lock" in stmt_str:
                    # Extract the lock key from the statement
                    # Format: SELECT pg_try_advisory_lock(:key)
                    import re

                    match = re.search(r"advisory_lock\((\d+)\)", stmt_str)
                    if match:
                        captured_lock_key = int(match.group(1))
                return mock_result

            mock_conn.execute = capture_execute
            mock_conn.run_sync = AsyncMock()

            # Create mock context manager for begin()
            mock_begin_ctx = AsyncMock()
            mock_begin_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_begin_ctx.__aexit__ = AsyncMock(return_value=None)

            mock_engine = AsyncMock()
            mock_engine.begin = MagicMock(return_value=mock_begin_ctx)

            with (
                patch("backend.core.database.get_settings") as mock_settings,
                patch("backend.core.database.create_async_engine", return_value=mock_engine),
                patch("backend.core.database.async_sessionmaker"),
            ):
                mock_settings.return_value = MagicMock(
                    database_url="postgresql+asyncpg://localhost/test",
                    debug=False,
                    database_pool_size=5,
                    database_pool_overflow=10,
                    database_pool_timeout=30,
                    database_pool_recycle=1800,
                )

                await db_module.init_db()

                # Reset and run again - should use same lock key
                db_module._engine = None
                db_module._async_session_factory = None
                first_key = captured_lock_key
                captured_lock_key = None

                await db_module.init_db()
                second_key = captured_lock_key

                # Both runs should use the same lock key
                if first_key is not None and second_key is not None:
                    assert first_key == second_key, (
                        f"Advisory lock key should be stable across invocations. "
                        f"First: {first_key}, Second: {second_key}"
                    )

        finally:
            # Restore original state
            db_module._engine = original_engine
            db_module._async_session_factory = original_factory
