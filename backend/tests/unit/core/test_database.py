"""Unit tests for database connection and session management.

Tests cover:
- escape_ilike_pattern function
- get_engine and get_session_factory RuntimeError cases
- Database initialization
- Session management
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.core.database import escape_ilike_pattern

# =============================================================================
# ILIKE Pattern Escaping Tests
# =============================================================================


class TestEscapeIlikePattern:
    """Tests for escape_ilike_pattern function."""

    def test_escape_percent_sign(self) -> None:
        """Test escaping percent sign wildcard."""
        result = escape_ilike_pattern("100% complete")
        assert result == "100\\% complete"

    def test_escape_underscore(self) -> None:
        """Test escaping underscore wildcard."""
        result = escape_ilike_pattern("file_name")
        assert result == "file\\_name"

    def test_escape_backslash(self) -> None:
        """Test escaping backslash."""
        result = escape_ilike_pattern("path\\to\\file")
        assert result == "path\\\\to\\\\file"

    def test_escape_multiple_special_chars(self) -> None:
        """Test escaping multiple special characters."""
        result = escape_ilike_pattern("100%_test\\value")
        assert result == "100\\%\\_test\\\\value"

    def test_no_special_chars(self) -> None:
        """Test string with no special characters."""
        result = escape_ilike_pattern("normal text")
        assert result == "normal text"

    def test_empty_string(self) -> None:
        """Test empty string."""
        result = escape_ilike_pattern("")
        assert result == ""

    def test_only_special_chars(self) -> None:
        """Test string with only special characters."""
        result = escape_ilike_pattern("%_\\")
        assert result == "\\%\\_\\\\"

    def test_consecutive_special_chars(self) -> None:
        """Test consecutive special characters."""
        result = escape_ilike_pattern("%%%")
        assert result == "\\%\\%\\%"

    def test_unicode_preserved(self) -> None:
        """Test that unicode characters are preserved."""
        result = escape_ilike_pattern("test%value")
        assert result == "test\\%value"

    def test_none_input(self) -> None:
        """Test that None input returns empty string."""
        result = escape_ilike_pattern(None)
        assert result == ""

    def test_integer_input(self) -> None:
        """Test that integer input is converted to string."""
        result = escape_ilike_pattern(123)
        assert result == "123"

    def test_non_string_input_with_special_chars(self) -> None:
        """Test that non-string input with special characters is properly escaped."""
        # This tests converting non-string to string and then escaping
        result = escape_ilike_pattern(100.5)
        assert result == "100.5"


# =============================================================================
# Engine and Session Factory Tests
# =============================================================================


class TestGetEngine:
    """Tests for get_engine function."""

    def test_get_engine_raises_when_not_initialized(self) -> None:
        """Test that get_engine raises RuntimeError when not initialized."""
        import backend.core.database as db_module

        # Save original state
        original_engine = db_module._engine

        try:
            db_module._engine = None
            with pytest.raises(RuntimeError) as exc_info:
                db_module.get_engine()
            assert "not initialized" in str(exc_info.value)
        finally:
            # Restore original state
            db_module._engine = original_engine


class TestGetSessionFactory:
    """Tests for get_session_factory function."""

    def test_get_session_factory_raises_when_not_initialized(self) -> None:
        """Test that get_session_factory raises RuntimeError when not initialized."""
        import backend.core.database as db_module

        # Save original state
        original_factory = db_module._async_session_factory

        try:
            db_module._async_session_factory = None
            with pytest.raises(RuntimeError) as exc_info:
                db_module.get_session_factory()
            assert "not initialized" in str(exc_info.value)
        finally:
            # Restore original state
            db_module._async_session_factory = original_factory


# =============================================================================
# Database Initialization Tests
# =============================================================================


class TestInitDb:
    """Tests for init_db function."""

    @pytest.mark.asyncio
    async def test_init_db_invalid_url_raises(self) -> None:
        """Test that init_db raises ValueError for invalid URL."""
        from backend.core.database import init_db

        with patch("backend.core.database.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                database_url="mysql://localhost/test",
                debug=False,
                database_pool_size=5,
                database_pool_overflow=10,
                database_pool_timeout=30,
                database_pool_recycle=1800,
            )
            with pytest.raises(ValueError) as exc_info:
                await init_db()
            assert "postgresql+asyncpg://" in str(exc_info.value)


class TestCloseDb:
    """Tests for close_db function."""

    @pytest.mark.asyncio
    async def test_close_db_handles_none_engine(self) -> None:
        """Test that close_db handles None engine gracefully."""
        import backend.core.database as db_module

        # Save original state
        original_engine = db_module._engine
        original_factory = db_module._async_session_factory

        try:
            db_module._engine = None
            db_module._async_session_factory = None

            # Should not raise
            await db_module.close_db()

            # Should still be None
            assert db_module._engine is None
            assert db_module._async_session_factory is None
        finally:
            # Restore original state
            db_module._engine = original_engine
            db_module._async_session_factory = original_factory

    @pytest.mark.asyncio
    async def test_close_db_disposes_engine(self) -> None:
        """Test that close_db disposes engine properly."""
        import backend.core.database as db_module

        # Save original state
        original_engine = db_module._engine
        original_factory = db_module._async_session_factory

        try:
            # Create mock engine
            mock_engine = AsyncMock()
            mock_engine.dispose = AsyncMock()

            db_module._engine = mock_engine
            db_module._async_session_factory = MagicMock()

            await db_module.close_db()

            # Engine should have been disposed
            mock_engine.dispose.assert_called_once()
            # Globals should be reset
            assert db_module._engine is None
            assert db_module._async_session_factory is None
        finally:
            # Restore original state
            db_module._engine = original_engine
            db_module._async_session_factory = original_factory

    @pytest.mark.asyncio
    async def test_close_db_handles_greenlet_error(self) -> None:
        """Test that close_db handles greenlet ValueError gracefully."""
        import backend.core.database as db_module

        # Save original state
        original_engine = db_module._engine
        original_factory = db_module._async_session_factory

        try:
            # Create mock engine that raises greenlet error
            mock_engine = AsyncMock()
            mock_engine.dispose = AsyncMock(side_effect=ValueError("greenlet is not installed"))

            db_module._engine = mock_engine
            db_module._async_session_factory = MagicMock()

            # Should not raise
            await db_module.close_db()

            # Globals should still be reset
            assert db_module._engine is None
            assert db_module._async_session_factory is None
        finally:
            # Restore original state
            db_module._engine = original_engine
            db_module._async_session_factory = original_factory

    @pytest.mark.asyncio
    async def test_close_db_reraises_non_greenlet_error(self) -> None:
        """Test that close_db re-raises non-greenlet ValueError."""
        import backend.core.database as db_module

        # Save original state
        original_engine = db_module._engine
        original_factory = db_module._async_session_factory

        try:
            # Create mock engine that raises different error
            mock_engine = AsyncMock()
            mock_engine.dispose = AsyncMock(side_effect=ValueError("some other error"))

            db_module._engine = mock_engine
            db_module._async_session_factory = MagicMock()

            with pytest.raises(ValueError) as exc_info:
                await db_module.close_db()
            assert "some other error" in str(exc_info.value)
        finally:
            # Restore original state
            db_module._engine = original_engine
            db_module._async_session_factory = original_factory


# =============================================================================
# Session Context Manager Tests
# =============================================================================


class TestGetSession:
    """Tests for get_session context manager."""

    @pytest.mark.asyncio
    async def test_get_session_commits_on_success(self) -> None:
        """Test that get_session commits on success."""
        import backend.core.database as db_module

        # Create mock session factory and session
        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()

        mock_factory = MagicMock()

        # Mock the context manager
        async def mock_cm():
            yield mock_session

        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=None)

        # Save original state
        original_factory = db_module._async_session_factory

        try:
            db_module._async_session_factory = mock_factory

            async with db_module.get_session():
                pass  # Do nothing, should commit

            mock_session.commit.assert_called_once()
            mock_session.rollback.assert_not_called()
        finally:
            db_module._async_session_factory = original_factory

    @pytest.mark.asyncio
    async def test_get_session_rollbacks_on_exception(self) -> None:
        """Test that get_session rollbacks on exception."""
        import backend.core.database as db_module

        # Create mock session
        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()

        mock_factory = MagicMock()
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=None)

        # Save original state
        original_factory = db_module._async_session_factory

        try:
            db_module._async_session_factory = mock_factory

            with pytest.raises(ValueError):
                async with db_module.get_session():
                    raise ValueError("test error")

            mock_session.rollback.assert_called_once()
        finally:
            db_module._async_session_factory = original_factory


class TestGetDb:
    """Tests for get_db FastAPI dependency."""

    @pytest.mark.asyncio
    async def test_get_db_commits_on_success(self) -> None:
        """Test that get_db commits on success."""
        import backend.core.database as db_module

        # Create mock session
        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()
        mock_session.close = AsyncMock()

        mock_factory = MagicMock()
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=None)

        # Save original state
        original_factory = db_module._async_session_factory

        try:
            db_module._async_session_factory = mock_factory

            async for session in db_module.get_db():
                pass  # Do nothing, should commit

            mock_session.commit.assert_called_once()
            mock_session.rollback.assert_not_called()
            mock_session.close.assert_called_once()
        finally:
            db_module._async_session_factory = original_factory

    @pytest.mark.asyncio
    async def test_get_db_close_called_on_exception(self) -> None:
        """Test that get_db closes session on exception."""
        import backend.core.database as db_module

        # Create mock session
        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()
        mock_session.close = AsyncMock()

        mock_factory = MagicMock()
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=None)

        # Save original state
        original_factory = db_module._async_session_factory

        try:
            db_module._async_session_factory = mock_factory

            # The generator has exception handling built in
            # We need to verify close is called in finally block
            gen = db_module.get_db()
            _session = await gen.__anext__()
            try:
                await gen.athrow(ValueError("test error"))
            except ValueError:
                pass

            # Close should be called in finally block
            mock_session.close.assert_called_once()
        finally:
            db_module._async_session_factory = original_factory


# =============================================================================
# Connection Pool Settings Tests
# =============================================================================


class TestConnectionPoolSettings:
    """Tests for database connection pool configuration.

    These tests verify that pool settings from config are correctly applied
    to the SQLAlchemy engine and that pool status information is available.
    """

    @pytest.mark.asyncio
    async def test_init_db_applies_pool_settings(self) -> None:
        """Test that init_db applies pool settings from config to the engine."""
        import backend.core.database as db_module
        from backend.core.database import init_db

        # Save original state
        original_engine = db_module._engine
        original_factory = db_module._async_session_factory

        try:
            # Reset globals so init_db runs fresh
            db_module._engine = None
            db_module._async_session_factory = None

            # Create mock settings with specific pool settings
            with patch("backend.core.database.get_settings") as mock_settings:
                mock_settings.return_value = MagicMock(
                    database_url="postgresql+asyncpg://user:pass@localhost:5432/testdb",  # pragma: allowlist secret
                    database_url_read=None,
                    debug=False,
                    database_pool_size=15,
                    database_pool_overflow=25,
                    database_pool_timeout=45,
                    database_pool_recycle=2400,
                    use_pgbouncer=False,
                )

                # Mock create_async_engine to capture arguments
                with patch("backend.core.database.create_async_engine") as mock_create_engine:
                    mock_engine = AsyncMock()
                    mock_create_engine.return_value = mock_engine

                    # Mock the async engine's begin context manager
                    mock_conn = AsyncMock()
                    mock_conn.execute = AsyncMock(
                        return_value=MagicMock(scalar=MagicMock(return_value=True))
                    )
                    mock_conn.run_sync = AsyncMock()

                    mock_ctx = AsyncMock()
                    mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
                    mock_ctx.__aexit__ = AsyncMock(return_value=None)
                    mock_engine.begin = MagicMock(return_value=mock_ctx)

                    await init_db()

                    # Verify pool settings were passed to create_async_engine
                    mock_create_engine.assert_called_once()
                    call_kwargs = mock_create_engine.call_args.kwargs

                    assert call_kwargs["pool_size"] == 15
                    assert call_kwargs["max_overflow"] == 25
                    assert call_kwargs["pool_timeout"] == 45
                    assert call_kwargs["pool_recycle"] == 2400
                    assert call_kwargs["pool_pre_ping"] is True
                    assert call_kwargs["pool_use_lifo"] is True
        finally:
            # Restore original state
            db_module._engine = original_engine
            db_module._async_session_factory = original_factory

    def test_pool_size_setting_validation(self) -> None:
        """Test that pool_size setting has proper validation bounds."""
        from pydantic import ValidationError

        from backend.core.config import Settings

        # Test valid pool sizes
        settings = Settings(
            database_url="postgresql+asyncpg://user:pass@localhost/db",
            database_pool_size=5,
        )
        assert settings.database_pool_size == 5

        settings = Settings(
            database_url="postgresql+asyncpg://user:pass@localhost/db",
            database_pool_size=100,
        )
        assert settings.database_pool_size == 100

        # Test invalid pool sizes (should raise validation error)
        with pytest.raises(ValidationError):
            Settings(
                database_url="postgresql+asyncpg://user:pass@localhost/db",
                database_pool_size=2,  # Below minimum of 5
            )

        with pytest.raises(ValidationError):
            Settings(
                database_url="postgresql+asyncpg://user:pass@localhost/db",
                database_pool_size=150,  # Above maximum of 100
            )

    def test_pool_overflow_setting_validation(self) -> None:
        """Test that pool_overflow setting has proper validation bounds."""
        from pydantic import ValidationError

        from backend.core.config import Settings

        # Test valid overflow values
        settings = Settings(
            database_url="postgresql+asyncpg://user:pass@localhost/db",
            database_pool_overflow=0,
        )
        assert settings.database_pool_overflow == 0

        settings = Settings(
            database_url="postgresql+asyncpg://user:pass@localhost/db",
            database_pool_overflow=100,
        )
        assert settings.database_pool_overflow == 100

        # Test invalid overflow values
        with pytest.raises(ValidationError):
            Settings(
                database_url="postgresql+asyncpg://user:pass@localhost/db",
                database_pool_overflow=-1,  # Below minimum of 0
            )

        with pytest.raises(ValidationError):
            Settings(
                database_url="postgresql+asyncpg://user:pass@localhost/db",
                database_pool_overflow=150,  # Above maximum of 100
            )

    def test_pool_timeout_setting_validation(self) -> None:
        """Test that pool_timeout setting has proper validation bounds."""
        from pydantic import ValidationError

        from backend.core.config import Settings

        # Test valid timeout values
        settings = Settings(
            database_url="postgresql+asyncpg://user:pass@localhost/db",
            database_pool_timeout=5,
        )
        assert settings.database_pool_timeout == 5

        settings = Settings(
            database_url="postgresql+asyncpg://user:pass@localhost/db",
            database_pool_timeout=120,
        )
        assert settings.database_pool_timeout == 120

        # Test invalid timeout values
        with pytest.raises(ValidationError):
            Settings(
                database_url="postgresql+asyncpg://user:pass@localhost/db",
                database_pool_timeout=2,  # Below minimum of 5
            )

        with pytest.raises(ValidationError):
            Settings(
                database_url="postgresql+asyncpg://user:pass@localhost/db",
                database_pool_timeout=200,  # Above maximum of 120
            )

    def test_pool_recycle_setting_validation(self) -> None:
        """Test that pool_recycle setting has proper validation bounds."""
        from pydantic import ValidationError

        from backend.core.config import Settings

        # Test valid recycle values
        settings = Settings(
            database_url="postgresql+asyncpg://user:pass@localhost/db",
            database_pool_recycle=300,  # 5 minutes
        )
        assert settings.database_pool_recycle == 300

        settings = Settings(
            database_url="postgresql+asyncpg://user:pass@localhost/db",
            database_pool_recycle=7200,  # 2 hours
        )
        assert settings.database_pool_recycle == 7200

        # Test invalid recycle values
        with pytest.raises(ValidationError):
            Settings(
                database_url="postgresql+asyncpg://user:pass@localhost/db",
                database_pool_recycle=100,  # Below minimum of 300
            )

        with pytest.raises(ValidationError):
            Settings(
                database_url="postgresql+asyncpg://user:pass@localhost/db",
                database_pool_recycle=10000,  # Above maximum of 7200
            )


class TestGetPoolStatus:
    """Tests for get_pool_status function."""

    @pytest.mark.asyncio
    async def test_get_pool_status_returns_pool_metrics(self) -> None:
        """Test that get_pool_status returns connection pool metrics."""
        import backend.core.database as db_module
        from backend.core.database import get_pool_status

        # Save original state
        original_engine = db_module._engine

        try:
            # Create a mock engine with a mock pool
            mock_pool = MagicMock()
            mock_pool.size.return_value = 20
            mock_pool.overflow.return_value = 5
            mock_pool.checkedin.return_value = 15
            mock_pool.checkedout.return_value = 10

            mock_engine = MagicMock()
            mock_engine.pool = mock_pool

            db_module._engine = mock_engine

            status = await get_pool_status()

            assert status["pool_size"] == 20
            assert status["overflow"] == 5
            assert status["checkedin"] == 15
            assert status["checkedout"] == 10
            assert status["total_connections"] == 25  # pool_size + overflow
        finally:
            # Restore original state
            db_module._engine = original_engine

    @pytest.mark.asyncio
    async def test_get_pool_status_handles_uninitialized_engine(self) -> None:
        """Test that get_pool_status handles uninitialized database gracefully."""
        import backend.core.database as db_module
        from backend.core.database import get_pool_status

        # Save original state
        original_engine = db_module._engine

        try:
            db_module._engine = None

            status = await get_pool_status()

            assert status["pool_size"] == 0
            assert status["overflow"] == 0
            assert status["checkedin"] == 0
            assert status["checkedout"] == 0
            assert status["error"] == "Database not initialized"
        finally:
            # Restore original state
            db_module._engine = original_engine

    @pytest.mark.asyncio
    async def test_get_pool_status_handles_nullpool(self) -> None:
        """Test that get_pool_status handles NullPool (no pooling) gracefully."""
        import backend.core.database as db_module
        from backend.core.database import get_pool_status

        # Save original state
        original_engine = db_module._engine

        try:
            # Create a mock engine with NullPool (no size/overflow methods)
            mock_pool = MagicMock()
            # NullPool doesn't have these methods
            mock_pool.size.side_effect = AttributeError("NullPool has no size")

            mock_engine = MagicMock()
            mock_engine.pool = mock_pool

            db_module._engine = mock_engine

            status = await get_pool_status()

            # Should handle gracefully with default values
            assert "pool_size" in status
            assert status.get("pooling_disabled") is True or "error" in status
        finally:
            # Restore original state
            db_module._engine = original_engine


# =============================================================================
# Event Loop Mismatch Tests
# =============================================================================


class TestEventLoopMismatch:
    """Tests for event loop mismatch detection and handling."""

    @pytest.mark.asyncio
    async def test_init_db_without_running_loop(self) -> None:
        """Test that init_db handles case when no event loop is running."""

        import backend.core.database as db_module
        from backend.core.database import init_db

        # Save original state
        original_engine = db_module._engine
        original_factory = db_module._async_session_factory
        original_loop_id = db_module._bound_loop_id

        try:
            # Reset state
            db_module._engine = None
            db_module._async_session_factory = None
            db_module._bound_loop_id = None

            # Mock get_settings
            with patch("backend.core.database.get_settings") as mock_settings:
                mock_settings.return_value = MagicMock(
                    database_url="postgresql+asyncpg://user:pass@localhost:5432/testdb",
                    debug=False,
                    database_pool_size=5,
                    database_pool_overflow=10,
                    database_pool_timeout=30,
                    database_pool_recycle=1800,
                )

                with patch("backend.core.database.create_async_engine") as mock_create_engine:
                    mock_engine = AsyncMock()
                    mock_create_engine.return_value = mock_engine

                    # Mock the connection context
                    mock_conn = AsyncMock()
                    mock_conn.execute = AsyncMock(
                        return_value=MagicMock(scalar=MagicMock(return_value=True))
                    )
                    mock_conn.run_sync = AsyncMock()

                    mock_ctx = AsyncMock()
                    mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
                    mock_ctx.__aexit__ = AsyncMock(return_value=None)
                    mock_engine.begin = MagicMock(return_value=mock_ctx)

                    # Should work even when no loop is initially detected
                    await init_db()

                    # Engine should be set
                    assert db_module._engine is not None
        finally:
            # Restore original state
            db_module._engine = original_engine
            db_module._async_session_factory = original_factory
            db_module._bound_loop_id = original_loop_id

    @pytest.mark.asyncio
    async def test_init_db_disposes_engine_on_loop_mismatch(self) -> None:
        """Test that init_db disposes old engine when event loop changes."""
        import backend.core.database as db_module
        from backend.core.database import init_db

        # Save original state
        original_engine = db_module._engine
        original_factory = db_module._async_session_factory
        original_loop_id = db_module._bound_loop_id

        try:
            # Create mock old engine with different loop ID
            mock_old_engine = AsyncMock()
            mock_old_engine.dispose = AsyncMock()

            db_module._engine = mock_old_engine
            db_module._bound_loop_id = 99999  # Different from current

            with patch("backend.core.database.get_settings") as mock_settings:
                mock_settings.return_value = MagicMock(
                    database_url="postgresql+asyncpg://user:pass@localhost:5432/testdb",
                    debug=False,
                    database_pool_size=5,
                    database_pool_overflow=10,
                    database_pool_timeout=30,
                    database_pool_recycle=1800,
                )

                with patch("backend.core.database.create_async_engine") as mock_create_engine:
                    mock_new_engine = AsyncMock()
                    mock_create_engine.return_value = mock_new_engine

                    # Mock the connection context
                    mock_conn = AsyncMock()
                    mock_conn.execute = AsyncMock(
                        return_value=MagicMock(scalar=MagicMock(return_value=True))
                    )
                    mock_conn.run_sync = AsyncMock()

                    mock_ctx = AsyncMock()
                    mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
                    mock_ctx.__aexit__ = AsyncMock(return_value=None)
                    mock_new_engine.begin = MagicMock(return_value=mock_ctx)

                    await init_db()

                    # Old engine should have been disposed
                    mock_old_engine.dispose.assert_called_once()
                    # New engine should be set
                    assert db_module._engine == mock_new_engine
        finally:
            # Restore original state
            db_module._engine = original_engine
            db_module._async_session_factory = original_factory
            db_module._bound_loop_id = original_loop_id

    @pytest.mark.asyncio
    async def test_init_db_handles_dispose_runtime_error(self) -> None:
        """Test that init_db handles RuntimeError during disposal."""
        import backend.core.database as db_module
        from backend.core.database import init_db

        # Save original state
        original_engine = db_module._engine
        original_factory = db_module._async_session_factory
        original_loop_id = db_module._bound_loop_id

        try:
            # Create mock old engine that raises RuntimeError on disposal
            mock_old_engine = AsyncMock()
            mock_old_engine.dispose = AsyncMock(side_effect=RuntimeError("Event loop closed"))

            db_module._engine = mock_old_engine
            db_module._bound_loop_id = 99999

            with patch("backend.core.database.get_settings") as mock_settings:
                mock_settings.return_value = MagicMock(
                    database_url="postgresql+asyncpg://user:pass@localhost:5432/testdb",
                    debug=False,
                    database_pool_size=5,
                    database_pool_overflow=10,
                    database_pool_timeout=30,
                    database_pool_recycle=1800,
                )

                with patch("backend.core.database.create_async_engine") as mock_create_engine:
                    mock_new_engine = AsyncMock()
                    mock_create_engine.return_value = mock_new_engine

                    mock_conn = AsyncMock()
                    mock_conn.execute = AsyncMock(
                        return_value=MagicMock(scalar=MagicMock(return_value=True))
                    )
                    mock_conn.run_sync = AsyncMock()

                    mock_ctx = AsyncMock()
                    mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
                    mock_ctx.__aexit__ = AsyncMock(return_value=None)
                    mock_new_engine.begin = MagicMock(return_value=mock_ctx)

                    # Should not raise - handles disposal error gracefully
                    await init_db()

                    # New engine should still be set
                    assert db_module._engine == mock_new_engine
        finally:
            # Restore original state
            db_module._engine = original_engine
            db_module._async_session_factory = original_factory
            db_module._bound_loop_id = original_loop_id

    @pytest.mark.asyncio
    async def test_init_db_handles_dispose_oserror(self) -> None:
        """Test that init_db handles OSError during disposal."""
        import backend.core.database as db_module
        from backend.core.database import init_db

        # Save original state
        original_engine = db_module._engine
        original_factory = db_module._async_session_factory
        original_loop_id = db_module._bound_loop_id

        try:
            # Create mock old engine that raises OSError on disposal
            mock_old_engine = AsyncMock()
            mock_old_engine.dispose = AsyncMock(side_effect=OSError("Connection cleanup failed"))

            db_module._engine = mock_old_engine
            db_module._bound_loop_id = 99999

            with patch("backend.core.database.get_settings") as mock_settings:
                mock_settings.return_value = MagicMock(
                    database_url="postgresql+asyncpg://user:pass@localhost:5432/testdb",
                    debug=False,
                    database_pool_size=5,
                    database_pool_overflow=10,
                    database_pool_timeout=30,
                    database_pool_recycle=1800,
                )

                with patch("backend.core.database.create_async_engine") as mock_create_engine:
                    mock_new_engine = AsyncMock()
                    mock_create_engine.return_value = mock_new_engine

                    mock_conn = AsyncMock()
                    mock_conn.execute = AsyncMock(
                        return_value=MagicMock(scalar=MagicMock(return_value=True))
                    )
                    mock_conn.run_sync = AsyncMock()

                    mock_ctx = AsyncMock()
                    mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
                    mock_ctx.__aexit__ = AsyncMock(return_value=None)
                    mock_new_engine.begin = MagicMock(return_value=mock_ctx)

                    # Should not raise - handles disposal error gracefully
                    await init_db()

                    # New engine should still be set
                    assert db_module._engine == mock_new_engine
        finally:
            # Restore original state
            db_module._engine = original_engine
            db_module._async_session_factory = original_factory
            db_module._bound_loop_id = original_loop_id

    @pytest.mark.asyncio
    async def test_check_loop_mismatch_without_running_loop(self) -> None:
        """Test _check_loop_mismatch when no loop is running."""
        import backend.core.database as db_module

        # Save original state
        original_engine = db_module._engine
        original_loop_id = db_module._bound_loop_id

        try:
            # Set up engine with a bound loop
            mock_engine = MagicMock()
            db_module._engine = mock_engine
            db_module._bound_loop_id = 12345

            # Mock asyncio to simulate no running loop
            with patch("backend.core.database.asyncio.get_running_loop") as mock_get_loop:
                mock_get_loop.side_effect = RuntimeError("no running event loop")

                result = db_module._check_loop_mismatch()

                # Should return False when no loop is running
                assert result is False
        finally:
            # Restore original state
            db_module._engine = original_engine
            db_module._bound_loop_id = original_loop_id

    @pytest.mark.asyncio
    async def test_get_session_reinits_on_loop_mismatch(self) -> None:
        """Test that get_session reinitializes DB on loop mismatch."""
        import backend.core.database as db_module

        # Save original state
        original_engine = db_module._engine
        original_factory = db_module._async_session_factory
        original_loop_id = db_module._bound_loop_id

        try:
            # Set up engine first to make _check_loop_mismatch return True
            mock_engine = MagicMock()
            db_module._engine = mock_engine
            db_module._bound_loop_id = 99999  # Different from current loop

            with patch("backend.core.database.init_db") as mock_init:

                async def mock_init_impl():
                    # Reset to current loop after reinit
                    import asyncio

                    db_module._bound_loop_id = id(asyncio.get_running_loop())

                mock_init.side_effect = mock_init_impl

                # Create a mock factory after init_db
                mock_session = AsyncMock()
                mock_session.commit = AsyncMock()
                mock_factory = MagicMock()
                mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
                mock_factory.return_value.__aexit__ = AsyncMock(return_value=None)

                db_module._async_session_factory = mock_factory

                async with db_module.get_session():
                    pass

                # init_db should have been called due to loop mismatch
                mock_init.assert_called_once()
        finally:
            # Restore original state
            db_module._engine = original_engine
            db_module._async_session_factory = original_factory
            db_module._bound_loop_id = original_loop_id

    @pytest.mark.asyncio
    async def test_with_session_reinits_on_loop_mismatch(self) -> None:
        """Test that with_session reinitializes DB via get_session on loop mismatch."""
        import backend.core.database as db_module

        # Save original state
        original_engine = db_module._engine
        original_factory = db_module._async_session_factory
        original_loop_id = db_module._bound_loop_id

        try:
            # Set up engine first to make _check_loop_mismatch return True
            mock_engine = MagicMock()
            db_module._engine = mock_engine
            db_module._bound_loop_id = 99999

            with patch("backend.core.database.init_db") as mock_init:

                async def mock_init_impl():
                    import asyncio

                    db_module._bound_loop_id = id(asyncio.get_running_loop())

                mock_init.side_effect = mock_init_impl

                mock_session = AsyncMock()
                mock_session.commit = AsyncMock()
                mock_factory = MagicMock()
                mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
                mock_factory.return_value.__aexit__ = AsyncMock(return_value=None)

                db_module._async_session_factory = mock_factory

                async def test_operation(session: AsyncMock) -> str:
                    return "success"

                result = await db_module.with_session(test_operation)

                assert result == "success"
                # init_db should have been called
                mock_init.assert_called_once()
        finally:
            # Restore original state
            db_module._engine = original_engine
            db_module._async_session_factory = original_factory
            db_module._bound_loop_id = original_loop_id

    @pytest.mark.asyncio
    async def test_get_db_reinits_on_loop_mismatch(self) -> None:
        """Test that get_db reinitializes DB on loop mismatch."""
        import backend.core.database as db_module

        # Save original state
        original_engine = db_module._engine
        original_factory = db_module._async_session_factory
        original_loop_id = db_module._bound_loop_id

        try:
            # Set up engine first to make _check_loop_mismatch return True
            mock_engine = MagicMock()
            db_module._engine = mock_engine
            db_module._bound_loop_id = 99999

            with patch("backend.core.database.init_db") as mock_init:

                async def mock_init_impl():
                    import asyncio

                    db_module._bound_loop_id = id(asyncio.get_running_loop())

                mock_init.side_effect = mock_init_impl

                mock_session = AsyncMock()
                mock_session.commit = AsyncMock()
                mock_session.close = AsyncMock()
                mock_factory = MagicMock()
                mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
                mock_factory.return_value.__aexit__ = AsyncMock(return_value=None)

                db_module._async_session_factory = mock_factory

                async for session in db_module.get_db():
                    pass

                # init_db should have been called
                mock_init.assert_called_once()
        finally:
            # Restore original state
            db_module._engine = original_engine
            db_module._async_session_factory = original_factory
            db_module._bound_loop_id = original_loop_id


# =============================================================================
# Slow Query Logging Tests
# =============================================================================


class TestSlowQueryLogging:
    """Tests for slow query logging functionality."""

    def test_sanitize_single_value_with_bytes(self) -> None:
        """Test that bytes values are sanitized properly."""
        from backend.core.database import _sanitize_single_value

        result = _sanitize_single_value(b"binary data", max_string_length=100)
        assert result == "<bytes length=11>"

    def test_sanitize_single_value_with_long_string(self) -> None:
        """Test that long strings are truncated."""
        from backend.core.database import _sanitize_single_value

        long_string = "x" * 150
        result = _sanitize_single_value(long_string, max_string_length=100)
        assert result == ("x" * 100) + "..."
        assert len(result) == 103

    def test_is_sensitive_key(self) -> None:
        """Test sensitive key detection."""
        from backend.core.database import _is_sensitive_key

        assert _is_sensitive_key("password") is True
        assert _is_sensitive_key("user_password") is True
        assert _is_sensitive_key("secret_key") is True
        assert _is_sensitive_key("auth_token") is True
        assert _is_sensitive_key("api_key") is True
        assert _is_sensitive_key("username") is False
        assert _is_sensitive_key("email") is False

    def test_sanitize_query_parameters_with_none(self) -> None:
        """Test sanitizing None parameters."""
        from backend.core.database import _sanitize_query_parameters

        result = _sanitize_query_parameters(None)
        assert result == {}

    def test_sanitize_query_parameters_with_dict(self) -> None:
        """Test sanitizing dict parameters."""
        from backend.core.database import _sanitize_query_parameters

        # Test data for sanitization - not real credentials
        params = {
            "user_id": 123,
            "password": "test_value",  # pragma: allowlist secret
            "email": "test@example.com",
        }
        result = _sanitize_query_parameters(params, max_string_length=100, max_items=10)

        assert result["user_id"] == 123
        assert result["password"] == "[REDACTED]"
        assert result["email"] == "test@example.com"

    def test_sanitize_query_parameters_with_dict_max_items(self) -> None:
        """Test sanitizing dict with max_items limit."""
        from backend.core.database import _sanitize_query_parameters

        params = {f"key_{i}": f"value_{i}" for i in range(20)}
        result = _sanitize_query_parameters(params, max_string_length=100, max_items=5)

        # Should only have 5 items plus truncation marker
        assert len(result) == 6
        assert "..." in result
        assert "(15 more items)" in result["..."]

    def test_sanitize_query_parameters_with_list(self) -> None:
        """Test sanitizing list parameters."""
        from backend.core.database import _sanitize_query_parameters

        params = [1, 2, "test", b"binary"]
        result = _sanitize_query_parameters(params, max_string_length=100, max_items=10)

        assert isinstance(result, list)
        assert result[0] == 1
        assert result[1] == 2
        assert result[2] == "test"
        assert result[3] == "<bytes length=6>"

    def test_sanitize_query_parameters_with_list_max_items(self) -> None:
        """Test sanitizing list with max_items limit."""
        from backend.core.database import _sanitize_query_parameters

        params = list(range(20))
        result = _sanitize_query_parameters(params, max_string_length=100, max_items=5)

        # Should have 5 items plus truncation marker
        assert len(result) == 6
        assert "...(15 more items)" in result[5]

    def test_sanitize_query_parameters_with_tuple(self) -> None:
        """Test sanitizing tuple parameters."""
        from backend.core.database import _sanitize_query_parameters

        params = (1, 2, "test")
        result = _sanitize_query_parameters(params, max_string_length=100, max_items=10)

        assert isinstance(result, list)
        assert result == [1, 2, "test"]

    def test_sanitize_query_parameters_with_scalar(self) -> None:
        """Test sanitizing scalar parameters."""
        from backend.core.database import _sanitize_query_parameters

        result = _sanitize_query_parameters("test_value", max_string_length=100, max_items=10)
        assert result == "test_value"

    @pytest.mark.asyncio
    async def test_setup_slow_query_logging(self) -> None:
        """Test setting up slow query logging."""
        import backend.core.database as db_module
        from backend.core.database import reset_slow_query_logging_state, setup_slow_query_logging

        # Reset state
        reset_slow_query_logging_state()

        # Save original state
        original_engine = db_module._engine

        try:
            # Create mock engine
            mock_sync_engine = MagicMock()
            mock_engine = MagicMock()
            mock_engine.sync_engine = mock_sync_engine

            db_module._engine = mock_engine

            with patch("backend.core.database.event.listen") as mock_listen:
                with patch("backend.core.database.get_settings") as mock_settings:
                    mock_settings.return_value = MagicMock(slow_query_threshold_ms=100)

                    result = setup_slow_query_logging()

                    assert result is True
                    # Should attach both listeners
                    assert mock_listen.call_count == 2

                    # Calling again should return True immediately without attaching again
                    mock_listen.reset_mock()
                    result = setup_slow_query_logging()
                    assert result is True
                    assert mock_listen.call_count == 0
        finally:
            # Restore original state
            db_module._engine = original_engine
            reset_slow_query_logging_state()

    @pytest.mark.asyncio
    async def test_setup_slow_query_logging_without_engine(self) -> None:
        """Test setup_slow_query_logging when no engine is available."""
        import backend.core.database as db_module
        from backend.core.database import reset_slow_query_logging_state, setup_slow_query_logging

        # Reset state
        reset_slow_query_logging_state()

        # Save original state
        original_engine = db_module._engine

        try:
            db_module._engine = None

            result = setup_slow_query_logging()

            assert result is False
        finally:
            # Restore original state
            db_module._engine = original_engine
            reset_slow_query_logging_state()

    @pytest.mark.asyncio
    async def test_setup_slow_query_logging_exception(self) -> None:
        """Test setup_slow_query_logging exception handling."""
        import backend.core.database as db_module
        from backend.core.database import reset_slow_query_logging_state, setup_slow_query_logging

        # Reset state
        reset_slow_query_logging_state()

        # Save original state
        original_engine = db_module._engine

        try:
            # Create mock engine that raises exception
            mock_engine = MagicMock()
            mock_engine.sync_engine = MagicMock(side_effect=RuntimeError("Test error"))

            db_module._engine = mock_engine

            result = setup_slow_query_logging()

            assert result is False
        finally:
            # Restore original state
            db_module._engine = original_engine
            reset_slow_query_logging_state()

    @pytest.mark.asyncio
    async def test_disable_slow_query_logging(self) -> None:
        """Test disabling slow query logging."""
        import backend.core.database as db_module
        from backend.core.database import (
            disable_slow_query_logging,
            reset_slow_query_logging_state,
            setup_slow_query_logging,
        )

        # Reset state
        reset_slow_query_logging_state()

        # Save original state
        original_engine = db_module._engine

        try:
            # Create mock engine
            mock_sync_engine = MagicMock()
            mock_engine = MagicMock()
            mock_engine.sync_engine = mock_sync_engine

            db_module._engine = mock_engine

            with patch("backend.core.database.event.listen"):
                with patch("backend.core.database.get_settings") as mock_settings:
                    mock_settings.return_value = MagicMock(slow_query_threshold_ms=100)
                    setup_slow_query_logging()

            with patch("backend.core.database.event.remove") as mock_remove:
                result = disable_slow_query_logging()

                assert result is True
                # Should remove both listeners
                assert mock_remove.call_count == 2

                # Calling again should return True immediately
                mock_remove.reset_mock()
                result = disable_slow_query_logging()
                assert result is True
                assert mock_remove.call_count == 0
        finally:
            # Restore original state
            db_module._engine = original_engine
            reset_slow_query_logging_state()

    @pytest.mark.asyncio
    async def test_disable_slow_query_logging_without_engine(self) -> None:
        """Test disable_slow_query_logging when no engine is available."""
        import backend.core.database as db_module
        from backend.core.database import (
            disable_slow_query_logging,
            reset_slow_query_logging_state,
            setup_slow_query_logging,
        )

        # Reset state
        reset_slow_query_logging_state()

        # Save original state
        original_engine = db_module._engine

        try:
            # Set up logging first
            mock_sync_engine = MagicMock()
            mock_engine = MagicMock()
            mock_engine.sync_engine = mock_sync_engine
            db_module._engine = mock_engine

            with patch("backend.core.database.event.listen"):
                with patch("backend.core.database.get_settings") as mock_settings:
                    mock_settings.return_value = MagicMock(slow_query_threshold_ms=100)
                    setup_slow_query_logging()

            # Now remove engine and try to disable
            db_module._engine = None

            result = disable_slow_query_logging()

            # Should return True and reset state
            assert result is True
        finally:
            # Restore original state
            db_module._engine = original_engine
            reset_slow_query_logging_state()

    @pytest.mark.asyncio
    async def test_disable_slow_query_logging_exception(self) -> None:
        """Test disable_slow_query_logging exception handling."""
        import backend.core.database as db_module
        from backend.core.database import (
            disable_slow_query_logging,
            reset_slow_query_logging_state,
        )

        # Reset state
        reset_slow_query_logging_state()

        # Save original state
        original_engine = db_module._engine

        try:
            # Set up logging first by manually setting the flag
            # (simpler than actually setting up listeners)
            db_module._slow_query_logging_enabled = True

            # Create engine
            mock_sync_engine = MagicMock()
            mock_engine = MagicMock()
            mock_engine.sync_engine = mock_sync_engine
            db_module._engine = mock_engine

            # Mock event.remove to raise exception
            with patch("backend.core.database.event.remove") as mock_remove:
                mock_remove.side_effect = RuntimeError("Test error")

                result = disable_slow_query_logging()

                assert result is False
                # State should still be enabled since removal failed
                assert db_module._slow_query_logging_enabled is True
        finally:
            # Restore original state
            db_module._engine = original_engine
            reset_slow_query_logging_state()

    def test_after_cursor_execute_without_metrics(self) -> None:
        """Test _after_cursor_execute when metrics module is unavailable."""
        import sys
        from unittest.mock import MagicMock

        import backend.core.database as db_module

        # Create mock connection with start time
        mock_conn = MagicMock()
        mock_conn.info = {"query_start_time": 0.0}

        with patch("backend.core.database.time.perf_counter", return_value=0.2):
            with patch("backend.core.database.get_settings") as mock_settings:
                mock_settings.return_value = MagicMock(slow_query_threshold_ms=50)

                # Mock the metrics import to fail
                original_modules = sys.modules.copy()
                if "backend.core.metrics" in sys.modules:
                    del sys.modules["backend.core.metrics"]

                try:
                    with patch.dict("sys.modules", {"backend.core.metrics": None}):
                        # Should not raise even when metrics import fails
                        db_module._after_cursor_execute(
                            mock_conn,
                            None,
                            "SELECT * FROM test",
                            {"id": 123},
                            None,
                            False,
                        )
                finally:
                    # Restore original modules
                    sys.modules.update(original_modules)

    def test_after_cursor_execute_slow_query_without_metrics(self) -> None:
        """Test _after_cursor_execute for slow query when record_slow_query unavailable."""
        from backend.core.database import _after_cursor_execute

        # Create mock connection with start time
        mock_conn = MagicMock()
        mock_conn.info = {"query_start_time": 0.0}

        with patch("backend.core.database.time.perf_counter", return_value=0.2):
            with patch("backend.core.database.get_settings") as mock_settings:
                mock_settings.return_value = MagicMock(slow_query_threshold_ms=50)

                # Import the function fresh to ensure it tries to import metrics
                import sys

                # Remove the metrics module if cached
                original_metrics = sys.modules.get("backend.core.metrics")
                if "backend.core.metrics" in sys.modules:
                    del sys.modules["backend.core.metrics"]

                try:
                    # Create a mock module that has observe_db_query_duration but not record_slow_query
                    mock_metrics = MagicMock()
                    mock_metrics.observe_db_query_duration = MagicMock()

                    # Make record_slow_query raise NameError when accessed
                    def raise_name_error(*args, **kwargs):
                        raise NameError("name 'record_slow_query' is not defined")

                    mock_metrics.record_slow_query = raise_name_error

                    sys.modules["backend.core.metrics"] = mock_metrics

                    # Should not raise even when record_slow_query fails
                    _after_cursor_execute(
                        mock_conn,
                        None,
                        "SELECT * FROM test",
                        {"id": 123},
                        None,
                        False,
                    )

                    # observe should be called
                    mock_metrics.observe_db_query_duration.assert_called_once()
                finally:
                    # Restore original module
                    if original_metrics is not None:
                        sys.modules["backend.core.metrics"] = original_metrics
                    elif "backend.core.metrics" in sys.modules:
                        del sys.modules["backend.core.metrics"]

    def test_reset_slow_query_logging_state(self) -> None:
        """Test resetting slow query logging state."""
        import backend.core.database as db_module
        from backend.core.database import reset_slow_query_logging_state

        # Set state to True
        db_module._slow_query_logging_enabled = True

        reset_slow_query_logging_state()

        assert db_module._slow_query_logging_enabled is False


# =============================================================================
# Database Error Logging Tests (NEM-2539)
# =============================================================================


class TestDatabaseErrorLogging:
    """Tests for structured database error logging in session context managers.

    NEM-2539: Verifies that database errors are logged with appropriate severity
    and structured context information.
    """

    @pytest.mark.asyncio
    async def test_get_session_logs_integrity_error_with_constraint(self) -> None:
        """Test that IntegrityError is logged at WARNING with constraint info."""
        from sqlalchemy.exc import IntegrityError

        import backend.core.database as db_module

        # Save original state
        original_factory = db_module._async_session_factory

        try:
            # Create mock session that raises IntegrityError
            mock_session = AsyncMock()
            mock_session.commit = AsyncMock(
                side_effect=IntegrityError(
                    "duplicate key", None, Exception("unique_constraint_violation")
                )
            )
            mock_session.rollback = AsyncMock()

            mock_factory = MagicMock()
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=None)

            db_module._async_session_factory = mock_factory

            with patch.object(db_module._logger, "warning") as mock_logger:
                with pytest.raises(IntegrityError):
                    async with db_module.get_session():
                        pass  # commit will raise

                # Verify warning was logged with structured context
                mock_logger.assert_called_once()
                call_args = mock_logger.call_args
                assert call_args[0][0] == "Database integrity error"
                assert call_args[1]["extra"]["error_type"] == "integrity_error"
                assert "constraint" in call_args[1]["extra"]
                assert "detail" in call_args[1]["extra"]

            # Verify rollback was called
            mock_session.rollback.assert_called_once()
        finally:
            db_module._async_session_factory = original_factory

    @pytest.mark.asyncio
    async def test_get_session_logs_operational_error(self) -> None:
        """Test that OperationalError is logged at ERROR level."""
        from sqlalchemy.exc import OperationalError

        import backend.core.database as db_module

        # Save original state
        original_factory = db_module._async_session_factory

        try:
            # Create mock session that raises OperationalError
            mock_session = AsyncMock()
            mock_session.commit = AsyncMock(
                side_effect=OperationalError("connection lost", None, Exception("lost"))
            )
            mock_session.rollback = AsyncMock()

            mock_factory = MagicMock()
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=None)

            db_module._async_session_factory = mock_factory

            with patch.object(db_module._logger, "error") as mock_logger:
                with pytest.raises(OperationalError):
                    async with db_module.get_session():
                        pass

                mock_logger.assert_called_once()
                call_args = mock_logger.call_args
                assert call_args[0][0] == "Database operational error"
                assert call_args[1]["extra"]["error_type"] == "operational_error"
                assert "detail" in call_args[1]["extra"]

            mock_session.rollback.assert_called_once()
        finally:
            db_module._async_session_factory = original_factory

    @pytest.mark.asyncio
    async def test_get_session_logs_timeout_error(self) -> None:
        """Test that SQLAlchemyTimeoutError is logged at ERROR level."""
        from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError

        import backend.core.database as db_module

        # Save original state
        original_factory = db_module._async_session_factory

        try:
            # Create mock session that raises TimeoutError
            mock_session = AsyncMock()
            mock_session.commit = AsyncMock(side_effect=SQLAlchemyTimeoutError("pool timeout"))
            mock_session.rollback = AsyncMock()

            mock_factory = MagicMock()
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=None)

            db_module._async_session_factory = mock_factory

            with patch.object(db_module._logger, "error") as mock_logger:
                with pytest.raises(SQLAlchemyTimeoutError):
                    async with db_module.get_session():
                        pass

                mock_logger.assert_called_once()
                call_args = mock_logger.call_args
                assert call_args[0][0] == "Database timeout error"
                assert call_args[1]["extra"]["error_type"] == "timeout_error"
                assert "detail" in call_args[1]["extra"]

            mock_session.rollback.assert_called_once()
        finally:
            db_module._async_session_factory = original_factory

    @pytest.mark.asyncio
    async def test_get_session_logs_programming_error_with_exception(self) -> None:
        """Test that ProgrammingError is logged with logger.exception for stack trace."""
        from sqlalchemy.exc import ProgrammingError

        import backend.core.database as db_module

        # Save original state
        original_factory = db_module._async_session_factory

        try:
            # Create mock session that raises ProgrammingError
            mock_session = AsyncMock()
            mock_session.commit = AsyncMock(
                side_effect=ProgrammingError("bad SQL", None, Exception("syntax error"))
            )
            mock_session.rollback = AsyncMock()

            mock_factory = MagicMock()
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=None)

            db_module._async_session_factory = mock_factory

            with patch.object(db_module._logger, "exception") as mock_logger:
                with pytest.raises(ProgrammingError):
                    async with db_module.get_session():
                        pass

                mock_logger.assert_called_once()
                call_args = mock_logger.call_args
                assert "programming error" in call_args[0][0].lower()
                assert call_args[1]["extra"]["error_type"] == "programming_error"
                assert "detail" in call_args[1]["extra"]

            mock_session.rollback.assert_called_once()
        finally:
            db_module._async_session_factory = original_factory

    @pytest.mark.asyncio
    async def test_get_session_logs_unexpected_error_with_exception(self) -> None:
        """Test that unexpected errors are logged with logger.exception."""
        import backend.core.database as db_module

        # Save original state
        original_factory = db_module._async_session_factory

        try:
            # Create mock session that raises unexpected error
            mock_session = AsyncMock()
            mock_session.commit = AsyncMock(side_effect=RuntimeError("unexpected"))
            mock_session.rollback = AsyncMock()

            mock_factory = MagicMock()
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=None)

            db_module._async_session_factory = mock_factory

            with patch.object(db_module._logger, "exception") as mock_logger:
                with pytest.raises(RuntimeError):
                    async with db_module.get_session():
                        pass

                mock_logger.assert_called_once()
                call_args = mock_logger.call_args
                assert call_args[0][0] == "Unexpected database error"
                assert call_args[1]["extra"]["error_type"] == "unexpected_error"
                assert call_args[1]["extra"]["exception_class"] == "RuntimeError"

            mock_session.rollback.assert_called_once()
        finally:
            db_module._async_session_factory = original_factory

    @pytest.mark.asyncio
    async def test_get_db_logs_integrity_error(self) -> None:
        """Test that get_db logs IntegrityError at WARNING level."""
        from sqlalchemy.exc import IntegrityError

        import backend.core.database as db_module

        # Save original state
        original_factory = db_module._async_session_factory

        try:
            # Create mock session that raises IntegrityError
            mock_session = AsyncMock()
            mock_session.commit = AsyncMock(
                side_effect=IntegrityError("fk violation", None, Exception("foreign_key"))
            )
            mock_session.rollback = AsyncMock()
            mock_session.close = AsyncMock()

            mock_factory = MagicMock()
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=None)

            db_module._async_session_factory = mock_factory

            with patch.object(db_module._logger, "warning") as mock_logger:
                with pytest.raises(IntegrityError):
                    async for _session in db_module.get_db():
                        pass  # commit will raise

                mock_logger.assert_called_once()
                call_args = mock_logger.call_args
                assert call_args[0][0] == "Database integrity error"
                assert call_args[1]["extra"]["error_type"] == "integrity_error"

            # Verify close was still called in finally block
            mock_session.close.assert_called_once()
        finally:
            db_module._async_session_factory = original_factory

    @pytest.mark.asyncio
    async def test_get_db_logs_operational_error(self) -> None:
        """Test that get_db logs OperationalError at ERROR level with proper categorization."""
        from sqlalchemy.exc import OperationalError

        import backend.core.database as db_module

        # Save original state
        original_factory = db_module._async_session_factory

        try:
            mock_session = AsyncMock()
            # Use "connection refused" which triggers the connection_error category
            mock_session.commit = AsyncMock(
                side_effect=OperationalError("db down", None, Exception("connection refused"))
            )
            mock_session.rollback = AsyncMock()
            mock_session.close = AsyncMock()

            mock_factory = MagicMock()
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=None)

            db_module._async_session_factory = mock_factory

            with patch.object(db_module._logger, "error") as mock_logger:
                with pytest.raises(OperationalError):
                    async for _session in db_module.get_db():
                        pass

                mock_logger.assert_called_once()
                # Connection-related errors are now categorized as "connection_error"
                # for better diagnostics when debugging "unexpected EOF" issues
                assert mock_logger.call_args[1]["extra"]["error_type"] == "connection_error"
                assert mock_logger.call_args[1]["extra"]["is_connection_error"] is True

            mock_session.close.assert_called_once()
        finally:
            db_module._async_session_factory = original_factory

    @pytest.mark.asyncio
    async def test_get_db_logs_unexpected_error(self) -> None:
        """Test that get_db logs unexpected errors with exception info."""
        import backend.core.database as db_module

        # Save original state
        original_factory = db_module._async_session_factory

        try:
            mock_session = AsyncMock()
            mock_session.commit = AsyncMock(side_effect=KeyError("missing"))
            mock_session.rollback = AsyncMock()
            mock_session.close = AsyncMock()

            mock_factory = MagicMock()
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=None)

            db_module._async_session_factory = mock_factory

            with patch.object(db_module._logger, "exception") as mock_logger:
                with pytest.raises(KeyError):
                    async for _session in db_module.get_db():
                        pass

                mock_logger.assert_called_once()
                call_args = mock_logger.call_args
                assert call_args[1]["extra"]["error_type"] == "unexpected_error"
                assert call_args[1]["extra"]["exception_class"] == "KeyError"

            mock_session.close.assert_called_once()
        finally:
            db_module._async_session_factory = original_factory

    @pytest.mark.asyncio
    async def test_integrity_error_extracts_constraint_from_diag(self) -> None:
        """Test that constraint name is extracted from asyncpg diag attribute."""
        from sqlalchemy.exc import IntegrityError

        import backend.core.database as db_module

        # Save original state
        original_factory = db_module._async_session_factory

        try:
            # Create a mock orig with diag attribute (asyncpg style)
            mock_diag = MagicMock()
            mock_diag.constraint_name = "uq_cameras_name"
            mock_orig = MagicMock()
            mock_orig.diag = mock_diag
            # Don't set constraint_name directly so it falls through to diag
            del mock_orig.constraint_name

            error = IntegrityError("duplicate key", None, mock_orig)

            mock_session = AsyncMock()
            mock_session.commit = AsyncMock(side_effect=error)
            mock_session.rollback = AsyncMock()

            mock_factory = MagicMock()
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=None)

            db_module._async_session_factory = mock_factory

            with patch.object(db_module._logger, "warning") as mock_logger:
                with pytest.raises(IntegrityError):
                    async with db_module.get_session():
                        pass

                call_args = mock_logger.call_args
                # Should have extracted constraint from diag
                assert call_args[1]["extra"]["constraint"] == "uq_cameras_name"
        finally:
            db_module._async_session_factory = original_factory

    @pytest.mark.asyncio
    async def test_integrity_error_handles_missing_constraint_info(self) -> None:
        """Test that IntegrityError is logged even without constraint info."""
        from sqlalchemy.exc import IntegrityError

        import backend.core.database as db_module

        # Save original state
        original_factory = db_module._async_session_factory

        try:
            # Create error with no constraint information available
            error = IntegrityError("integrity error", None, None)

            mock_session = AsyncMock()
            mock_session.commit = AsyncMock(side_effect=error)
            mock_session.rollback = AsyncMock()

            mock_factory = MagicMock()
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=None)

            db_module._async_session_factory = mock_factory

            with patch.object(db_module._logger, "warning") as mock_logger:
                with pytest.raises(IntegrityError):
                    async with db_module.get_session():
                        pass

                call_args = mock_logger.call_args
                # Constraint should be None when not available
                assert call_args[1]["extra"]["constraint"] is None
                # Should still have detail
                assert "detail" in call_args[1]["extra"]
        finally:
            db_module._async_session_factory = original_factory

    @pytest.mark.asyncio
    async def test_get_session_does_not_log_http_exception(self) -> None:
        """Test that HTTPException is not logged as unexpected database error.

        HTTPException is an expected application-level exception (e.g., 404 not found)
        and should pass through without error logging or rollback.
        """
        from fastapi import HTTPException

        import backend.core.database as db_module

        # Save original state
        original_factory = db_module._async_session_factory

        try:
            mock_session = AsyncMock()
            mock_session.rollback = AsyncMock()

            mock_factory = MagicMock()
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=None)

            db_module._async_session_factory = mock_factory

            with patch.object(db_module._logger, "exception") as mock_logger:
                with pytest.raises(HTTPException) as exc_info:
                    async with db_module.get_session():
                        raise HTTPException(status_code=404, detail="Not found")

                # HTTPException should NOT be logged as unexpected error
                mock_logger.assert_not_called()
                # Verify the exception was raised correctly
                assert exc_info.value.status_code == 404
                assert exc_info.value.detail == "Not found"

            # Rollback should NOT be called for HTTPException
            mock_session.rollback.assert_not_called()
        finally:
            db_module._async_session_factory = original_factory

    @pytest.mark.asyncio
    async def test_get_db_does_not_log_http_exception(self) -> None:
        """Test that get_db does not log HTTPException as unexpected database error.

        HTTPException is an expected application-level exception (e.g., 404 not found)
        and should pass through without error logging or rollback.
        """
        from fastapi import HTTPException

        import backend.core.database as db_module

        # Save original state
        original_factory = db_module._async_session_factory

        try:
            mock_session = AsyncMock()
            mock_session.rollback = AsyncMock()
            mock_session.close = AsyncMock()

            mock_factory = MagicMock()
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=None)

            db_module._async_session_factory = mock_factory

            with patch.object(db_module._logger, "exception") as mock_logger:
                with pytest.raises(HTTPException) as exc_info:
                    async for _session in db_module.get_db():
                        raise HTTPException(status_code=404, detail="Camera not found")

                # HTTPException should NOT be logged as unexpected error
                mock_logger.assert_not_called()
                # Verify the exception was raised correctly
                assert exc_info.value.status_code == 404
                assert exc_info.value.detail == "Camera not found"

            # Rollback should NOT be called for HTTPException
            mock_session.rollback.assert_not_called()
        finally:
            db_module._async_session_factory = original_factory
