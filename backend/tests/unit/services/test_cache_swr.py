"""Unit tests for Stale-While-Revalidate (SWR) cache pattern (NEM-3367).

This module tests the SWR caching functionality added to CacheService:
- get_or_set_swr method for SWR pattern
- Background refresh functionality
- cached_swr decorator
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.cache_service import (
    CacheService,
    cached_swr,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_redis_client():
    """Create a mock Redis client with common operations."""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=None)
    mock_client.set = AsyncMock(return_value=True)
    mock_client.delete = AsyncMock(return_value=1)
    mock_client.exists = AsyncMock(return_value=0)
    mock_client.expire = AsyncMock(return_value=True)
    return mock_client


@pytest.fixture
def cache_service(mock_redis_client):
    """Create a CacheService with mocked Redis client."""
    return CacheService(mock_redis_client)


# =============================================================================
# SWR Method Tests
# =============================================================================


@pytest.mark.asyncio
async def test_swr_returns_fresh_data_immediately(cache_service, mock_redis_client):
    """Test SWR returns fresh cached data without background refresh."""
    cached_data = {"stats": "data"}
    fresh_until = time.time() + 100  # Still fresh

    # Simulate: first get returns cached value, second returns freshness marker
    mock_redis_client.get.side_effect = [
        cached_data,  # First call - cached value
        str(fresh_until),  # Second call - freshness timestamp
    ]

    factory = MagicMock(return_value={"fresh": "data"})

    result = await cache_service.get_or_set_swr("stats:dashboard", factory, ttl=60, stale_ttl=30)

    assert result == cached_data
    factory.assert_not_called()


@pytest.mark.asyncio
async def test_swr_cache_miss_computes_synchronously(cache_service, mock_redis_client):
    """Test SWR computes value synchronously on cache miss."""
    mock_redis_client.get.return_value = None
    mock_redis_client.set.return_value = True

    async def factory():
        return {"computed": "value"}

    result = await cache_service.get_or_set_swr("stats:new", factory, ttl=60, stale_ttl=30)

    assert result == {"computed": "value"}
    # Should have set the value
    assert mock_redis_client.set.called


@pytest.mark.asyncio
async def test_swr_handles_redis_error_gracefully(cache_service, mock_redis_client):
    """Test SWR falls back to direct computation on Redis error."""
    from redis.exceptions import RedisError

    mock_redis_client.get.side_effect = RedisError("Connection failed")

    async def factory():
        return {"fallback": "value"}

    result = await cache_service.get_or_set_swr("test:key", factory, ttl=60, stale_ttl=30)

    assert result == {"fallback": "value"}


@pytest.mark.asyncio
async def test_swr_with_sync_factory(cache_service, mock_redis_client):
    """Test SWR works with synchronous factory function."""
    mock_redis_client.get.return_value = None
    mock_redis_client.set.return_value = True

    def sync_factory():
        return {"sync": "result"}

    result = await cache_service.get_or_set_swr("test:key", sync_factory, ttl=60, stale_ttl=30)

    assert result == {"sync": "result"}


# =============================================================================
# cached_swr Decorator Tests
# =============================================================================


@pytest.mark.asyncio
async def test_cached_swr_decorator_basic():
    """Test cached_swr decorator basic functionality."""
    mock_cache = AsyncMock()
    mock_cache.get_or_set_swr = AsyncMock(return_value={"cached": True})

    @cached_swr("test:key", ttl=60, stale_ttl=30, cache_type="system")
    async def test_function():
        return {"fresh": True}

    with (
        patch(
            "backend.services.cache_service.get_cache_service",
            return_value=mock_cache,
        ),
        patch("backend.services.cache_service.get_settings") as mock_settings,
    ):
        mock_settings.return_value.cache_swr_enabled = True

        result = await test_function()

        assert result == {"cached": True}
        mock_cache.get_or_set_swr.assert_called_once()


@pytest.mark.asyncio
async def test_cached_swr_decorator_with_dynamic_key():
    """Test cached_swr decorator with callable cache key."""
    mock_cache = AsyncMock()
    mock_cache.get_or_set_swr = AsyncMock(return_value={"cached": True})

    @cached_swr(lambda item_id: f"items:{item_id}", ttl=60)
    async def get_item(item_id: str):
        return {"id": item_id}

    with (
        patch(
            "backend.services.cache_service.get_cache_service",
            return_value=mock_cache,
        ),
        patch("backend.services.cache_service.get_settings") as mock_settings,
    ):
        mock_settings.return_value.cache_swr_enabled = True
        mock_settings.return_value.cache_swr_stale_ttl = 60

        await get_item("123")

        # Check that the key was generated correctly
        call_args = mock_cache.get_or_set_swr.call_args
        assert call_args[1]["key"] == "items:123"


@pytest.mark.asyncio
async def test_cached_swr_decorator_disabled_falls_back_to_regular():
    """Test cached_swr falls back to regular caching when SWR is disabled."""
    mock_cache = AsyncMock()
    mock_cache.get.return_value = {"cached": True}
    mock_cache.set.return_value = True

    @cached_swr("test:key", ttl=60)
    async def test_function():
        return {"fresh": True}

    with (
        patch(
            "backend.services.cache_service.get_cache_service",
            return_value=mock_cache,
        ),
        patch("backend.services.cache_service.get_settings") as mock_settings,
    ):
        mock_settings.return_value.cache_swr_enabled = False

        result = await test_function()

        assert result == {"cached": True}
        # Should use regular get, not get_or_set_swr
        mock_cache.get.assert_called_once()
        mock_cache.get_or_set_swr.assert_not_called()


@pytest.mark.asyncio
async def test_cached_swr_decorator_preserves_function_metadata():
    """Test cached_swr decorator preserves function name and docstring."""

    @cached_swr("test:key")
    async def my_function():
        """My docstring."""
        return "result"

    assert my_function.__name__ == "my_function"
    assert my_function.__doc__ == "My docstring."


@pytest.mark.asyncio
async def test_cached_swr_decorator_handles_redis_error():
    """Test cached_swr decorator falls back on Redis error."""
    from redis.exceptions import RedisError

    mock_cache = AsyncMock()
    mock_cache.get_or_set_swr = AsyncMock(side_effect=RedisError("Connection failed"))

    call_count = 0

    @cached_swr("test:key", ttl=60)
    async def test_function():
        nonlocal call_count
        call_count += 1
        return {"fresh": True}

    with (
        patch(
            "backend.services.cache_service.get_cache_service",
            return_value=mock_cache,
        ),
        patch("backend.services.cache_service.get_settings") as mock_settings,
    ):
        mock_settings.return_value.cache_swr_enabled = True
        mock_settings.return_value.cache_swr_stale_ttl = 60

        result = await test_function()

        assert result == {"fresh": True}
        assert call_count == 1  # Function was called directly as fallback


# =============================================================================
# Configuration Tests
# =============================================================================


@pytest.mark.asyncio
async def test_swr_uses_default_stale_ttl_from_settings(cache_service, mock_redis_client):
    """Test SWR uses default stale_ttl from settings when not provided."""
    mock_redis_client.get.return_value = None
    mock_redis_client.set.return_value = True

    async def factory():
        return {"data": "value"}

    with patch("backend.services.cache_service.get_settings") as mock_settings:
        mock_settings.return_value.cache_swr_stale_ttl = 120

        await cache_service.get_or_set_swr(
            "test:key",
            factory,
            ttl=60,
            # stale_ttl not provided
        )

        # Verify set was called
        assert mock_redis_client.set.called
