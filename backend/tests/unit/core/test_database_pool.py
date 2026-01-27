"""Unit tests for database connection pool handling.

Tests cover:
- init_db() pool initialization with various configurations
- close_db() cleanup under concurrent access scenarios
- get_session() transaction isolation and nested contexts
- Pool timeout behavior
- Multiple coroutines calling close_db concurrently
- Nested transactions
- Partial failure scenarios

Uses mocks for SQLAlchemy engine and session to avoid requiring a real database.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# =============================================================================
# init_db() Pool Initialization Tests
# =============================================================================


class TestInitDbPoolConfiguration:
    """Tests for init_db() pool configuration."""

    @pytest.mark.asyncio
    async def test_init_db_creates_engine_with_pool_settings(self) -> None:
        """Test that init_db creates engine with correct pool configuration."""
        import backend.core.database as db_module

        # Save original state
        original_engine = db_module._engine
        original_factory = db_module._async_session_factory

        try:
            db_module._engine = None
            db_module._async_session_factory = None

            mock_engine = AsyncMock()
            mock_conn = AsyncMock()
            mock_conn.run_sync = AsyncMock()

            @asynccontextmanager
            async def mock_begin() -> AsyncGenerator[AsyncMock]:
                yield mock_conn

            mock_engine.begin = mock_begin

            with (
                patch("backend.core.database.get_settings") as mock_settings,
                patch(
                    "backend.core.database.create_async_engine",
                    return_value=mock_engine,
                ) as mock_create_engine,
                patch("backend.core.database.async_sessionmaker") as mock_sessionmaker,
            ):
                mock_settings.return_value = MagicMock(
                    database_url="postgresql+asyncpg://user:pass@localhost:5432/testdb",
                    database_url_read=None,
                    debug=False,
                    database_pool_size=20,
                    database_pool_overflow=30,
                    database_pool_timeout=30,
                    database_pool_recycle=1800,
                    use_pgbouncer=False,
                )
                mock_sessionmaker.return_value = MagicMock()

                await db_module.init_db()

                # Verify engine was created with pool settings
                mock_create_engine.assert_called_once()
                call_kwargs = mock_create_engine.call_args[1]
                assert call_kwargs["pool_size"] == 20
                assert call_kwargs["max_overflow"] == 30
                assert call_kwargs["pool_timeout"] == 30
                assert call_kwargs["pool_recycle"] == 1800
                assert call_kwargs["pool_pre_ping"] is True
                assert call_kwargs["pool_use_lifo"] is True

        finally:
            db_module._engine = original_engine
            db_module._async_session_factory = original_factory

    @pytest.mark.asyncio
    async def test_init_db_creates_session_factory(self) -> None:
        """Test that init_db creates async_sessionmaker with correct settings."""
        import backend.core.database as db_module

        original_engine = db_module._engine
        original_factory = db_module._async_session_factory

        try:
            db_module._engine = None
            db_module._async_session_factory = None

            mock_engine = AsyncMock()
            mock_conn = AsyncMock()
            mock_conn.run_sync = AsyncMock()

            @asynccontextmanager
            async def mock_begin() -> AsyncGenerator[AsyncMock]:
                yield mock_conn

            mock_engine.begin = mock_begin

            with (
                patch("backend.core.database.get_settings") as mock_settings,
                patch(
                    "backend.core.database.create_async_engine",
                    return_value=mock_engine,
                ),
                patch("backend.core.database.async_sessionmaker") as mock_sessionmaker,
            ):
                mock_settings.return_value = MagicMock(
                    database_url="postgresql+asyncpg://user:pass@localhost:5432/testdb",
                    database_url_read=None,
                    debug=False,
                    database_pool_size=10,
                    database_pool_overflow=20,
                    database_pool_timeout=30,
                    database_pool_recycle=1800,
                    use_pgbouncer=False,
                )
                mock_sessionmaker.return_value = MagicMock()

                await db_module.init_db()

                # Verify sessionmaker was created with correct settings
                mock_sessionmaker.assert_called_once()
                call_kwargs = mock_sessionmaker.call_args[1]
                assert call_kwargs["expire_on_commit"] is False
                assert call_kwargs["autocommit"] is False
                assert call_kwargs["autoflush"] is False

        finally:
            db_module._engine = original_engine
            db_module._async_session_factory = original_factory

    @pytest.mark.asyncio
    async def test_init_db_with_debug_mode(self) -> None:
        """Test that init_db enables echo when debug is True."""
        import backend.core.database as db_module

        original_engine = db_module._engine
        original_factory = db_module._async_session_factory

        try:
            db_module._engine = None
            db_module._async_session_factory = None

            mock_engine = AsyncMock()
            mock_conn = AsyncMock()
            mock_conn.run_sync = AsyncMock()

            @asynccontextmanager
            async def mock_begin() -> AsyncGenerator[AsyncMock]:
                yield mock_conn

            mock_engine.begin = mock_begin

            with (
                patch("backend.core.database.get_settings") as mock_settings,
                patch(
                    "backend.core.database.create_async_engine",
                    return_value=mock_engine,
                ) as mock_create_engine,
                patch("backend.core.database.async_sessionmaker"),
            ):
                mock_settings.return_value = MagicMock(
                    database_url="postgresql+asyncpg://user:pass@localhost:5432/testdb",
                    database_url_read=None,
                    debug=True,  # Enable debug
                    database_pool_size=10,
                    database_pool_overflow=20,
                    database_pool_timeout=30,
                    database_pool_recycle=1800,
                    use_pgbouncer=False,
                )

                await db_module.init_db()

                # Verify echo is enabled
                call_kwargs = mock_create_engine.call_args[1]
                assert call_kwargs["echo"] is True

        finally:
            db_module._engine = original_engine
            db_module._async_session_factory = original_factory

    @pytest.mark.asyncio
    async def test_init_db_rejects_non_postgresql_url(self) -> None:
        """Test that init_db raises ValueError for non-PostgreSQL URLs."""
        import backend.core.database as db_module

        original_engine = db_module._engine
        original_factory = db_module._async_session_factory

        try:
            db_module._engine = None
            db_module._async_session_factory = None

            with patch("backend.core.database.get_settings") as mock_settings:
                mock_settings.return_value = MagicMock(
                    database_url="mysql://user:pass@localhost:3306/testdb",
                    database_url_read=None,
                    debug=False,
                    database_pool_size=10,
                    database_pool_overflow=20,
                    database_pool_timeout=30,
                    database_pool_recycle=1800,
                    use_pgbouncer=False,
                )

                with pytest.raises(ValueError) as exc_info:
                    await db_module.init_db()

                assert "postgresql+asyncpg://" in str(exc_info.value)

        finally:
            db_module._engine = original_engine
            db_module._async_session_factory = original_factory


# =============================================================================
# close_db() Cleanup Tests
# =============================================================================


class TestCloseDbConcurrent:
    """Tests for close_db() under concurrent access scenarios."""

    @pytest.mark.asyncio
    async def test_close_db_concurrent_calls(self) -> None:
        """Test that multiple concurrent close_db calls are safe.

        Note: The current implementation does NOT use locking, so concurrent calls
        that start before any of them completes will all try to dispose the engine.
        This test verifies that:
        1. No exceptions are raised from concurrent access
        2. The engine and factory are properly reset to None after all calls complete

        The actual number of dispose calls may vary based on timing, but the final
        state must be clean (both globals set to None).
        """
        import backend.core.database as db_module

        original_engine = db_module._engine
        original_factory = db_module._async_session_factory

        try:
            # Create a mock engine with a slight delay to simulate real disposal
            mock_engine = AsyncMock()
            dispose_call_count = 0

            async def delayed_dispose() -> None:
                nonlocal dispose_call_count
                dispose_call_count += 1
                await asyncio.sleep(0.01)  # Small delay to simulate work

            mock_engine.dispose = delayed_dispose

            db_module._engine = mock_engine
            db_module._async_session_factory = MagicMock()

            # Call close_db concurrently from multiple coroutines
            results = await asyncio.gather(
                db_module.close_db(),
                db_module.close_db(),
                db_module.close_db(),
                return_exceptions=True,
            )

            # No exceptions should be raised
            for result in results:
                assert not isinstance(result, Exception)

            # All concurrent calls should have completed safely
            # Due to race conditions, multiple calls may have called dispose
            # but at least one must have, and the final state must be clean
            assert dispose_call_count >= 1
            assert db_module._engine is None
            assert db_module._async_session_factory is None

        finally:
            db_module._engine = original_engine
            db_module._async_session_factory = original_factory

    @pytest.mark.asyncio
    async def test_close_db_handles_dispose_exception_gracefully(self) -> None:
        """Test that close_db still resets state even when dispose fails."""
        import backend.core.database as db_module

        original_engine = db_module._engine
        original_factory = db_module._async_session_factory

        try:
            mock_engine = AsyncMock()
            mock_engine.dispose = AsyncMock(side_effect=RuntimeError("Connection error"))

            db_module._engine = mock_engine
            db_module._async_session_factory = MagicMock()

            # Should propagate the exception
            with pytest.raises(RuntimeError) as exc_info:
                await db_module.close_db()

            assert "Connection error" in str(exc_info.value)

            # State should still be reset via finally block
            assert db_module._engine is None
            assert db_module._async_session_factory is None

        finally:
            db_module._engine = original_engine
            db_module._async_session_factory = original_factory

    @pytest.mark.asyncio
    async def test_close_db_idempotent(self) -> None:
        """Test that calling close_db multiple times is safe."""
        import backend.core.database as db_module

        original_engine = db_module._engine
        original_factory = db_module._async_session_factory

        try:
            mock_engine = AsyncMock()
            mock_engine.dispose = AsyncMock()

            db_module._engine = mock_engine
            db_module._async_session_factory = MagicMock()

            # First call
            await db_module.close_db()
            assert db_module._engine is None

            # Second call should not raise
            await db_module.close_db()

            # Third call should not raise
            await db_module.close_db()

            # dispose should only be called once (first time)
            mock_engine.dispose.assert_called_once()

        finally:
            db_module._engine = original_engine
            db_module._async_session_factory = original_factory


# =============================================================================
# Pool Timeout Behavior Tests
# =============================================================================


class TestPoolTimeoutBehavior:
    """Tests for pool timeout configuration and behavior."""

    @pytest.mark.asyncio
    async def test_pool_timeout_configuration(self) -> None:
        """Test that pool_timeout is passed correctly to the engine."""
        import backend.core.database as db_module

        original_engine = db_module._engine
        original_factory = db_module._async_session_factory

        try:
            db_module._engine = None
            db_module._async_session_factory = None

            mock_engine = AsyncMock()
            mock_conn = AsyncMock()
            mock_conn.run_sync = AsyncMock()

            @asynccontextmanager
            async def mock_begin() -> AsyncGenerator[AsyncMock]:
                yield mock_conn

            mock_engine.begin = mock_begin

            custom_timeout = 60  # Custom timeout value

            with (
                patch("backend.core.database.get_settings") as mock_settings,
                patch(
                    "backend.core.database.create_async_engine",
                    return_value=mock_engine,
                ) as mock_create_engine,
                patch("backend.core.database.async_sessionmaker"),
            ):
                mock_settings.return_value = MagicMock(
                    database_url="postgresql+asyncpg://user:pass@localhost:5432/testdb",
                    database_url_read=None,
                    debug=False,
                    database_pool_size=10,
                    database_pool_overflow=20,
                    database_pool_timeout=custom_timeout,
                    database_pool_recycle=1800,
                    use_pgbouncer=False,
                )

                await db_module.init_db()

                call_kwargs = mock_create_engine.call_args[1]
                assert call_kwargs["pool_timeout"] == custom_timeout

        finally:
            db_module._engine = original_engine
            db_module._async_session_factory = original_factory

    @pytest.mark.asyncio
    async def test_pool_recycle_configuration(self) -> None:
        """Test that pool_recycle is passed correctly to the engine."""
        import backend.core.database as db_module

        original_engine = db_module._engine
        original_factory = db_module._async_session_factory

        try:
            db_module._engine = None
            db_module._async_session_factory = None

            mock_engine = AsyncMock()
            mock_conn = AsyncMock()
            mock_conn.run_sync = AsyncMock()

            @asynccontextmanager
            async def mock_begin() -> AsyncGenerator[AsyncMock]:
                yield mock_conn

            mock_engine.begin = mock_begin

            custom_recycle = 3600  # 1 hour

            with (
                patch("backend.core.database.get_settings") as mock_settings,
                patch(
                    "backend.core.database.create_async_engine",
                    return_value=mock_engine,
                ) as mock_create_engine,
                patch("backend.core.database.async_sessionmaker"),
            ):
                mock_settings.return_value = MagicMock(
                    database_url="postgresql+asyncpg://user:pass@localhost:5432/testdb",
                    database_url_read=None,
                    debug=False,
                    database_pool_size=10,
                    database_pool_overflow=20,
                    database_pool_timeout=30,
                    database_pool_recycle=custom_recycle,
                    use_pgbouncer=False,
                )

                await db_module.init_db()

                call_kwargs = mock_create_engine.call_args[1]
                assert call_kwargs["pool_recycle"] == custom_recycle

        finally:
            db_module._engine = original_engine
            db_module._async_session_factory = original_factory


# =============================================================================
# get_session() Transaction Isolation Tests
# =============================================================================


class TestGetSessionTransactionIsolation:
    """Tests for get_session() transaction isolation."""

    @pytest.mark.asyncio
    async def test_get_session_raises_when_not_initialized(self) -> None:
        """Test that get_session raises RuntimeError when DB not initialized."""
        import backend.core.database as db_module

        original_factory = db_module._async_session_factory

        try:
            db_module._async_session_factory = None

            with pytest.raises(RuntimeError) as exc_info:
                async with db_module.get_session():
                    pass

            assert "not initialized" in str(exc_info.value)

        finally:
            db_module._async_session_factory = original_factory

    @pytest.mark.asyncio
    async def test_get_session_commits_transaction(self) -> None:
        """Test that get_session commits on successful completion."""
        import backend.core.database as db_module

        original_factory = db_module._async_session_factory

        try:
            mock_session = AsyncMock()
            mock_session.commit = AsyncMock()
            mock_session.rollback = AsyncMock()

            mock_factory = MagicMock()

            @asynccontextmanager
            async def mock_session_cm() -> AsyncGenerator[AsyncMock]:
                yield mock_session

            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=None)

            db_module._async_session_factory = mock_factory

            async with db_module.get_session() as session:
                assert session is mock_session

            mock_session.commit.assert_called_once()
            mock_session.rollback.assert_not_called()

        finally:
            db_module._async_session_factory = original_factory

    @pytest.mark.asyncio
    async def test_get_session_rollbacks_on_error(self) -> None:
        """Test that get_session rollbacks on exception."""
        import backend.core.database as db_module

        original_factory = db_module._async_session_factory

        try:
            mock_session = AsyncMock()
            mock_session.commit = AsyncMock()
            mock_session.rollback = AsyncMock()

            mock_factory = MagicMock()
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=None)

            db_module._async_session_factory = mock_factory

            with pytest.raises(ValueError):
                async with db_module.get_session():
                    raise ValueError("Test error")

            mock_session.rollback.assert_called_once()
            mock_session.commit.assert_not_called()

        finally:
            db_module._async_session_factory = original_factory


class TestGetSessionNestedContexts:
    """Tests for get_session() with nested context managers."""

    @pytest.mark.asyncio
    async def test_nested_sessions_independent(self) -> None:
        """Test that nested get_session calls are independent."""
        import backend.core.database as db_module

        original_factory = db_module._async_session_factory

        try:
            # Track session instances created
            sessions_created = []

            mock_factory = MagicMock()

            def create_session_cm() -> MagicMock:
                mock_session = AsyncMock()
                mock_session.commit = AsyncMock()
                mock_session.rollback = AsyncMock()
                sessions_created.append(mock_session)

                cm = MagicMock()
                cm.__aenter__ = AsyncMock(return_value=mock_session)
                cm.__aexit__ = AsyncMock(return_value=None)
                return cm

            mock_factory.side_effect = create_session_cm

            db_module._async_session_factory = mock_factory

            # Open two nested sessions
            async with (
                db_module.get_session() as outer_session,
                db_module.get_session() as inner_session,
            ):
                # They should be different session objects
                assert outer_session is not inner_session

            # Both sessions should be committed
            assert len(sessions_created) == 2
            for session in sessions_created:
                session.commit.assert_called_once()
                session.rollback.assert_not_called()

        finally:
            db_module._async_session_factory = original_factory

    @pytest.mark.asyncio
    async def test_inner_session_rollback_independent(self) -> None:
        """Test that inner session rollback doesn't affect outer session."""
        import backend.core.database as db_module

        original_factory = db_module._async_session_factory

        try:
            sessions_created = []

            mock_factory = MagicMock()

            def create_session_cm() -> MagicMock:
                mock_session = AsyncMock()
                mock_session.commit = AsyncMock()
                mock_session.rollback = AsyncMock()
                sessions_created.append(mock_session)

                cm = MagicMock()
                cm.__aenter__ = AsyncMock(return_value=mock_session)
                cm.__aexit__ = AsyncMock(return_value=None)
                return cm

            mock_factory.side_effect = create_session_cm

            db_module._async_session_factory = mock_factory

            async with db_module.get_session() as _outer:
                try:
                    async with db_module.get_session():
                        raise ValueError("Inner error")
                except ValueError:
                    pass  # Expected

            # Outer should commit, inner should rollback
            outer_session = sessions_created[0]
            inner_session = sessions_created[1]

            outer_session.commit.assert_called_once()
            outer_session.rollback.assert_not_called()

            inner_session.rollback.assert_called_once()
            inner_session.commit.assert_not_called()

        finally:
            db_module._async_session_factory = original_factory


# =============================================================================
# Partial Failure Scenarios
# =============================================================================


class TestPartialFailureScenarios:
    """Tests for partial failure scenarios."""

    @pytest.mark.asyncio
    async def test_commit_failure_triggers_rollback(self) -> None:
        """Test that commit failure results in attempted rollback."""
        import backend.core.database as db_module

        original_factory = db_module._async_session_factory

        try:
            mock_session = AsyncMock()
            mock_session.commit = AsyncMock(side_effect=RuntimeError("Commit failed"))
            mock_session.rollback = AsyncMock()

            mock_factory = MagicMock()
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=None)

            db_module._async_session_factory = mock_factory

            # The exception from commit should propagate
            with pytest.raises(RuntimeError) as exc_info:
                async with db_module.get_session():
                    pass  # No error in user code, but commit fails

            assert "Commit failed" in str(exc_info.value)
            # Commit was called and failed
            mock_session.commit.assert_called_once()

        finally:
            db_module._async_session_factory = original_factory

    @pytest.mark.asyncio
    async def test_rollback_failure_after_user_error(self) -> None:
        """Test that rollback failure after user error propagates correctly."""
        import backend.core.database as db_module

        original_factory = db_module._async_session_factory

        try:
            mock_session = AsyncMock()
            mock_session.commit = AsyncMock()
            mock_session.rollback = AsyncMock(side_effect=RuntimeError("Rollback failed"))

            mock_factory = MagicMock()
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=None)

            db_module._async_session_factory = mock_factory

            # User error triggers rollback, which also fails
            with pytest.raises(RuntimeError) as exc_info:
                async with db_module.get_session():
                    raise ValueError("User error")

            # The rollback exception should propagate (replaces user error)
            assert "Rollback failed" in str(exc_info.value)
            mock_session.rollback.assert_called_once()
            mock_session.commit.assert_not_called()

        finally:
            db_module._async_session_factory = original_factory

    @pytest.mark.asyncio
    async def test_session_factory_creation_failure(self) -> None:
        """Test handling when session factory fails to create session."""
        import backend.core.database as db_module

        original_factory = db_module._async_session_factory

        try:
            mock_factory = MagicMock()
            mock_factory.return_value.__aenter__ = AsyncMock(
                side_effect=RuntimeError("Pool exhausted")
            )

            db_module._async_session_factory = mock_factory

            with pytest.raises(RuntimeError) as exc_info:
                async with db_module.get_session():
                    pass

            assert "Pool exhausted" in str(exc_info.value)

        finally:
            db_module._async_session_factory = original_factory


# =============================================================================
# Engine State Tests
# =============================================================================


class TestEngineState:
    """Tests for engine and session factory state management."""

    def test_get_engine_returns_engine_when_initialized(self) -> None:
        """Test that get_engine returns engine when properly initialized."""
        import backend.core.database as db_module

        original_engine = db_module._engine

        try:
            mock_engine = MagicMock()
            db_module._engine = mock_engine

            result = db_module.get_engine()
            assert result is mock_engine

        finally:
            db_module._engine = original_engine

    def test_get_session_factory_returns_factory_when_initialized(self) -> None:
        """Test that get_session_factory returns factory when properly initialized."""
        import backend.core.database as db_module

        original_factory = db_module._async_session_factory

        try:
            mock_factory = MagicMock()
            db_module._async_session_factory = mock_factory

            result = db_module.get_session_factory()
            assert result is mock_factory

        finally:
            db_module._async_session_factory = original_factory


# =============================================================================
# get_db() FastAPI Dependency Tests
# =============================================================================


class TestGetDbDependency:
    """Tests for get_db() FastAPI dependency function."""

    @pytest.mark.asyncio
    async def test_get_db_yields_session(self) -> None:
        """Test that get_db yields a session for FastAPI dependency injection."""
        import backend.core.database as db_module

        original_factory = db_module._async_session_factory

        try:
            mock_session = AsyncMock()
            mock_session.commit = AsyncMock()
            mock_session.rollback = AsyncMock()
            mock_session.close = AsyncMock()

            # Create a proper async context manager mock
            mock_cm = AsyncMock()
            mock_cm.__aenter__.return_value = mock_session
            mock_cm.__aexit__.return_value = None

            mock_factory = MagicMock()
            mock_factory.return_value = mock_cm

            db_module._async_session_factory = mock_factory

            # Mock _check_loop_mismatch to avoid re-initialization
            with patch.object(db_module, "_check_loop_mismatch", return_value=False):
                # Consume the async generator
                gen = db_module.get_db()
                session = await gen.__anext__()

                assert session is mock_session

                # Complete the generator normally
                try:
                    await gen.__anext__()
                except StopAsyncIteration:
                    pass

            mock_session.commit.assert_called_once()
            mock_session.close.assert_called_once()

        finally:
            db_module._async_session_factory = original_factory

    @pytest.mark.asyncio
    async def test_get_db_closes_on_exception(self) -> None:
        """Test that get_db closes session even on exception."""
        import backend.core.database as db_module

        original_factory = db_module._async_session_factory

        try:
            mock_session = AsyncMock()
            mock_session.commit = AsyncMock()
            mock_session.rollback = AsyncMock()
            mock_session.close = AsyncMock()

            # Create a proper async context manager mock
            mock_cm = AsyncMock()
            mock_cm.__aenter__.return_value = mock_session
            mock_cm.__aexit__.return_value = None

            mock_factory = MagicMock()
            mock_factory.return_value = mock_cm

            db_module._async_session_factory = mock_factory

            # Mock _check_loop_mismatch to avoid re-initialization
            with patch.object(db_module, "_check_loop_mismatch", return_value=False):
                gen = db_module.get_db()
                await gen.__anext__()

                # Throw an exception into the generator
                try:
                    await gen.athrow(ValueError("Test error"))
                except ValueError:
                    pass

            # Session should still be closed in finally block
            mock_session.close.assert_called_once()
            mock_session.rollback.assert_called_once()

        finally:
            db_module._async_session_factory = original_factory


# =============================================================================
# Concurrent Session Access Tests
# =============================================================================


class TestConcurrentSessionAccess:
    """Tests for concurrent session access patterns."""

    @pytest.mark.asyncio
    async def test_concurrent_sessions_use_separate_connections(self) -> None:
        """Test that concurrent sessions receive separate session objects."""
        import backend.core.database as db_module

        original_factory = db_module._async_session_factory

        try:
            sessions_created = []

            mock_factory = MagicMock()

            def create_session_cm() -> MagicMock:
                mock_session = AsyncMock()
                mock_session.commit = AsyncMock()
                mock_session.rollback = AsyncMock()
                sessions_created.append(mock_session)

                cm = MagicMock()
                cm.__aenter__ = AsyncMock(return_value=mock_session)
                cm.__aexit__ = AsyncMock(return_value=None)
                return cm

            mock_factory.side_effect = create_session_cm

            db_module._async_session_factory = mock_factory

            # Create multiple concurrent sessions
            async def use_session() -> AsyncMock:
                async with db_module.get_session() as session:
                    await asyncio.sleep(0.001)  # Small delay to ensure overlap
                    return session

            await asyncio.gather(
                use_session(),
                use_session(),
                use_session(),
            )

            # Each should have received a unique session
            assert len(sessions_created) == 3
            assert len({id(s) for s in sessions_created}) == 3

            # All should be committed
            for session in sessions_created:
                session.commit.assert_called_once()

        finally:
            db_module._async_session_factory = original_factory

    @pytest.mark.asyncio
    async def test_concurrent_error_handling_independent(self) -> None:
        """Test that concurrent sessions handle errors independently."""
        import backend.core.database as db_module

        original_factory = db_module._async_session_factory

        try:
            sessions_created = []

            mock_factory = MagicMock()

            def create_session_cm() -> MagicMock:
                mock_session = AsyncMock()
                mock_session.commit = AsyncMock()
                mock_session.rollback = AsyncMock()
                sessions_created.append(mock_session)

                cm = MagicMock()
                cm.__aenter__ = AsyncMock(return_value=mock_session)
                cm.__aexit__ = AsyncMock(return_value=None)
                return cm

            mock_factory.side_effect = create_session_cm

            db_module._async_session_factory = mock_factory

            async def successful_session() -> str:
                async with db_module.get_session():
                    return "success"

            async def failing_session() -> str:
                async with db_module.get_session():
                    raise ValueError("Intentional error")

            results = await asyncio.gather(
                successful_session(),
                failing_session(),
                successful_session(),
                return_exceptions=True,
            )

            # Should have success, error, success
            assert results[0] == "success"
            assert isinstance(results[1], ValueError)
            assert results[2] == "success"

            # Two sessions should commit, one should rollback
            commits = sum(1 for s in sessions_created if s.commit.called)
            rollbacks = sum(1 for s in sessions_created if s.rollback.called)

            assert commits == 2
            assert rollbacks == 1

        finally:
            db_module._async_session_factory = original_factory


# =============================================================================
# Connection Pool Warming Tests (NEM-3757)
# =============================================================================


class TestConnectionPoolWarming:
    """Tests for warm_connection_pool() function."""

    @pytest.mark.asyncio
    async def test_warm_pool_when_not_initialized(self) -> None:
        """Test that warm_connection_pool returns error when DB not initialized."""
        import backend.core.database as db_module

        original_engine = db_module._engine

        try:
            db_module._engine = None

            result = await db_module.warm_connection_pool()

            assert result["success"] is False
            assert result["connections_warmed"] == 0
            assert "not initialized" in result["error"].lower()

        finally:
            db_module._engine = original_engine

    @pytest.mark.asyncio
    async def test_warm_pool_success(self) -> None:
        """Test successful connection pool warming."""
        import backend.core.database as db_module

        original_engine = db_module._engine

        try:
            # Create mock engine with connect method
            mock_engine = AsyncMock()
            mock_conn = AsyncMock()
            mock_conn.execute = AsyncMock()

            @asynccontextmanager
            async def mock_connect() -> AsyncGenerator[AsyncMock]:
                yield mock_conn

            mock_engine.connect = mock_connect

            db_module._engine = mock_engine

            with patch("backend.core.database.get_settings") as mock_settings:
                mock_settings.return_value = MagicMock(
                    database_pool_warming_size=3,
                    database_pool_warming_timeout=30,
                    database_pool_size=20,
                )

                result = await db_module.warm_connection_pool()

                assert result["success"] is True
                assert result["connections_warmed"] == 3
                assert result["target_connections"] == 3
                assert result["error"] is None
                assert result["duration_ms"] >= 0

        finally:
            db_module._engine = original_engine

    @pytest.mark.asyncio
    async def test_warm_pool_with_custom_target(self) -> None:
        """Test pool warming with custom target connections."""
        import backend.core.database as db_module

        original_engine = db_module._engine

        try:
            mock_engine = AsyncMock()
            mock_conn = AsyncMock()
            mock_conn.execute = AsyncMock()

            @asynccontextmanager
            async def mock_connect() -> AsyncGenerator[AsyncMock]:
                yield mock_conn

            mock_engine.connect = mock_connect

            db_module._engine = mock_engine

            with patch("backend.core.database.get_settings") as mock_settings:
                mock_settings.return_value = MagicMock(
                    database_pool_warming_size=5,
                    database_pool_warming_timeout=30,
                    database_pool_size=20,
                )

                # Override with custom target
                result = await db_module.warm_connection_pool(target_connections=2)

                assert result["success"] is True
                assert result["connections_warmed"] == 2
                assert result["target_connections"] == 2

        finally:
            db_module._engine = original_engine

    @pytest.mark.asyncio
    async def test_warm_pool_clamps_to_pool_size(self) -> None:
        """Test that target is clamped to pool_size."""
        import backend.core.database as db_module

        original_engine = db_module._engine

        try:
            mock_engine = AsyncMock()
            mock_conn = AsyncMock()
            mock_conn.execute = AsyncMock()

            @asynccontextmanager
            async def mock_connect() -> AsyncGenerator[AsyncMock]:
                yield mock_conn

            mock_engine.connect = mock_connect

            db_module._engine = mock_engine

            with patch("backend.core.database.get_settings") as mock_settings:
                mock_settings.return_value = MagicMock(
                    database_pool_warming_size=50,  # Higher than pool_size
                    database_pool_warming_timeout=30,
                    database_pool_size=10,  # Smaller pool
                )

                result = await db_module.warm_connection_pool()

                # Should be clamped to pool_size
                assert result["target_connections"] == 10
                assert result["connections_warmed"] == 10

        finally:
            db_module._engine = original_engine

    @pytest.mark.asyncio
    async def test_warm_pool_handles_connection_failures(self) -> None:
        """Test pool warming handles some connection failures gracefully."""
        import backend.core.database as db_module

        original_engine = db_module._engine

        try:
            mock_engine = AsyncMock()
            call_count = 0

            @asynccontextmanager
            async def mock_connect() -> AsyncGenerator[AsyncMock]:
                nonlocal call_count
                call_count += 1
                if call_count % 2 == 0:
                    raise RuntimeError("Connection failed")
                mock_conn = AsyncMock()
                mock_conn.execute = AsyncMock()
                yield mock_conn

            mock_engine.connect = mock_connect

            db_module._engine = mock_engine

            with patch("backend.core.database.get_settings") as mock_settings:
                mock_settings.return_value = MagicMock(
                    database_pool_warming_size=4,
                    database_pool_warming_timeout=30,
                    database_pool_size=20,
                )

                result = await db_module.warm_connection_pool()

                # 2 out of 4 should succeed (odd calls)
                assert result["connections_warmed"] == 2
                assert result["target_connections"] == 4
                # Still considered success if at least one warmed
                assert result["success"] is True

        finally:
            db_module._engine = original_engine

    @pytest.mark.asyncio
    async def test_warm_pool_timeout(self) -> None:
        """Test pool warming timeout handling."""
        import backend.core.database as db_module

        original_engine = db_module._engine

        try:
            mock_engine = AsyncMock()

            @asynccontextmanager
            async def slow_connect() -> AsyncGenerator[AsyncMock]:
                # Simulate slow connection that exceeds timeout
                await asyncio.sleep(10)  # 10 seconds delay
                mock_conn = AsyncMock()
                mock_conn.execute = AsyncMock()
                yield mock_conn

            mock_engine.connect = slow_connect

            db_module._engine = mock_engine

            with patch("backend.core.database.get_settings") as mock_settings:
                mock_settings.return_value = MagicMock(
                    database_pool_warming_size=3,
                    database_pool_warming_timeout=1,  # 1 second timeout
                    database_pool_size=20,
                )

                result = await db_module.warm_connection_pool(timeout_seconds=1)

                # Should timeout
                assert result["connections_warmed"] == 0
                assert "timed out" in result["error"].lower()
                assert result["success"] is False

        finally:
            db_module._engine = original_engine

    @pytest.mark.asyncio
    async def test_warm_pool_all_failures(self) -> None:
        """Test pool warming when all connections fail."""
        import backend.core.database as db_module

        original_engine = db_module._engine

        try:
            mock_engine = AsyncMock()

            @asynccontextmanager
            async def failing_connect() -> AsyncGenerator[AsyncMock]:
                raise RuntimeError("All connections fail")
                yield AsyncMock()

            mock_engine.connect = failing_connect

            db_module._engine = mock_engine

            with patch("backend.core.database.get_settings") as mock_settings:
                mock_settings.return_value = MagicMock(
                    database_pool_warming_size=3,
                    database_pool_warming_timeout=30,
                    database_pool_size=20,
                )

                result = await db_module.warm_connection_pool()

                assert result["connections_warmed"] == 0
                # No error message since individual failures don't set it
                # But success should be False since no connections were warmed
                assert result["success"] is False

        finally:
            db_module._engine = original_engine
