"""Unit tests for CacheService class.

This module tests the cache service that provides Redis-backed caching
with cache-aside pattern support. All Redis operations are mocked.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.cache_service import (
    CACHE_PREFIX,
    CAMERAS_PREFIX,
    DEFAULT_TTL,
    EVENTS_PREFIX,
    LONG_TTL,
    SHORT_TTL,
    STATS_PREFIX,
    CacheKeys,
    CacheService,
    get_cache_service,
    reset_cache_service,
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
    mock_client._ensure_connected = MagicMock()
    return mock_client


@pytest.fixture
def cache_service(mock_redis_client):
    """Create a CacheService with mocked Redis client."""
    return CacheService(mock_redis_client)


# =============================================================================
# CacheService Initialization Tests
# =============================================================================


def test_cache_service_initialization(mock_redis_client):
    """Test CacheService initializes with Redis client."""
    service = CacheService(mock_redis_client)

    assert service._redis is mock_redis_client


def test_cache_service_stores_redis_reference(mock_redis_client):
    """Test that CacheService keeps reference to the Redis client."""
    service = CacheService(mock_redis_client)

    # Verify the internal reference is set
    assert hasattr(service, "_redis")
    assert service._redis == mock_redis_client


# =============================================================================
# Cache Get Operation Tests
# =============================================================================


@pytest.mark.asyncio
async def test_cache_get_returns_value_on_hit(cache_service, mock_redis_client):
    """Test cache get returns value when key exists."""
    mock_redis_client.get.return_value = {"data": "test_value"}

    result = await cache_service.get("my_key")

    assert result == {"data": "test_value"}
    mock_redis_client.get.assert_awaited_once_with(f"{CACHE_PREFIX}my_key")


@pytest.mark.asyncio
async def test_cache_get_returns_none_on_miss(cache_service, mock_redis_client):
    """Test cache get returns None when key doesn't exist."""
    mock_redis_client.get.return_value = None

    result = await cache_service.get("nonexistent_key")

    assert result is None
    mock_redis_client.get.assert_awaited_once()


@pytest.mark.asyncio
async def test_cache_get_prefixes_key(cache_service, mock_redis_client):
    """Test cache get adds 'cache:' prefix to key."""
    mock_redis_client.get.return_value = "value"

    await cache_service.get("user:123")

    # Key should be prefixed with 'cache:'
    mock_redis_client.get.assert_awaited_once_with("cache:user:123")


@pytest.mark.asyncio
async def test_cache_get_handles_redis_error(cache_service, mock_redis_client):
    """Test cache get returns None and logs warning on Redis error."""
    mock_redis_client.get.side_effect = Exception("Redis connection failed")

    result = await cache_service.get("key")

    assert result is None


@pytest.mark.asyncio
async def test_cache_get_with_complex_data(cache_service, mock_redis_client):
    """Test cache get handles complex nested data structures."""
    complex_data = {
        "cameras": [{"id": "cam1", "name": "Front Door"}],
        "metadata": {"count": 1, "nested": {"deep": True}},
    }
    mock_redis_client.get.return_value = complex_data

    result = await cache_service.get("complex_key")

    assert result == complex_data


# =============================================================================
# Cache Set Operation Tests
# =============================================================================


@pytest.mark.asyncio
async def test_cache_set_stores_value(cache_service, mock_redis_client):
    """Test cache set stores value in Redis."""
    mock_redis_client.set.return_value = True

    result = await cache_service.set("my_key", {"data": "value"})

    assert result is True
    mock_redis_client.set.assert_awaited_once()


@pytest.mark.asyncio
async def test_cache_set_uses_default_ttl(cache_service, mock_redis_client):
    """Test cache set uses default TTL when not specified."""
    mock_redis_client.set.return_value = True

    await cache_service.set("key", "value")

    # Verify called with default TTL
    mock_redis_client.set.assert_awaited_once_with(
        f"{CACHE_PREFIX}key", "value", expire=DEFAULT_TTL
    )


@pytest.mark.asyncio
async def test_cache_set_uses_custom_ttl(cache_service, mock_redis_client):
    """Test cache set uses custom TTL when provided."""
    mock_redis_client.set.return_value = True

    await cache_service.set("key", "value", ttl=3600)

    mock_redis_client.set.assert_awaited_once_with(f"{CACHE_PREFIX}key", "value", expire=3600)


@pytest.mark.asyncio
async def test_cache_set_prefixes_key(cache_service, mock_redis_client):
    """Test cache set adds 'cache:' prefix to key."""
    mock_redis_client.set.return_value = True

    await cache_service.set("user:456", {"name": "test"})

    call_args = mock_redis_client.set.call_args
    assert call_args[0][0] == "cache:user:456"


@pytest.mark.asyncio
async def test_cache_set_returns_false_on_error(cache_service, mock_redis_client):
    """Test cache set returns False on Redis error."""
    mock_redis_client.set.side_effect = Exception("Redis error")

    result = await cache_service.set("key", "value")

    assert result is False


@pytest.mark.asyncio
async def test_cache_set_with_short_ttl(cache_service, mock_redis_client):
    """Test cache set with short TTL constant."""
    mock_redis_client.set.return_value = True

    await cache_service.set("key", "value", ttl=SHORT_TTL)

    mock_redis_client.set.assert_awaited_once_with(f"{CACHE_PREFIX}key", "value", expire=60)


@pytest.mark.asyncio
async def test_cache_set_with_long_ttl(cache_service, mock_redis_client):
    """Test cache set with long TTL constant."""
    mock_redis_client.set.return_value = True

    await cache_service.set("key", "value", ttl=LONG_TTL)

    mock_redis_client.set.assert_awaited_once_with(f"{CACHE_PREFIX}key", "value", expire=3600)


# =============================================================================
# Cache Get or Set (Cache-Aside Pattern) Tests
# =============================================================================


@pytest.mark.asyncio
async def test_get_or_set_returns_cached_value(cache_service, mock_redis_client):
    """Test get_or_set returns cached value on hit without calling factory."""
    mock_redis_client.get.return_value = {"cached": True}
    factory = MagicMock(return_value={"fresh": True})

    result = await cache_service.get_or_set("key", factory)

    assert result == {"cached": True}
    factory.assert_not_called()


@pytest.mark.asyncio
async def test_get_or_set_calls_factory_on_miss(cache_service, mock_redis_client):
    """Test get_or_set calls factory on cache miss."""
    mock_redis_client.get.return_value = None
    mock_redis_client.set.return_value = True
    factory = MagicMock(return_value={"fresh": True})

    result = await cache_service.get_or_set("key", factory)

    assert result == {"fresh": True}
    factory.assert_called_once()


@pytest.mark.asyncio
async def test_get_or_set_caches_factory_result(cache_service, mock_redis_client):
    """Test get_or_set stores factory result in cache."""
    mock_redis_client.get.return_value = None
    mock_redis_client.set.return_value = True
    factory = MagicMock(return_value={"fresh": True})

    await cache_service.get_or_set("key", factory, ttl=120)

    # Verify value was cached
    mock_redis_client.set.assert_awaited_once_with(
        f"{CACHE_PREFIX}key", {"fresh": True}, expire=120
    )


@pytest.mark.asyncio
async def test_get_or_set_with_async_factory(cache_service, mock_redis_client):
    """Test get_or_set works with async factory functions."""
    mock_redis_client.get.return_value = None
    mock_redis_client.set.return_value = True

    async def async_factory():
        return {"async": "result"}

    result = await cache_service.get_or_set("key", async_factory)

    assert result == {"async": "result"}
    mock_redis_client.set.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_or_set_propagates_factory_exception(cache_service, mock_redis_client):
    """Test get_or_set propagates exceptions from factory."""
    mock_redis_client.get.return_value = None

    def failing_factory():
        raise ValueError("Factory failed")

    with pytest.raises(ValueError, match="Factory failed"):
        await cache_service.get_or_set("key", failing_factory)


@pytest.mark.asyncio
async def test_get_or_set_uses_default_ttl(cache_service, mock_redis_client):
    """Test get_or_set uses default TTL when not specified."""
    mock_redis_client.get.return_value = None
    mock_redis_client.set.return_value = True
    factory = MagicMock(return_value="value")

    await cache_service.get_or_set("key", factory)

    # Verify default TTL was used
    call_args = mock_redis_client.set.call_args
    assert call_args[1]["expire"] == DEFAULT_TTL


# =============================================================================
# Cache Invalidation Tests
# =============================================================================


@pytest.mark.asyncio
async def test_invalidate_deletes_key(cache_service, mock_redis_client):
    """Test invalidate deletes the specified key."""
    mock_redis_client.delete.return_value = 1

    result = await cache_service.invalidate("key_to_delete")

    assert result is True
    mock_redis_client.delete.assert_awaited_once_with(f"{CACHE_PREFIX}key_to_delete")


@pytest.mark.asyncio
async def test_invalidate_returns_false_if_key_not_found(cache_service, mock_redis_client):
    """Test invalidate returns False if key doesn't exist."""
    mock_redis_client.delete.return_value = 0

    result = await cache_service.invalidate("nonexistent_key")

    assert result is False


@pytest.mark.asyncio
async def test_invalidate_handles_error(cache_service, mock_redis_client):
    """Test invalidate returns False on Redis error."""
    mock_redis_client.delete.side_effect = Exception("Redis error")

    result = await cache_service.invalidate("key")

    assert result is False


@pytest.mark.asyncio
async def test_invalidate_prefixes_key(cache_service, mock_redis_client):
    """Test invalidate adds 'cache:' prefix to key."""
    mock_redis_client.delete.return_value = 1

    await cache_service.invalidate("cameras:list")

    mock_redis_client.delete.assert_awaited_once_with("cache:cameras:list")


# =============================================================================
# Pattern Invalidation Tests
# =============================================================================


@pytest.mark.asyncio
async def test_invalidate_pattern_deletes_matching_keys(cache_service, mock_redis_client):
    """Test invalidate_pattern deletes all keys matching pattern."""
    # Setup mock to return keys during scan
    mock_scan_iter = AsyncMock()
    mock_scan_iter.__aiter__ = lambda self: self
    mock_scan_iter.__anext__ = AsyncMock(
        side_effect=[
            "cache:cameras:cam1",
            "cache:cameras:cam2",
            StopAsyncIteration,
        ]
    )

    mock_client = MagicMock()
    mock_client.scan_iter.return_value = mock_scan_iter
    mock_redis_client._ensure_connected.return_value = mock_client
    mock_redis_client.delete.return_value = 2

    result = await cache_service.invalidate_pattern("cameras:*")

    assert result == 2
    mock_client.scan_iter.assert_called_once_with(match=f"{CACHE_PREFIX}cameras:*", count=100)


@pytest.mark.asyncio
async def test_invalidate_pattern_returns_zero_when_no_matches(cache_service, mock_redis_client):
    """Test invalidate_pattern returns 0 when no keys match."""
    mock_scan_iter = AsyncMock()
    mock_scan_iter.__aiter__ = lambda self: self
    mock_scan_iter.__anext__ = AsyncMock(side_effect=StopAsyncIteration)

    mock_client = MagicMock()
    mock_client.scan_iter.return_value = mock_scan_iter
    mock_redis_client._ensure_connected.return_value = mock_client

    result = await cache_service.invalidate_pattern("nonexistent:*")

    assert result == 0
    mock_redis_client.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_invalidate_pattern_handles_error(cache_service, mock_redis_client):
    """Test invalidate_pattern returns 0 on error."""
    mock_redis_client._ensure_connected.side_effect = Exception("Redis error")

    result = await cache_service.invalidate_pattern("pattern:*")

    assert result == 0


# =============================================================================
# Cache Exists Tests
# =============================================================================


@pytest.mark.asyncio
async def test_exists_returns_true_when_key_exists(cache_service, mock_redis_client):
    """Test exists returns True when key exists."""
    mock_redis_client.exists.return_value = 1

    result = await cache_service.exists("my_key")

    assert result is True
    mock_redis_client.exists.assert_awaited_once_with(f"{CACHE_PREFIX}my_key")


@pytest.mark.asyncio
async def test_exists_returns_false_when_key_missing(cache_service, mock_redis_client):
    """Test exists returns False when key doesn't exist."""
    mock_redis_client.exists.return_value = 0

    result = await cache_service.exists("missing_key")

    assert result is False


@pytest.mark.asyncio
async def test_exists_handles_error(cache_service, mock_redis_client):
    """Test exists returns False on Redis error."""
    mock_redis_client.exists.side_effect = Exception("Redis error")

    result = await cache_service.exists("key")

    assert result is False


@pytest.mark.asyncio
async def test_exists_prefixes_key(cache_service, mock_redis_client):
    """Test exists adds 'cache:' prefix to key."""
    mock_redis_client.exists.return_value = 1

    await cache_service.exists("stats:daily")

    mock_redis_client.exists.assert_awaited_once_with("cache:stats:daily")


# =============================================================================
# Cache Refresh (TTL) Tests
# =============================================================================


@pytest.mark.asyncio
async def test_refresh_sets_new_ttl(cache_service, mock_redis_client):
    """Test refresh sets new TTL on existing key."""
    mock_redis_client.expire.return_value = True

    result = await cache_service.refresh("my_key", ttl=600)

    assert result is True
    mock_redis_client.expire.assert_awaited_once_with(f"{CACHE_PREFIX}my_key", 600)


@pytest.mark.asyncio
async def test_refresh_uses_default_ttl(cache_service, mock_redis_client):
    """Test refresh uses default TTL when not specified."""
    mock_redis_client.expire.return_value = True

    await cache_service.refresh("key")

    mock_redis_client.expire.assert_awaited_once_with(f"{CACHE_PREFIX}key", DEFAULT_TTL)


@pytest.mark.asyncio
async def test_refresh_returns_false_for_nonexistent_key(cache_service, mock_redis_client):
    """Test refresh returns False for non-existent key."""
    mock_redis_client.expire.return_value = False

    result = await cache_service.refresh("nonexistent_key")

    assert result is False


@pytest.mark.asyncio
async def test_refresh_handles_error(cache_service, mock_redis_client):
    """Test refresh returns False on Redis error."""
    mock_redis_client.expire.side_effect = Exception("Redis error")

    result = await cache_service.refresh("key")

    assert result is False


# =============================================================================
# CacheKeys Static Methods Tests
# =============================================================================


def test_cache_keys_cameras_list():
    """Test CacheKeys.cameras_list() returns correct key."""
    key = CacheKeys.cameras_list()

    assert key == "cameras:list"


def test_cache_keys_cameras_list_by_status_with_status():
    """Test CacheKeys.cameras_list_by_status() with status."""
    key = CacheKeys.cameras_list_by_status("online")

    assert key == "cameras:list:online"


def test_cache_keys_cameras_list_by_status_none():
    """Test CacheKeys.cameras_list_by_status() with None status."""
    key = CacheKeys.cameras_list_by_status(None)

    assert key == "cameras:list:all"


def test_cache_keys_camera():
    """Test CacheKeys.camera() returns correct key."""
    key = CacheKeys.camera("cam_123")

    assert key == "cameras:cam_123"


def test_cache_keys_event_stats_with_dates():
    """Test CacheKeys.event_stats() with date range."""
    key = CacheKeys.event_stats("2024-01-01", "2024-01-31")

    assert key == "stats:events:2024-01-01:2024-01-31"


def test_cache_keys_event_stats_no_dates():
    """Test CacheKeys.event_stats() without dates."""
    key = CacheKeys.event_stats()

    assert key == "stats:events:none:none"


def test_cache_keys_event_stats_partial_dates():
    """Test CacheKeys.event_stats() with only start date."""
    key = CacheKeys.event_stats(start_date="2024-01-01")

    assert key == "stats:events:2024-01-01:none"


def test_cache_keys_system_status():
    """Test CacheKeys.system_status() returns correct key."""
    key = CacheKeys.system_status()

    assert key == "system:status"


# =============================================================================
# TTL Constants Tests
# =============================================================================


def test_default_ttl_value():
    """Test DEFAULT_TTL is 5 minutes (300 seconds)."""
    assert DEFAULT_TTL == 300


def test_short_ttl_value():
    """Test SHORT_TTL is 1 minute (60 seconds)."""
    assert SHORT_TTL == 60


def test_long_ttl_value():
    """Test LONG_TTL is 1 hour (3600 seconds)."""
    assert LONG_TTL == 3600


# =============================================================================
# Cache Prefix Constants Tests
# =============================================================================


def test_cache_prefix_value():
    """Test CACHE_PREFIX constant."""
    assert CACHE_PREFIX == "cache:"


def test_cameras_prefix_includes_cache_prefix():
    """Test CAMERAS_PREFIX includes 'cache:'."""
    assert CAMERAS_PREFIX == "cache:cameras:"


def test_events_prefix_includes_cache_prefix():
    """Test EVENTS_PREFIX includes 'cache:'."""
    assert EVENTS_PREFIX == "cache:events:"


def test_stats_prefix_includes_cache_prefix():
    """Test STATS_PREFIX includes 'cache:'."""
    assert STATS_PREFIX == "cache:stats:"


# =============================================================================
# Singleton Pattern Tests
# =============================================================================


@pytest.mark.asyncio
async def test_get_cache_service_returns_singleton():
    """Test get_cache_service returns singleton instance."""
    # Reset singleton before test
    await reset_cache_service()

    with patch("backend.services.cache_service.init_redis") as mock_init:
        mock_redis = AsyncMock()
        mock_init.return_value = mock_redis

        service1 = await get_cache_service()
        service2 = await get_cache_service()

        assert service1 is service2
        # init_redis should only be called once
        mock_init.assert_called_once()

        # Cleanup
        await reset_cache_service()


@pytest.mark.asyncio
async def test_get_cache_service_initializes_redis():
    """Test get_cache_service initializes Redis connection."""
    await reset_cache_service()

    with patch("backend.services.cache_service.init_redis") as mock_init:
        mock_redis = AsyncMock()
        mock_init.return_value = mock_redis

        service = await get_cache_service()

        assert service is not None
        assert isinstance(service, CacheService)
        mock_init.assert_called_once()

        # Cleanup
        await reset_cache_service()


@pytest.mark.asyncio
async def test_reset_cache_service_clears_singleton():
    """Test reset_cache_service clears the singleton instance."""
    # First create a service
    with patch("backend.services.cache_service.init_redis") as mock_init:
        mock_redis = AsyncMock()
        mock_init.return_value = mock_redis

        service1 = await get_cache_service()
        await reset_cache_service()

        # Create new service - should call init_redis again
        mock_init.reset_mock()
        service2 = await get_cache_service()

        assert service1 is not service2
        mock_init.assert_called_once()

        # Cleanup
        await reset_cache_service()


# =============================================================================
# Error Handling Tests
# =============================================================================


@pytest.mark.asyncio
async def test_cache_operations_graceful_on_redis_unavailable(mock_redis_client):
    """Test cache operations handle Redis being unavailable gracefully."""
    # Configure all operations to fail
    mock_redis_client.get.side_effect = ConnectionError("Redis unavailable")
    mock_redis_client.set.side_effect = ConnectionError("Redis unavailable")
    mock_redis_client.delete.side_effect = ConnectionError("Redis unavailable")
    mock_redis_client.exists.side_effect = ConnectionError("Redis unavailable")
    mock_redis_client.expire.side_effect = ConnectionError("Redis unavailable")

    service = CacheService(mock_redis_client)

    # All operations should return graceful defaults
    assert await service.get("key") is None
    assert await service.set("key", "value") is False
    assert await service.invalidate("key") is False
    assert await service.exists("key") is False
    assert await service.refresh("key") is False


@pytest.mark.asyncio
async def test_get_or_set_still_works_when_cache_fails(mock_redis_client):
    """Test get_or_set returns factory result even when cache operations fail."""
    mock_redis_client.get.side_effect = ConnectionError("Redis unavailable")
    mock_redis_client.set.side_effect = ConnectionError("Redis unavailable")

    service = CacheService(mock_redis_client)

    def factory():
        return {"from": "factory"}

    # Should return factory result even though cache failed
    # Note: get returns None on error, which triggers factory
    result = await service.get_or_set("key", factory)

    assert result == {"from": "factory"}


# =============================================================================
# Concurrent Access Tests
# =============================================================================


@pytest.mark.asyncio
async def test_concurrent_get_or_set_calls(cache_service, mock_redis_client):
    """Test multiple concurrent get_or_set calls."""
    call_count = 0

    async def counting_factory():
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.01)
        return {"call": call_count}

    # First call hits cache miss, subsequent calls should also miss
    # (no locking in current implementation)
    mock_redis_client.get.return_value = None
    mock_redis_client.set.return_value = True

    results = await asyncio.gather(
        cache_service.get_or_set("key", counting_factory),
        cache_service.get_or_set("key", counting_factory),
        cache_service.get_or_set("key", counting_factory),
    )

    # Each call should have executed the factory (no distributed locking)
    assert len(results) == 3
    # All results should be valid
    for result in results:
        assert "call" in result


# =============================================================================
# Integration-Style Tests (With Mocks)
# =============================================================================


@pytest.mark.asyncio
async def test_cache_workflow_hit_scenario(cache_service, mock_redis_client):
    """Test typical cache hit workflow."""
    # Setup: Key already cached
    mock_redis_client.get.return_value = {"cameras": [{"id": "cam1"}]}

    # First, check if key exists
    mock_redis_client.exists.return_value = 1
    exists = await cache_service.exists("cameras:list")
    assert exists is True

    # Get the cached value
    result = await cache_service.get("cameras:list")
    assert result == {"cameras": [{"id": "cam1"}]}


@pytest.mark.asyncio
async def test_cache_workflow_miss_and_populate(cache_service, mock_redis_client):
    """Test typical cache miss and populate workflow."""
    # Setup: Key not cached
    mock_redis_client.get.return_value = None
    mock_redis_client.set.return_value = True

    def fetch_cameras():
        return [{"id": "cam1", "name": "Front"}]

    # Use get_or_set to fetch and cache
    result = await cache_service.get_or_set(
        CacheKeys.cameras_list(),
        fetch_cameras,
        ttl=SHORT_TTL,
    )

    assert result == [{"id": "cam1", "name": "Front"}]
    # Verify it was cached
    mock_redis_client.set.assert_awaited_once()


@pytest.mark.asyncio
async def test_cache_invalidation_workflow(cache_service, mock_redis_client):
    """Test cache invalidation workflow after data update."""
    mock_redis_client.delete.return_value = 1

    # Simulate: Camera was updated, invalidate its cache
    result = await cache_service.invalidate(CacheKeys.camera("cam1"))
    assert result is True

    # Also invalidate the list
    result = await cache_service.invalidate(CacheKeys.cameras_list())
    assert result is True

    assert mock_redis_client.delete.await_count == 2
