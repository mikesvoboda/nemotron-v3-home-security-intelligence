"""Integration tests for cache invalidation on event mutation endpoints.

These tests verify that event mutation operations properly invalidate
related Redis caches to prevent stale data. Tests use real Redis to
verify actual cache invalidation behavior.

Endpoints tested:
- POST /api/events/bulk - Bulk event creation
- PATCH /api/events/{id} - Single event update
- PATCH /api/events/bulk - Bulk event update
- DELETE /api/events/bulk - Bulk event deletion

Each test follows the pattern:
1. Pre-populate cache with known values
2. Perform the mutation operation
3. Verify cache entries were invalidated (deleted)

Uses real_redis fixture for actual Redis cache verification.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from httpx import AsyncClient

from backend.models.camera import Camera
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
    """Create a test camera for event relationships."""
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
    ]

    for pattern in patterns:
        keys = []
        async for key in client.scan_iter(match=pattern, count=100):
            keys.append(key)
        if keys:
            await client.delete(*keys)

    yield

    # Cleanup after test - remove all event-related cache keys
    for pattern in patterns:
        keys = []
        async for key in client.scan_iter(match=pattern, count=100):
            keys.append(key)
        if keys:
            await client.delete(*keys)


# =============================================================================
# Test: POST /api/events/bulk - Bulk Event Creation
# =============================================================================


class TestBulkCreateEventsCacheInvalidation:
    """Test cache invalidation on bulk event creation."""

    @pytest.mark.asyncio
    async def test_bulk_create_invalidates_event_list_cache(
        self,
        client_with_cache: AsyncClient,
        test_camera: Camera,
        cache_service: CacheService,
        cleanup_cache: None,
    ) -> None:
        """Test that bulk event creation invalidates event list cache."""
        # Pre-populate event list cache
        cache_key = "events:list"
        cached_data = {"events": [], "count": 0}
        await cache_service.set(cache_key, cached_data, ttl=300)

        # Verify cache is populated
        assert await cache_service.get(cache_key) == cached_data

        # Create events via bulk endpoint
        request_data = {
            "events": [
                {
                    "batch_id": _unique_id("batch"),
                    "camera_id": test_camera.id,
                    "started_at": datetime.now(UTC).isoformat(),
                    "ended_at": datetime.now(UTC).isoformat(),
                    "risk_score": 75,
                    "risk_level": "high",
                    "summary": "Test event 1",
                    "reasoning": "Test reasoning",
                    "detection_ids": [1, 2, 3],
                },
                {
                    "batch_id": _unique_id("batch"),
                    "camera_id": test_camera.id,
                    "started_at": datetime.now(UTC).isoformat(),
                    "ended_at": datetime.now(UTC).isoformat(),
                    "risk_score": 45,
                    "risk_level": "medium",
                    "summary": "Test event 2",
                    "reasoning": "Test reasoning",
                    "detection_ids": [4, 5],
                },
            ]
        }

        response = await client_with_cache.post("/api/events/bulk", json=request_data)
        assert response.status_code == 207  # Multi-Status

        # Verify cache was invalidated (key should be deleted)
        assert await cache_service.get(cache_key) is None

    @pytest.mark.asyncio
    async def test_bulk_create_invalidates_event_stats_cache(
        self,
        client_with_cache: AsyncClient,
        test_camera: Camera,
        cache_service: CacheService,
        cleanup_cache: None,
    ) -> None:
        """Test that bulk event creation invalidates event stats cache."""
        # Pre-populate event stats cache with multiple date range keys
        stats_keys = [
            "stats:events:none:none",  # No date filter
            "stats:events:2024-01-01T00:00:00:2024-12-31T23:59:59",  # Date range
        ]

        for key in stats_keys:
            cached_stats = {
                "total_events": 10,
                "events_by_risk_level": {"high": 5, "medium": 3, "low": 2, "critical": 0},
                "events_by_camera": [],
            }
            await cache_service.set(key, cached_stats, ttl=300)

        # Verify caches are populated
        for key in stats_keys:
            assert await cache_service.get(key) is not None

        # Create events via bulk endpoint
        request_data = {
            "events": [
                {
                    "batch_id": _unique_id("batch"),
                    "camera_id": test_camera.id,
                    "started_at": datetime.now(UTC).isoformat(),
                    "ended_at": datetime.now(UTC).isoformat(),
                    "risk_score": 85,
                    "risk_level": "critical",
                    "summary": "Critical event",
                    "reasoning": "Test reasoning",
                }
            ]
        }

        response = await client_with_cache.post("/api/events/bulk", json=request_data)
        assert response.status_code == 207

        # Verify all stats caches were invalidated
        for key in stats_keys:
            assert await cache_service.get(key) is None


# =============================================================================
# Test: PATCH /api/events/{id} - Single Event Update
# =============================================================================


class TestSingleEventUpdateCacheInvalidation:
    """Test cache invalidation on single event update."""

    @pytest.mark.asyncio
    async def test_single_update_invalidates_specific_event_cache(
        self,
        client_with_cache: AsyncClient,
        db_session: AsyncSession,
        test_camera: Camera,
        cache_service: CacheService,
        cleanup_cache: None,
    ) -> None:
        """Test that updating an event invalidates its specific cache entry."""
        # Create an event in the database
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

        # Pre-populate specific event cache
        cache_key = f"events:{event.id}"
        cached_event = {
            "id": event.id,
            "summary": "Original summary",
            "reviewed": False,
        }
        await cache_service.set(cache_key, cached_event, ttl=300)

        # Verify cache is populated
        assert await cache_service.get(cache_key) == cached_event

        # Update event via API
        update_data = {"reviewed": True, "notes": "Reviewed by test"}
        response = await client_with_cache.patch(f"/api/events/{event.id}", json=update_data)
        assert response.status_code == 200

        # Verify specific event cache was invalidated
        assert await cache_service.get(cache_key) is None

    @pytest.mark.asyncio
    async def test_single_update_invalidates_event_list_cache(
        self,
        client_with_cache: AsyncClient,
        db_session: AsyncSession,
        test_camera: Camera,
        cache_service: CacheService,
        cleanup_cache: None,
    ) -> None:
        """Test that updating an event invalidates event list cache."""
        # Create an event in the database
        event = Event(
            batch_id=_unique_id("batch"),
            camera_id=test_camera.id,
            started_at=datetime.now(UTC),
            ended_at=datetime.now(UTC),
            risk_score=65,
            risk_level="high",
            summary="Test event",
            reviewed=False,
        )
        db_session.add(event)
        await db_session.commit()
        await db_session.refresh(event)

        # Pre-populate event list cache
        list_cache_key = "events:list"
        cached_list = {"events": [{"id": event.id, "reviewed": False}], "count": 1}
        await cache_service.set(list_cache_key, cached_list, ttl=300)

        # Verify cache is populated
        assert await cache_service.get(list_cache_key) == cached_list

        # Update event via API
        update_data = {"reviewed": True}
        response = await client_with_cache.patch(f"/api/events/{event.id}", json=update_data)
        assert response.status_code == 200

        # Verify event list cache was invalidated
        assert await cache_service.get(list_cache_key) is None


# =============================================================================
# Test: PATCH /api/events/bulk - Bulk Event Update
# =============================================================================


class TestBulkUpdateEventsCacheInvalidation:
    """Test cache invalidation on bulk event updates."""

    @pytest.mark.asyncio
    async def test_bulk_update_invalidates_multiple_event_caches(
        self,
        client_with_cache: AsyncClient,
        db_session: AsyncSession,
        test_camera: Camera,
        cache_service: CacheService,
        cleanup_cache: None,
    ) -> None:
        """Test that bulk update invalidates caches for all updated events."""
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
            await cache_service.set(cache_key, {"id": event.id, "reviewed": False}, ttl=300)

        # Verify all caches are populated
        for key in event_cache_keys:
            assert await cache_service.get(key) is not None

        # Bulk update events via API
        update_data = {
            "events": [
                {"id": events[0].id, "reviewed": True},
                {"id": events[1].id, "reviewed": True, "notes": "Bulk update"},
                {"id": events[2].id, "notes": "Notes only"},
            ]
        }

        response = await client_with_cache.patch("/api/events/bulk", json=update_data)
        assert response.status_code == 207

        # Verify all event caches were invalidated
        for key in event_cache_keys:
            assert await cache_service.get(key) is None

    @pytest.mark.asyncio
    async def test_bulk_update_invalidates_event_list_cache(
        self,
        client_with_cache: AsyncClient,
        db_session: AsyncSession,
        test_camera: Camera,
        cache_service: CacheService,
        cleanup_cache: None,
    ) -> None:
        """Test that bulk update invalidates event list cache."""
        # Create events
        events = []
        for i in range(2):
            event = Event(
                batch_id=_unique_id("batch"),
                camera_id=test_camera.id,
                started_at=datetime.now(UTC),
                ended_at=datetime.now(UTC),
                risk_score=60,
                risk_level="high",
                summary=f"Event {i}",
                reviewed=False,
            )
            db_session.add(event)
            events.append(event)

        await db_session.commit()
        for event in events:
            await db_session.refresh(event)

        # Pre-populate event list cache
        list_cache_key = "events:list"
        await cache_service.set(list_cache_key, {"events": [], "count": 2}, ttl=300)

        # Verify cache is populated
        assert await cache_service.get(list_cache_key) is not None

        # Bulk update events
        update_data = {
            "events": [
                {"id": events[0].id, "reviewed": True},
                {"id": events[1].id, "reviewed": True},
            ]
        }

        response = await client_with_cache.patch("/api/events/bulk", json=update_data)
        assert response.status_code == 207

        # Verify event list cache was invalidated
        assert await cache_service.get(list_cache_key) is None


# =============================================================================
# Test: DELETE /api/events/bulk - Bulk Event Deletion
# =============================================================================


class TestBulkDeleteEventsCacheInvalidation:
    """Test cache invalidation on bulk event deletion."""

    @pytest.mark.asyncio
    async def test_bulk_delete_invalidates_event_caches(
        self,
        client_with_cache: AsyncClient,
        db_session: AsyncSession,
        test_camera: Camera,
        cache_service: CacheService,
        cleanup_cache: None,
    ) -> None:
        """Test that bulk deletion invalidates all related event caches."""
        # Create events
        events = []
        for i in range(3):
            event = Event(
                batch_id=_unique_id("batch"),
                camera_id=test_camera.id,
                started_at=datetime.now(UTC),
                ended_at=datetime.now(UTC),
                risk_score=70,
                risk_level="high",
                summary=f"Event {i}",
            )
            db_session.add(event)
            events.append(event)

        await db_session.commit()
        for event in events:
            await db_session.refresh(event)

        # Pre-populate specific event caches
        event_cache_keys = []
        for event in events:
            cache_key = f"events:{event.id}"
            event_cache_keys.append(cache_key)
            await cache_service.set(cache_key, {"id": event.id}, ttl=300)

        # Verify caches are populated
        for key in event_cache_keys:
            assert await cache_service.get(key) is not None

        # Bulk delete events (soft delete by default)
        delete_data = {"event_ids": [e.id for e in events]}

        response = await client_with_cache.request("DELETE", "/api/events/bulk", json=delete_data)
        assert response.status_code == 207

        # Verify all event caches were invalidated
        for key in event_cache_keys:
            assert await cache_service.get(key) is None

    @pytest.mark.asyncio
    async def test_bulk_delete_invalidates_event_list_cache(
        self,
        client_with_cache: AsyncClient,
        db_session: AsyncSession,
        test_camera: Camera,
        cache_service: CacheService,
        cleanup_cache: None,
    ) -> None:
        """Test that bulk deletion invalidates event list cache."""
        # Create events
        events = []
        for i in range(2):
            event = Event(
                batch_id=_unique_id("batch"),
                camera_id=test_camera.id,
                started_at=datetime.now(UTC),
                ended_at=datetime.now(UTC),
                risk_score=80,
                risk_level="critical",
                summary=f"Critical event {i}",
            )
            db_session.add(event)
            events.append(event)

        await db_session.commit()
        for event in events:
            await db_session.refresh(event)

        # Pre-populate event list cache
        list_cache_key = "events:list"
        await cache_service.set(list_cache_key, {"events": [], "count": 2}, ttl=300)

        # Verify cache is populated
        assert await cache_service.get(list_cache_key) is not None

        # Bulk delete events
        delete_data = {"event_ids": [e.id for e in events]}

        response = await client_with_cache.request("DELETE", "/api/events/bulk", json=delete_data)
        assert response.status_code == 207

        # Verify event list cache was invalidated
        assert await cache_service.get(list_cache_key) is None

    @pytest.mark.asyncio
    async def test_bulk_delete_invalidates_event_stats_cache(
        self,
        client_with_cache: AsyncClient,
        db_session: AsyncSession,
        test_camera: Camera,
        cache_service: CacheService,
        cleanup_cache: None,
    ) -> None:
        """Test that bulk deletion invalidates event stats cache."""
        # Create events
        events = []
        for i in range(2):
            event = Event(
                batch_id=_unique_id("batch"),
                camera_id=test_camera.id,
                started_at=datetime.now(UTC),
                ended_at=datetime.now(UTC),
                risk_score=90,
                risk_level="critical",
                summary=f"Event {i}",
            )
            db_session.add(event)
            events.append(event)

        await db_session.commit()
        for event in events:
            await db_session.refresh(event)

        # Pre-populate event stats cache
        stats_cache_key = "stats:events:none:none"
        cached_stats = {
            "total_events": 2,
            "events_by_risk_level": {"critical": 2, "high": 0, "medium": 0, "low": 0},
            "events_by_camera": [],
        }
        await cache_service.set(stats_cache_key, cached_stats, ttl=300)

        # Verify cache is populated
        assert await cache_service.get(stats_cache_key) is not None

        # Bulk delete events
        delete_data = {"event_ids": [e.id for e in events]}

        response = await client_with_cache.request("DELETE", "/api/events/bulk", json=delete_data)
        assert response.status_code == 207

        # Verify event stats cache was invalidated
        assert await cache_service.get(stats_cache_key) is None

    @pytest.mark.asyncio
    async def test_bulk_hard_delete_invalidates_all_caches(
        self,
        client_with_cache: AsyncClient,
        db_session: AsyncSession,
        test_camera: Camera,
        cache_service: CacheService,
        cleanup_cache: None,
    ) -> None:
        """Test that hard deletion invalidates all event-related caches."""
        # Create event
        event = Event(
            batch_id=_unique_id("batch"),
            camera_id=test_camera.id,
            started_at=datetime.now(UTC),
            ended_at=datetime.now(UTC),
            risk_score=95,
            risk_level="critical",
            summary="Hard delete test",
        )
        db_session.add(event)
        await db_session.commit()
        await db_session.refresh(event)

        # Pre-populate multiple cache types
        cache_keys = {
            "event": f"events:{event.id}",
            "list": "events:list",
            "stats": "stats:events:none:none",
        }

        for cache_type, key in cache_keys.items():
            await cache_service.set(key, {cache_type: "data"}, ttl=300)

        # Verify all caches are populated
        for key in cache_keys.values():
            assert await cache_service.get(key) is not None

        # Hard delete event (soft_delete=false)
        delete_data = {"event_ids": [event.id], "soft_delete": False}

        response = await client_with_cache.request("DELETE", "/api/events/bulk", json=delete_data)
        assert response.status_code == 207

        # Verify all caches were invalidated
        for key in cache_keys.values():
            assert await cache_service.get(key) is None


# =============================================================================
# Test: Cross-Endpoint Cache Consistency
# =============================================================================


class TestCrossEndpointCacheConsistency:
    """Test cache consistency across different event mutation endpoints."""

    @pytest.mark.asyncio
    async def test_create_then_update_maintains_cache_consistency(
        self,
        client_with_cache: AsyncClient,
        test_camera: Camera,
        cache_service: CacheService,
        cleanup_cache: None,
    ) -> None:
        """Test that creating then updating events maintains cache consistency."""
        # Pre-populate event list cache
        list_cache_key = "events:list"
        await cache_service.set(list_cache_key, {"count": 0}, ttl=300)

        # Create event via bulk endpoint
        create_data = {
            "events": [
                {
                    "batch_id": _unique_id("batch"),
                    "camera_id": test_camera.id,
                    "started_at": datetime.now(UTC).isoformat(),
                    "ended_at": datetime.now(UTC).isoformat(),
                    "risk_score": 55,
                    "risk_level": "medium",
                    "summary": "New event",
                    "reasoning": "Test",
                }
            ]
        }

        response = await client_with_cache.post("/api/events/bulk", json=create_data)
        assert response.status_code == 207
        event_id = response.json()["results"][0]["id"]

        # Verify cache was invalidated by creation
        assert await cache_service.get(list_cache_key) is None

        # Repopulate cache (simulating GET request)
        await cache_service.set(list_cache_key, {"count": 1}, ttl=300)

        # Update the event
        update_data = {"reviewed": True}
        response = await client_with_cache.patch(f"/api/events/{event_id}", json=update_data)
        assert response.status_code == 200

        # Verify cache was invalidated again by update
        assert await cache_service.get(list_cache_key) is None

    @pytest.mark.asyncio
    async def test_update_then_delete_maintains_cache_consistency(
        self,
        client_with_cache: AsyncClient,
        db_session: AsyncSession,
        test_camera: Camera,
        cache_service: CacheService,
        cleanup_cache: None,
    ) -> None:
        """Test that updating then deleting events maintains cache consistency."""
        # Create event
        event = Event(
            batch_id=_unique_id("batch"),
            camera_id=test_camera.id,
            started_at=datetime.now(UTC),
            ended_at=datetime.now(UTC),
            risk_score=70,
            risk_level="high",
            summary="Test event",
            reviewed=False,
        )
        db_session.add(event)
        await db_session.commit()
        await db_session.refresh(event)

        # Pre-populate caches
        event_cache_key = f"events:{event.id}"
        stats_cache_key = "stats:events:none:none"

        await cache_service.set(event_cache_key, {"reviewed": False}, ttl=300)
        await cache_service.set(stats_cache_key, {"total": 1}, ttl=300)

        # Update event
        update_data = {"reviewed": True}
        response = await client_with_cache.patch(f"/api/events/{event.id}", json=update_data)
        assert response.status_code == 200

        # Verify caches invalidated by update
        assert await cache_service.get(event_cache_key) is None
        assert await cache_service.get(stats_cache_key) is None

        # Repopulate caches
        await cache_service.set(event_cache_key, {"reviewed": True}, ttl=300)
        await cache_service.set(stats_cache_key, {"total": 1}, ttl=300)

        # Delete event
        delete_data = {"event_ids": [event.id]}
        response = await client_with_cache.request("DELETE", "/api/events/bulk", json=delete_data)
        assert response.status_code == 207

        # Verify caches invalidated by deletion
        assert await cache_service.get(event_cache_key) is None
        assert await cache_service.get(stats_cache_key) is None
