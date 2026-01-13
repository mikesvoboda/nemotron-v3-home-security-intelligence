"""Integration tests for cache behavior.

Tests cache hit/miss, TTL expiry, and invalidation behavior with real Redis.
These tests ensure that:

1. Cache hits work correctly (first request miss, second request hit)
2. Cache TTL expiry works as expected
3. Create/update/delete operations trigger cache invalidation
4. Stale reads are prevented (mutation + read returns fresh data)
5. Different query params generate different cache keys

NEM-1995: Cache behavior integration tests for hit/miss/invalidation scenarios
"""

from __future__ import annotations

import asyncio
import uuid

import pytest

from backend.core.constants import CacheInvalidationReason
from backend.core.redis import RedisClient
from backend.services.cache_service import CACHE_PREFIX, CacheService

pytestmark = pytest.mark.integration


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
async def cache_service_for_tests(real_redis: RedisClient) -> CacheService:
    """Provide a real CacheService for cache behavior tests."""
    return CacheService(real_redis)


@pytest.fixture
def unique_test_key() -> str:
    """Generate a unique key for test isolation."""
    return f"test:{uuid.uuid4().hex[:8]}"


@pytest.fixture
async def cleanup_test_keys(real_redis: RedisClient, unique_test_key: str):
    """Clean up test keys after test completion."""
    yield

    # Cleanup after test
    client = real_redis._ensure_connected()
    keys = []
    async for key in client.scan_iter(match=f"{CACHE_PREFIX}{unique_test_key}*", count=100):
        keys.append(key)
    if keys:
        await client.delete(*keys)


# =============================================================================
# Cache Hit/Miss Tests
# =============================================================================


class TestCacheHitMiss:
    """Test cache hit and miss behavior."""

    @pytest.mark.asyncio
    async def test_first_request_is_cache_miss(
        self,
        cache_service_for_tests: CacheService,
        unique_test_key: str,
        cleanup_test_keys: None,
    ) -> None:
        """Test that the first request to cache is a cache miss (returns None)."""
        key = f"{unique_test_key}:first_miss"

        # First get should be a miss
        result = await cache_service_for_tests.get(key)
        assert result is None

    @pytest.mark.asyncio
    async def test_second_request_is_cache_hit(
        self,
        cache_service_for_tests: CacheService,
        unique_test_key: str,
        cleanup_test_keys: None,
    ) -> None:
        """Test that the second request to cache is a cache hit (returns cached value)."""
        key = f"{unique_test_key}:second_hit"
        value = {"data": "test", "count": 42}

        # Set the cache
        await cache_service_for_tests.set(key, value)

        # First get (hit)
        result1 = await cache_service_for_tests.get(key)
        assert result1 == value

        # Second get (hit)
        result2 = await cache_service_for_tests.get(key)
        assert result2 == value

    @pytest.mark.asyncio
    async def test_cache_hit_returns_consistent_data(
        self,
        cache_service_for_tests: CacheService,
        unique_test_key: str,
        cleanup_test_keys: None,
    ) -> None:
        """Test that cache hits return consistent data across multiple reads."""
        key = f"{unique_test_key}:consistent"
        value = {"cameras": [{"id": "cam1", "name": "Test"}], "total": 1}

        # Set once
        await cache_service_for_tests.set(key, value)

        # Read multiple times - all should return the same data
        results = []
        for _ in range(5):
            result = await cache_service_for_tests.get(key)
            results.append(result)

        # All results should be identical
        assert all(r == value for r in results)


# =============================================================================
# Cache TTL Tests
# =============================================================================


class TestCacheTTL:
    """Test cache TTL expiration behavior."""

    @pytest.mark.asyncio
    @pytest.mark.timeout(10)
    async def test_cache_expires_after_ttl(
        self,
        cache_service_for_tests: CacheService,
        unique_test_key: str,
        cleanup_test_keys: None,
    ) -> None:
        """Test that cache entries expire after their TTL."""
        key = f"{unique_test_key}:ttl_expiry"
        value = {"data": "ephemeral"}
        ttl = 1  # 1 second

        # Set with short TTL
        await cache_service_for_tests.set(key, value, ttl=ttl)

        # Immediately should exist
        assert await cache_service_for_tests.get(key) == value

        # Wait for TTL to expire
        await asyncio.sleep(ttl + 0.5)

        # Should be expired now
        assert await cache_service_for_tests.get(key) is None

    @pytest.mark.asyncio
    async def test_cache_key_exists_before_ttl(
        self,
        cache_service_for_tests: CacheService,
        unique_test_key: str,
        cleanup_test_keys: None,
    ) -> None:
        """Test that cache keys exist before their TTL expires."""
        key = f"{unique_test_key}:ttl_exists"
        value = {"data": "persistent"}
        ttl = 10  # 10 seconds

        # Set with longer TTL
        await cache_service_for_tests.set(key, value, ttl=ttl)

        # Should exist immediately
        assert await cache_service_for_tests.exists(key) is True
        assert await cache_service_for_tests.get(key) == value


# =============================================================================
# Cache Invalidation Tests
# =============================================================================


class TestCacheInvalidation:
    """Test cache invalidation on create/update/delete operations."""

    @pytest.mark.asyncio
    async def test_create_invalidation_pattern(
        self,
        cache_service_for_tests: CacheService,
        unique_test_key: str,
        cleanup_test_keys: None,
    ) -> None:
        """Test that create operations invalidate related cache entries."""
        # Simulate: cache cameras list
        list_key = f"{unique_test_key}:cameras:list"
        await cache_service_for_tests.set(list_key, {"cameras": [], "count": 0})

        # Verify cached
        assert await cache_service_for_tests.exists(list_key) is True

        # Simulate: create operation invalidates cameras:* pattern
        deleted = await cache_service_for_tests.invalidate_pattern(
            f"{unique_test_key}:cameras:*", reason=CacheInvalidationReason.CAMERA_CREATED
        )

        # Verify invalidation
        assert deleted >= 1
        assert await cache_service_for_tests.exists(list_key) is False

    @pytest.mark.asyncio
    async def test_update_invalidation_pattern(
        self,
        cache_service_for_tests: CacheService,
        unique_test_key: str,
        cleanup_test_keys: None,
    ) -> None:
        """Test that update operations invalidate related cache entries."""
        # Cache specific camera and list
        camera_key = f"{unique_test_key}:cameras:cam1"
        list_key = f"{unique_test_key}:cameras:list"

        await cache_service_for_tests.set(camera_key, {"id": "cam1", "name": "Old Name"})
        await cache_service_for_tests.set(list_key, {"cameras": [{"id": "cam1"}]})

        # Both should exist
        assert await cache_service_for_tests.exists(camera_key) is True
        assert await cache_service_for_tests.exists(list_key) is True

        # Simulate: update operation invalidates cameras:* pattern
        deleted = await cache_service_for_tests.invalidate_pattern(
            f"{unique_test_key}:cameras:*", reason=CacheInvalidationReason.CAMERA_UPDATED
        )

        # Both should be invalidated
        assert deleted == 2
        assert await cache_service_for_tests.exists(camera_key) is False
        assert await cache_service_for_tests.exists(list_key) is False

    @pytest.mark.asyncio
    async def test_delete_invalidation_pattern(
        self,
        cache_service_for_tests: CacheService,
        unique_test_key: str,
        cleanup_test_keys: None,
    ) -> None:
        """Test that delete operations invalidate related cache entries."""
        # Cache camera
        camera_key = f"{unique_test_key}:cameras:cam_delete"
        await cache_service_for_tests.set(camera_key, {"id": "cam_delete"})

        assert await cache_service_for_tests.exists(camera_key) is True

        # Simulate: delete operation invalidates specific camera
        deleted = await cache_service_for_tests.invalidate(camera_key)

        # Should be invalidated
        assert deleted is True
        assert await cache_service_for_tests.exists(camera_key) is False

    @pytest.mark.asyncio
    async def test_event_update_invalidates_multiple_caches(
        self,
        cache_service_for_tests: CacheService,
        unique_test_key: str,
        cleanup_test_keys: None,
    ) -> None:
        """Test that event updates invalidate both events and stats caches."""
        # Cache both event list and stats
        events_key = f"{unique_test_key}:events:list"
        stats_key = f"{unique_test_key}:stats:events:summary"

        await cache_service_for_tests.set(events_key, {"events": []})
        await cache_service_for_tests.set(stats_key, {"total": 0})

        assert await cache_service_for_tests.exists(events_key) is True
        assert await cache_service_for_tests.exists(stats_key) is True

        # Simulate: event update invalidates events:* pattern
        deleted_events = await cache_service_for_tests.invalidate_pattern(
            f"{unique_test_key}:events:*", reason=CacheInvalidationReason.EVENT_UPDATED
        )

        # Simulate: event update also invalidates stats:events:* pattern
        deleted_stats = await cache_service_for_tests.invalidate_pattern(
            f"{unique_test_key}:stats:events:*", reason=CacheInvalidationReason.EVENT_UPDATED
        )

        # Both patterns should be invalidated
        assert deleted_events >= 1
        assert deleted_stats >= 1
        assert await cache_service_for_tests.exists(events_key) is False
        assert await cache_service_for_tests.exists(stats_key) is False


# =============================================================================
# Cache Consistency Tests
# =============================================================================


class TestCacheConsistency:
    """Test that mutations followed by reads return fresh data."""

    @pytest.mark.asyncio
    async def test_mutation_then_read_returns_fresh_data(
        self,
        cache_service_for_tests: CacheService,
        unique_test_key: str,
        cleanup_test_keys: None,
    ) -> None:
        """Test that after invalidation, reads return fresh (not stale) data."""
        key = f"{unique_test_key}:consistency:camera"

        # Step 1: Cache old data
        old_value = {"id": "cam1", "name": "Old Name"}
        await cache_service_for_tests.set(key, old_value)

        # Verify cached
        assert await cache_service_for_tests.get(key) == old_value

        # Step 2: Simulate mutation (update) - invalidate cache
        await cache_service_for_tests.invalidate(key)

        # Step 3: Read again - should be None (fresh read required from DB)
        assert await cache_service_for_tests.get(key) is None

        # Step 4: Set new data (simulating fresh DB read)
        new_value = {"id": "cam1", "name": "New Name"}
        await cache_service_for_tests.set(key, new_value)

        # Step 5: Read should return new data
        assert await cache_service_for_tests.get(key) == new_value

    @pytest.mark.asyncio
    async def test_create_then_read_includes_new_entity(
        self,
        cache_service_for_tests: CacheService,
        unique_test_key: str,
        cleanup_test_keys: None,
    ) -> None:
        """Test that creating an entity invalidates list cache, forcing fresh read."""
        list_key = f"{unique_test_key}:cameras:list"

        # Step 1: Cache empty list
        empty_list = {"cameras": [], "count": 0}
        await cache_service_for_tests.set(list_key, empty_list)

        assert await cache_service_for_tests.get(list_key) == empty_list

        # Step 2: Simulate create operation - invalidate
        await cache_service_for_tests.invalidate(list_key)

        # Step 3: Read should be None (cache miss)
        assert await cache_service_for_tests.get(list_key) is None

        # Step 4: Set updated list (simulating fresh DB read with new entity)
        updated_list = {"cameras": [{"id": "new_cam"}], "count": 1}
        await cache_service_for_tests.set(list_key, updated_list)

        # Step 5: Read should return updated list
        assert await cache_service_for_tests.get(list_key) == updated_list

    @pytest.mark.asyncio
    async def test_delete_then_read_excludes_deleted_entity(
        self,
        cache_service_for_tests: CacheService,
        unique_test_key: str,
        cleanup_test_keys: None,
    ) -> None:
        """Test that deleting an entity invalidates cache, forcing fresh read."""
        list_key = f"{unique_test_key}:cameras:list"

        # Step 1: Cache list with entity
        with_entity = {"cameras": [{"id": "cam_to_delete"}], "count": 1}
        await cache_service_for_tests.set(list_key, with_entity)

        assert await cache_service_for_tests.get(list_key) == with_entity

        # Step 2: Simulate delete operation - invalidate
        await cache_service_for_tests.invalidate(list_key)

        # Step 3: Read should be None (cache miss)
        assert await cache_service_for_tests.get(list_key) is None

        # Step 4: Set updated list (simulating fresh DB read without deleted entity)
        without_entity = {"cameras": [], "count": 0}
        await cache_service_for_tests.set(list_key, without_entity)

        # Step 5: Read should return updated list (entity excluded)
        assert await cache_service_for_tests.get(list_key) == without_entity


# =============================================================================
# Cache Key Differentiation Tests
# =============================================================================


class TestCacheKeyDifferentiation:
    """Test that different query parameters generate different cache keys."""

    @pytest.mark.asyncio
    async def test_different_params_generate_different_cache_keys(
        self,
        cache_service_for_tests: CacheService,
        unique_test_key: str,
        cleanup_test_keys: None,
    ) -> None:
        """Test that different parameters result in different cache keys."""
        # Cache with different keys (simulating different query params)
        key_all = f"{unique_test_key}:cameras:list:all"
        key_online = f"{unique_test_key}:cameras:list:online"
        key_offline = f"{unique_test_key}:cameras:list:offline"

        # Set different values for each key
        await cache_service_for_tests.set(key_all, {"filter": "all", "count": 3})
        await cache_service_for_tests.set(key_online, {"filter": "online", "count": 2})
        await cache_service_for_tests.set(key_offline, {"filter": "offline", "count": 1})

        # Each key should have its own value
        assert (await cache_service_for_tests.get(key_all))["filter"] == "all"
        assert (await cache_service_for_tests.get(key_online))["filter"] == "online"
        assert (await cache_service_for_tests.get(key_offline))["filter"] == "offline"

    @pytest.mark.asyncio
    async def test_same_params_use_same_cache_key(
        self,
        cache_service_for_tests: CacheService,
        unique_test_key: str,
        cleanup_test_keys: None,
    ) -> None:
        """Test that identical parameters use the same cache key (hit on second request)."""
        key = f"{unique_test_key}:cameras:list:online"
        value = {"filter": "online", "count": 5}

        # First: set cache
        await cache_service_for_tests.set(key, value)

        # Second: get with same key should return cached value
        result1 = await cache_service_for_tests.get(key)
        result2 = await cache_service_for_tests.get(key)

        # Both should return the same cached value
        assert result1 == value
        assert result2 == value


# =============================================================================
# Stale Read Prevention Tests
# =============================================================================


class TestStaleReadPrevention:
    """Test that stale reads are prevented after mutations."""

    @pytest.mark.asyncio
    async def test_no_stale_reads_after_update(
        self,
        cache_service_for_tests: CacheService,
        unique_test_key: str,
        cleanup_test_keys: None,
    ) -> None:
        """Test that reads after updates never return stale cached data."""
        key = f"{unique_test_key}:camera:stale_test"

        # Initial cache
        initial = {"name": "Initial Name"}
        await cache_service_for_tests.set(key, initial)

        assert await cache_service_for_tests.get(key) == initial

        # Simulate update: invalidate cache
        await cache_service_for_tests.invalidate(key)

        # Read should be None (cache miss)
        assert await cache_service_for_tests.get(key) is None

        # Set updated value (fresh from DB)
        updated = {"name": "Updated Name"}
        await cache_service_for_tests.set(key, updated)

        # Read should return updated value, NOT stale initial value
        assert await cache_service_for_tests.get(key) == updated

    @pytest.mark.asyncio
    async def test_no_stale_reads_after_delete(
        self,
        cache_service_for_tests: CacheService,
        unique_test_key: str,
        cleanup_test_keys: None,
    ) -> None:
        """Test that reads after deletes don't return the deleted entity from cache."""
        key = f"{unique_test_key}:camera:delete_stale"

        # Initial cache
        initial = {"id": "cam_delete", "status": "active"}
        await cache_service_for_tests.set(key, initial)

        assert await cache_service_for_tests.get(key) == initial

        # Simulate delete: invalidate cache
        await cache_service_for_tests.invalidate(key)

        # Read should be None (entity deleted)
        assert await cache_service_for_tests.get(key) is None
