"""Integration tests for CacheService with real Redis.

These tests verify the CacheService functionality against a real Redis instance,
including TTL expiration, concurrent access, pattern-based invalidation, and
cache hit/miss metrics.

Test coverage:
- Real TTL expiration verification
- Concurrent get/set operations
- Pattern-based cache invalidation with real Redis
- Cache hit/miss metrics verification

Uses the real_redis fixture from conftest.py for actual Redis connections.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest

from backend.services.cache_service import CacheService

if TYPE_CHECKING:
    from backend.core.redis import RedisClient

# Mark as integration tests
pytestmark = pytest.mark.integration


class TestCacheTTLExpiration:
    """Test real TTL expiration with Redis."""

    @pytest.mark.asyncio
    async def test_value_expires_after_ttl(self, real_redis: RedisClient) -> None:
        """Test that a cached value expires after the TTL."""
        cache = CacheService(real_redis)
        key = "test_ttl_expiration"
        value = {"data": "test_value"}

        # Set with 1 second TTL
        result = await cache.set(key, value, ttl=1)
        assert result is True

        # Value should exist immediately
        cached = await cache.get(key)
        assert cached == value

        # Wait for TTL to expire (intentional delay for TTL verification)
        await asyncio.sleep(1.5)  # patched: intentional TTL test

        # Value should no longer exist
        cached_after_ttl = await cache.get(key)
        assert cached_after_ttl is None

    @pytest.mark.asyncio
    async def test_value_exists_before_ttl_expires(self, real_redis: RedisClient) -> None:
        """Test that a cached value exists before TTL expires."""
        cache = CacheService(real_redis)
        key = "test_ttl_exists"
        value = {"data": "test_value"}

        # Set with 2 second TTL
        await cache.set(key, value, ttl=2)

        # Check multiple times before expiration
        for _ in range(3):
            cached = await cache.get(key)
            assert cached == value
            await asyncio.sleep(0.3)

    @pytest.mark.asyncio
    async def test_refresh_extends_ttl(self, real_redis: RedisClient) -> None:
        """Test that refresh() extends the TTL of a cached key."""
        cache = CacheService(real_redis)
        key = "test_ttl_refresh"
        value = {"data": "refresh_test"}

        # Set with 1 second TTL
        await cache.set(key, value, ttl=1)

        # Wait 0.6 seconds, then refresh TTL to 2 seconds
        await asyncio.sleep(0.6)
        refresh_result = await cache.refresh(key, ttl=2)
        assert refresh_result is True

        # Wait another 1 second - original TTL would have expired
        await asyncio.sleep(1)  # patched: intentional TTL test

        # Value should still exist due to refresh
        cached = await cache.get(key)
        assert cached == value

        # Wait for new TTL to expire
        await asyncio.sleep(1.5)  # patched: intentional TTL test

        # Now value should be gone
        cached_after = await cache.get(key)
        assert cached_after is None


class TestConcurrentCacheAccess:
    """Test concurrent get/set operations."""

    @pytest.mark.asyncio
    async def test_concurrent_set_operations(self, real_redis: RedisClient) -> None:
        """Test multiple concurrent set operations."""
        cache = CacheService(real_redis)
        num_concurrent = 20

        async def set_value(idx: int) -> bool:
            return await cache.set(f"concurrent_set_{idx}", {"index": idx})

        # Run concurrent set operations
        tasks = [asyncio.create_task(set_value(i)) for i in range(num_concurrent)]
        results = await asyncio.gather(*tasks)

        # All should succeed
        assert all(results)

        # Verify all values were set correctly
        for i in range(num_concurrent):
            value = await cache.get(f"concurrent_set_{i}")
            assert value == {"index": i}

    @pytest.mark.asyncio
    async def test_concurrent_get_operations(self, real_redis: RedisClient) -> None:
        """Test multiple concurrent get operations for the same key."""
        cache = CacheService(real_redis)
        key = "concurrent_get_key"
        value = {"data": "shared_value"}

        # Set the value first
        await cache.set(key, value)

        num_concurrent = 50

        async def get_value() -> dict | None:
            return await cache.get(key)

        # Run concurrent get operations
        tasks = [asyncio.create_task(get_value()) for _ in range(num_concurrent)]
        results = await asyncio.gather(*tasks)

        # All should return the same value
        assert all(r == value for r in results)

    @pytest.mark.asyncio
    async def test_concurrent_get_set_mixed(self, real_redis: RedisClient) -> None:
        """Test concurrent mixed get/set operations."""
        cache = CacheService(real_redis)
        key = "concurrent_mixed_key"
        initial_value = {"version": 0}
        num_operations = 30

        # Set initial value
        await cache.set(key, initial_value)

        async def update_value(new_version: int) -> bool:
            return await cache.set(key, {"version": new_version})

        async def read_value() -> dict | None:
            return await cache.get(key)

        # Mix of read and write operations
        tasks = []
        for i in range(num_operations):
            if i % 3 == 0:
                tasks.append(asyncio.create_task(update_value(i)))
            else:
                tasks.append(asyncio.create_task(read_value()))

        results = await asyncio.gather(*tasks)

        # Count successes
        set_results = [r for i, r in enumerate(results) if i % 3 == 0]
        get_results = [r for i, r in enumerate(results) if i % 3 != 0]

        # All sets should succeed
        assert all(r is True for r in set_results)

        # All gets should return valid values
        assert all(r is not None and "version" in r for r in get_results)

    @pytest.mark.asyncio
    async def test_concurrent_get_or_set_same_key(self, real_redis: RedisClient) -> None:
        """Test concurrent get_or_set operations for the same key."""
        cache = CacheService(real_redis)
        key = "concurrent_get_or_set"
        factory_call_count = 0

        async def factory():
            nonlocal factory_call_count
            factory_call_count += 1
            # Simulate some work
            await asyncio.sleep(0.05)
            return {"computed": True, "call_count": factory_call_count}

        num_concurrent = 10

        # Run concurrent get_or_set operations
        tasks = [
            asyncio.create_task(cache.get_or_set(key, factory, ttl=60))
            for _ in range(num_concurrent)
        ]
        results = await asyncio.gather(*tasks)

        # All should return a valid result
        assert all(r is not None and r.get("computed") is True for r in results)

        # Value should be cached
        cached = await cache.get(key)
        assert cached is not None
        assert cached.get("computed") is True


class TestCacheInvalidationPatterns:
    """Test pattern-based invalidation with real Redis."""

    @pytest.mark.asyncio
    async def test_invalidate_single_key(self, real_redis: RedisClient) -> None:
        """Test invalidating a single cache key."""
        cache = CacheService(real_redis)
        key = "invalidate_single"
        value = {"data": "to_invalidate"}

        # Set the value
        await cache.set(key, value)
        assert await cache.get(key) == value

        # Invalidate
        result = await cache.invalidate(key)
        assert result is True

        # Should be gone
        assert await cache.get(key) is None

    @pytest.mark.asyncio
    async def test_invalidate_pattern_multiple_keys(self, real_redis: RedisClient) -> None:
        """Test invalidating multiple keys matching a pattern."""
        cache = CacheService(real_redis)
        base_pattern = "cameras"

        # Create multiple keys matching the pattern
        keys = [
            f"{base_pattern}:camera_1",
            f"{base_pattern}:camera_2",
            f"{base_pattern}:camera_3",
            f"{base_pattern}:list",
        ]

        for key in keys:
            await cache.set(key, {"key": key})

        # Create a key that should NOT be deleted
        unrelated_key = "events:event_1"
        await cache.set(unrelated_key, {"key": unrelated_key})

        # Verify all keys exist
        for key in keys:
            assert await cache.get(key) is not None
        assert await cache.get(unrelated_key) is not None

        # Invalidate all cameras:* keys
        deleted_count = await cache.invalidate_pattern(f"{base_pattern}:*")
        assert deleted_count == len(keys)

        # All cameras:* keys should be gone
        for key in keys:
            assert await cache.get(key) is None

        # Unrelated key should still exist
        assert await cache.get(unrelated_key) is not None

    @pytest.mark.asyncio
    async def test_invalidate_pattern_no_matches(self, real_redis: RedisClient) -> None:
        """Test invalidating a pattern with no matching keys."""
        cache = CacheService(real_redis)

        # Try to invalidate a pattern that doesn't exist
        deleted_count = await cache.invalidate_pattern("nonexistent:*")
        assert deleted_count == 0

    @pytest.mark.asyncio
    async def test_invalidate_nested_pattern(self, real_redis: RedisClient) -> None:
        """Test invalidating nested pattern keys."""
        cache = CacheService(real_redis)
        base = "stats"

        # Create nested keys
        keys = [
            f"{base}:events:daily",
            f"{base}:events:weekly",
            f"{base}:events:monthly",
            f"{base}:gpu:usage",
        ]

        for key in keys:
            await cache.set(key, {"key": key})

        # Invalidate only stats:events:* keys
        deleted = await cache.invalidate_pattern(f"{base}:events:*")
        assert deleted == 3

        # events keys should be gone
        assert await cache.get(f"{base}:events:daily") is None
        assert await cache.get(f"{base}:events:weekly") is None
        assert await cache.get(f"{base}:events:monthly") is None

        # gpu key should remain
        assert await cache.get(f"{base}:gpu:usage") is not None

    @pytest.mark.asyncio
    async def test_invalidate_all_with_wildcard(self, real_redis: RedisClient) -> None:
        """Test invalidating all cache keys with wildcard pattern."""
        cache = CacheService(real_redis)

        # Create various keys (these all get prefixed with 'cache:' by CacheService)
        keys = ["test1", "test2", "other1", "other2"]
        for key in keys:
            await cache.set(key, {"key": key})

        # Verify all exist
        for key in keys:
            assert await cache.get(key) is not None

        # Invalidate all with wildcard
        deleted = await cache.invalidate_pattern("*")
        assert deleted == len(keys)

        # All should be gone
        for key in keys:
            assert await cache.get(key) is None


class TestCacheHitMissMetrics:
    """Test that cache operations affect keyspace_hits/keyspace_misses metrics."""

    @pytest.mark.asyncio
    async def test_cache_hit_increments_keyspace_hits(self, real_redis: RedisClient) -> None:
        """Test that cache hits increment the keyspace_hits counter."""
        cache = CacheService(real_redis)

        # Enable keyspace notifications for accurate stats
        client = real_redis._ensure_connected()

        # Get initial stats
        initial_stats = await client.info("stats")
        initial_hits = int(initial_stats.get("keyspace_hits", 0))

        # Set a value
        key = "metrics_hit_test"
        await cache.set(key, {"data": "test"})

        # Perform multiple gets (cache hits)
        num_gets = 5
        for _ in range(num_gets):
            result = await cache.get(key)
            assert result is not None

        # Get updated stats
        updated_stats = await client.info("stats")
        updated_hits = int(updated_stats.get("keyspace_hits", 0))

        # Hits should have increased by at least num_gets
        # (might be slightly more due to internal operations)
        assert updated_hits >= initial_hits + num_gets

    @pytest.mark.asyncio
    async def test_cache_miss_increments_keyspace_misses(self, real_redis: RedisClient) -> None:
        """Test that cache misses increment the keyspace_misses counter."""
        cache = CacheService(real_redis)
        client = real_redis._ensure_connected()

        # Get initial stats
        initial_stats = await client.info("stats")
        initial_misses = int(initial_stats.get("keyspace_misses", 0))

        # Perform multiple gets for non-existent keys (cache misses)
        num_misses = 5
        for i in range(num_misses):
            result = await cache.get(f"nonexistent_key_{i}")
            assert result is None

        # Get updated stats
        updated_stats = await client.info("stats")
        updated_misses = int(updated_stats.get("keyspace_misses", 0))

        # Misses should have increased by at least num_misses
        assert updated_misses >= initial_misses + num_misses

    @pytest.mark.asyncio
    async def test_get_or_set_cache_miss_then_hit(self, real_redis: RedisClient) -> None:
        """Test get_or_set generates miss on first call, hit on subsequent calls."""
        cache = CacheService(real_redis)
        client = real_redis._ensure_connected()

        key = "get_or_set_metrics_test"

        # Ensure key doesn't exist
        await cache.invalidate(key)

        # Get initial stats
        initial_stats = await client.info("stats")
        initial_hits = int(initial_stats.get("keyspace_hits", 0))
        initial_misses = int(initial_stats.get("keyspace_misses", 0))

        # First call - should be a miss, then factory is called and value is set
        factory_calls = 0

        def factory():
            nonlocal factory_calls
            factory_calls += 1
            return {"data": "computed"}

        result1 = await cache.get_or_set(key, factory)
        assert result1 == {"data": "computed"}
        assert factory_calls == 1

        # Second call - should be a hit
        result2 = await cache.get_or_set(key, factory)
        assert result2 == {"data": "computed"}
        assert factory_calls == 1  # Factory should NOT be called again

        # Get updated stats
        updated_stats = await client.info("stats")
        updated_hits = int(updated_stats.get("keyspace_hits", 0))
        updated_misses = int(updated_stats.get("keyspace_misses", 0))

        # Should have at least 1 miss (first get_or_set) and 1 hit (second get_or_set)
        # The actual numbers might be higher due to internal operations
        assert updated_misses >= initial_misses + 1
        assert updated_hits >= initial_hits + 1

    @pytest.mark.asyncio
    async def test_exists_has_less_impact_on_metrics_than_get(
        self, real_redis: RedisClient
    ) -> None:
        """Test that exists() has less impact on hit/miss metrics than get().

        The EXISTS command in Redis may or may not count toward keyspace_hits/misses
        depending on Redis version, but GET operations definitely do. This test
        verifies that get() has at least as much impact on metrics as exists().
        """
        cache = CacheService(real_redis)
        client = real_redis._ensure_connected()
        num_operations = 10

        # Test with existing key - measure impact of exists() calls
        key_exists = "exists_impact_test_existing"
        await cache.set(key_exists, {"data": "test"})

        # Get baseline and measure exists() impact
        stats_before_exists = await client.info("stats")
        hits_before_exists = int(stats_before_exists.get("keyspace_hits", 0))

        for _ in range(num_operations):
            await cache.exists(key_exists)

        stats_after_exists = await client.info("stats")
        hits_after_exists = int(stats_after_exists.get("keyspace_hits", 0))
        exists_hit_impact = hits_after_exists - hits_before_exists

        # Now measure get() impact
        stats_before_get = await client.info("stats")
        hits_before_get = int(stats_before_get.get("keyspace_hits", 0))

        for _ in range(num_operations):
            await cache.get(key_exists)

        stats_after_get = await client.info("stats")
        hits_after_get = int(stats_after_get.get("keyspace_hits", 0))
        get_hit_impact = hits_after_get - hits_before_get

        # GET operations should definitely cause hits to increase by at least num_operations
        assert get_hit_impact >= num_operations, (
            f"Expected get() to cause at least {num_operations} hits, but got {get_hit_impact}"
        )

        # The exists impact should be less than or equal to get impact
        # (EXISTS may or may not contribute to hits depending on Redis version/config)
        # This verifies that the cache.exists() behavior is reasonable
        assert exists_hit_impact <= get_hit_impact + 5, (
            f"exists() caused more hits ({exists_hit_impact}) than get() ({get_hit_impact})"
        )


class TestCacheServiceErrorHandling:
    """Test CacheService error handling with real Redis."""

    @pytest.mark.asyncio
    async def test_get_nonexistent_key_returns_none(self, real_redis: RedisClient) -> None:
        """Test that getting a non-existent key returns None without error."""
        cache = CacheService(real_redis)
        result = await cache.get("definitely_does_not_exist_12345")
        assert result is None

    @pytest.mark.asyncio
    async def test_invalidate_nonexistent_key_returns_false(self, real_redis: RedisClient) -> None:
        """Test that invalidating a non-existent key returns False."""
        cache = CacheService(real_redis)
        result = await cache.invalidate("definitely_does_not_exist_67890")
        assert result is False

    @pytest.mark.asyncio
    async def test_refresh_nonexistent_key_returns_false(self, real_redis: RedisClient) -> None:
        """Test that refreshing a non-existent key returns False."""
        cache = CacheService(real_redis)
        result = await cache.refresh("definitely_does_not_exist_abcde", ttl=60)
        assert result is False

    @pytest.mark.asyncio
    async def test_cache_complex_data_types(self, real_redis: RedisClient) -> None:
        """Test caching various complex data types."""
        cache = CacheService(real_redis)

        test_cases = [
            ("nested_dict", {"a": {"b": {"c": [1, 2, 3]}}}),
            ("list_of_dicts", [{"id": 1}, {"id": 2}, {"id": 3}]),
            ("mixed_types", {"int": 42, "float": 3.14, "bool": True, "null": None}),
            ("unicode", {"text": "Hello, World!"}),
            ("empty_dict", {}),
            ("empty_list", []),
        ]

        for key, value in test_cases:
            # Set value
            result = await cache.set(key, value)
            assert result is True, f"Failed to set {key}"

            # Get value back
            cached = await cache.get(key)
            assert cached == value, f"Value mismatch for {key}: {cached} != {value}"
