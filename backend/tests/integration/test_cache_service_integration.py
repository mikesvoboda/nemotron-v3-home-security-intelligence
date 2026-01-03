"""Integration tests for CacheService with real Redis.

These tests verify the CacheService behavior against a real Redis instance,
covering scenarios that cannot be properly tested with mocks:
- TTL expiration verification
- Pattern-based invalidation with actual key scanning
- Concurrent cache access
- Cache hit/miss behavior
- Multi-key operations

Uses the real_redis fixture from conftest.py for actual Redis connections.

IMPORTANT: These tests must be run serially (-n0) due to shared Redis state.
The real_redis fixture flushes the database, which causes race conditions
when tests run in parallel. Run with:

    uv run pytest backend/tests/integration/test_cache_service_integration.py -n0

Each test uses a unique key prefix to avoid collisions within serial execution.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import TYPE_CHECKING

import pytest

from backend.services.cache_service import (
    CACHE_PREFIX,
    CacheService,
)

if TYPE_CHECKING:
    from backend.core.redis import RedisClient

# Mark as integration tests
pytestmark = pytest.mark.integration


# =============================================================================
# Fixtures
# =============================================================================


def _unique_prefix() -> str:
    """Generate a unique prefix for test isolation in parallel test runs."""
    return f"test_{uuid.uuid4().hex[:8]}"


@pytest.fixture
async def cache_service(real_redis: RedisClient) -> CacheService:
    """Create a CacheService with a real Redis client."""
    return CacheService(real_redis)


@pytest.fixture
async def test_prefix() -> str:
    """Generate a unique prefix for this test to avoid key collisions."""
    return _unique_prefix()


@pytest.fixture
async def cleanup_keys(real_redis: RedisClient, test_prefix: str):
    """Clean up test keys after test completion."""
    yield

    # Cleanup after test - delete all keys with this test's prefix
    client = real_redis._ensure_connected()
    keys = []
    async for key in client.scan_iter(match=f"{CACHE_PREFIX}{test_prefix}*", count=100):
        keys.append(key)
    if keys:
        await client.delete(*keys)


# =============================================================================
# Basic Get/Set Operations Tests
# =============================================================================


class TestBasicCacheOperations:
    """Test basic get/set operations with real Redis."""

    @pytest.mark.asyncio
    async def test_set_and_get_string_value(
        self, cache_service: CacheService, test_prefix: str, cleanup_keys: None
    ) -> None:
        """Test setting and getting a string value."""
        key = f"{test_prefix}:string_key"
        value = "hello world"

        result = await cache_service.set(key, value)
        assert result is True

        retrieved = await cache_service.get(key)
        assert retrieved == value

    @pytest.mark.asyncio
    async def test_set_and_get_dict_value(
        self, cache_service: CacheService, test_prefix: str, cleanup_keys: None
    ) -> None:
        """Test setting and getting a dictionary value."""
        key = f"{test_prefix}:dict_key"
        value = {"name": "test", "count": 42, "nested": {"key": "value"}}

        result = await cache_service.set(key, value)
        assert result is True

        retrieved = await cache_service.get(key)
        assert retrieved == value

    @pytest.mark.asyncio
    async def test_set_and_get_list_value(
        self, cache_service: CacheService, test_prefix: str, cleanup_keys: None
    ) -> None:
        """Test setting and getting a list value."""
        key = f"{test_prefix}:list_key"
        value = [1, 2, 3, {"nested": True}]

        result = await cache_service.set(key, value)
        assert result is True

        retrieved = await cache_service.get(key)
        assert retrieved == value

    @pytest.mark.asyncio
    async def test_get_nonexistent_key_returns_none(
        self, cache_service: CacheService, test_prefix: str
    ) -> None:
        """Test that getting a non-existent key returns None."""
        result = await cache_service.get(f"{test_prefix}:definitely_not_exists")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_overwrites_existing_value(
        self, cache_service: CacheService, test_prefix: str, cleanup_keys: None
    ) -> None:
        """Test that set overwrites an existing value."""
        key = f"{test_prefix}:overwrite_key"

        await cache_service.set(key, "original")
        assert await cache_service.get(key) == "original"

        await cache_service.set(key, "updated")
        assert await cache_service.get(key) == "updated"

    @pytest.mark.asyncio
    async def test_cache_key_prefixing(
        self,
        cache_service: CacheService,
        real_redis: RedisClient,
        test_prefix: str,
        cleanup_keys: None,
    ) -> None:
        """Test that cache keys are properly prefixed with 'cache:'."""
        key = f"{test_prefix}:my_test_key"
        await cache_service.set(key, "value")

        # Verify the key is stored with the prefix in Redis
        client = real_redis._ensure_connected()
        full_key = f"{CACHE_PREFIX}{key}"

        # Use Redis EXISTS to verify the key exists
        exists = await client.exists(full_key)
        assert exists == 1

        # Verify unprefixed key does not exist
        exists_unprefixed = await client.exists(key)
        assert exists_unprefixed == 0


# =============================================================================
# TTL Expiration Tests
# =============================================================================


class TestTTLExpiration:
    """Test TTL (Time To Live) expiration behavior with real Redis."""

    @pytest.mark.asyncio
    async def test_key_expires_after_ttl(
        self, cache_service: CacheService, test_prefix: str, cleanup_keys: None
    ) -> None:
        """Test that a key expires after the specified TTL."""
        key = f"{test_prefix}:ttl_expiration"
        ttl = 1  # 1 second TTL

        await cache_service.set(key, "temporary_value", ttl=ttl)

        # Immediately should exist
        value = await cache_service.get(key)
        assert value == "temporary_value"

        # Wait for TTL to expire (add small buffer)
        await asyncio.sleep(ttl + 0.5)

        # Should be expired now
        value = await cache_service.get(key)
        assert value is None

    @pytest.mark.asyncio
    async def test_key_exists_before_ttl_expires(
        self, cache_service: CacheService, test_prefix: str, cleanup_keys: None
    ) -> None:
        """Test that a key exists before TTL expires."""
        key = f"{test_prefix}:ttl_exists"
        ttl = 10  # 10 seconds (increased for CI stability)

        await cache_service.set(key, "value", ttl=ttl)

        # Small delay to ensure Redis has processed the SET command
        await asyncio.sleep(0.05)

        # Should exist immediately
        assert await cache_service.exists(key) is True

        # Should still exist after partial TTL
        await asyncio.sleep(1)  # intentional: TTL integration test
        assert await cache_service.exists(key) is True
        assert await cache_service.get(key) == "value"

    @pytest.mark.asyncio
    @pytest.mark.timeout(15)  # Increase timeout for sleep tests
    async def test_refresh_extends_ttl(
        self,
        cache_service: CacheService,
        real_redis: RedisClient,
        test_prefix: str,
        cleanup_keys: None,
    ) -> None:
        """Test that refresh extends the TTL of a key."""
        key = f"{test_prefix}:refresh_ttl"
        initial_ttl = 3  # 3 seconds (increased for CI stability)
        new_ttl = 15  # 15 seconds

        await cache_service.set(key, "value", ttl=initial_ttl)

        # Small delay to ensure Redis has processed the SET command
        await asyncio.sleep(0.05)

        # Refresh with longer TTL
        result = await cache_service.refresh(key, ttl=new_ttl)
        assert result is True

        # Wait for initial TTL to pass
        await asyncio.sleep(initial_ttl + 1)

        # Key should still exist due to extended TTL
        value = await cache_service.get(key)
        assert value == "value"

    @pytest.mark.asyncio
    async def test_refresh_nonexistent_key_returns_false(
        self, cache_service: CacheService, test_prefix: str
    ) -> None:
        """Test that refresh returns False for non-existent key."""
        result = await cache_service.refresh(f"{test_prefix}:nonexistent_key", ttl=60)
        assert result is False

    @pytest.mark.asyncio
    @pytest.mark.timeout(10)  # Increase timeout for sleep tests
    async def test_multiple_keys_with_different_ttls(
        self, cache_service: CacheService, test_prefix: str, cleanup_keys: None
    ) -> None:
        """Test multiple keys with different TTLs expire independently."""
        short_key = f"{test_prefix}:short_ttl_key"
        long_key = f"{test_prefix}:long_ttl_key"

        await cache_service.set(short_key, "short", ttl=2)  # 2 seconds
        await cache_service.set(long_key, "long", ttl=15)  # 15 seconds (increased for CI stability)

        # Small delay to ensure Redis has processed the SET commands
        await asyncio.sleep(0.05)

        # Both should exist initially
        assert await cache_service.get(short_key) == "short"
        assert await cache_service.get(long_key) == "long"

        # Wait for short TTL to expire
        await asyncio.sleep(2.5)  # intentional: TTL integration test

        # Short should be gone, long should remain
        assert await cache_service.get(short_key) is None
        assert await cache_service.get(long_key) == "long"


# =============================================================================
# Cache Invalidation Tests
# =============================================================================


class TestCacheInvalidation:
    """Test cache invalidation operations with real Redis."""

    @pytest.mark.asyncio
    async def test_invalidate_existing_key(
        self, cache_service: CacheService, test_prefix: str, cleanup_keys: None
    ) -> None:
        """Test invalidating an existing key."""
        key = f"{test_prefix}:invalidate_existing"
        await cache_service.set(key, "value")

        # Verify it exists
        assert await cache_service.exists(key) is True

        # Invalidate
        result = await cache_service.invalidate(key)
        assert result is True

        # Verify it's gone
        assert await cache_service.exists(key) is False
        assert await cache_service.get(key) is None

    @pytest.mark.asyncio
    async def test_invalidate_nonexistent_key_returns_false(
        self, cache_service: CacheService, test_prefix: str
    ) -> None:
        """Test invalidating a non-existent key returns False."""
        result = await cache_service.invalidate(f"{test_prefix}:nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_invalidate_pattern_deletes_matching_keys(
        self, cache_service: CacheService, test_prefix: str, cleanup_keys: None
    ) -> None:
        """Test pattern-based invalidation deletes all matching keys."""
        # Create multiple keys with same prefix
        await cache_service.set(f"{test_prefix}:cameras:cam1", {"id": "cam1"})
        await cache_service.set(f"{test_prefix}:cameras:cam2", {"id": "cam2"})
        await cache_service.set(f"{test_prefix}:cameras:cam3", {"id": "cam3"})
        await cache_service.set(f"{test_prefix}:other:key", "should_remain")

        # Verify all exist
        assert await cache_service.exists(f"{test_prefix}:cameras:cam1") is True
        assert await cache_service.exists(f"{test_prefix}:cameras:cam2") is True
        assert await cache_service.exists(f"{test_prefix}:cameras:cam3") is True
        assert await cache_service.exists(f"{test_prefix}:other:key") is True

        # Invalidate by pattern
        deleted_count = await cache_service.invalidate_pattern(f"{test_prefix}:cameras:*")
        assert deleted_count == 3

        # Verify cameras keys are gone
        assert await cache_service.exists(f"{test_prefix}:cameras:cam1") is False
        assert await cache_service.exists(f"{test_prefix}:cameras:cam2") is False
        assert await cache_service.exists(f"{test_prefix}:cameras:cam3") is False

        # Verify other key remains
        assert await cache_service.exists(f"{test_prefix}:other:key") is True

    @pytest.mark.asyncio
    async def test_invalidate_pattern_with_no_matches(
        self, cache_service: CacheService, test_prefix: str, cleanup_keys: None
    ) -> None:
        """Test pattern invalidation with no matching keys returns 0."""
        await cache_service.set(f"{test_prefix}:some:key", "value")

        deleted_count = await cache_service.invalidate_pattern(f"{test_prefix}:nonexistent:*")
        assert deleted_count == 0

        # Original key should still exist
        assert await cache_service.exists(f"{test_prefix}:some:key") is True

    @pytest.mark.asyncio
    async def test_invalidate_pattern_with_nested_keys(
        self, cache_service: CacheService, test_prefix: str, cleanup_keys: None
    ) -> None:
        """Test pattern invalidation with nested key structures."""
        await cache_service.set(f"{test_prefix}:events:2024:01:event1", {"id": 1})
        await cache_service.set(f"{test_prefix}:events:2024:01:event2", {"id": 2})
        await cache_service.set(f"{test_prefix}:events:2024:02:event1", {"id": 3})
        await cache_service.set(f"{test_prefix}:events:2023:12:event1", {"id": 4})

        # Invalidate all 2024-01 events
        deleted_count = await cache_service.invalidate_pattern(f"{test_prefix}:events:2024:01:*")
        assert deleted_count == 2

        # Verify 2024-01 events are gone
        assert await cache_service.exists(f"{test_prefix}:events:2024:01:event1") is False
        assert await cache_service.exists(f"{test_prefix}:events:2024:01:event2") is False

        # Verify other events remain
        assert await cache_service.exists(f"{test_prefix}:events:2024:02:event1") is True
        assert await cache_service.exists(f"{test_prefix}:events:2023:12:event1") is True


# =============================================================================
# Cache-Aside Pattern (get_or_set) Tests
# =============================================================================


class TestCacheAsidePattern:
    """Test cache-aside (get_or_set) pattern with real Redis."""

    @pytest.mark.asyncio
    async def test_get_or_set_returns_cached_on_hit(
        self, cache_service: CacheService, test_prefix: str, cleanup_keys: None
    ) -> None:
        """Test get_or_set returns cached value without calling factory."""
        key = f"{test_prefix}:get_or_set_hit"
        factory_calls = 0

        # Pre-populate cache
        await cache_service.set(key, {"cached": True})

        def factory():
            nonlocal factory_calls
            factory_calls += 1
            return {"fresh": True}

        result = await cache_service.get_or_set(key, factory)

        assert result == {"cached": True}
        assert factory_calls == 0

    @pytest.mark.asyncio
    async def test_get_or_set_calls_factory_on_miss(
        self, cache_service: CacheService, test_prefix: str, cleanup_keys: None
    ) -> None:
        """Test get_or_set calls factory on cache miss and caches result."""
        key = f"{test_prefix}:get_or_set_miss"
        factory_calls = 0

        def factory():
            nonlocal factory_calls
            factory_calls += 1
            return {"fresh": True}

        result = await cache_service.get_or_set(key, factory)

        assert result == {"fresh": True}
        assert factory_calls == 1

        # Verify result was cached
        cached = await cache_service.get(key)
        assert cached == {"fresh": True}

    @pytest.mark.asyncio
    async def test_get_or_set_with_async_factory(
        self, cache_service: CacheService, test_prefix: str, cleanup_keys: None
    ) -> None:
        """Test get_or_set works with async factory functions."""
        key = f"{test_prefix}:async_factory"

        async def async_factory():
            await asyncio.sleep(0.01)  # Simulate async operation
            return {"async": "result", "timestamp": 12345}

        result = await cache_service.get_or_set(key, async_factory)

        assert result == {"async": "result", "timestamp": 12345}

        # Verify cached
        cached = await cache_service.get(key)
        assert cached == {"async": "result", "timestamp": 12345}

    @pytest.mark.asyncio
    async def test_get_or_set_respects_ttl(
        self, cache_service: CacheService, test_prefix: str, cleanup_keys: None
    ) -> None:
        """Test get_or_set respects the provided TTL."""
        key = f"{test_prefix}:get_or_set_ttl"
        ttl = 1

        def factory():
            return "ephemeral_value"

        await cache_service.get_or_set(key, factory, ttl=ttl)

        # Should exist immediately
        assert await cache_service.get(key) == "ephemeral_value"

        # Wait for expiration
        await asyncio.sleep(ttl + 0.5)

        # Should be expired
        assert await cache_service.get(key) is None

    @pytest.mark.asyncio
    async def test_get_or_set_subsequent_calls_use_cache(
        self, cache_service: CacheService, test_prefix: str, cleanup_keys: None
    ) -> None:
        """Test that subsequent get_or_set calls use the cache."""
        key = f"{test_prefix}:subsequent_calls"
        factory_calls = 0

        def factory():
            nonlocal factory_calls
            factory_calls += 1
            return f"value_{factory_calls}"

        # First call - factory invoked
        result1 = await cache_service.get_or_set(key, factory)
        assert result1 == "value_1"
        assert factory_calls == 1

        # Second call - cache hit
        result2 = await cache_service.get_or_set(key, factory)
        assert result2 == "value_1"  # Same value from cache
        assert factory_calls == 1  # Factory not called again

        # Third call - still cached
        result3 = await cache_service.get_or_set(key, factory)
        assert result3 == "value_1"
        assert factory_calls == 1


# =============================================================================
# Concurrent Access Tests
# =============================================================================


class TestConcurrentAccess:
    """Test concurrent cache access with real Redis."""

    @pytest.mark.asyncio
    async def test_concurrent_set_operations(
        self, cache_service: CacheService, test_prefix: str, cleanup_keys: None
    ) -> None:
        """Test multiple concurrent set operations don't conflict."""
        keys_values = [(f"{test_prefix}:concurrent_key_{i}", f"value_{i}") for i in range(10)]

        async def set_value(key: str, value: str) -> bool:
            return await cache_service.set(key, value)

        # Run all sets concurrently
        results = await asyncio.gather(*[set_value(k, v) for k, v in keys_values])

        # All should succeed
        assert all(results)

        # All values should be retrievable
        for key, expected_value in keys_values:
            actual = await cache_service.get(key)
            assert actual == expected_value

    @pytest.mark.asyncio
    async def test_concurrent_get_operations(
        self, cache_service: CacheService, test_prefix: str, cleanup_keys: None
    ) -> None:
        """Test multiple concurrent get operations work correctly."""
        key = f"{test_prefix}:concurrent_get_key"
        value = {"data": "test", "items": [1, 2, 3]}

        await cache_service.set(key, value)

        async def get_value() -> dict:
            return await cache_service.get(key)

        # Run many gets concurrently
        results = await asyncio.gather(*[get_value() for _ in range(20)])

        # All should return the same value
        for result in results:
            assert result == value

    @pytest.mark.asyncio
    async def test_concurrent_get_or_set_thundering_herd(
        self, cache_service: CacheService, test_prefix: str, cleanup_keys: None
    ) -> None:
        """Test concurrent get_or_set calls (thundering herd scenario).

        Note: Without distributed locking, all concurrent misses will call
        the factory. This test verifies consistency of the final cached value.
        """
        key = f"{test_prefix}:thundering_herd_key"
        factory_calls = 0
        factory_lock = asyncio.Lock()

        async def factory():
            nonlocal factory_calls
            async with factory_lock:
                factory_calls += 1
                current_call = factory_calls
            await asyncio.sleep(0.05)  # Simulate slow factory
            return {"call_number": current_call}

        # Start multiple concurrent get_or_set calls
        results = await asyncio.gather(*[cache_service.get_or_set(key, factory) for _ in range(5)])

        # All results should be valid dictionaries
        for result in results:
            assert "call_number" in result

        # The cached value should be consistent
        cached = await cache_service.get(key)
        assert cached is not None
        assert "call_number" in cached

    @pytest.mark.asyncio
    async def test_concurrent_set_and_invalidate(
        self, cache_service: CacheService, test_prefix: str, cleanup_keys: None
    ) -> None:
        """Test concurrent set and invalidate operations."""
        key = f"{test_prefix}:set_invalidate_key"

        async def set_operation(value: int) -> bool:
            return await cache_service.set(key, value)

        async def invalidate_operation() -> bool:
            return await cache_service.invalidate(key)

        # Mix of set and invalidate operations
        operations = [
            set_operation(1),
            set_operation(2),
            invalidate_operation(),
            set_operation(3),
            set_operation(4),
            invalidate_operation(),
            set_operation(5),
        ]

        await asyncio.gather(*operations)

        # The final state depends on execution order, but should be consistent
        # (either a value exists or it doesn't)
        result = await cache_service.get(key)
        # Result is either None (invalidated last) or an integer (set last)
        assert result is None or isinstance(result, int)


# =============================================================================
# Cache Exists Tests
# =============================================================================


class TestCacheExists:
    """Test cache exists operations with real Redis."""

    @pytest.mark.asyncio
    async def test_exists_returns_true_for_existing_key(
        self, cache_service: CacheService, test_prefix: str, cleanup_keys: None
    ) -> None:
        """Test exists returns True for existing key."""
        key = f"{test_prefix}:existing_key"
        await cache_service.set(key, "value")

        result = await cache_service.exists(key)
        assert result is True

    @pytest.mark.asyncio
    async def test_exists_returns_false_for_missing_key(
        self, cache_service: CacheService, test_prefix: str
    ) -> None:
        """Test exists returns False for non-existent key."""
        result = await cache_service.exists(f"{test_prefix}:missing_key")
        assert result is False

    @pytest.mark.asyncio
    async def test_exists_returns_false_after_expiration(
        self, cache_service: CacheService, test_prefix: str, cleanup_keys: None
    ) -> None:
        """Test exists returns False after key expires."""
        key = f"{test_prefix}:expiring_key"
        await cache_service.set(key, "value", ttl=1)

        # Should exist immediately
        assert await cache_service.exists(key) is True

        # Wait for expiration
        await asyncio.sleep(1.5)  # intentional: TTL integration test

        # Should not exist after expiration
        assert await cache_service.exists(key) is False

    @pytest.mark.asyncio
    async def test_exists_returns_false_after_invalidation(
        self, cache_service: CacheService, test_prefix: str, cleanup_keys: None
    ) -> None:
        """Test exists returns False after invalidation."""
        key = f"{test_prefix}:invalidate_exists_key"
        await cache_service.set(key, "value")

        assert await cache_service.exists(key) is True

        await cache_service.invalidate(key)

        assert await cache_service.exists(key) is False


# =============================================================================
# CacheKeys Integration Tests
# =============================================================================


class TestCacheKeysIntegration:
    """Test cache operations using key patterns similar to CacheKeys helpers."""

    @pytest.mark.asyncio
    async def test_cameras_list_pattern(
        self, cache_service: CacheService, test_prefix: str, cleanup_keys: None
    ) -> None:
        """Test using cameras list key pattern with cache service."""
        key = f"{test_prefix}:cameras:list"
        cameras = [{"id": "cam1", "name": "Front"}, {"id": "cam2", "name": "Back"}]

        await cache_service.set(key, cameras)

        retrieved = await cache_service.get(key)
        assert retrieved == cameras

    @pytest.mark.asyncio
    async def test_camera_single_key_pattern(
        self, cache_service: CacheService, test_prefix: str, cleanup_keys: None
    ) -> None:
        """Test using single camera key pattern with cache service."""
        camera_id = "cam_test_123"
        key = f"{test_prefix}:cameras:{camera_id}"
        camera_data = {"id": camera_id, "name": "Test Camera", "status": "online"}

        await cache_service.set(key, camera_data)

        retrieved = await cache_service.get(key)
        assert retrieved == camera_data

    @pytest.mark.asyncio
    async def test_event_stats_key_pattern(
        self, cache_service: CacheService, test_prefix: str, cleanup_keys: None
    ) -> None:
        """Test using event stats key pattern with cache service."""
        key = f"{test_prefix}:stats:events:2024-01-01:2024-01-31"
        stats = {"total_events": 100, "high_risk": 5, "medium_risk": 20}

        await cache_service.set(key, stats)

        retrieved = await cache_service.get(key)
        assert retrieved == stats

    @pytest.mark.asyncio
    async def test_system_status_key_pattern(
        self, cache_service: CacheService, test_prefix: str, cleanup_keys: None
    ) -> None:
        """Test using system status key pattern with cache service."""
        key = f"{test_prefix}:system:status"
        status = {"healthy": True, "services": {"db": "ok", "redis": "ok"}}

        await cache_service.set(key, status)

        retrieved = await cache_service.get(key)
        assert retrieved == status

    @pytest.mark.asyncio
    async def test_invalidate_all_camera_keys_pattern(
        self, cache_service: CacheService, test_prefix: str, cleanup_keys: None
    ) -> None:
        """Test invalidating all camera-related keys with pattern."""
        # Set multiple camera-related keys
        await cache_service.set(f"{test_prefix}:cameras:list", [])
        await cache_service.set(f"{test_prefix}:cameras:list:online", [])
        await cache_service.set(f"{test_prefix}:cameras:list:offline", [])
        await cache_service.set(f"{test_prefix}:cameras:cam1", {})
        await cache_service.set(f"{test_prefix}:cameras:cam2", {})

        # Invalidate all cameras:* keys
        deleted = await cache_service.invalidate_pattern(f"{test_prefix}:cameras:*")
        assert deleted == 5

        # All should be gone
        assert await cache_service.exists(f"{test_prefix}:cameras:list") is False
        assert await cache_service.exists(f"{test_prefix}:cameras:cam1") is False


# =============================================================================
# Edge Cases and Error Handling Tests
# =============================================================================


class TestEdgeCases:
    """Test edge cases and error handling with real Redis."""

    @pytest.mark.asyncio
    async def test_cache_empty_string(
        self, cache_service: CacheService, test_prefix: str, cleanup_keys: None
    ) -> None:
        """Test caching an empty string works correctly.

        Empty strings are valid cached values and should be retrievable.
        """
        key = f"{test_prefix}:empty_string_key"
        await cache_service.set(key, "")

        # Empty string should be retrievable (not None)
        result = await cache_service.get(key)
        assert result == ""

        # The key should exist in Redis
        assert await cache_service.exists(key) is True

    @pytest.mark.asyncio
    async def test_cache_null_value(
        self, cache_service: CacheService, test_prefix: str, cleanup_keys: None
    ) -> None:
        """Test caching a null/None value."""
        key = f"{test_prefix}:null_value_key"
        await cache_service.set(key, None)

        # None should be stored and retrievable as null
        result = await cache_service.get(key)
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_complex_nested_structure(
        self, cache_service: CacheService, test_prefix: str, cleanup_keys: None
    ) -> None:
        """Test caching a complex nested data structure."""
        key = f"{test_prefix}:complex_structure"
        value = {
            "level1": {
                "level2": {
                    "level3": {
                        "array": [1, 2, {"nested_in_array": True}],
                        "boolean": False,
                        "number": 3.14159,
                        "null": None,
                    }
                }
            },
            "root_array": [[1, 2], [3, 4], {"mixed": "content"}],
        }

        await cache_service.set(key, value)

        retrieved = await cache_service.get(key)
        assert retrieved == value

    @pytest.mark.asyncio
    async def test_cache_unicode_content(
        self, cache_service: CacheService, test_prefix: str, cleanup_keys: None
    ) -> None:
        """Test caching content with unicode characters."""
        key = f"{test_prefix}:unicode_key"
        value = {
            "greeting": "Hello, world!",
            "emoji": "Test passed!",
            "chinese": "Chinese Characters",
            "arabic": "Arabic Characters",
        }

        await cache_service.set(key, value)

        retrieved = await cache_service.get(key)
        assert retrieved == value

    @pytest.mark.asyncio
    async def test_cache_large_value(
        self, cache_service: CacheService, test_prefix: str, cleanup_keys: None
    ) -> None:
        """Test caching a large value."""
        key = f"{test_prefix}:large_value_key"
        # Create a large value (~100KB)
        large_list = [{"index": i, "data": "x" * 100} for i in range(1000)]

        await cache_service.set(key, large_list)

        retrieved = await cache_service.get(key)
        assert retrieved == large_list

    @pytest.mark.asyncio
    async def test_special_characters_in_key(
        self, cache_service: CacheService, test_prefix: str, cleanup_keys: None
    ) -> None:
        """Test using special characters in cache keys."""
        # Keys with colons (common in namespacing)
        key = f"{test_prefix}:namespace:sub:item:123"
        await cache_service.set(key, "value")
        assert await cache_service.get(key) == "value"

    @pytest.mark.asyncio
    async def test_get_or_set_factory_exception_not_cached(
        self, cache_service: CacheService, test_prefix: str
    ) -> None:
        """Test that factory exceptions are not cached."""
        key = f"{test_prefix}:exception_factory_key"
        call_count = 0

        def failing_factory():
            nonlocal call_count
            call_count += 1
            raise ValueError("Factory failed")

        # First call should raise
        with pytest.raises(ValueError, match="Factory failed"):
            await cache_service.get_or_set(key, failing_factory)

        # Key should not be cached
        assert await cache_service.exists(key) is False

        # Second call should also raise (factory called again)
        with pytest.raises(ValueError, match="Factory failed"):
            await cache_service.get_or_set(key, failing_factory)

        # Factory should have been called twice
        assert call_count == 2


# =============================================================================
# Cache Metrics and Hit/Miss Verification Tests
# =============================================================================


class TestCacheMetrics:
    """Test cache hit/miss behavior verification with real Redis."""

    @pytest.mark.asyncio
    async def test_cache_hit_scenario(
        self, cache_service: CacheService, test_prefix: str, cleanup_keys: None
    ) -> None:
        """Test that cache hits return correct value."""
        key = f"{test_prefix}:hit_test_key"
        value = {"cached": True, "timestamp": 1234567890}

        # First, populate the cache
        await cache_service.set(key, value)

        # Now do multiple gets - all should be hits
        for _ in range(5):
            result = await cache_service.get(key)
            assert result == value

    @pytest.mark.asyncio
    async def test_cache_miss_scenario(self, cache_service: CacheService, test_prefix: str) -> None:
        """Test that cache misses return None."""
        # Get non-existent keys - all should be misses
        for i in range(5):
            result = await cache_service.get(f"{test_prefix}:nonexistent_key_{i}")
            assert result is None

    @pytest.mark.asyncio
    async def test_get_or_set_tracks_hit_miss(
        self, cache_service: CacheService, test_prefix: str, cleanup_keys: None
    ) -> None:
        """Test get_or_set hit/miss behavior."""
        key = f"{test_prefix}:get_or_set_metrics"
        factory_calls = 0

        def factory():
            nonlocal factory_calls
            factory_calls += 1
            return {"fresh": True}

        # First call is a miss (factory called)
        await cache_service.get_or_set(key, factory)
        assert factory_calls == 1

        # Subsequent calls are hits (factory not called)
        for _ in range(5):
            await cache_service.get_or_set(key, factory)
            assert factory_calls == 1  # Still 1, factory not called again


# =============================================================================
# Performance and Stress Tests
# =============================================================================


class TestCachePerformance:
    """Performance and stress tests for cache operations."""

    @pytest.mark.asyncio
    async def test_high_volume_operations(
        self, cache_service: CacheService, test_prefix: str, cleanup_keys: None
    ) -> None:
        """Test high volume of cache operations."""
        num_operations = 100

        # Write many keys
        for i in range(num_operations):
            await cache_service.set(f"{test_prefix}:perf_key_{i}", {"index": i})

        # Read all keys back
        for i in range(num_operations):
            result = await cache_service.get(f"{test_prefix}:perf_key_{i}")
            assert result == {"index": i}

        # Invalidate by pattern
        deleted = await cache_service.invalidate_pattern(f"{test_prefix}:perf_key_*")
        assert deleted == num_operations

    @pytest.mark.asyncio
    async def test_rapid_set_get_cycles(
        self, cache_service: CacheService, test_prefix: str, cleanup_keys: None
    ) -> None:
        """Test rapid set/get cycles on same key."""
        key = f"{test_prefix}:rapid_cycle_key"

        for i in range(50):
            await cache_service.set(key, i)
            result = await cache_service.get(key)
            assert result == i

    @pytest.mark.asyncio
    async def test_parallel_pattern_invalidation(
        self, cache_service: CacheService, test_prefix: str, cleanup_keys: None
    ) -> None:
        """Test parallel pattern invalidation doesn't cause issues."""
        # Create keys in multiple namespaces
        for ns in ["ns1", "ns2", "ns3"]:
            for i in range(10):
                await cache_service.set(f"{test_prefix}:{ns}:key_{i}", {"ns": ns, "index": i})

        # Invalidate all namespaces in parallel
        results = await asyncio.gather(
            cache_service.invalidate_pattern(f"{test_prefix}:ns1:*"),
            cache_service.invalidate_pattern(f"{test_prefix}:ns2:*"),
            cache_service.invalidate_pattern(f"{test_prefix}:ns3:*"),
        )

        # Each should have deleted 10 keys
        assert results == [10, 10, 10]

        # Verify all are gone
        for ns in ["ns1", "ns2", "ns3"]:
            for i in range(10):
                assert await cache_service.exists(f"{test_prefix}:{ns}:key_{i}") is False
