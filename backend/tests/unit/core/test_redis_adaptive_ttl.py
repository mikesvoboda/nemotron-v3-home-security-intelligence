"""Unit tests for Redis adaptive TTL based on access patterns (NEM-3764).

Tests cover:
- get_with_adaptive_ttl() - Basic caching with adaptive TTL extension
- Access pattern tracking - Hit counting and TTL extension thresholds
- TTL extension logic - Extending TTL for frequently accessed keys
- TTL reduction for volatile data
- Configuration options for adaptive behavior

Uses mocks for Redis operations.
"""

from collections.abc import Awaitable, Callable
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.core.redis import RedisClient

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def redis_client() -> RedisClient:
    """Create a RedisClient instance for testing.

    Returns a client with mock settings for adaptive TTL testing.
    """
    with patch("backend.core.redis.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(
            redis_url="redis://localhost:6379/0",
            redis_ssl_enabled=False,
            redis_ssl_cert_reqs="required",
            redis_ssl_ca_certs=None,
            redis_ssl_certfile=None,
            redis_ssl_keyfile=None,
            redis_ssl_check_hostname=True,
            redis_password=None,
            redis_pool_dedicated_enabled=False,
            redis_pool_size=50,
            redis_pool_size_cache=20,
            redis_pool_size_queue=20,
            redis_pool_size_pubsub=10,
            redis_pool_size_ratelimit=10,
            redis_compression_enabled=False,
            redis_compression_threshold=1024,
        )
        client = RedisClient()
        # Mock the Redis client
        client._client = MagicMock()
        return client


@pytest.fixture
def mock_fetch_fn() -> Callable[[], Awaitable[dict[str, Any]]]:
    """Create a mock fetch function for testing."""
    return AsyncMock(return_value={"id": 1, "name": "test_item"})


# =============================================================================
# get_with_adaptive_ttl Tests - Cache Hit Scenarios
# =============================================================================


class TestGetWithAdaptiveTTLCacheHit:
    """Tests for get_with_adaptive_ttl when data exists in cache."""

    @pytest.mark.asyncio
    async def test_returns_cached_data_on_hit(
        self, redis_client: RedisClient, mock_fetch_fn: Callable[[], Awaitable[dict[str, Any]]]
    ) -> None:
        """Test that cached data is returned without calling fetch function."""
        cached_data = {"id": 1, "name": "cached_item"}

        # Mock Redis get to return cached data
        redis_client._client.get = AsyncMock(return_value='{"id": 1, "name": "cached_item"}')
        redis_client._client.incr = AsyncMock(return_value=1)
        redis_client._client.expire = AsyncMock(return_value=True)

        result = await redis_client.get_with_adaptive_ttl("test:key", mock_fetch_fn)

        assert result == cached_data
        mock_fetch_fn.assert_not_called()

    @pytest.mark.asyncio
    async def test_increments_access_counter_on_hit(
        self, redis_client: RedisClient, mock_fetch_fn: Callable[[], Awaitable[dict[str, Any]]]
    ) -> None:
        """Test that access counter is incremented on cache hit."""
        redis_client._client.get = AsyncMock(return_value='{"id": 1}')
        redis_client._client.incr = AsyncMock(return_value=5)
        redis_client._client.expire = AsyncMock(return_value=True)

        await redis_client.get_with_adaptive_ttl("test:key", mock_fetch_fn)

        redis_client._client.incr.assert_called_once_with("test:key:hits")

    @pytest.mark.asyncio
    async def test_extends_ttl_after_threshold_hits(
        self, redis_client: RedisClient, mock_fetch_fn: Callable[[], Awaitable[dict[str, Any]]]
    ) -> None:
        """Test that TTL is extended when access count exceeds threshold."""
        redis_client._client.get = AsyncMock(return_value='{"id": 1}')
        # Simulate 11 hits (exceeds default threshold of 10)
        redis_client._client.incr = AsyncMock(return_value=11)
        redis_client._client.expire = AsyncMock(return_value=True)

        base_ttl = 300
        await redis_client.get_with_adaptive_ttl("test:key", mock_fetch_fn, base_ttl=base_ttl)

        # TTL should be extended to 2x base_ttl
        redis_client._client.expire.assert_called_once_with("test:key", base_ttl * 2)

    @pytest.mark.asyncio
    async def test_no_ttl_extension_below_threshold(
        self, redis_client: RedisClient, mock_fetch_fn: Callable[[], Awaitable[dict[str, Any]]]
    ) -> None:
        """Test that TTL is NOT extended when access count is below threshold."""
        redis_client._client.get = AsyncMock(return_value='{"id": 1}')
        # Simulate 5 hits (below default threshold of 10)
        redis_client._client.incr = AsyncMock(return_value=5)
        redis_client._client.expire = AsyncMock(return_value=True)

        await redis_client.get_with_adaptive_ttl("test:key", mock_fetch_fn)

        # expire should not be called
        redis_client._client.expire.assert_not_called()

    @pytest.mark.asyncio
    async def test_custom_hit_threshold(
        self, redis_client: RedisClient, mock_fetch_fn: Callable[[], Awaitable[dict[str, Any]]]
    ) -> None:
        """Test that custom hit threshold is respected."""
        redis_client._client.get = AsyncMock(return_value='{"id": 1}')
        redis_client._client.incr = AsyncMock(return_value=6)
        redis_client._client.expire = AsyncMock(return_value=True)

        # Use custom threshold of 5
        await redis_client.get_with_adaptive_ttl("test:key", mock_fetch_fn, hit_threshold=5)

        # With 6 hits and threshold of 5, TTL should be extended
        redis_client._client.expire.assert_called_once()

    @pytest.mark.asyncio
    async def test_custom_ttl_multiplier(
        self, redis_client: RedisClient, mock_fetch_fn: Callable[[], Awaitable[dict[str, Any]]]
    ) -> None:
        """Test that custom TTL multiplier is applied."""
        redis_client._client.get = AsyncMock(return_value='{"id": 1}')
        redis_client._client.incr = AsyncMock(return_value=15)
        redis_client._client.expire = AsyncMock(return_value=True)

        base_ttl = 300
        # Use 3x multiplier instead of default 2x
        await redis_client.get_with_adaptive_ttl(
            "test:key", mock_fetch_fn, base_ttl=base_ttl, ttl_multiplier=3
        )

        redis_client._client.expire.assert_called_once_with("test:key", base_ttl * 3)


# =============================================================================
# get_with_adaptive_ttl Tests - Cache Miss Scenarios
# =============================================================================


class TestGetWithAdaptiveTTLCacheMiss:
    """Tests for get_with_adaptive_ttl when data is not in cache."""

    @pytest.mark.asyncio
    async def test_calls_fetch_fn_on_miss(
        self, redis_client: RedisClient, mock_fetch_fn: Callable[[], Awaitable[dict[str, Any]]]
    ) -> None:
        """Test that fetch function is called when cache misses."""
        redis_client._client.get = AsyncMock(return_value=None)
        redis_client._client.setex = AsyncMock(return_value=True)
        redis_client._client.delete = AsyncMock(return_value=1)

        await redis_client.get_with_adaptive_ttl("test:key", mock_fetch_fn)

        mock_fetch_fn.assert_called_once()

    @pytest.mark.asyncio
    async def test_stores_fetched_data_with_base_ttl(
        self, redis_client: RedisClient, mock_fetch_fn: Callable[[], Awaitable[dict[str, Any]]]
    ) -> None:
        """Test that fetched data is stored with base TTL."""
        redis_client._client.get = AsyncMock(return_value=None)
        redis_client._client.setex = AsyncMock(return_value=True)
        redis_client._client.delete = AsyncMock(return_value=1)

        base_ttl = 600
        await redis_client.get_with_adaptive_ttl("test:key", mock_fetch_fn, base_ttl=base_ttl)

        redis_client._client.setex.assert_called_once()
        call_args = redis_client._client.setex.call_args
        assert call_args[0][0] == "test:key"
        assert call_args[0][1] == base_ttl

    @pytest.mark.asyncio
    async def test_returns_fetched_data(
        self, redis_client: RedisClient, mock_fetch_fn: Callable[[], Awaitable[dict[str, Any]]]
    ) -> None:
        """Test that fetched data is returned on cache miss."""
        expected_data = {"id": 1, "name": "test_item"}
        redis_client._client.get = AsyncMock(return_value=None)
        redis_client._client.setex = AsyncMock(return_value=True)
        redis_client._client.delete = AsyncMock(return_value=1)

        result = await redis_client.get_with_adaptive_ttl("test:key", mock_fetch_fn)

        assert result == expected_data

    @pytest.mark.asyncio
    async def test_resets_hit_counter_on_miss(
        self, redis_client: RedisClient, mock_fetch_fn: Callable[[], Awaitable[dict[str, Any]]]
    ) -> None:
        """Test that hit counter is reset when data is fetched fresh."""
        redis_client._client.get = AsyncMock(return_value=None)
        redis_client._client.setex = AsyncMock(return_value=True)
        redis_client._client.delete = AsyncMock(return_value=1)

        await redis_client.get_with_adaptive_ttl("test:key", mock_fetch_fn)

        # Hit counter should be deleted to reset
        redis_client._client.delete.assert_called_once_with("test:key:hits")


# =============================================================================
# get_with_adaptive_ttl Tests - Configuration Options
# =============================================================================


class TestGetWithAdaptiveTTLConfiguration:
    """Tests for get_with_adaptive_ttl configuration options."""

    @pytest.mark.asyncio
    async def test_default_base_ttl(
        self, redis_client: RedisClient, mock_fetch_fn: Callable[[], Awaitable[dict[str, Any]]]
    ) -> None:
        """Test that default base TTL is 300 seconds."""
        redis_client._client.get = AsyncMock(return_value=None)
        redis_client._client.setex = AsyncMock(return_value=True)
        redis_client._client.delete = AsyncMock(return_value=1)

        await redis_client.get_with_adaptive_ttl("test:key", mock_fetch_fn)

        call_args = redis_client._client.setex.call_args
        assert call_args[0][1] == 300  # Default TTL

    @pytest.mark.asyncio
    async def test_default_hit_threshold(
        self, redis_client: RedisClient, mock_fetch_fn: Callable[[], Awaitable[dict[str, Any]]]
    ) -> None:
        """Test that default hit threshold is 10."""
        redis_client._client.get = AsyncMock(return_value='{"id": 1}')
        redis_client._client.incr = AsyncMock(return_value=10)  # Exactly at threshold
        redis_client._client.expire = AsyncMock(return_value=True)

        await redis_client.get_with_adaptive_ttl("test:key", mock_fetch_fn)

        # At exactly 10, should not extend yet (> not >=)
        redis_client._client.expire.assert_not_called()

    @pytest.mark.asyncio
    async def test_max_ttl_cap(
        self, redis_client: RedisClient, mock_fetch_fn: Callable[[], Awaitable[dict[str, Any]]]
    ) -> None:
        """Test that extended TTL is capped at max_ttl."""
        redis_client._client.get = AsyncMock(return_value='{"id": 1}')
        redis_client._client.incr = AsyncMock(return_value=15)
        redis_client._client.expire = AsyncMock(return_value=True)

        base_ttl = 300
        max_ttl = 500
        # With 2x multiplier, would be 600, but capped at 500
        await redis_client.get_with_adaptive_ttl(
            "test:key", mock_fetch_fn, base_ttl=base_ttl, max_ttl=max_ttl
        )

        redis_client._client.expire.assert_called_once_with("test:key", max_ttl)


# =============================================================================
# Adaptive TTL for Volatile Data Tests
# =============================================================================


class TestAdaptiveTTLVolatileData:
    """Tests for reducing TTL for volatile/frequently changing data."""

    @pytest.mark.asyncio
    async def test_set_with_volatile_flag_uses_reduced_ttl(self, redis_client: RedisClient) -> None:
        """Test that volatile flag reduces TTL."""
        redis_client._client.setex = AsyncMock(return_value=True)

        base_ttl = 300
        await redis_client.set_with_adaptive_ttl(
            "test:key", {"id": 1}, base_ttl=base_ttl, volatile=True
        )

        call_args = redis_client._client.setex.call_args
        # Volatile data should use half the base TTL
        assert call_args[0][1] == base_ttl // 2

    @pytest.mark.asyncio
    async def test_non_volatile_uses_full_ttl(self, redis_client: RedisClient) -> None:
        """Test that non-volatile data uses full TTL."""
        redis_client._client.setex = AsyncMock(return_value=True)

        base_ttl = 300
        await redis_client.set_with_adaptive_ttl(
            "test:key", {"id": 1}, base_ttl=base_ttl, volatile=False
        )

        call_args = redis_client._client.setex.call_args
        assert call_args[0][1] == base_ttl


# =============================================================================
# Access Pattern Tracking Tests
# =============================================================================


class TestAccessPatternTracking:
    """Tests for access pattern tracking functionality."""

    @pytest.mark.asyncio
    async def test_track_access_increments_counter(self, redis_client: RedisClient) -> None:
        """Test that track_access increments the access counter."""
        redis_client._client.incr = AsyncMock(return_value=5)
        redis_client._client.expire = AsyncMock(return_value=True)

        count = await redis_client.track_access("test:key", counter_ttl=3600)

        assert count == 5
        redis_client._client.incr.assert_called_once_with("test:key:hits")

    @pytest.mark.asyncio
    async def test_track_access_sets_counter_ttl(self, redis_client: RedisClient) -> None:
        """Test that track_access sets TTL on the counter."""
        redis_client._client.incr = AsyncMock(return_value=1)
        redis_client._client.expire = AsyncMock(return_value=True)

        counter_ttl = 7200
        await redis_client.track_access("test:key", counter_ttl=counter_ttl)

        redis_client._client.expire.assert_called_once_with("test:key:hits", counter_ttl)

    @pytest.mark.asyncio
    async def test_get_access_count(self, redis_client: RedisClient) -> None:
        """Test getting access count for a key."""
        redis_client._client.get = AsyncMock(return_value="42")

        count = await redis_client.get_access_count("test:key")

        assert count == 42
        redis_client._client.get.assert_called_once_with("test:key:hits")

    @pytest.mark.asyncio
    async def test_get_access_count_returns_zero_for_missing_key(
        self, redis_client: RedisClient
    ) -> None:
        """Test that get_access_count returns 0 for missing keys."""
        redis_client._client.get = AsyncMock(return_value=None)

        count = await redis_client.get_access_count("test:key")

        assert count == 0

    @pytest.mark.asyncio
    async def test_reset_access_count(self, redis_client: RedisClient) -> None:
        """Test resetting access count for a key."""
        redis_client._client.delete = AsyncMock(return_value=1)

        result = await redis_client.reset_access_count("test:key")

        assert result is True
        redis_client._client.delete.assert_called_once_with("test:key:hits")


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestAdaptiveTTLErrorHandling:
    """Tests for error handling in adaptive TTL methods."""

    @pytest.mark.asyncio
    async def test_fetch_fn_failure_propagates(self, redis_client: RedisClient) -> None:
        """Test that fetch function failures propagate correctly."""
        redis_client._client.get = AsyncMock(return_value=None)
        failing_fetch = AsyncMock(side_effect=ValueError("Database error"))

        with pytest.raises(ValueError, match="Database error"):
            await redis_client.get_with_adaptive_ttl("test:key", failing_fetch)

    @pytest.mark.asyncio
    async def test_graceful_handling_of_incr_failure(
        self, redis_client: RedisClient, mock_fetch_fn: Callable[[], Awaitable[dict[str, Any]]]
    ) -> None:
        """Test that INCR failure doesn't prevent returning cached data."""
        from redis.exceptions import RedisError

        redis_client._client.get = AsyncMock(return_value='{"id": 1}')
        redis_client._client.incr = AsyncMock(side_effect=RedisError("Connection lost"))

        # Should still return cached data even if tracking fails
        result = await redis_client.get_with_adaptive_ttl("test:key", mock_fetch_fn)

        assert result == {"id": 1}

    @pytest.mark.asyncio
    async def test_graceful_handling_of_expire_failure(
        self, redis_client: RedisClient, mock_fetch_fn: Callable[[], Awaitable[dict[str, Any]]]
    ) -> None:
        """Test that EXPIRE failure doesn't prevent returning cached data."""
        from redis.exceptions import RedisError

        redis_client._client.get = AsyncMock(return_value='{"id": 1}')
        redis_client._client.incr = AsyncMock(return_value=15)
        redis_client._client.expire = AsyncMock(side_effect=RedisError("Connection lost"))

        # Should still return cached data even if TTL extension fails
        result = await redis_client.get_with_adaptive_ttl("test:key", mock_fetch_fn)

        assert result == {"id": 1}


# =============================================================================
# Integration-style Tests
# =============================================================================


class TestAdaptiveTTLIntegration:
    """Integration-style tests combining multiple adaptive TTL behaviors."""

    @pytest.mark.asyncio
    async def test_full_lifecycle_cache_warm_to_hot(
        self, redis_client: RedisClient, mock_fetch_fn: Callable[[], Awaitable[dict[str, Any]]]
    ) -> None:
        """Test the full lifecycle from cold to hot cache."""
        # First call - cache miss
        redis_client._client.get = AsyncMock(return_value=None)
        redis_client._client.setex = AsyncMock(return_value=True)
        redis_client._client.delete = AsyncMock(return_value=1)

        result1 = await redis_client.get_with_adaptive_ttl("test:key", mock_fetch_fn)
        assert result1 == {"id": 1, "name": "test_item"}
        mock_fetch_fn.assert_called_once()

        # Simulate subsequent calls - cache hits with increasing access count
        redis_client._client.get = AsyncMock(return_value='{"id": 1, "name": "test_item"}')
        redis_client._client.expire = AsyncMock(return_value=True)

        for i in range(1, 12):
            redis_client._client.incr = AsyncMock(return_value=i)
            await redis_client.get_with_adaptive_ttl("test:key", mock_fetch_fn)

        # After 11 hits, TTL should have been extended
        assert redis_client._client.expire.called
