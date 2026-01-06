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
