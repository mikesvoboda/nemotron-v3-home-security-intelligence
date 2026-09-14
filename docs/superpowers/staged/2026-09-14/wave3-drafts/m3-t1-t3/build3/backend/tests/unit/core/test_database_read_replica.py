"""Unit tests for read replica routing (NEM-3392).

Tests cover:
- get_read_engine function with fallback to primary
- get_read_db and get_read_session with fallback to primary
- Read replica initialization in init_db
- Read replica cleanup in close_db
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# =============================================================================
# get_read_engine Tests
# =============================================================================


class TestGetReadEngine:
    """Tests for get_read_engine function."""

    def test_get_read_engine_returns_read_engine_when_configured(self) -> None:
        """Test that get_read_engine returns read engine when configured."""
        import backend.core.database as db_module

        # Save original state
        original_engine = db_module._engine
        original_read_engine = db_module._read_engine

        try:
            mock_primary = MagicMock()
            mock_read = MagicMock()

            db_module._engine = mock_primary
            db_module._read_engine = mock_read

            result = db_module.get_read_engine()
            assert result is mock_read
        finally:
            db_module._engine = original_engine
            db_module._read_engine = original_read_engine

    def test_get_read_engine_falls_back_to_primary_when_not_configured(self) -> None:
        """Test that get_read_engine falls back to primary when read replica not set."""
        import backend.core.database as db_module

        # Save original state
        original_engine = db_module._engine
        original_read_engine = db_module._read_engine

        try:
            mock_primary = MagicMock()

            db_module._engine = mock_primary
            db_module._read_engine = None

            result = db_module.get_read_engine()
            assert result is mock_primary
        finally:
            db_module._engine = original_engine
            db_module._read_engine = original_read_engine

    def test_get_read_engine_raises_when_not_initialized(self) -> None:
        """Test that get_read_engine raises RuntimeError when not initialized."""
        import backend.core.database as db_module

        # Save original state
        original_engine = db_module._engine
        original_read_engine = db_module._read_engine

        try:
            db_module._engine = None
            db_module._read_engine = None

            with pytest.raises(RuntimeError) as exc_info:
                db_module.get_read_engine()
            assert "not initialized" in str(exc_info.value)
        finally:
            db_module._engine = original_engine
            db_module._read_engine = original_read_engine


# =============================================================================
# Read Replica Initialization Tests
# =============================================================================


class TestInitDbReadReplica:
    """Tests for read replica initialization in init_db."""

    @pytest.mark.asyncio
    async def test_init_db_initializes_read_replica_when_configured(self) -> None:
        """Test that init_db initializes read replica when database_url_read is set."""
        import backend.core.database as db_module

        # Save original state
        original_engine = db_module._engine
        original_factory = db_module._async_session_factory
        original_read_engine = db_module._read_engine
        original_read_factory = db_module._read_session_factory
        original_bound_loop = db_module._bound_loop_id

        try:
            # Reset state
            db_module._engine = None
            db_module._async_session_factory = None
            db_module._read_engine = None
            db_module._read_session_factory = None
            db_module._bound_loop_id = None

            mock_engine = MagicMock()
            mock_read_engine = MagicMock()
            mock_conn = AsyncMock()

            # Create engine side effect to track calls
            engine_calls = []

            def mock_create_engine(url, **kwargs):
                engine_calls.append(url)
                if "replica" in url:
                    return mock_read_engine
                return mock_engine

            with (
                patch("backend.core.database.get_settings") as mock_settings,
                patch(
                    "backend.core.database.create_async_engine",
                    side_effect=mock_create_engine,
                ),
                patch("backend.core.database._setup_pool_event_handlers") as mock_setup_handlers,
                patch("backend.core.database.async_sessionmaker") as mock_sessionmaker,
            ):
                mock_settings.return_value = MagicMock(
                    database_url="postgresql+asyncpg://localhost/test",
                    database_url_read="postgresql+asyncpg://replica/test",
                    debug=False,
                    database_pool_size=5,
                    database_pool_overflow=10,
                    database_pool_timeout=30,
                    database_pool_recycle=1800,
                    use_pgbouncer=False,
                )

                # Mock engine.begin() context manager
                mock_engine.begin = MagicMock()
                mock_engine.begin.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
                mock_engine.begin.return_value.__aexit__ = AsyncMock(return_value=None)

                # Mock advisory lock query
                mock_conn.execute = AsyncMock()
                mock_result = MagicMock()
                mock_result.scalar.return_value = False  # Lock not acquired
                mock_conn.execute.return_value = mock_result

                await db_module.init_db()

                # Verify both engines were created
                assert len(engine_calls) == 2
                assert "postgresql+asyncpg://localhost/test" in engine_calls
                assert "postgresql+asyncpg://replica/test" in engine_calls

                # Verify pool handlers were set up for both engines
                assert mock_setup_handlers.call_count == 2

                # Verify session factories were created for both
                assert mock_sessionmaker.call_count == 2
        finally:
            db_module._engine = original_engine
            db_module._async_session_factory = original_factory
            db_module._read_engine = original_read_engine
            db_module._read_session_factory = original_read_factory
            db_module._bound_loop_id = original_bound_loop

    @pytest.mark.asyncio
    async def test_init_db_skips_read_replica_when_not_configured(self) -> None:
        """Test that init_db skips read replica when database_url_read is None."""
        import backend.core.database as db_module

        # Save original state
        original_engine = db_module._engine
        original_factory = db_module._async_session_factory
        original_read_engine = db_module._read_engine
        original_read_factory = db_module._read_session_factory
        original_bound_loop = db_module._bound_loop_id

        try:
            # Reset state
            db_module._engine = None
            db_module._async_session_factory = None
            db_module._read_engine = None
            db_module._read_session_factory = None
            db_module._bound_loop_id = None

            mock_engine = MagicMock()
            mock_conn = AsyncMock()

            engine_calls = []

            def mock_create_engine(url, **kwargs):
                engine_calls.append(url)
                return mock_engine

            with (
                patch("backend.core.database.get_settings") as mock_settings,
                patch(
                    "backend.core.database.create_async_engine",
                    side_effect=mock_create_engine,
                ),
                patch("backend.core.database._setup_pool_event_handlers") as mock_setup_handlers,
                patch("backend.core.database.async_sessionmaker") as mock_sessionmaker,
            ):
                mock_settings.return_value = MagicMock(
                    database_url="postgresql+asyncpg://localhost/test",
                    database_url_read=None,  # No read replica
                    debug=False,
                    database_pool_size=5,
                    database_pool_overflow=10,
                    database_pool_timeout=30,
                    database_pool_recycle=1800,
                    use_pgbouncer=False,
                )

                # Mock engine.begin() context manager
                mock_engine.begin = MagicMock()
                mock_engine.begin.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
                mock_engine.begin.return_value.__aexit__ = AsyncMock(return_value=None)

                # Mock advisory lock query
                mock_conn.execute = AsyncMock()
                mock_result = MagicMock()
                mock_result.scalar.return_value = False  # Lock not acquired
                mock_conn.execute.return_value = mock_result

                await db_module.init_db()

                # Verify only primary engine was created
                assert len(engine_calls) == 1
                assert "postgresql+asyncpg://localhost/test" in engine_calls

                # Verify pool handlers were set up only for primary
                assert mock_setup_handlers.call_count == 1

                # Verify session factory was created only for primary
                assert mock_sessionmaker.call_count == 1
        finally:
            db_module._engine = original_engine
            db_module._async_session_factory = original_factory
            db_module._read_engine = original_read_engine
            db_module._read_session_factory = original_read_factory
            db_module._bound_loop_id = original_bound_loop

    @pytest.mark.asyncio
    async def test_init_db_invalid_read_replica_url_raises(self) -> None:
        """Test that init_db raises ValueError for invalid read replica URL."""
        import backend.core.database as db_module

        # Save original state
        original_engine = db_module._engine
        original_factory = db_module._async_session_factory
        original_read_engine = db_module._read_engine
        original_read_factory = db_module._read_session_factory
        original_bound_loop = db_module._bound_loop_id

        try:
            # Reset state
            db_module._engine = None
            db_module._async_session_factory = None
            db_module._read_engine = None
            db_module._read_session_factory = None
            db_module._bound_loop_id = None

            mock_engine = MagicMock()
            mock_conn = AsyncMock()

            with (
                patch("backend.core.database.get_settings") as mock_settings,
                patch("backend.core.database.create_async_engine", return_value=mock_engine),
                patch("backend.core.database._setup_pool_event_handlers"),
                patch("backend.core.database.async_sessionmaker"),
            ):
                mock_settings.return_value = MagicMock(
                    database_url="postgresql+asyncpg://localhost/test",
                    database_url_read="mysql://replica/test",  # Invalid format
                    debug=False,
                    database_pool_size=5,
                    database_pool_overflow=10,
                    database_pool_timeout=30,
                    database_pool_recycle=1800,
                    use_pgbouncer=False,
                )

                # Mock engine.begin() context manager
                mock_engine.begin = MagicMock()
                mock_engine.begin.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
                mock_engine.begin.return_value.__aexit__ = AsyncMock(return_value=None)

                # Mock advisory lock query
                mock_conn.execute = AsyncMock()
                mock_result = MagicMock()
                mock_result.scalar.return_value = False
                mock_conn.execute.return_value = mock_result

                with pytest.raises(ValueError) as exc_info:
                    await db_module.init_db()
                assert "read replica" in str(exc_info.value).lower()
                assert "postgresql+asyncpg://" in str(exc_info.value)
        finally:
            db_module._engine = original_engine
            db_module._async_session_factory = original_factory
            db_module._read_engine = original_read_engine
            db_module._read_session_factory = original_read_factory
            db_module._bound_loop_id = original_bound_loop


# =============================================================================
# Read Replica Cleanup Tests
# =============================================================================


class TestCloseDbReadReplica:
    """Tests for read replica cleanup in close_db."""

    @pytest.mark.asyncio
    async def test_close_db_disposes_read_engine(self) -> None:
        """Test that close_db disposes read replica engine."""
        import backend.core.database as db_module

        # Save original state
        original_engine = db_module._engine
        original_factory = db_module._async_session_factory
        original_read_engine = db_module._read_engine
        original_read_factory = db_module._read_session_factory

        try:
            mock_primary = AsyncMock()
            mock_primary.dispose = AsyncMock()
            mock_read = AsyncMock()
            mock_read.dispose = AsyncMock()

            db_module._engine = mock_primary
            db_module._async_session_factory = MagicMock()
            db_module._read_engine = mock_read
            db_module._read_session_factory = MagicMock()

            await db_module.close_db()

            # Both engines should have been disposed
            mock_primary.dispose.assert_called_once()
            mock_read.dispose.assert_called_once()

            # All globals should be reset
            assert db_module._engine is None
            assert db_module._async_session_factory is None
            assert db_module._read_engine is None
            assert db_module._read_session_factory is None
        finally:
            db_module._engine = original_engine
            db_module._async_session_factory = original_factory
            db_module._read_engine = original_read_engine
            db_module._read_session_factory = original_read_factory

    @pytest.mark.asyncio
    async def test_close_db_handles_none_read_engine(self) -> None:
        """Test that close_db handles None read engine gracefully."""
        import backend.core.database as db_module

        # Save original state
        original_engine = db_module._engine
        original_factory = db_module._async_session_factory
        original_read_engine = db_module._read_engine
        original_read_factory = db_module._read_session_factory

        try:
            mock_primary = AsyncMock()
            mock_primary.dispose = AsyncMock()

            db_module._engine = mock_primary
            db_module._async_session_factory = MagicMock()
            db_module._read_engine = None
            db_module._read_session_factory = None

            # Should not raise
            await db_module.close_db()

            # Primary engine should have been disposed
            mock_primary.dispose.assert_called_once()

            # All globals should be reset
            assert db_module._engine is None
            assert db_module._async_session_factory is None
            assert db_module._read_engine is None
            assert db_module._read_session_factory is None
        finally:
            db_module._engine = original_engine
            db_module._async_session_factory = original_factory
            db_module._read_engine = original_read_engine
            db_module._read_session_factory = original_read_factory


# =============================================================================
# get_read_db Fallback Tests
# =============================================================================


class TestGetReadDbFallback:
    """Tests for get_read_db fallback to primary database."""

    @pytest.mark.asyncio
    async def test_get_read_db_uses_read_factory_when_available(self) -> None:
        """Test that get_read_db uses read replica session factory when configured."""
        import backend.core.database as db_module

        # Save original state
        original_engine = db_module._engine
        original_factory = db_module._async_session_factory
        original_read_engine = db_module._read_engine
        original_read_factory = db_module._read_session_factory
        original_bound_loop = db_module._bound_loop_id

        try:
            # Set up mock sessions
            mock_primary_session = AsyncMock()
            mock_primary_session.commit = AsyncMock()
            mock_primary_session.close = AsyncMock()

            mock_read_session = AsyncMock()
            mock_read_session.commit = AsyncMock()
            mock_read_session.close = AsyncMock()

            # Create async context manager mocks that return sessions
            mock_primary_ctx = AsyncMock()
            mock_primary_ctx.__aenter__ = AsyncMock(return_value=mock_primary_session)
            mock_primary_ctx.__aexit__ = AsyncMock(return_value=None)
            mock_primary_factory = MagicMock(return_value=mock_primary_ctx)

            mock_read_ctx = AsyncMock()
            mock_read_ctx.__aenter__ = AsyncMock(return_value=mock_read_session)
            mock_read_ctx.__aexit__ = AsyncMock(return_value=None)
            mock_read_factory = MagicMock(return_value=mock_read_ctx)

            db_module._engine = MagicMock()
            db_module._async_session_factory = mock_primary_factory
            db_module._read_engine = MagicMock()
            db_module._read_session_factory = mock_read_factory
            db_module._bound_loop_id = None

            with patch("backend.core.database._check_loop_mismatch", return_value=False):
                # Call get_read_db and consume the generator
                gen = db_module.get_read_db()
                session = await gen.__anext__()

                # Should use read session, not primary
                assert session is mock_read_session
                assert session is not mock_primary_session
        finally:
            db_module._engine = original_engine
            db_module._async_session_factory = original_factory
            db_module._read_engine = original_read_engine
            db_module._read_session_factory = original_read_factory
            db_module._bound_loop_id = original_bound_loop

    @pytest.mark.asyncio
    async def test_get_read_db_falls_back_to_primary_when_not_configured(self) -> None:
        """Test that get_read_db falls back to primary when read replica not set."""
        import backend.core.database as db_module

        # Save original state
        original_engine = db_module._engine
        original_factory = db_module._async_session_factory
        original_read_engine = db_module._read_engine
        original_read_factory = db_module._read_session_factory
        original_bound_loop = db_module._bound_loop_id

        try:
            # Set up mock primary session
            mock_primary_session = AsyncMock()
            mock_primary_session.commit = AsyncMock()
            mock_primary_session.close = AsyncMock()

            # Create async context manager mock that returns the session
            mock_primary_ctx = AsyncMock()
            mock_primary_ctx.__aenter__ = AsyncMock(return_value=mock_primary_session)
            mock_primary_ctx.__aexit__ = AsyncMock(return_value=None)
            mock_primary_factory = MagicMock(return_value=mock_primary_ctx)

            db_module._engine = MagicMock()
            db_module._async_session_factory = mock_primary_factory
            db_module._read_engine = None
            db_module._read_session_factory = None
            db_module._bound_loop_id = None

            with patch("backend.core.database._check_loop_mismatch", return_value=False):
                # Call get_read_db and consume the generator
                gen = db_module.get_read_db()
                session = await gen.__anext__()

                # Should use primary session as fallback
                assert session is mock_primary_session
        finally:
            db_module._engine = original_engine
            db_module._async_session_factory = original_factory
            db_module._read_engine = original_read_engine
            db_module._read_session_factory = original_read_factory
            db_module._bound_loop_id = original_bound_loop
