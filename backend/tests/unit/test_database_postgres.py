"""Unit tests for PostgreSQL support in database module.

These tests verify that the database module correctly handles:
- URL detection for PostgreSQL vs SQLite (legacy helper functions)
- Engine configuration for PostgreSQL
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import pool

from backend.core.config import get_settings
from backend.core.database import (
    _is_postgresql,
    _is_sqlite,
    close_db,
    init_db,
)


class TestIsPostgresql:
    """Tests for the _is_postgresql helper function."""

    def test_postgresql_url_returns_true(self) -> None:
        """Verify _is_postgresql returns True for postgresql:// URLs."""
        assert _is_postgresql("postgresql://localhost:5432/db") is True

    def test_postgresql_asyncpg_url_returns_true(self) -> None:
        """Verify _is_postgresql returns True for postgresql+asyncpg:// URLs."""
        assert _is_postgresql("postgresql+asyncpg://localhost:5432/db") is True

    def test_postgres_url_returns_true(self) -> None:
        """Verify _is_postgresql returns True for postgres:// URLs."""
        assert _is_postgresql("postgres://localhost:5432/db") is True

    def test_sqlite_url_returns_false(self) -> None:
        """Verify _is_postgresql returns False for sqlite:// URLs."""
        assert _is_postgresql("sqlite:///path/to/db.db") is False

    def test_sqlite_aiosqlite_url_returns_false(self) -> None:
        """Verify _is_postgresql returns False for sqlite+aiosqlite:// URLs."""
        assert _is_postgresql("sqlite+aiosqlite:///path/to/db.db") is False


class TestIsSqlite:
    """Tests for the _is_sqlite helper function."""

    def test_sqlite_url_returns_true(self) -> None:
        """Verify _is_sqlite returns True for sqlite:// URLs."""
        assert _is_sqlite("sqlite:///path/to/db.db") is True

    def test_sqlite_aiosqlite_url_returns_true(self) -> None:
        """Verify _is_sqlite returns True for sqlite+aiosqlite:// URLs."""
        assert _is_sqlite("sqlite+aiosqlite:///path/to/db.db") is True

    def test_postgresql_url_returns_false(self) -> None:
        """Verify _is_sqlite returns False for postgresql:// URLs."""
        assert _is_sqlite("postgresql://localhost:5432/db") is False

    def test_postgres_url_returns_false(self) -> None:
        """Verify _is_sqlite returns False for postgres:// URLs."""
        assert _is_sqlite("postgres://localhost:5432/db") is False

    def test_postgresql_asyncpg_url_returns_false(self) -> None:
        """Verify _is_sqlite returns False for postgresql+asyncpg:// URLs."""
        assert _is_sqlite("postgresql+asyncpg://localhost:5432/db") is False


class TestPostgresqlEngineConfiguration:
    """Tests for PostgreSQL engine configuration in init_db."""

    @pytest.mark.asyncio
    async def test_postgresql_uses_connection_pooling(self) -> None:
        """Verify that PostgreSQL databases are configured with connection pooling."""
        original_db_url = os.environ.get("DATABASE_URL")
        get_settings.cache_clear()

        # Use a PostgreSQL URL
        test_db_url = "postgresql+asyncpg://localhost:5432/testdb"

        os.environ["DATABASE_URL"] = test_db_url
        get_settings.cache_clear()

        try:
            await close_db()

            # Mock create_async_engine to capture the arguments
            with patch("backend.core.database.create_async_engine") as mock_create:
                # Create a mock engine
                mock_engine = MagicMock()
                mock_engine.dispose = AsyncMock()
                mock_engine.begin = MagicMock(
                    return_value=MagicMock(__aenter__=MagicMock(), __aexit__=MagicMock())
                )
                mock_create.return_value = mock_engine

                # Call init_db but expect it to fail on table creation
                try:
                    await init_db()
                except Exception:  # noqa: S110
                    pass  # Expected - we only care about engine creation args

                # Verify create_async_engine was called
                mock_create.assert_called_once()
                call_kwargs = mock_create.call_args[1]

                # PostgreSQL should have connection pool settings
                assert call_kwargs.get("pool_size") == 5
                assert call_kwargs.get("max_overflow") == 10
                assert call_kwargs.get("pool_pre_ping") is True

                # PostgreSQL should NOT have poolclass (uses default QueuePool)
                assert "poolclass" not in call_kwargs

                # PostgreSQL should NOT have connect_args
                assert "connect_args" not in call_kwargs

        finally:
            await close_db()
            if original_db_url:
                os.environ["DATABASE_URL"] = original_db_url
            else:
                os.environ.pop("DATABASE_URL", None)
            get_settings.cache_clear()

    @pytest.mark.asyncio
    async def test_postgresql_no_nullpool(self) -> None:
        """Verify that PostgreSQL does not use NullPool."""
        original_db_url = os.environ.get("DATABASE_URL")
        get_settings.cache_clear()

        test_db_url = "postgresql+asyncpg://localhost:5432/testdb"

        os.environ["DATABASE_URL"] = test_db_url
        get_settings.cache_clear()

        try:
            await close_db()

            with patch("backend.core.database.create_async_engine") as mock_create:
                mock_engine = MagicMock()
                mock_engine.dispose = AsyncMock()
                mock_engine.begin = MagicMock(
                    return_value=MagicMock(__aenter__=MagicMock(), __aexit__=MagicMock())
                )
                mock_create.return_value = mock_engine

                try:
                    await init_db()
                except Exception:  # noqa: S110
                    pass  # Expected - we only care about engine creation args

                call_kwargs = mock_create.call_args[1]

                # Verify NullPool is NOT used for PostgreSQL
                assert call_kwargs.get("poolclass") != pool.NullPool
                assert "poolclass" not in call_kwargs  # Should not specify poolclass at all

        finally:
            await close_db()
            if original_db_url:
                os.environ["DATABASE_URL"] = original_db_url
            else:
                os.environ.pop("DATABASE_URL", None)
            get_settings.cache_clear()


class TestDatabaseUrlParsing:
    """Tests for edge cases in database URL parsing."""

    def test_postgresql_with_credentials(self) -> None:
        """Verify detection works with credentials in URL."""
        url = "postgresql://user:password@localhost:5432/db"
        assert _is_postgresql(url) is True
        assert _is_sqlite(url) is False

    def test_postgresql_with_ssl_params(self) -> None:
        """Verify detection works with SSL parameters."""
        url = "postgresql+asyncpg://user:pass@host:5432/db?sslmode=require"
        assert _is_postgresql(url) is True
        assert _is_sqlite(url) is False

    def test_sqlite_memory_database(self) -> None:
        """Verify detection works for in-memory SQLite."""
        url = "sqlite+aiosqlite:///:memory:"
        assert _is_sqlite(url) is True
        assert _is_postgresql(url) is False

    def test_postgres_shorthand(self) -> None:
        """Verify postgres:// (shorthand) is detected as PostgreSQL."""
        url = "postgres://user:pass@localhost:5432/db"
        assert _is_postgresql(url) is True
        assert _is_sqlite(url) is False
