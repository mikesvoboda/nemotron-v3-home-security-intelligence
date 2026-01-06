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
                    debug=False,
                    database_pool_size=15,
                    database_pool_overflow=25,
                    database_pool_timeout=45,
                    database_pool_recycle=2400,
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
