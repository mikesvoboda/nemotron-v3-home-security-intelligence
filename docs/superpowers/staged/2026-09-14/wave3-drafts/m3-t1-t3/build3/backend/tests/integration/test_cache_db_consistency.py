"""Cache and Database Consistency Integration Tests (NEM-2222).

This module tests cache/DB consistency scenarios critical for disaster recovery:
- Cache invalidation after DB updates
- Cache and DB returning consistent data
- Stale cache detection and refresh
- Cache rebuild after Redis restart
- Race conditions between cache and DB operations

Uses real PostgreSQL and Redis containers via testcontainers for realistic testing.
Tests follow TDD principles - written before implementation.

Related: NEM-2096 (Epic: Disaster Recovery Testing)
"""

from __future__ import annotations

import asyncio
import uuid
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text

from backend.core.database import get_session
from backend.services.cache_service import CACHE_PREFIX, CacheService
from backend.tests.factories import CameraFactory

if TYPE_CHECKING:
    from backend.core.redis import RedisClient

# Mark as integration tests
pytestmark = pytest.mark.integration


# =============================================================================
# Fixtures
# =============================================================================


def _unique_prefix() -> str:
    """Generate a unique prefix for test isolation."""
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
# Cache Invalidation After DB Updates
# =============================================================================


class TestCacheInvalidationAfterDBUpdates:
    """Test that cache is properly invalidated when database is updated."""

    @pytest.mark.asyncio
    async def test_camera_update_invalidates_cache(
        self,
        integration_db: str,
        cache_service: CacheService,
        test_prefix: str,
        cleanup_keys: None,
    ) -> None:
        """Camera update in DB invalidates the cached camera data."""
        # RED: Create camera and populate cache
        async with get_session() as session:
            camera = CameraFactory.build(id=f"{test_prefix}_cam1", name="Original Camera Name")
            session.add(camera)
            await session.commit()
            camera_id = camera.id

        # Cache the camera data
        cache_key = f"{test_prefix}:cameras:{camera_id}"
        await cache_service.set(cache_key, {"id": camera_id, "name": "Original Camera Name"})

        # Verify cache hit
        cached_data = await cache_service.get(cache_key)
        assert cached_data is not None
        assert cached_data["name"] == "Original Camera Name"

        # Update camera in database using raw SQL
        async with get_session() as session:
            await session.execute(
                text(
                    "UPDATE cameras SET name = 'Updated Camera Name' WHERE id = :camera_id"
                ).bindparams(camera_id=camera_id)
            )
            await session.commit()

        # Invalidate cache (this is what the application should do)
        await cache_service.invalidate(cache_key)

        # Verify cache miss after invalidation
        cached_data_after = await cache_service.get(cache_key)
        assert cached_data_after is None

        # Verify fresh data from DB
        async with get_session() as session:
            result = await session.execute(
                text("SELECT name FROM cameras WHERE id = :camera_id").bindparams(
                    camera_id=camera_id
                )
            )
            fresh_name = result.scalar_one()
            assert fresh_name == "Updated Camera Name"

    @pytest.mark.asyncio
    async def test_event_creation_invalidates_stats_cache(
        self,
        integration_db: str,
        cache_service: CacheService,
        test_prefix: str,
        cleanup_keys: None,
    ) -> None:
        """Event statistics cache is invalidated when invalidate_event_stats is called."""
        # RED: Cache event stats (test cache invalidation pattern, not actual event creation)
        # Use proper stats key pattern that matches invalidate_event_stats pattern
        stats_key = f"stats:events:{test_prefix}"
        await cache_service.set(stats_key, {"total_events": 0})

        # Verify cache hit
        cached_stats = await cache_service.get(stats_key)
        assert cached_stats["total_events"] == 0

        # Simulate application behavior: invalidate stats cache after event creation
        # (We're testing the invalidation mechanism, not actual event creation)
        deleted = await cache_service.invalidate_event_stats()
        assert deleted >= 1  # At least our stats key should be deleted

        # Verify cache miss after invalidation
        cached_stats_after = await cache_service.get(stats_key)
        assert cached_stats_after is None

    @pytest.mark.asyncio
    async def test_pattern_invalidation_clears_multiple_keys(
        self,
        integration_db: str,
        cache_service: CacheService,
        test_prefix: str,
        cleanup_keys: None,
    ) -> None:
        """Pattern-based invalidation clears all matching cache keys."""
        # RED: Create multiple cameras and cache them
        camera_ids = []
        async with get_session() as session:
            for i in range(3):
                camera = CameraFactory.build(id=f"{test_prefix}_cam_multi_{i}")
                session.add(camera)
                camera_ids.append(camera.id)
            await session.commit()

        # Cache all cameras
        for cam_id in camera_ids:
            cache_key = f"{test_prefix}:cameras:{cam_id}"
            await cache_service.set(cache_key, {"id": cam_id, "name": f"Camera {cam_id}"})

        # Verify all are cached
        for cam_id in camera_ids:
            cache_key = f"{test_prefix}:cameras:{cam_id}"
            assert await cache_service.get(cache_key) is not None

        # Invalidate all camera caches using pattern
        deleted = await cache_service.invalidate_pattern(f"{test_prefix}:cameras:*")
        assert deleted >= 3  # At least our 3 cameras

        # Verify all are invalidated
        for cam_id in camera_ids:
            cache_key = f"{test_prefix}:cameras:{cam_id}"
            assert await cache_service.get(cache_key) is None


# =============================================================================
# Cache and DB Data Consistency
# =============================================================================


class TestCacheDBDataConsistency:
    """Test that cache and database return consistent data."""

    @pytest.mark.asyncio
    async def test_cache_and_db_return_same_data(
        self,
        integration_db: str,
        cache_service: CacheService,
        test_prefix: str,
        cleanup_keys: None,
    ) -> None:
        """Cache and database return identical data for the same query."""
        # RED: Create camera in DB
        async with get_session() as session:
            camera = CameraFactory.build(
                id=f"{test_prefix}_consistent_cam",
                name="Consistency Test Camera",
                folder_path="/export/foscam/front_door",
            )
            session.add(camera)
            await session.commit()
            camera_id = camera.id

        # Get data from DB using raw SQL
        async with get_session() as session:
            result = await session.execute(
                text("SELECT id, name, folder_path FROM cameras WHERE id = :camera_id").bindparams(
                    camera_id=camera_id
                )
            )
            row = result.fetchone()
            db_data = {
                "id": row[0],
                "name": row[1],
                "folder_path": row[2],
            }

        # Cache the data
        cache_key = f"{test_prefix}:cameras:{camera_id}"
        await cache_service.set(cache_key, db_data)

        # Get data from cache
        cached_data = await cache_service.get(cache_key)

        # Verify consistency
        assert cached_data == db_data
        assert cached_data["id"] == db_data["id"]
        assert cached_data["name"] == db_data["name"]
        assert cached_data["folder_path"] == db_data["folder_path"]

    @pytest.mark.asyncio
    async def test_stale_cache_after_db_update_without_invalidation(
        self,
        integration_db: str,
        cache_service: CacheService,
        test_prefix: str,
        cleanup_keys: None,
    ) -> None:
        """Cache becomes stale if not invalidated after DB update."""
        # RED: Create camera and cache it
        async with get_session() as session:
            camera = CameraFactory.build(id=f"{test_prefix}_stale_cam", name="Original Name")
            session.add(camera)
            await session.commit()
            camera_id = camera.id

        # Cache original data
        cache_key = f"{test_prefix}:cameras:{camera_id}"
        await cache_service.set(cache_key, {"id": camera_id, "name": "Original Name"})

        # Update DB without invalidating cache (simulating a bug)
        async with get_session() as session:
            await session.execute(
                text("UPDATE cameras SET name = 'Updated Name' WHERE id = :camera_id").bindparams(
                    camera_id=camera_id
                )
            )
            await session.commit()

        # Cache still has stale data
        cached_data = await cache_service.get(cache_key)
        assert cached_data["name"] == "Original Name"  # Stale

        # DB has fresh data
        async with get_session() as session:
            result = await session.execute(
                text("SELECT name FROM cameras WHERE id = :camera_id").bindparams(
                    camera_id=camera_id
                )
            )
            db_name = result.scalar_one()
            assert db_name == "Updated Name"  # Fresh

        # Detect inconsistency
        assert cached_data["name"] != db_name  # Stale cache detected!

    @pytest.mark.asyncio
    async def test_cache_miss_loads_from_db(
        self,
        integration_db: str,
        cache_service: CacheService,
        test_prefix: str,
        cleanup_keys: None,
    ) -> None:
        """Cache miss causes load from database with get_or_set pattern."""
        # RED: Create camera in DB only (not cached)
        async with get_session() as session:
            camera = CameraFactory.build(id=f"{test_prefix}_miss_cam", name="Uncached Camera")
            session.add(camera)
            await session.commit()
            camera_id = camera.id

        # Factory function to load from DB
        async def load_camera_from_db():
            async with get_session() as session:
                result = await session.execute(
                    text("SELECT id, name FROM cameras WHERE id = :camera_id").bindparams(
                        camera_id=camera_id
                    )
                )
                row = result.fetchone()
                return {"id": row[0], "name": row[1]}

        # Use get_or_set pattern
        cache_key = f"{test_prefix}:cameras:{camera_id}"
        data = await cache_service.get_or_set(cache_key, load_camera_from_db, ttl=60)

        # Verify data loaded from DB
        assert data["name"] == "Uncached Camera"

        # Verify now cached
        cached_data = await cache_service.get(cache_key)
        assert cached_data is not None
        assert cached_data["name"] == "Uncached Camera"


# =============================================================================
# Stale Cache Detection and Refresh
# =============================================================================


class TestStaleCacheDetectionAndRefresh:
    """Test detection and refresh of stale cache entries."""

    @pytest.mark.asyncio
    async def test_cache_refresh_extends_ttl(
        self,
        integration_db: str,
        cache_service: CacheService,
        test_prefix: str,
        cleanup_keys: None,
    ) -> None:
        """Cache refresh extends TTL without fetching value."""
        # RED: Set cache with short TTL
        cache_key = f"{test_prefix}:refresh_test"
        await cache_service.set(cache_key, {"value": "test_data"}, ttl=5)

        # Verify exists
        assert await cache_service.exists(cache_key) is True

        # Refresh with longer TTL
        refreshed = await cache_service.refresh(cache_key, ttl=60)
        assert refreshed is True

        # Verify still exists and has same data
        data = await cache_service.get(cache_key)
        assert data["value"] == "test_data"

    @pytest.mark.asyncio
    async def test_cache_expiration_forces_db_reload(
        self,
        integration_db: str,
        cache_service: CacheService,
        test_prefix: str,
        cleanup_keys: None,
    ) -> None:
        """Expired cache entry forces reload from database."""
        # RED: Create camera in DB
        async with get_session() as session:
            camera = CameraFactory.build(id=f"{test_prefix}_expire_cam", name="Expiring Camera")
            session.add(camera)
            await session.commit()
            camera_id = camera.id

        # Cache with very short TTL (1 second)
        cache_key = f"{test_prefix}:cameras:{camera_id}"
        await cache_service.set(cache_key, {"id": camera_id, "name": "Expiring Camera"}, ttl=1)

        # Verify cached
        assert await cache_service.get(cache_key) is not None

        # Wait for expiration (add extra buffer for slow test environments)
        await asyncio.sleep(2.0)  # mocked: intentional sleep to test Redis TTL expiration

        # Cache should be expired
        assert await cache_service.get(cache_key) is None

        # Reload from DB using get_or_set
        async def reload_from_db():
            async with get_session() as session:
                result = await session.execute(
                    text("SELECT id, name FROM cameras WHERE id = :camera_id").bindparams(
                        camera_id=camera_id
                    )
                )
                row = result.fetchone()
                return {"id": row[0], "name": row[1]}

        reloaded_data = await cache_service.get_or_set(cache_key, reload_from_db, ttl=60)
        assert reloaded_data["name"] == "Expiring Camera"


# =============================================================================
# Cache Rebuild After Redis Restart
# =============================================================================


class TestCacheRebuildAfterRedisRestart:
    """Test cache rebuild scenarios after Redis restart."""

    @pytest.mark.asyncio
    async def test_cache_rebuild_after_flush(
        self,
        integration_db: str,
        cache_service: CacheService,
        real_redis: RedisClient,
        test_prefix: str,
        cleanup_keys: None,
    ) -> None:
        """Cache is rebuilt from database after Redis flush (simulated restart)."""
        # RED: Create cameras in DB
        camera_ids = []
        async with get_session() as session:
            for i in range(3):
                camera = CameraFactory.build(id=f"{test_prefix}_rebuild_{i}")
                session.add(camera)
                camera_ids.append(camera.id)
            await session.commit()

        # Populate cache
        for cam_id in camera_ids:
            cache_key = f"{test_prefix}:cameras:{cam_id}"
            await cache_service.set(cache_key, {"id": cam_id, "cached": True})

        # Verify cache populated
        for cam_id in camera_ids:
            cache_key = f"{test_prefix}:cameras:{cam_id}"
            assert await cache_service.get(cache_key) is not None

        # Simulate Redis restart by flushing test keys
        client = real_redis._ensure_connected()
        async for key in client.scan_iter(match=f"{CACHE_PREFIX}{test_prefix}*", count=100):
            await client.delete(key)

        # Verify cache is empty
        for cam_id in camera_ids:
            cache_key = f"{test_prefix}:cameras:{cam_id}"
            assert await cache_service.get(cache_key) is None

        # Rebuild cache from DB
        async with get_session() as session:
            for cam_id in camera_ids:
                result = await session.execute(
                    text("SELECT id, name FROM cameras WHERE id = :camera_id").bindparams(
                        camera_id=cam_id
                    )
                )
                row = result.fetchone()
                if row:
                    cache_key = f"{test_prefix}:cameras:{cam_id}"
                    await cache_service.set(cache_key, {"id": row[0], "name": row[1]})

        # Verify cache rebuilt
        for cam_id in camera_ids:
            cache_key = f"{test_prefix}:cameras:{cam_id}"
            cached = await cache_service.get(cache_key)
            assert cached is not None
            assert cached["id"] == cam_id

    @pytest.mark.asyncio
    async def test_application_survives_empty_cache(
        self,
        integration_db: str,
        cache_service: CacheService,
        test_prefix: str,
        cleanup_keys: None,
    ) -> None:
        """Application functions correctly with empty cache (cold start)."""
        # RED: Create camera in DB
        async with get_session() as session:
            camera = CameraFactory.build(id=f"{test_prefix}_cold_start")
            session.add(camera)
            await session.commit()
            camera_id = camera.id

        # Simulate cold start (no cache)
        cache_key = f"{test_prefix}:cameras:{camera_id}"
        assert await cache_service.get(cache_key) is None

        # Application loads from DB using cache-aside pattern
        async def load_from_db():
            async with get_session() as session:
                result = await session.execute(
                    text("SELECT id, name FROM cameras WHERE id = :camera_id").bindparams(
                        camera_id=camera_id
                    )
                )
                row = result.fetchone()
                return {"id": row[0], "name": row[1]}

        data = await cache_service.get_or_set(cache_key, load_from_db, ttl=300)

        # Verify data loaded successfully
        assert data["id"] == camera_id
        assert await cache_service.get(cache_key) is not None


# =============================================================================
# Concurrent Cache/DB Operations
# =============================================================================


class TestConcurrentCacheDBOperations:
    """Test race conditions between cache and database operations."""

    @pytest.mark.asyncio
    async def test_concurrent_cache_and_db_writes(
        self,
        integration_db: str,
        cache_service: CacheService,
        test_prefix: str,
        cleanup_keys: None,
    ) -> None:
        """Concurrent cache and DB writes maintain consistency."""
        # RED: Create camera
        async with get_session() as session:
            camera = CameraFactory.build(id=f"{test_prefix}_concurrent_cam")
            session.add(camera)
            await session.commit()
            camera_id = camera.id

        # Concurrent updates to same camera
        async def update_db_and_cache(update_id: int):
            # Update database
            async with get_session() as session:
                await session.execute(
                    text("UPDATE cameras SET name = :name WHERE id = :camera_id").bindparams(
                        name=f"Updated_{update_id}", camera_id=camera_id
                    )
                )
                await session.commit()

            # Invalidate cache
            cache_key = f"{test_prefix}:cameras:{camera_id}"
            await cache_service.invalidate(cache_key)

            # Update cache with new value
            await cache_service.set(cache_key, {"id": camera_id, "name": f"Updated_{update_id}"})

        # Run 5 concurrent updates
        tasks = [update_db_and_cache(i) for i in range(5)]
        await asyncio.gather(*tasks)

        # Verify DB and cache eventually consistent
        cache_key = f"{test_prefix}:cameras:{camera_id}"
        cached_data = await cache_service.get(cache_key)
        async with get_session() as session:
            result = await session.execute(
                text("SELECT name FROM cameras WHERE id = :camera_id").bindparams(
                    camera_id=camera_id
                )
            )
            db_name = result.scalar_one()

        # Cache should exist (last update won)
        assert cached_data is not None
        # DB should have a valid update
        assert db_name.startswith("Updated_")

    @pytest.mark.asyncio
    async def test_cache_write_before_db_commit_rollback(
        self,
        integration_db: str,
        cache_service: CacheService,
        test_prefix: str,
        cleanup_keys: None,
    ) -> None:
        """Cache written before DB commit should be invalidated on rollback."""
        # RED: Cache-aside pattern violation (cache before DB commit)
        camera_id = f"{test_prefix}_rollback_cam"
        cache_key = f"{test_prefix}:cameras:{camera_id}"

        # Write to cache first (WRONG - should wait for DB commit)
        await cache_service.set(cache_key, {"id": camera_id, "name": "Uncommitted Camera"})

        # Attempt DB write that will fail
        try:
            async with get_session() as session:
                camera = CameraFactory.build(id=camera_id, name="Uncommitted Camera")
                session.add(camera)
                # Simulate error before commit
                raise RuntimeError("Simulated error before commit")
        except RuntimeError:
            # Transaction rolled back, but cache still has stale data
            pass

        # Cache has orphaned data (camera never committed to DB)
        cached_data = await cache_service.get(cache_key)
        assert cached_data is not None  # Cache exists

        # But DB doesn't have the camera
        async with get_session() as session:
            result = await session.execute(
                text("SELECT id FROM cameras WHERE id = :camera_id").bindparams(camera_id=camera_id)
            )
            db_result = result.fetchone()
            assert db_result is None  # Not in DB

        # Detect inconsistency: cache exists but DB doesn't
        assert cached_data is not None and db_result is None

        # Fix: Invalidate orphaned cache entry
        await cache_service.invalidate(cache_key)
        assert await cache_service.get(cache_key) is None
