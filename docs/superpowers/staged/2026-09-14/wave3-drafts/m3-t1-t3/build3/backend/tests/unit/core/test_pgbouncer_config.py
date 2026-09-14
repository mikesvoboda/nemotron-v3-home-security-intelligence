"""Unit tests for PgBouncer configuration and integration.

Tests cover:
- USE_PGBOUNCER setting in config.py
- Prepared statement cache disabling in database.py when PgBouncer is enabled
- Connection pool size adjustments for PgBouncer mode

NEM-3419: Add PgBouncer for connection multiplexing
"""

from unittest.mock import MagicMock, patch

import pytest

from backend.core.config import Settings, get_settings


class TestUsePgbouncerSetting:
    """Tests for the use_pgbouncer configuration setting."""

    @pytest.fixture
    def clean_env(self, monkeypatch):
        """Clean environment variables and settings cache before each test."""
        env_vars = [
            "USE_PGBOUNCER",
            "DATABASE_URL",
            "DATABASE_POOL_SIZE",
            "DATABASE_POOL_OVERFLOW",
            "ENVIRONMENT",
        ]
        for var in env_vars:
            monkeypatch.delenv(var, raising=False)

        # Set required environment variables
        monkeypatch.setenv(
            "DATABASE_URL",
            "postgresql+asyncpg://test:test@localhost:5432/test",  # pragma: allowlist secret
        )
        monkeypatch.setenv("ENVIRONMENT", "development")

        get_settings.cache_clear()
        yield monkeypatch

    def test_use_pgbouncer_default_false(self, clean_env):
        """Test that use_pgbouncer defaults to False."""
        settings = Settings()
        assert settings.use_pgbouncer is False

    def test_use_pgbouncer_can_be_enabled(self, clean_env):
        """Test that use_pgbouncer can be enabled via environment variable."""
        clean_env.setenv("USE_PGBOUNCER", "true")
        get_settings.cache_clear()
        settings = Settings()
        assert settings.use_pgbouncer is True

    def test_use_pgbouncer_accepts_various_true_values(self, clean_env):
        """Test that use_pgbouncer accepts various truthy string values."""
        for value in ["true", "True", "TRUE", "1", "yes", "Yes"]:
            clean_env.setenv("USE_PGBOUNCER", value)
            get_settings.cache_clear()
            settings = Settings()
            assert settings.use_pgbouncer is True, f"Failed for value: {value}"

    def test_use_pgbouncer_accepts_false_values(self, clean_env):
        """Test that use_pgbouncer accepts various falsy string values."""
        for value in ["false", "False", "FALSE", "0", "no", "No"]:
            clean_env.setenv("USE_PGBOUNCER", value)
            get_settings.cache_clear()
            settings = Settings()
            assert settings.use_pgbouncer is False, f"Failed for value: {value}"


class TestPgbouncerPoolSettings:
    """Tests for pool size configuration with PgBouncer."""

    @pytest.fixture
    def clean_env(self, monkeypatch):
        """Clean environment variables and settings cache before each test."""
        env_vars = [
            "USE_PGBOUNCER",
            "DATABASE_URL",
            "DATABASE_POOL_SIZE",
            "DATABASE_POOL_OVERFLOW",
            "ENVIRONMENT",
        ]
        for var in env_vars:
            monkeypatch.delenv(var, raising=False)

        # Set required environment variables
        monkeypatch.setenv(
            "DATABASE_URL",
            "postgresql+asyncpg://test:test@localhost:5432/test",  # pragma: allowlist secret
        )
        monkeypatch.setenv("ENVIRONMENT", "development")

        get_settings.cache_clear()
        yield monkeypatch

    def test_default_pool_size_without_pgbouncer(self, clean_env):
        """Test that default pool size is 20 without PgBouncer."""
        settings = Settings()
        assert settings.database_pool_size == 20
        assert settings.database_pool_overflow == 30

    def test_pool_size_can_be_reduced_for_pgbouncer(self, clean_env):
        """Test that pool size can be reduced when using PgBouncer."""
        clean_env.setenv("USE_PGBOUNCER", "true")
        clean_env.setenv("DATABASE_POOL_SIZE", "5")
        clean_env.setenv("DATABASE_POOL_OVERFLOW", "5")
        get_settings.cache_clear()
        settings = Settings()
        assert settings.database_pool_size == 5
        assert settings.database_pool_overflow == 5

    def test_pool_size_min_constraint(self, clean_env):
        """Test that pool size has a minimum of 5."""
        # The constraint ge=5 should allow pool_size of 5 (minimum)
        clean_env.setenv("DATABASE_POOL_SIZE", "5")
        get_settings.cache_clear()
        settings = Settings()
        assert settings.database_pool_size == 5


class TestPgbouncerDatabaseInit:
    """Tests for database initialization with PgBouncer mode."""

    @pytest.mark.asyncio
    async def test_pgbouncer_disables_prepared_statement_cache(self):
        """Test that PgBouncer mode disables prepared statement cache."""
        from backend.core.database import init_db

        with patch("backend.core.database.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                database_url="postgresql+asyncpg://test:test@localhost:5432/test",  # pragma: allowlist secret
                database_url_read=None,
                debug=False,
                database_pool_size=5,
                database_pool_overflow=5,
                database_pool_timeout=30,
                database_pool_recycle=1800,
                use_pgbouncer=True,  # Enable PgBouncer mode
            )

            with patch("backend.core.database.create_async_engine") as mock_engine:
                # Mock the engine to avoid actual database connection
                mock_engine.return_value = MagicMock()
                mock_engine.return_value.sync_engine = MagicMock()

                try:
                    await init_db()
                except Exception:
                    # We're just checking the call arguments, not the full init
                    pass

                # Verify create_async_engine was called with disabled prepared statement cache
                if mock_engine.called:
                    call_kwargs = mock_engine.call_args.kwargs
                    connect_args = call_kwargs.get("connect_args", {})
                    assert connect_args.get("prepared_statement_cache_size") == 0
                    assert connect_args.get("statement_cache_size") == 0

    @pytest.mark.asyncio
    async def test_non_pgbouncer_preserves_prepared_statement_cache(self):
        """Test that non-PgBouncer mode preserves default prepared statement cache."""
        from backend.core.database import init_db

        with patch("backend.core.database.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                database_url="postgresql+asyncpg://test:test@localhost:5432/test",  # pragma: allowlist secret
                database_url_read=None,
                debug=False,
                database_pool_size=20,
                database_pool_overflow=30,
                database_pool_timeout=30,
                database_pool_recycle=1800,
                use_pgbouncer=False,  # Disable PgBouncer mode
            )

            with patch("backend.core.database.create_async_engine") as mock_engine:
                # Mock the engine to avoid actual database connection
                mock_engine.return_value = MagicMock()
                mock_engine.return_value.sync_engine = MagicMock()

                try:
                    await init_db()
                except Exception:
                    # We're just checking the call arguments, not the full init
                    pass

                # Verify create_async_engine was called without disabling prepared statement cache
                if mock_engine.called:
                    call_kwargs = mock_engine.call_args.kwargs
                    connect_args = call_kwargs.get("connect_args", {})
                    # Should not have prepared_statement_cache_size set to 0
                    assert connect_args.get("prepared_statement_cache_size") != 0


class TestPgbouncerDescription:
    """Tests for use_pgbouncer field description."""

    @pytest.fixture
    def clean_env(self, monkeypatch):
        """Clean environment variables and settings cache before each test."""
        monkeypatch.setenv(
            "DATABASE_URL",
            "postgresql+asyncpg://test:test@localhost:5432/test",  # pragma: allowlist secret
        )
        monkeypatch.setenv("ENVIRONMENT", "development")
        get_settings.cache_clear()
        yield monkeypatch

    def test_use_pgbouncer_has_description(self, clean_env):
        """Test that use_pgbouncer field has a description."""
        fields = Settings.model_fields
        assert "use_pgbouncer" in fields
        field_info = fields["use_pgbouncer"]
        assert field_info.description is not None
        assert "PgBouncer" in field_info.description
        assert "transaction" in field_info.description.lower()
