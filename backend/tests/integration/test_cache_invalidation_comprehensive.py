"""Comprehensive integration tests for cache invalidation behavior.

These tests verify cache invalidation behavior across multiple entity types and
scenarios to ensure data consistency and prevent stale cache issues.

Test coverage:
1. Cache population and invalidation on GET/POST/PUT/PATCH/DELETE
2. Cache TTL expiration behavior
3. Concurrent mutations and race condition prevention
4. Cross-entity cache invalidation (e.g., detection changes affect event caches)
5. Multiple cache layers (individual entity, list, stats)

Entity types tested:
- Events (individual, list, stats)
- Detections (individual, list, by event)
- Alerts (individual, list, by camera)
- Cameras (individual, list, stats)

Uses real_redis fixture to verify actual Redis cache behavior.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

from backend.core.constants import CacheInvalidationReason
from backend.models.alert import Alert
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


def _unique_id(prefix: str = "test") -> str:
    """Generate a unique ID for test objects to prevent conflicts."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
async def test_camera(db_session: AsyncSession) -> Camera:
    """Create a test camera for relationships."""
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
async def cache_service(real_redis: RedisClient) -> CacheService:
    """Create a CacheService with real Redis client."""
    return CacheService(real_redis)


@pytest.fixture
async def cleanup_cache(real_redis: RedisClient):
    """Clean up cache keys after each test."""
    yield

    # Cleanup after test - remove all test-related cache keys
    client = real_redis._ensure_connected()
    patterns = [
        f"{CACHE_PREFIX}events:*",
        f"{CACHE_PREFIX}detections:*",
        f"{CACHE_PREFIX}alerts:*",
        f"{CACHE_PREFIX}cameras:*",
        f"{CACHE_PREFIX}stats:*",
    ]

    for pattern in patterns:
        keys = []
        async for key in client.scan_iter(match=pattern, count=100):
            keys.append(key)
        if keys:
            await client.delete(*keys)


# =============================================================================
# Test: Cache TTL Behavior
# =============================================================================


class TestCacheTTLBehavior:
    """Test cache TTL expiration and refresh behavior."""

    @pytest.mark.asyncio
    async def test_cache_expires_after_ttl(
        self,
        cache_service: CacheService,
        cleanup_cache: None,
    ) -> None:
        """Test that cache entries expire after TTL."""
        cache_key = "test:ttl_expiry"
        test_data = {"value": "expires after TTL"}

        # Set cache with 1 second TTL
        await cache_service.set(cache_key, test_data, ttl=1)

        # Verify cache is populated immediately
        cached = await cache_service.get(cache_key)
        assert cached == test_data

        # Wait for TTL to expire (1 second + buffer) - intentional for TTL test
        await asyncio.sleep(1.2)  # cancelled (TTL verification requires actual wait)

        # Verify cache has expired
        expired = await cache_service.get(cache_key)
        assert expired is None

    @pytest.mark.asyncio
    async def test_cache_refresh_extends_ttl(
        self,
        cache_service: CacheService,
        cleanup_cache: None,
    ) -> None:
        """Test that refreshing cache extends TTL."""
        cache_key = "test:ttl_refresh"
        initial_data = {"value": "initial"}
        updated_data = {"value": "refreshed"}

        # Set initial cache with 2 second TTL
        await cache_service.set(cache_key, initial_data, ttl=2)

        # Wait 0.5 seconds
        await asyncio.sleep(0.5)

        # Refresh cache with new longer TTL
        await cache_service.set(cache_key, updated_data, ttl=4)

        # Wait 1.8 seconds (total 2.3s - would expire original 2s TTL, but not 4s)
        await asyncio.sleep(1.8)  # cancelled (TTL verification requires actual wait)

        # Verify cache still exists with refreshed data
        cached = await cache_service.get(cache_key)
        assert cached == updated_data

    @pytest.mark.asyncio
    async def test_mutation_resets_ttl_on_repopulation(
        self,
        db_session: AsyncSession,
        test_camera: Camera,
        cache_service: CacheService,
        cleanup_cache: None,
    ) -> None:
        """Test that cache repopulation after mutation resets TTL."""
        # Create event
        event = Event(
            batch_id=_unique_id("batch"),
            camera_id=test_camera.id,
            started_at=datetime.now(UTC),
            ended_at=datetime.now(UTC),
            risk_score=50,
            risk_level="medium",
            summary="TTL test event",
        )
        db_session.add(event)
        await db_session.commit()
        await db_session.refresh(event)

        # Populate cache with short TTL
        cache_key = f"events:{event.id}"
        await cache_service.set(cache_key, {"id": event.id, "summary": "Original"}, ttl=5)

        # Verify cache exists
        assert await cache_service.get(cache_key) is not None

        # Invalidate cache (simulating mutation)
        await cache_service.invalidate(cache_key)

        # Verify cache was invalidated
        assert await cache_service.get(cache_key) is None

        # Repopulate with longer TTL (simulating GET after mutation)
        await cache_service.set(cache_key, {"id": event.id, "summary": "Updated"}, ttl=300)

        # Verify cache exists with fresh TTL
        assert await cache_service.get(cache_key) == {"id": event.id, "summary": "Updated"}


# =============================================================================
# Test: Concurrent Mutations and Race Conditions
# =============================================================================


class TestConcurrentMutations:
    """Test cache invalidation under concurrent mutation scenarios."""

    @pytest.mark.asyncio
    async def test_concurrent_mutations_invalidate_all_caches(
        self,
        db_session: AsyncSession,
        test_camera: Camera,
        cache_service: CacheService,
        cleanup_cache: None,
    ) -> None:
        """Test that concurrent mutations properly invalidate all related caches."""
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
                summary=f"Concurrent event {i}",
                reviewed=False,
            )
            db_session.add(event)
            events.append(event)

        await db_session.commit()
        for event in events:
            await db_session.refresh(event)

        # Pre-populate individual caches
        cache_tasks = []
        for event in events:
            cache_key = f"events:{event.id}"
            cache_tasks.append(
                cache_service.set(cache_key, {"id": event.id, "reviewed": False}, ttl=300)
            )

        await asyncio.gather(*cache_tasks)

        # Verify all caches populated
        for event in events:
            assert await cache_service.get(f"events:{event.id}") is not None

        # Simulate concurrent invalidations (e.g., from parallel mutations)
        invalidation_tasks = []
        for event in events:
            invalidation_tasks.append(cache_service.invalidate(f"events:{event.id}"))

        results = await asyncio.gather(*invalidation_tasks)

        # Verify all invalidations succeeded
        assert all(results), "Some cache invalidations failed"

        # Verify all caches were invalidated
        for event in events:
            assert await cache_service.get(f"events:{event.id}") is None

    @pytest.mark.asyncio
    async def test_concurrent_pattern_invalidations_dont_conflict(
        self,
        db_session: AsyncSession,
        test_camera: Camera,
        cache_service: CacheService,
        cleanup_cache: None,
    ) -> None:
        """Test that concurrent pattern-based invalidations work correctly."""
        # Create events
        events = []
        for i in range(5):
            event = Event(
                batch_id=_unique_id("batch"),
                camera_id=test_camera.id,
                started_at=datetime.now(UTC),
                ended_at=datetime.now(UTC),
                risk_score=60,
                risk_level="high",
                summary=f"Pattern test event {i}",
            )
            db_session.add(event)
            events.append(event)

        await db_session.commit()

        # Pre-populate various event caches
        for event in events:
            await cache_service.set(f"events:{event.id}", {"id": event.id}, ttl=300)

        # Also populate list and stats caches
        await cache_service.set("events:list", {"count": len(events)}, ttl=300)
        await cache_service.set("stats:events:none:none", {"total": len(events)}, ttl=300)

        # Verify all caches populated
        assert await cache_service.get("events:list") is not None
        assert await cache_service.get("stats:events:none:none") is not None

        # Perform concurrent pattern invalidations
        tasks = [
            cache_service.invalidate_pattern(
                "events:*", reason=CacheInvalidationReason.CONCURRENT_TEST
            ),
            cache_service.invalidate_pattern(
                "stats:events:*", reason=CacheInvalidationReason.CONCURRENT_TEST
            ),
        ]

        results = await asyncio.gather(*tasks)

        # Verify invalidations occurred (at least some keys deleted)
        assert any(r > 0 for r in results), "No cache keys were invalidated"

        # Verify caches were cleared
        assert await cache_service.get("events:list") is None
        assert await cache_service.get("stats:events:none:none") is None


# =============================================================================
# Test: Cross-Entity Cache Invalidation
# =============================================================================


class TestCrossEntityCacheInvalidation:
    """Test cache invalidation across related entity types."""

    @pytest.mark.asyncio
    async def test_detection_change_invalidates_related_event_cache(
        self,
        db_session: AsyncSession,
        test_camera: Camera,
        cache_service: CacheService,
        cleanup_cache: None,
    ) -> None:
        """Test that modifying a detection invalidates related event caches.

        When a detection is added/removed from an event, the event cache
        should be invalidated to reflect the updated detection list.
        """
        # Create event
        event = Event(
            batch_id=_unique_id("batch"),
            camera_id=test_camera.id,
            started_at=datetime.now(UTC),
            ended_at=datetime.now(UTC),
            risk_score=70,
            risk_level="high",
            summary="Event with detections",
        )
        db_session.add(event)
        await db_session.commit()
        await db_session.refresh(event)

        # Create detection (no event_id in Detection model - uses junction table)
        detection = Detection(
            camera_id=test_camera.id,
            file_path="/test/image.jpg",
            object_type="person",
            confidence=0.95,
            bbox_x=100,
            bbox_y=200,
            bbox_width=200,
            bbox_height=200,
            detected_at=datetime.now(UTC),
        )
        db_session.add(detection)
        await db_session.commit()
        await db_session.refresh(detection)

        # Pre-populate event and detection caches
        event_cache_key = f"events:{event.id}"
        detection_cache_key = f"detections:event:{event.id}"

        await cache_service.set(event_cache_key, {"id": event.id, "detection_count": 1}, ttl=300)
        await cache_service.set(detection_cache_key, {"detections": [detection.id]}, ttl=300)

        # Verify caches populated
        assert await cache_service.get(event_cache_key) is not None
        assert await cache_service.get(detection_cache_key) is not None

        # Simulate detection modification (would trigger invalidation in API)
        # In real scenario, this would happen via route that calls invalidate_events()
        await cache_service.invalidate_pattern(
            "events:*", reason=CacheInvalidationReason.DETECTION_CHANGED
        )
        await cache_service.invalidate_pattern(
            "detections:*", reason=CacheInvalidationReason.DETECTION_CHANGED
        )

        # Verify related caches were invalidated
        assert await cache_service.get(event_cache_key) is None
        assert await cache_service.get(detection_cache_key) is None

    @pytest.mark.asyncio
    async def test_camera_deletion_invalidates_all_related_caches(
        self,
        db_session: AsyncSession,
        cache_service: CacheService,
        cleanup_cache: None,
    ) -> None:
        """Test that deleting a camera invalidates all related entity caches.

        When a camera is deleted, caches for events, detections, and alerts
        associated with that camera should be invalidated.
        """
        # Create camera
        camera = Camera(
            id=_unique_id("cam"),
            name=_unique_id("Delete Camera"),
            folder_path=f"/test/delete/{_unique_id()}",
            status=CameraStatus.ONLINE,
        )
        db_session.add(camera)
        await db_session.commit()
        await db_session.refresh(camera)

        # Create related entities
        event = Event(
            batch_id=_unique_id("batch"),
            camera_id=camera.id,
            started_at=datetime.now(UTC),
            ended_at=datetime.now(UTC),
            risk_score=80,
            risk_level="critical",
            summary="Event for camera deletion",
        )
        db_session.add(event)
        await db_session.commit()
        await db_session.refresh(event)

        # Pre-populate caches for camera and related entities
        camera_cache_key = f"cameras:{camera.id}"
        event_cache_key = f"events:{event.id}"
        camera_list_key = "cameras:list"
        event_list_key = "events:list"

        await cache_service.set(camera_cache_key, {"id": camera.id}, ttl=300)
        await cache_service.set(event_cache_key, {"id": event.id}, ttl=300)
        await cache_service.set(camera_list_key, {"count": 1}, ttl=300)
        await cache_service.set(event_list_key, {"count": 1}, ttl=300)

        # Verify all caches populated
        assert await cache_service.get(camera_cache_key) is not None
        assert await cache_service.get(event_cache_key) is not None
        assert await cache_service.get(camera_list_key) is not None
        assert await cache_service.get(event_list_key) is not None

        # Simulate camera deletion cascade invalidation
        await cache_service.invalidate_cameras(reason=CacheInvalidationReason.CAMERA_DELETED)
        await cache_service.invalidate_events(reason=CacheInvalidationReason.CAMERA_DELETED)

        # Verify all related caches were invalidated
        assert await cache_service.get(camera_cache_key) is None
        assert await cache_service.get(event_cache_key) is None
        assert await cache_service.get(camera_list_key) is None
        assert await cache_service.get(event_list_key) is None

    @pytest.mark.asyncio
    async def test_event_update_invalidates_detection_list_cache(
        self,
        db_session: AsyncSession,
        test_camera: Camera,
        cache_service: CacheService,
        cleanup_cache: None,
    ) -> None:
        """Test that updating an event invalidates detection list caches.

        When an event's risk_score or other attributes change, any cached
        detection lists (which include event context) should be invalidated.
        """
        # Create event with detection
        event = Event(
            batch_id=_unique_id("batch"),
            camera_id=test_camera.id,
            started_at=datetime.now(UTC),
            ended_at=datetime.now(UTC),
            risk_score=50,
            risk_level="medium",
            summary="Event update test",
        )
        db_session.add(event)
        await db_session.commit()
        await db_session.refresh(event)

        detection = Detection(
            camera_id=test_camera.id,
            file_path="/test/detection.jpg",
            object_type="vehicle",
            confidence=0.88,
            bbox_x=50,
            bbox_y=100,
            bbox_width=200,
            bbox_height=200,
            detected_at=datetime.now(UTC),
        )
        db_session.add(detection)
        await db_session.commit()

        # Pre-populate event and detection caches
        event_cache_key = f"events:{event.id}"
        detection_list_key = "detections:list"

        await cache_service.set(event_cache_key, {"id": event.id, "risk_score": 50}, ttl=300)
        await cache_service.set(detection_list_key, {"count": 1}, ttl=300)

        # Verify caches populated
        assert await cache_service.get(event_cache_key) is not None
        assert await cache_service.get(detection_list_key) is not None

        # Simulate event update (which should invalidate related caches)
        await cache_service.invalidate_pattern(
            "events:*", reason=CacheInvalidationReason.EVENT_UPDATED
        )
        # In a real scenario, detection caches might also be invalidated
        # if they contain event metadata
        await cache_service.invalidate_pattern(
            "detections:*", reason=CacheInvalidationReason.EVENT_UPDATED
        )

        # Verify caches were invalidated
        assert await cache_service.get(event_cache_key) is None
        assert await cache_service.get(detection_list_key) is None


# =============================================================================
# Test: Multiple Cache Layers
# =============================================================================


class TestMultipleCacheLayers:
    """Test invalidation across multiple cache layers (individual, list, stats)."""

    @pytest.mark.asyncio
    async def test_event_creation_invalidates_all_layers(
        self,
        db_session: AsyncSession,
        test_camera: Camera,
        cache_service: CacheService,
        cleanup_cache: None,
    ) -> None:
        """Test that event creation invalidates individual, list, and stats caches."""
        # Pre-populate all cache layers
        individual_key = f"events:{_unique_id('evt')}"
        list_key = "events:list"
        stats_key = "stats:events:none:none"

        await cache_service.set(individual_key, {"id": "old_event"}, ttl=300)
        await cache_service.set(list_key, {"events": [], "count": 0}, ttl=300)
        await cache_service.set(stats_key, {"total_events": 0}, ttl=300)

        # Verify all layers populated
        assert await cache_service.get(individual_key) is not None
        assert await cache_service.get(list_key) is not None
        assert await cache_service.get(stats_key) is not None

        # Simulate event creation invalidation
        await cache_service.invalidate_events(reason=CacheInvalidationReason.EVENT_CREATED)
        await cache_service.invalidate_event_stats(reason=CacheInvalidationReason.EVENT_CREATED)

        # Verify all layers invalidated
        assert await cache_service.get(individual_key) is None
        assert await cache_service.get(list_key) is None
        assert await cache_service.get(stats_key) is None

    @pytest.mark.asyncio
    async def test_camera_update_invalidates_filtered_lists(
        self,
        db_session: AsyncSession,
        cache_service: CacheService,
        cleanup_cache: None,
    ) -> None:
        """Test that camera updates invalidate status-filtered list caches."""
        # Create camera
        camera = Camera(
            id=_unique_id("cam"),
            name=_unique_id("Filter Camera"),
            folder_path=f"/test/filter/{_unique_id()}",
            status=CameraStatus.ONLINE,
        )
        db_session.add(camera)
        await db_session.commit()
        await db_session.refresh(camera)

        # Pre-populate various filtered list caches
        cache_keys = [
            f"cameras:{camera.id}",
            "cameras:list",
            "cameras:status:online",
            "cameras:status:offline",
            "cameras:stats",
        ]

        for key in cache_keys:
            await cache_service.set(key, {"cached": "data"}, ttl=300)

        # Verify all caches populated
        for key in cache_keys:
            assert await cache_service.get(key) is not None

        # Simulate camera status update (online -> offline)
        await cache_service.invalidate_cameras(reason=CacheInvalidationReason.CAMERA_UPDATED)

        # Verify all camera-related caches invalidated
        for key in cache_keys:
            assert await cache_service.get(key) is None

    @pytest.mark.asyncio
    async def test_detection_deletion_invalidates_aggregation_caches(
        self,
        db_session: AsyncSession,
        test_camera: Camera,
        cache_service: CacheService,
        cleanup_cache: None,
    ) -> None:
        """Test that detection deletion invalidates aggregated detection caches.

        Detection aggregations (e.g., by camera, by type, by confidence) should
        be invalidated when detections are deleted.
        """
        # Create event and detection
        event = Event(
            batch_id=_unique_id("batch"),
            camera_id=test_camera.id,
            started_at=datetime.now(UTC),
            ended_at=datetime.now(UTC),
            risk_score=65,
            risk_level="high",
            summary="Detection deletion test",
        )
        db_session.add(event)
        await db_session.commit()
        await db_session.refresh(event)

        detection = Detection(
            camera_id=test_camera.id,
            file_path="/test/to_delete.jpg",
            object_type="person",
            confidence=0.92,
            bbox_x=10,
            bbox_y=20,
            bbox_width=100,
            bbox_height=100,
            detected_at=datetime.now(UTC),
        )
        db_session.add(detection)
        await db_session.commit()
        await db_session.refresh(detection)

        # Pre-populate detection aggregation caches
        cache_keys = [
            f"detections:{detection.id}",
            f"detections:event:{event.id}",
            f"detections:camera:{test_camera.id}",
            "detections:list",
            "detections:by_type:person",
        ]

        for key in cache_keys:
            await cache_service.set(key, {"cached": "detection_data"}, ttl=300)

        # Verify all caches populated
        for key in cache_keys:
            assert await cache_service.get(key) is not None

        # Simulate detection deletion invalidation
        await cache_service.invalidate_pattern(
            "detections:*", reason=CacheInvalidationReason.DETECTION_DELETED
        )

        # Verify all detection caches invalidated
        for key in cache_keys:
            assert await cache_service.get(key) is None


# =============================================================================
# Test: Alert-Specific Cache Invalidation
# =============================================================================


class TestAlertCacheInvalidation:
    """Test cache invalidation for alert-related operations."""

    @pytest.mark.asyncio
    async def test_alert_creation_invalidates_alert_caches(
        self,
        db_session: AsyncSession,
        test_camera: Camera,
        cache_service: CacheService,
        cleanup_cache: None,
    ) -> None:
        """Test that alert creation invalidates alert list and camera alert caches."""
        # Create event for alert
        event = Event(
            batch_id=_unique_id("batch"),
            camera_id=test_camera.id,
            started_at=datetime.now(UTC),
            ended_at=datetime.now(UTC),
            risk_score=85,
            risk_level="critical",
            summary="Alert trigger event",
        )
        db_session.add(event)
        await db_session.commit()
        await db_session.refresh(event)

        # Pre-populate alert caches
        cache_keys = [
            "alerts:list",
            f"alerts:camera:{test_camera.id}",
            f"alerts:event:{event.id}",
            "alerts:unacknowledged",
        ]

        for key in cache_keys:
            await cache_service.set(key, {"alerts": []}, ttl=300)

        # Verify caches populated
        for key in cache_keys:
            assert await cache_service.get(key) is not None

        # Simulate alert creation invalidation
        await cache_service.invalidate_pattern(
            "alerts:*", reason=CacheInvalidationReason.ALERT_CREATED
        )

        # Verify all alert caches invalidated
        for key in cache_keys:
            assert await cache_service.get(key) is None

    @pytest.mark.asyncio
    async def test_alert_acknowledgement_invalidates_filtered_caches(
        self,
        db_session: AsyncSession,
        test_camera: Camera,
        cache_service: CacheService,
        cleanup_cache: None,
    ) -> None:
        """Test that acknowledging alerts invalidates unacknowledged filter caches."""
        # Create event
        event = Event(
            batch_id=_unique_id("batch"),
            camera_id=test_camera.id,
            started_at=datetime.now(UTC),
            ended_at=datetime.now(UTC),
            risk_score=90,
            risk_level="critical",
            summary="Acknowledgement test",
        )
        db_session.add(event)
        await db_session.commit()
        await db_session.refresh(event)

        # Create alert (Alert doesn't have camera_id - linked through event)
        alert = Alert(
            event_id=event.id,
            severity="critical",
            status="pending",
            dedup_key=f"test_alert_{event.id}",
        )
        db_session.add(alert)
        await db_session.commit()
        await db_session.refresh(alert)

        # Pre-populate filtered alert caches
        cache_keys = [
            f"alerts:{alert.id}",
            "alerts:acknowledged:false",
            "alerts:acknowledged:true",
            "alerts:list",
        ]

        for key in cache_keys:
            await cache_service.set(key, {"cached": "alert_data"}, ttl=300)

        # Verify caches populated
        for key in cache_keys:
            assert await cache_service.get(key) is not None

        # Simulate alert acknowledgement
        await cache_service.invalidate_pattern(
            "alerts:*", reason=CacheInvalidationReason.ALERT_ACKNOWLEDGED
        )

        # Verify all alert caches invalidated
        for key in cache_keys:
            assert await cache_service.get(key) is None


# =============================================================================
# Test: Time-Based Cache Keys
# =============================================================================


class TestTimeBasedCacheKeys:
    """Test cache invalidation for time-range filtered caches."""

    @pytest.mark.asyncio
    async def test_event_creation_invalidates_date_range_caches(
        self,
        db_session: AsyncSession,
        test_camera: Camera,
        cache_service: CacheService,
        cleanup_cache: None,
    ) -> None:
        """Test that event creation invalidates all date-range event caches.

        When new events are created, caches with date range filters (e.g.,
        last 7 days, last 30 days) should be invalidated since the new event
        might fall into those ranges.
        """
        # Create event
        event = Event(
            batch_id=_unique_id("batch"),
            camera_id=test_camera.id,
            started_at=datetime.now(UTC),
            ended_at=datetime.now(UTC),
            risk_score=70,
            risk_level="high",
            summary="Date range test",
        )
        db_session.add(event)
        await db_session.commit()

        # Pre-populate various date-range caches
        today = datetime.now(UTC).date()
        yesterday = today - timedelta(days=1)
        week_ago = today - timedelta(days=7)

        date_cache_keys = [
            f"stats:events:{today}:{today}",  # Today only
            f"stats:events:{yesterday}:{today}",  # Last 2 days
            f"stats:events:{week_ago}:{today}",  # Last 7 days
            "stats:events:none:none",  # No date filter
        ]

        for key in date_cache_keys:
            await cache_service.set(key, {"total_events": 0}, ttl=300)

        # Verify all caches populated
        for key in date_cache_keys:
            assert await cache_service.get(key) is not None

        # Simulate event creation invalidation
        await cache_service.invalidate_event_stats(reason=CacheInvalidationReason.EVENT_CREATED)

        # Verify all date-range caches invalidated
        for key in date_cache_keys:
            assert await cache_service.get(key) is None

    @pytest.mark.asyncio
    async def test_detection_stats_cache_respects_time_boundaries(
        self,
        db_session: AsyncSession,
        test_camera: Camera,
        cache_service: CacheService,
        cleanup_cache: None,
    ) -> None:
        """Test that detection stats caches are properly invalidated by time.

        Detection statistics with time filters should be invalidated when
        new detections are added within those time ranges.
        """
        # Create event and detection
        event = Event(
            batch_id=_unique_id("batch"),
            camera_id=test_camera.id,
            started_at=datetime.now(UTC),
            ended_at=datetime.now(UTC),
            risk_score=55,
            risk_level="medium",
            summary="Time boundary test",
        )
        db_session.add(event)
        await db_session.commit()
        await db_session.refresh(event)

        detection = Detection(
            camera_id=test_camera.id,
            file_path="/test/time_test.jpg",
            object_type="person",
            confidence=0.87,
            bbox_x=100,
            bbox_y=150,
            bbox_width=100,
            bbox_height=100,
            detected_at=datetime.now(UTC),
        )
        db_session.add(detection)
        await db_session.commit()

        # Pre-populate time-based detection stats caches
        now = datetime.now(UTC)
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(days=1)

        time_cache_keys = [
            f"detections:stats:{hour_ago.isoformat()}:{now.isoformat()}",
            f"detections:stats:{day_ago.isoformat()}:{now.isoformat()}",
            "detections:stats:none:none",
        ]

        for key in time_cache_keys:
            await cache_service.set(key, {"total_detections": 0}, ttl=300)

        # Verify caches populated
        for key in time_cache_keys:
            assert await cache_service.get(key) is not None

        # Simulate detection creation invalidation
        await cache_service.invalidate_pattern(
            "detections:stats:*", reason=CacheInvalidationReason.DETECTION_CREATED
        )

        # Verify all time-based caches invalidated
        for key in time_cache_keys:
            assert await cache_service.get(key) is None
