"""Unit tests for prepared statement caching (NEM-3760).

Tests for the PreparedStatementCache class that provides query plan caching
for frequently executed queries to improve PostgreSQL performance.

Following TDD approach - tests written first before implementation.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select, text

from backend.models import Camera, Detection, Event

# =============================================================================
# PreparedStatementCache Tests
# =============================================================================


class TestPreparedStatementCache:
    """Tests for prepared statement cache functionality."""

    def test_cache_initialization(self) -> None:
        """Test that PreparedStatementCache initializes with correct defaults."""
        from backend.core.prepared_statements import PreparedStatementCache

        cache = PreparedStatementCache()

        assert cache.max_size == 100  # Default max cache size
        assert len(cache._cache) == 0
        assert cache.enabled is True

    def test_cache_initialization_with_custom_size(self) -> None:
        """Test cache initialization with custom max size."""
        from backend.core.prepared_statements import PreparedStatementCache

        cache = PreparedStatementCache(max_size=50)

        assert cache.max_size == 50

    def test_cache_initialization_disabled(self) -> None:
        """Test cache can be initialized in disabled state."""
        from backend.core.prepared_statements import PreparedStatementCache

        cache = PreparedStatementCache(enabled=False)

        assert cache.enabled is False

    def test_generate_cache_key_for_select_query(self) -> None:
        """Test generating cache key from a SELECT query."""
        from backend.core.prepared_statements import PreparedStatementCache

        cache = PreparedStatementCache()

        stmt = select(Camera).where(Camera.id == "test")
        key = cache._generate_cache_key(stmt)

        assert isinstance(key, str)
        assert len(key) > 0

    def test_cache_key_consistency(self) -> None:
        """Test that same query generates same cache key."""
        from backend.core.prepared_statements import PreparedStatementCache

        cache = PreparedStatementCache()

        stmt1 = select(Camera).where(Camera.id == "test")
        stmt2 = select(Camera).where(Camera.id == "test")

        key1 = cache._generate_cache_key(stmt1)
        key2 = cache._generate_cache_key(stmt2)

        assert key1 == key2

    def test_different_queries_generate_different_keys(self) -> None:
        """Test that different queries generate different cache keys."""
        from backend.core.prepared_statements import PreparedStatementCache

        cache = PreparedStatementCache()

        stmt1 = select(Camera).where(Camera.id == "test1")
        stmt2 = select(Detection).where(Detection.id == 1)

        key1 = cache._generate_cache_key(stmt1)
        key2 = cache._generate_cache_key(stmt2)

        assert key1 != key2

    def test_register_query(self) -> None:
        """Test registering a query for prepared statement caching."""
        from backend.core.prepared_statements import PreparedStatementCache

        cache = PreparedStatementCache()

        stmt = select(Camera).where(Camera.id == "test")
        cache.register(stmt, name="get_camera_by_id")

        assert "get_camera_by_id" in cache._named_queries
        assert len(cache._named_queries) == 1

    def test_register_multiple_queries(self) -> None:
        """Test registering multiple queries."""
        from backend.core.prepared_statements import PreparedStatementCache

        cache = PreparedStatementCache()

        cache.register(select(Camera), name="list_cameras")
        cache.register(select(Detection), name="list_detections")
        cache.register(select(Event), name="list_events")

        assert len(cache._named_queries) == 3

    def test_get_prepared_statement_hit(self) -> None:
        """Test getting a prepared statement that's in cache."""
        from backend.core.prepared_statements import PreparedStatementCache

        cache = PreparedStatementCache()

        stmt = select(Camera).where(Camera.id == "test")
        cache.register(stmt, name="get_camera")

        # Simulate cache hit
        cached_stmt = cache.get("get_camera")

        assert cached_stmt is not None

    def test_get_prepared_statement_miss(self) -> None:
        """Test getting a non-existent prepared statement returns None."""
        from backend.core.prepared_statements import PreparedStatementCache

        cache = PreparedStatementCache()

        result = cache.get("nonexistent")

        assert result is None

    def test_cache_stats_tracking(self) -> None:
        """Test that cache tracks hit/miss statistics."""
        from backend.core.prepared_statements import PreparedStatementCache

        cache = PreparedStatementCache()

        stmt = select(Camera)
        cache.register(stmt, name="list_cameras")

        # Access registered query (hit)
        cache.get("list_cameras")
        cache.get("list_cameras")
        # Access non-existent (miss)
        cache.get("nonexistent")

        stats = cache.get_stats()

        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["registered_queries"] == 1

    def test_cache_respects_max_size(self) -> None:
        """Test that cache evicts entries when max size is exceeded."""
        from backend.core.prepared_statements import PreparedStatementCache

        cache = PreparedStatementCache(max_size=3)

        # Register more than max_size queries
        cache.register(select(Camera), name="q1")
        cache.register(select(Detection), name="q2")
        cache.register(select(Event), name="q3")
        cache.register(select(Camera).where(Camera.id == "x"), name="q4")

        # Should have evicted oldest entry
        assert len(cache._named_queries) <= 3

    def test_clear_cache(self) -> None:
        """Test clearing the cache."""
        from backend.core.prepared_statements import PreparedStatementCache

        cache = PreparedStatementCache()

        cache.register(select(Camera), name="q1")
        cache.register(select(Detection), name="q2")

        cache.clear()

        assert len(cache._named_queries) == 0
        assert cache.get("q1") is None

    def test_cache_disabled_no_registration(self) -> None:
        """Test that disabled cache doesn't register queries."""
        from backend.core.prepared_statements import PreparedStatementCache

        cache = PreparedStatementCache(enabled=False)

        cache.register(select(Camera), name="list_cameras")

        # Should not be registered when disabled
        assert cache.get("list_cameras") is None
        assert len(cache._named_queries) == 0


# =============================================================================
# Frequently Executed Query Registration Tests
# =============================================================================


class TestFrequentQueryRegistration:
    """Tests for registering frequently executed queries."""

    def test_register_detection_queries(self) -> None:
        """Test registering detection-related queries."""
        from backend.core.prepared_statements import (
            PreparedStatementCache,
            register_common_queries,
        )

        cache = PreparedStatementCache()
        register_common_queries(cache)

        # Should have registered detection queries
        assert cache.get("get_detection_by_id") is not None
        assert cache.get("list_detections_by_camera") is not None

    def test_register_event_queries(self) -> None:
        """Test registering event-related queries."""
        from backend.core.prepared_statements import (
            PreparedStatementCache,
            register_common_queries,
        )

        cache = PreparedStatementCache()
        register_common_queries(cache)

        # Should have registered event queries
        assert cache.get("get_event_by_id") is not None
        assert cache.get("list_events_by_camera") is not None
        assert cache.get("count_unreviewed_events") is not None

    def test_register_camera_queries(self) -> None:
        """Test registering camera-related queries."""
        from backend.core.prepared_statements import (
            PreparedStatementCache,
            register_common_queries,
        )

        cache = PreparedStatementCache()
        register_common_queries(cache)

        # Should have registered camera queries
        assert cache.get("list_cameras") is not None
        assert cache.get("get_camera_by_id") is not None


# =============================================================================
# Integration with SQLAlchemy Session Tests
# =============================================================================


class TestSessionIntegration:
    """Tests for integration with SQLAlchemy AsyncSession."""

    @pytest.mark.asyncio
    async def test_execute_with_prepared_statement(self) -> None:
        """Test executing a query using prepared statement cache."""
        from backend.core.prepared_statements import (
            PreparedStatementCache,
            execute_prepared,
        )

        cache = PreparedStatementCache()
        cache.register(select(Camera), name="list_cameras")

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_session.execute.return_value = mock_result

        result = await execute_prepared(mock_session, cache, "list_cameras")

        mock_session.execute.assert_called_once()
        assert result == mock_result

    @pytest.mark.asyncio
    async def test_execute_with_parameters(self) -> None:
        """Test executing prepared statement with bound parameters."""
        from backend.core.prepared_statements import (
            PreparedStatementCache,
            execute_prepared,
        )

        cache = PreparedStatementCache()
        stmt = select(Camera).where(Camera.id == text(":camera_id"))
        cache.register(stmt, name="get_camera_by_id")

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_session.execute.return_value = mock_result

        result = await execute_prepared(
            mock_session,
            cache,
            "get_camera_by_id",
            params={"camera_id": "front_door"},
        )

        mock_session.execute.assert_called_once()
        # Verify parameters were passed
        call_args = mock_session.execute.call_args
        assert call_args is not None

    @pytest.mark.asyncio
    async def test_execute_nonexistent_query_raises(self) -> None:
        """Test that executing non-registered query raises error."""
        from backend.core.prepared_statements import (
            PreparedStatementCache,
            PreparedStatementError,
            execute_prepared,
        )

        cache = PreparedStatementCache()
        mock_session = AsyncMock()

        with pytest.raises(PreparedStatementError):
            await execute_prepared(mock_session, cache, "nonexistent")


# =============================================================================
# Global Cache Instance Tests
# =============================================================================


class TestGlobalCacheInstance:
    """Tests for the global prepared statement cache instance."""

    def test_get_global_cache_returns_singleton(self) -> None:
        """Test that get_prepared_cache returns singleton instance."""
        from backend.core.prepared_statements import get_prepared_cache

        cache1 = get_prepared_cache()
        cache2 = get_prepared_cache()

        assert cache1 is cache2

    def test_global_cache_initialization(self) -> None:
        """Test that global cache is properly initialized."""
        from backend.core.prepared_statements import get_prepared_cache

        cache = get_prepared_cache()

        # Should be a PreparedStatementCache instance
        from backend.core.prepared_statements import PreparedStatementCache

        assert isinstance(cache, PreparedStatementCache)


# =============================================================================
# Configuration Tests
# =============================================================================


class TestCacheConfiguration:
    """Tests for cache configuration from settings."""

    def test_cache_respects_pgbouncer_setting(self) -> None:
        """Test that cache is disabled when PgBouncer mode is enabled."""
        from backend.core.prepared_statements import create_cache_from_settings

        # Mock settings with PgBouncer enabled
        mock_settings = MagicMock()
        mock_settings.use_pgbouncer = True
        mock_settings.prepared_statement_cache_size = 100

        with patch("backend.core.config.get_settings", return_value=mock_settings):
            cache = create_cache_from_settings()

            # Should be disabled for PgBouncer compatibility
            assert cache.enabled is False

    def test_cache_uses_configured_size(self) -> None:
        """Test that cache uses size from settings."""
        from backend.core.prepared_statements import create_cache_from_settings

        # Mock settings
        mock_settings = MagicMock()
        mock_settings.use_pgbouncer = False
        mock_settings.prepared_statement_cache_size = 200

        with patch("backend.core.config.get_settings", return_value=mock_settings):
            cache = create_cache_from_settings()

            assert cache.max_size == 200
            assert cache.enabled is True


# =============================================================================
# Performance Monitoring Tests
# =============================================================================


class TestPerformanceMonitoring:
    """Tests for prepared statement performance monitoring."""

    def test_cache_hit_ratio_calculation(self) -> None:
        """Test calculation of cache hit ratio."""
        from backend.core.prepared_statements import PreparedStatementCache

        cache = PreparedStatementCache()
        cache.register(select(Camera), name="q1")

        # 3 hits, 1 miss
        cache.get("q1")
        cache.get("q1")
        cache.get("q1")
        cache.get("nonexistent")

        stats = cache.get_stats()

        assert stats["hit_ratio"] == 0.75  # 3/4 = 0.75

    def test_cache_hit_ratio_zero_requests(self) -> None:
        """Test hit ratio is 0 when no requests made."""
        from backend.core.prepared_statements import PreparedStatementCache

        cache = PreparedStatementCache()

        stats = cache.get_stats()

        assert stats["hit_ratio"] == 0.0
        assert stats["total_requests"] == 0
