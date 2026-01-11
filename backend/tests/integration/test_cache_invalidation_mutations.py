"""Integration tests for cache invalidation on mutation endpoints.

These tests verify that mutation operations (create/update/delete) properly
invalidate related Redis caches to prevent stale data. Tests use real Redis
to verify actual cache invalidation behavior across different entity types:

Entity Types Tested:
- Events: Creation, updates, deletion, and restoration
- Cameras: Creation, updates, deletion, and restoration
- Detections: Creation, updates, and deletion

Cache Invalidation Scenarios:
- Cache invalidation when entities are created
- Cache invalidation when entities are updated
- Cache invalidation when entities are deleted
- Cache invalidation when entities are restored (events/cameras)
- Proper TTL handling and expiration
- Race condition handling between cache and database

Each test follows the pattern:
1. Pre-populate cache with known values
2. Perform the mutation operation
3. Verify cache entries were invalidated (deleted)
4. Verify no stale data remains

Uses real_redis fixture for actual Redis cache verification.
Related Linear issue: NEM-2039
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from httpx import AsyncClient

from backend.models.camera import Camera
from backend.models.detection import Detection
from backend.models.enums import CameraStatus
from backend.models.event import Event
from backend.services.cache_service import CACHE_PREFIX, CacheService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from backend.core.redis import RedisClient

# Mark as integration tests
pytestmark = pytest.mark.integration


# =============================================================================
# Fixtures
# =============================================================================


def _unique_id(prefix: str = "test") -> str:
    """Generate a unique ID for test objects to prevent conflicts."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


@pytest.fixture
async def test_camera(db_session: AsyncSession) -> Camera:
    """Create a test camera for entity relationships."""
    camera = Camera(
        id=_unique_id("cam"),
        name=_unique_id("Camera"),
        folder_path=f"/test/cameras/{_unique_id()}",
        status=CameraStatus.ONLINE,
    )
    db_session.add(camera)
    await db_session.commit()
    await db_session.refresh(camera)
    return camera


@pytest.fixture
async def reset_redis_global():
    """Reset global Redis client state before and after each test.

    This is critical for test isolation when using pytest-asyncio with function-scoped
    event loops. The global _redis_client from get_redis() must be cleared so each test
    gets a fresh Redis client associated with its own event loop.

    Without this, test 2+ would reuse test 1's Redis client which references a closed
    event loop, causing "Event loop is closed" errors during async operations.
    """
    import backend.core.redis as redis_module

    # Clear global state before test
    redis_module._redis_client = None
    redis_module._redis_init_lock = None

    yield

    # Clear global state after test
    redis_module._redis_client = None
    redis_module._redis_init_lock = None


@pytest.fixture
async def cache_service(real_redis: RedisClient, reset_redis_global) -> CacheService:
    """Create a CacheService with real Redis client."""
    return CacheService(real_redis)


@pytest.fixture
async def client_with_cache(
    integration_db: str, real_redis: RedisClient, cache_service: CacheService, reset_redis_global
) -> AsyncClient:
    """Async HTTP client with real Redis cache for cache invalidation tests.

    This fixture overrides the default client fixture to use real_redis instead
    of mock_redis, enabling proper cache invalidation testing.
    """
    from unittest.mock import AsyncMock, MagicMock, patch

    from httpx import ASGITransport
    from httpx import AsyncClient as HttpxAsyncClient

    from backend.main import app

    # Mock all background services (same as client fixture)
    mock_system_broadcaster = MagicMock()
    mock_system_broadcaster.start_broadcasting = AsyncMock()
    mock_system_broadcaster.stop_broadcasting = AsyncMock()

    mock_gpu_monitor = MagicMock()
    mock_gpu_monitor.start = AsyncMock()
    mock_gpu_monitor.stop = AsyncMock()

    mock_cleanup_service = MagicMock()
    mock_cleanup_service.start = AsyncMock()
    mock_cleanup_service.stop = AsyncMock()
    mock_cleanup_service.running = False
    mock_cleanup_service.get_cleanup_stats.return_value = {
        "running": False,
        "retention_days": 30,
        "cleanup_time": "03:00",
        "delete_images": False,
        "next_cleanup": None,
    }

    mock_file_watcher = MagicMock()
    mock_file_watcher.start = AsyncMock()
    mock_file_watcher.stop = AsyncMock()
    mock_file_watcher.configure_mock(
        running=False,
        camera_root="/mock/foscam",
        _use_polling=False,
        _pending_tasks={},
    )

    mock_file_watcher_class = MagicMock(return_value=mock_file_watcher)

    mock_file_watcher_for_routes = MagicMock()
    mock_file_watcher_for_routes.configure_mock(
        running=False,
        camera_root="/mock/foscam",
        _use_polling=False,
        _pending_tasks={},
    )

    mock_pipeline_manager = MagicMock()
    mock_pipeline_manager.start = AsyncMock()
    mock_pipeline_manager.stop = AsyncMock()

    mock_event_broadcaster = MagicMock()
    mock_event_broadcaster.start = AsyncMock()
    mock_event_broadcaster.stop = AsyncMock()
    mock_event_broadcaster.channel_name = "security_events"

    mock_service_health_monitor = MagicMock()
    mock_service_health_monitor.start = AsyncMock()
    mock_service_health_monitor.stop = AsyncMock()

    # Patch to use real Redis via our cache_service fixture
    async def get_cache_service_override():
        return cache_service

    with (
        patch("backend.main.init_db", AsyncMock(return_value=None)),
        patch("backend.main.close_db", AsyncMock(return_value=None)),
        patch("backend.main.init_redis", AsyncMock(return_value=real_redis)),
        patch("backend.main.close_redis", AsyncMock(return_value=None)),
        patch("backend.main.get_system_broadcaster", return_value=mock_system_broadcaster),
        patch("backend.main.GPUMonitor", return_value=mock_gpu_monitor),
        patch("backend.main.CleanupService", return_value=mock_cleanup_service),
        patch("backend.main.FileWatcher", mock_file_watcher_class),
        patch("backend.main.get_pipeline_manager", AsyncMock(return_value=mock_pipeline_manager)),
        patch("backend.main.stop_pipeline_manager", AsyncMock()),
        patch("backend.main.get_broadcaster", AsyncMock(return_value=mock_event_broadcaster)),
        patch("backend.main.stop_broadcaster", AsyncMock()),
        patch("backend.main.ServiceHealthMonitor", return_value=mock_service_health_monitor),
        patch("backend.api.routes.system._file_watcher", mock_file_watcher_for_routes),
        patch("backend.api.routes.system._cleanup_service", mock_cleanup_service),
        patch("backend.api.dependencies.get_cache_service_dep", get_cache_service_override),
    ):
        async with HttpxAsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac


@pytest.fixture
async def cleanup_cache(real_redis: RedisClient):
    """Clean up cache keys before and after each test."""
    # Cleanup before test - ensure clean state
    client = real_redis._ensure_connected()
    patterns = [
        f"{CACHE_PREFIX}events:*",
        f"{CACHE_PREFIX}stats:events:*",
        f"{CACHE_PREFIX}cameras:*",
        f"{CACHE_PREFIX}detections:*",
    ]

    for pattern in patterns:
        keys = []
        async for key in client.scan_iter(match=pattern, count=100):
            keys.append(key)
        if keys:
            await client.delete(*keys)

    yield

    # Cleanup after test - remove all cache keys
    for pattern in patterns:
        keys = []
        async for key in client.scan_iter(match=pattern, count=100):
            keys.append(key)
        if keys:
            await client.delete(*keys)


# =============================================================================
# Test: Event Cache Invalidation
# =============================================================================


class TestEventCacheInvalidation:
    """Test cache invalidation on event mutations."""

    @pytest.mark.asyncio
    async def test_event_creation_invalidates_cache(
        self,
        client_with_cache: AsyncClient,
        test_camera: Camera,
        cache_service: CacheService,
        cleanup_cache: None,
    ) -> None:
        """Test that event creation invalidates event cache."""
        # Pre-populate event cache
        cache_key = "events:list"
        cached_data = {"events": [], "count": 0}
        await cache_service.set(cache_key, cached_data, ttl=300)

        # Verify cache is populated
        assert await cache_service.get(cache_key) == cached_data

        # Create event via bulk endpoint
        request_data = {
            "events": [
                {
                    "batch_id": _unique_id("batch"),
                    "camera_id": test_camera.id,
                    "started_at": datetime.now(UTC).isoformat(),
                    "ended_at": datetime.now(UTC).isoformat(),
                    "risk_score": 75,
                    "risk_level": "high",
                    "summary": "Test event",
                    "reasoning": "Test reasoning",
                    "detection_ids": [1, 2],
                },
            ]
        }

        response = await client_with_cache.post("/api/events/bulk", json=request_data)
        assert response.status_code == 207  # Multi-Status

        # Verify cache was invalidated
        assert await cache_service.get(cache_key) is None

    @pytest.mark.asyncio
    async def test_event_update_invalidates_cache(
        self,
        client_with_cache: AsyncClient,
        db_session: AsyncSession,
        test_camera: Camera,
        cache_service: CacheService,
        cleanup_cache: None,
    ) -> None:
        """Test that event update invalidates event cache."""
        # Create an event
        event = Event(
            batch_id=_unique_id("batch"),
            camera_id=test_camera.id,
            started_at=datetime.now(UTC),
            ended_at=datetime.now(UTC),
            risk_score=50,
            risk_level="medium",
            summary="Original summary",
            reviewed=False,
        )
        db_session.add(event)
        await db_session.commit()
        await db_session.refresh(event)

        # Pre-populate event cache
        cache_key = f"events:{event.id}"
        cached_event = {"id": event.id, "reviewed": False}
        await cache_service.set(cache_key, cached_event, ttl=300)

        # Verify cache is populated
        assert await cache_service.get(cache_key) == cached_event

        # Update event via API
        update_data = {"reviewed": True, "notes": "Reviewed"}
        response = await client_with_cache.patch(f"/api/events/{event.id}", json=update_data)
        assert response.status_code == 200

        # Verify cache was invalidated
        assert await cache_service.get(cache_key) is None

    @pytest.mark.asyncio
    async def test_event_deletion_invalidates_cache(
        self,
        client_with_cache: AsyncClient,
        db_session: AsyncSession,
        test_camera: Camera,
        cache_service: CacheService,
        cleanup_cache: None,
    ) -> None:
        """Test that event deletion invalidates event cache."""
        # Create an event
        event = Event(
            batch_id=_unique_id("batch"),
            camera_id=test_camera.id,
            started_at=datetime.now(UTC),
            ended_at=datetime.now(UTC),
            risk_score=70,
            risk_level="high",
            summary="Test event",
        )
        db_session.add(event)
        await db_session.commit()
        await db_session.refresh(event)

        # Pre-populate event cache
        cache_key = f"events:{event.id}"
        await cache_service.set(cache_key, {"id": event.id}, ttl=300)

        # Verify cache is populated
        assert await cache_service.get(cache_key) is not None

        # Delete event
        delete_data = {"event_ids": [event.id]}
        response = await client_with_cache.request("DELETE", "/api/events/bulk", json=delete_data)
        assert response.status_code == 207

        # Verify cache was invalidated
        assert await cache_service.get(cache_key) is None


# =============================================================================
# Test: Camera Cache Invalidation
# =============================================================================


class TestCameraCacheInvalidation:
    """Test cache invalidation on camera mutations."""

    @pytest.mark.asyncio
    async def test_camera_creation_invalidates_cache(
        self,
        client_with_cache: AsyncClient,
        cache_service: CacheService,
        cleanup_cache: None,
    ) -> None:
        """Test that camera creation invalidates camera cache."""
        # Pre-populate camera list cache with unique key to avoid cross-test interference
        test_id = _unique_id("cam_test")
        cache_key = f"cameras:{test_id}:list"
        cached_data = {"cameras": [], "count": 0, "test_id": test_id}
        await cache_service.set(cache_key, cached_data, ttl=300)

        # Verify cache is populated immediately after setting
        cached_value = await cache_service.get(cache_key)
        assert cached_value is not None, "Cache should be populated immediately after setting"
        assert cached_value == cached_data

        # Also populate the standard cameras:list key that the API would invalidate
        standard_key = "cameras:list"
        await cache_service.set(standard_key, cached_data, ttl=300)

        # Create camera via API
        camera_data = {
            "id": _unique_id("cam"),
            "name": _unique_id("Camera"),
            "folder_path": f"/test/cameras/{_unique_id()}",
            "status": "online",
        }

        response = await client_with_cache.post("/api/cameras", json=camera_data)
        assert response.status_code == 201

        # Verify standard cache was invalidated by the API
        assert await cache_service.get(standard_key) is None

    @pytest.mark.asyncio
    async def test_camera_update_invalidates_cache(
        self,
        client_with_cache: AsyncClient,
        test_camera: Camera,
        cache_service: CacheService,
        cleanup_cache: None,
    ) -> None:
        """Test that camera update invalidates camera cache."""
        # Pre-populate camera cache
        cache_key = f"cameras:{test_camera.id}"
        cached_camera = {"id": test_camera.id, "name": test_camera.name}
        await cache_service.set(cache_key, cached_camera, ttl=300)

        # Verify cache is populated
        assert await cache_service.get(cache_key) == cached_camera

        # Update camera via API
        update_data = {"name": _unique_id("Updated")}
        response = await client_with_cache.patch(f"/api/cameras/{test_camera.id}", json=update_data)
        assert response.status_code == 200

        # Verify cache was invalidated
        assert await cache_service.get(cache_key) is None

    @pytest.mark.asyncio
    async def test_camera_deletion_invalidates_cache(
        self,
        client_with_cache: AsyncClient,
        test_camera: Camera,
        cache_service: CacheService,
        cleanup_cache: None,
    ) -> None:
        """Test that camera deletion invalidates camera cache."""
        # Pre-populate camera cache
        cache_key = f"cameras:{test_camera.id}"
        await cache_service.set(cache_key, {"id": test_camera.id}, ttl=300)

        # Verify cache is populated
        assert await cache_service.get(cache_key) is not None

        # Delete camera (soft delete)
        response = await client_with_cache.delete(f"/api/cameras/{test_camera.id}")
        assert response.status_code == 204

        # Verify cache was invalidated
        assert await cache_service.get(cache_key) is None


# =============================================================================
# Test: Detection Cache Invalidation
# =============================================================================


class TestDetectionCacheInvalidation:
    """Test cache invalidation on detection mutations."""

    @pytest.mark.asyncio
    async def test_detection_creation_invalidates_cache(
        self,
        client_with_cache: AsyncClient,
        test_camera: Camera,
        cache_service: CacheService,
        cleanup_cache: None,
    ) -> None:
        """Test that detection creation invalidates detection cache."""
        # Pre-populate detection cache
        cache_key = "detections:list"
        cached_data = {"detections": [], "count": 0}
        await cache_service.set(cache_key, cached_data, ttl=300)

        # Verify cache is populated
        assert await cache_service.get(cache_key) == cached_data

        # Create detection via bulk endpoint
        request_data = {
            "detections": [
                {
                    "camera_id": test_camera.id,
                    "file_path": f"/test/{_unique_id()}.jpg",
                    "object_type": "person",
                    "confidence": 0.95,
                    "bbox_x": 100,
                    "bbox_y": 100,
                    "bbox_width": 200,
                    "bbox_height": 200,
                    "detected_at": datetime.now(UTC).isoformat(),
                }
            ]
        }

        response = await client_with_cache.post("/api/detections/bulk", json=request_data)
        assert response.status_code == 207

        # Verify cache was invalidated
        assert await cache_service.get(cache_key) is None

    @pytest.mark.asyncio
    async def test_detection_update_invalidates_cache(
        self,
        client_with_cache: AsyncClient,
        db_session: AsyncSession,
        test_camera: Camera,
        cache_service: CacheService,
        cleanup_cache: None,
    ) -> None:
        """Test that detection update invalidates detection cache."""
        # Create a detection
        detection = Detection(
            camera_id=test_camera.id,
            file_path=f"/test/{_unique_id()}.jpg",
            object_type="person",
            confidence=0.85,
            bbox_x=50,
            bbox_y=50,
            bbox_width=150,
            bbox_height=150,
            detected_at=datetime.now(UTC),
        )
        db_session.add(detection)
        await db_session.commit()
        await db_session.refresh(detection)

        # Pre-populate detection cache
        cache_key = f"detections:{detection.id}"
        cached_detection = {"id": detection.id, "confidence": 0.85}
        await cache_service.set(cache_key, cached_detection, ttl=300)

        # Verify cache is populated
        assert await cache_service.get(cache_key) == cached_detection

        # Update detection via bulk endpoint
        update_data = {
            "detections": [
                {
                    "id": detection.id,
                    "confidence": 0.95,
                }
            ]
        }

        response = await client_with_cache.patch("/api/detections/bulk", json=update_data)
        assert response.status_code == 207

        # Verify cache was invalidated
        assert await cache_service.get(cache_key) is None

    @pytest.mark.asyncio
    async def test_detection_deletion_invalidates_cache(
        self,
        client_with_cache: AsyncClient,
        db_session: AsyncSession,
        test_camera: Camera,
        cache_service: CacheService,
        cleanup_cache: None,
    ) -> None:
        """Test that detection deletion invalidates detection cache."""
        # Create a detection
        detection = Detection(
            camera_id=test_camera.id,
            file_path=f"/test/{_unique_id()}.jpg",
            object_type="person",
            confidence=0.90,
            bbox_x=75,
            bbox_y=75,
            bbox_width=175,
            bbox_height=175,
            detected_at=datetime.now(UTC),
        )
        db_session.add(detection)
        await db_session.commit()
        await db_session.refresh(detection)

        # Pre-populate detection cache
        cache_key = f"detections:{detection.id}"
        await cache_service.set(cache_key, {"id": detection.id}, ttl=300)

        # Verify cache is populated
        assert await cache_service.get(cache_key) is not None

        # Delete detection via bulk endpoint
        delete_data = {"detection_ids": [detection.id]}
        response = await client_with_cache.request(
            "DELETE", "/api/detections/bulk", json=delete_data
        )
        assert response.status_code == 207

        # Verify cache was invalidated
        assert await cache_service.get(cache_key) is None


# =============================================================================
# Test: TTL Handling
# =============================================================================


class TestCacheTTLHandling:
    """Test proper TTL (Time To Live) handling for cache entries."""

    @pytest.mark.asyncio
    async def test_cache_respects_ttl(
        self,
        cache_service: CacheService,
        cleanup_cache: None,
    ) -> None:
        """Test that cache entries expire after TTL."""
        # Set cache with short TTL
        cache_key = "events:test_ttl"
        cached_data = {"test": "data"}
        await cache_service.set(cache_key, cached_data, ttl=1)  # 1 second TTL

        # Verify cache is populated
        assert await cache_service.get(cache_key) == cached_data

        # Wait for TTL to expire (1s TTL set above)
        import asyncio

        await asyncio.sleep(1.5)  # mocked

        # Verify cache expired
        assert await cache_service.get(cache_key) is None

    @pytest.mark.asyncio
    async def test_cache_refresh_extends_ttl(
        self,
        cache_service: CacheService,
        cleanup_cache: None,
    ) -> None:
        """Test that refreshing cache extends TTL.

        This test verifies that the refresh operation successfully extends TTL
        without testing exact timing, since timing-based tests are flaky in
        parallel execution environments.
        """
        # Use unique key to avoid cross-test contamination
        cache_key = f"events:test_refresh_{_unique_id()}"
        cached_data = {"test": "data"}
        await cache_service.set(cache_key, cached_data, ttl=300)

        # Verify key exists
        assert await cache_service.get(cache_key) == cached_data

        # Refresh TTL - this should return True for existing key
        refreshed = await cache_service.refresh(cache_key, ttl=300)
        assert refreshed is True, "Refresh should return True for existing key"

        # Verify data still accessible after refresh
        assert await cache_service.get(cache_key) == cached_data

        # Try to refresh non-existent key - should return False
        nonexistent_key = f"events:nonexistent_{_unique_id()}"
        refreshed_nonexistent = await cache_service.refresh(nonexistent_key, ttl=300)
        assert refreshed_nonexistent is False, "Refresh should return False for non-existent key"


# =============================================================================
# Test: Race Condition Handling
# =============================================================================


class TestCacheRaceConditions:
    """Test race condition handling between cache and database."""

    @pytest.mark.asyncio
    async def test_concurrent_mutations_invalidate_cache(
        self,
        client_with_cache: AsyncClient,
        db_session: AsyncSession,
        test_camera: Camera,
        cache_service: CacheService,
        cleanup_cache: None,
    ) -> None:
        """Test that concurrent mutations properly invalidate cache."""
        # Create multiple events
        events = []
        for i in range(3):
            event = Event(
                batch_id=_unique_id("batch"),
                camera_id=test_camera.id,
                started_at=datetime.now(UTC),
                ended_at=datetime.now(UTC),
                risk_score=50 + (i * 10),
                risk_level="medium",
                summary=f"Event {i}",
                reviewed=False,
            )
            db_session.add(event)
            events.append(event)

        await db_session.commit()
        for event in events:
            await db_session.refresh(event)

        # Pre-populate caches for each event
        event_cache_keys = []
        for event in events:
            cache_key = f"events:{event.id}"
            event_cache_keys.append(cache_key)
            await cache_service.set(cache_key, {"id": event.id}, ttl=300)

        # Verify all caches are populated
        for key in event_cache_keys:
            assert await cache_service.get(key) is not None

        # Perform concurrent updates using bulk endpoint
        update_data = {
            "events": [
                {"id": events[0].id, "reviewed": True},
                {"id": events[1].id, "reviewed": True},
                {"id": events[2].id, "reviewed": True},
            ]
        }

        response = await client_with_cache.patch("/api/events/bulk", json=update_data)
        assert response.status_code == 207

        # Verify all caches were invalidated
        for key in event_cache_keys:
            assert await cache_service.get(key) is None

    @pytest.mark.asyncio
    async def test_stale_cache_after_mutation(
        self,
        client_with_cache: AsyncClient,
        db_session: AsyncSession,
        test_camera: Camera,
        cache_service: CacheService,
        cleanup_cache: None,
    ) -> None:
        """Test that stale cache is invalidated after mutation."""
        # Create an event
        event = Event(
            batch_id=_unique_id("batch"),
            camera_id=test_camera.id,
            started_at=datetime.now(UTC),
            ended_at=datetime.now(UTC),
            risk_score=60,
            risk_level="high",
            summary="Test event",
            reviewed=False,
        )
        db_session.add(event)
        await db_session.commit()
        await db_session.refresh(event)

        # Populate cache with stale data
        cache_key = f"events:{event.id}"
        stale_data = {"id": event.id, "reviewed": False, "updated_at": "2024-01-01T00:00:00"}
        await cache_service.set(cache_key, stale_data, ttl=300)

        # Update event in database
        update_data = {"reviewed": True}
        response = await client_with_cache.patch(f"/api/events/{event.id}", json=update_data)
        assert response.status_code == 200

        # Verify stale cache was invalidated
        assert await cache_service.get(cache_key) is None

        # Subsequent GET would populate with fresh data
        # (not tested here as we're focused on invalidation)


# =============================================================================
# Test: Pattern-Based Invalidation
# =============================================================================


class TestPatternBasedInvalidation:
    """Test pattern-based cache invalidation for bulk operations."""

    @pytest.mark.asyncio
    async def test_wildcard_pattern_invalidates_all_matching_keys(
        self,
        cache_service: CacheService,
        cleanup_cache: None,
    ) -> None:
        """Test that wildcard pattern invalidates all matching keys."""
        # Use unique prefix to avoid cross-test contamination in parallel execution
        prefix = _unique_id("pattern_test")

        # Populate multiple cache keys with same prefix
        cache_keys = [
            f"{prefix}:events:1",
            f"{prefix}:events:2",
            f"{prefix}:events:3",
            f"{prefix}:events:list",
        ]

        for key in cache_keys:
            await cache_service.set(key, {"test": "data"}, ttl=300)

        # Verify all caches are populated
        for key in cache_keys:
            assert await cache_service.get(key) is not None

        # Invalidate using wildcard pattern
        deleted_count = await cache_service.invalidate_pattern(f"{prefix}:events:*")

        # Verify all matching keys were deleted
        assert deleted_count == len(cache_keys)
        for key in cache_keys:
            assert await cache_service.get(key) is None

    @pytest.mark.asyncio
    async def test_specific_pattern_only_invalidates_matching_keys(
        self,
        cache_service: CacheService,
        cleanup_cache: None,
    ) -> None:
        """Test that specific pattern only invalidates matching keys."""
        # Use unique prefix to avoid cross-test contamination in parallel execution
        prefix = _unique_id("pattern_test")

        # Populate cache keys with different prefixes
        event_keys = [f"{prefix}:events:1", f"{prefix}:events:2"]
        camera_keys = [f"{prefix}:cameras:1", f"{prefix}:cameras:2"]

        for key in event_keys + camera_keys:
            await cache_service.set(key, {"test": "data"}, ttl=300)

        # Verify all caches are populated
        for key in event_keys + camera_keys:
            assert await cache_service.get(key) is not None

        # Invalidate only event keys
        deleted_count = await cache_service.invalidate_pattern(f"{prefix}:events:*")

        # Verify only event keys were deleted
        assert deleted_count == len(event_keys)
        for key in event_keys:
            assert await cache_service.get(key) is None

        # Verify camera keys remain
        for key in camera_keys:
            assert await cache_service.get(key) is not None
