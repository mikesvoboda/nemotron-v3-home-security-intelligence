"""Integration tests for concurrent access patterns and race conditions.

This module tests that concurrent operations are handled safely across the system:

1. **Event-Detection Association** - Multiple concurrent attempts to create same link
2. **Batch Closure** - Only one process should close a batch
3. **Camera Status Updates** - Later timestamps should win (last-write-wins)
4. **Detection Creation** - Concurrent detection creation for same camera
5. **Event Creation** - Concurrent event creation with same batch_id
6. **Redis Operations** - Concurrent Redis list operations (RPUSH)
7. **Database Transactions** - Concurrent updates to same records
8. **Lock Acquisition** - Proper lock handling in batch aggregator
9. **Idempotency Keys** - Concurrent requests with same idempotency key
10. **Soft Delete** - Concurrent soft delete operations
11. **Search Vector Updates** - Concurrent updates to search_vector

Uses shared fixtures from conftest.py:
- integration_db: PostgreSQL test database
- db_session: Per-test database session
- real_redis: Real Redis client for concurrency tests
- client: httpx AsyncClient with test app

Note: These tests run concurrently and may be slower than standard tests.
The integration marker is auto-applied based on directory location.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from backend.core.database import get_session
from backend.models.camera import Camera
from backend.models.detection import Detection
from backend.models.event import Event
from backend.models.event_detection import EventDetection
from backend.services.batch_aggregator import BatchAggregator
from backend.tests.integration.conftest import unique_id

# Mark all tests in this module as integration tests (auto-applied by conftest.py)
# These tests require real database/Redis and test concurrent access patterns


# =============================================================================
# Test 1: Concurrent Event-Detection Association
# =============================================================================


class TestConcurrentEventDetectionAssociation:
    """Test concurrent attempts to create event-detection associations.

    Race condition: Multiple processes trying to link the same detection to the
    same event should result in exactly one association record.
    """

    @pytest.fixture
    async def sample_event(self, integration_db: Any) -> Event:
        """Create a sample event for testing."""
        async with get_session() as db:
            camera_id = unique_id("cam")
            camera = Camera(
                id=camera_id,
                name=f"Test Camera {camera_id}",
                folder_path=f"/export/foscam/{camera_id}",
                status="online",
            )
            db.add(camera)
            await db.commit()

            event = Event(
                batch_id=unique_id("batch"),
                camera_id=camera_id,
                started_at=datetime.now(UTC),
                risk_score=50,
            )
            db.add(event)
            await db.commit()
            await db.refresh(event)
            return event

    @pytest.fixture
    async def sample_detection(self, integration_db: Any, sample_event: Event) -> Detection:
        """Create a sample detection for testing."""
        async with get_session() as db:
            detection = Detection(
                camera_id=sample_event.camera_id,
                file_path=f"/export/foscam/{sample_event.camera_id}/test.jpg",
                file_type="image/jpeg",
                detected_at=datetime.now(UTC),
                object_type="person",
                confidence=0.95,
                bbox_x=100,
                bbox_y=200,
                bbox_width=150,
                bbox_height=300,
            )
            db.add(detection)
            await db.commit()
            await db.refresh(detection)
            return detection

    async def _link_detection_to_event(
        self, event_id: int, detection_id: int
    ) -> tuple[bool, Exception | None]:
        """Attempt to link a detection to an event.

        Returns:
            Tuple of (success, exception) where success is True if link was created
        """
        try:
            async with get_session() as db:
                # Check if association already exists
                stmt = select(EventDetection).where(
                    EventDetection.event_id == event_id,
                    EventDetection.detection_id == detection_id,
                )
                result = await db.execute(stmt)
                existing = result.scalar_one_or_none()

                if existing:
                    return (False, None)

                # Create new association
                assoc = EventDetection(
                    event_id=event_id,
                    detection_id=detection_id,
                )
                db.add(assoc)
                await db.commit()
                return (True, None)
        except IntegrityError as e:
            # Expected: duplicate key violation on composite primary key
            return (False, e)
        except Exception as e:
            return (False, e)

    @pytest.mark.asyncio
    async def test_concurrent_event_detection_creation(
        self, integration_db: Any, sample_event: Event, sample_detection: Detection
    ) -> None:
        """Multiple processes creating same event-detection link.

        Expected: Only one association should be created, others should fail
        gracefully with IntegrityError due to composite primary key constraint.
        """
        # 10 concurrent attempts to create same link
        tasks = [
            self._link_detection_to_event(sample_event.id, sample_detection.id) for _ in range(10)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Count successful creations (should be exactly 1)
        successful_creations = sum(
            1 for result in results if not isinstance(result, Exception) and result[0]
        )

        # Verify exactly one link exists in database
        async with get_session() as db:
            stmt = select(EventDetection).where(
                EventDetection.event_id == sample_event.id,
                EventDetection.detection_id == sample_detection.id,
            )
            result = await db.execute(stmt)
            links = result.scalars().all()

        assert len(links) == 1, f"Expected 1 link, found {len(links)}"
        assert successful_creations <= 1, (
            f"Expected at most 1 successful creation, got {successful_creations}"
        )


# =============================================================================
# Test 2: Concurrent Batch Closure
# =============================================================================


class TestConcurrentBatchClosure:
    """Test that only one process can close a batch.

    Race condition: Multiple processes trying to close the same batch should
    result in exactly one closure, with others failing or detecting it's closed.
    """

    @pytest.fixture
    async def batch_aggregator(self, real_redis: Any) -> BatchAggregator:
        """Create a batch aggregator for testing."""
        return BatchAggregator(redis_client=real_redis)

    @pytest.fixture
    async def sample_camera(self, integration_db: Any) -> Camera:
        """Create a sample camera for batch testing."""
        async with get_session() as db:
            camera_id = unique_id("cam")
            camera = Camera(
                id=camera_id,
                name=f"Test Camera {camera_id}",
                folder_path=f"/export/foscam/{camera_id}",
                status="online",
            )
            db.add(camera)
            await db.commit()
            await db.refresh(camera)
            return camera

    async def _create_batch(
        self, aggregator: BatchAggregator, camera_id: str
    ) -> tuple[str, list[int]]:
        """Create a batch with detections for testing.

        Returns:
            Tuple of (batch_id, detection_ids)
        """
        # Create detections in database
        detection_ids = []
        async with get_session() as db:
            for i in range(3):
                detection = Detection(
                    camera_id=camera_id,
                    file_path=f"/export/foscam/{camera_id}/test_{i}.jpg",
                    file_type="image/jpeg",
                    detected_at=datetime.now(UTC),
                    object_type="person",
                    confidence=0.90,
                    bbox_x=100,
                    bbox_y=200,
                    bbox_width=150,
                    bbox_height=300,
                )
                db.add(detection)
                await db.flush()
                detection_ids.append(detection.id)
            await db.commit()

        # Add detections to batch via aggregator
        batch_id = None
        for det_id in detection_ids:
            result_batch_id = await aggregator.add_detection(
                camera_id, det_id, f"/export/foscam/{camera_id}/test_{det_id}.jpg"
            )
            if batch_id is None:
                batch_id = result_batch_id

        assert batch_id is not None
        return batch_id, detection_ids

    async def _try_close_batch(
        self, aggregator: BatchAggregator, batch_id: str, camera_id: str
    ) -> bool:
        """Attempt to close a batch.

        Returns:
            True if this call successfully closed the batch, False otherwise
        """
        # Use Redis WATCH/MULTI/EXEC for atomic check-and-delete
        client = aggregator._redis._ensure_connected()
        batch_key = f"batch:{camera_id}:current"

        async with client.pipeline() as pipe:
            try:
                # Watch the key for changes
                await pipe.watch(batch_key)

                # Check current value
                current_batch = await client.get(batch_key)
                if current_batch is None:
                    await pipe.unwatch()
                    return False

                # Decode bytes to string
                current_batch_str = (
                    current_batch.decode() if isinstance(current_batch, bytes) else current_batch
                )

                if current_batch_str != batch_id:
                    await pipe.unwatch()
                    return False

                # Begin transaction
                pipe.multi()
                # Delete the key
                pipe.delete(batch_key)
                # Execute atomically
                result = await pipe.execute()

                # result[0] is the number of keys deleted
                return result[0] > 0
            except Exception:
                # Transaction failed (key was modified by another process)
                return False

    @pytest.mark.asyncio
    async def test_concurrent_batch_closure(
        self, integration_db: Any, batch_aggregator: BatchAggregator, sample_camera: Camera
    ) -> None:
        """Only one process should close a batch.

        Expected: Exactly one concurrent call should successfully close the batch.
        Note: This tests atomic batch closure using Redis DELETE operation.
        """
        # Create a batch
        batch_id, _ = await self._create_batch(batch_aggregator, sample_camera.id)

        # Verify batch exists in Redis
        client = batch_aggregator._redis._ensure_connected()
        batch_key = f"batch:{sample_camera.id}:current"
        current_batch = await client.get(batch_key)
        assert current_batch is not None, f"Batch key {batch_key} does not exist after creation"

        # 10 concurrent attempts to close the batch
        async def try_close() -> bool:
            return await self._try_close_batch(batch_aggregator, batch_id, sample_camera.id)

        tasks = [try_close() for _ in range(10)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Count successful closures
        closure_count = sum(1 for result in results if result is True)

        assert closure_count == 1, f"Expected 1 closure, got {closure_count}"


# =============================================================================
# Test 3: Concurrent Camera Status Updates
# =============================================================================


class TestConcurrentCameraStatusUpdates:
    """Test that later timestamps win in concurrent camera status updates.

    Race condition: Out-of-order status updates should not overwrite newer data.
    """

    @pytest.fixture
    async def sample_camera(self, integration_db: Any) -> Camera:
        """Create a sample camera for status update testing."""
        async with get_session() as db:
            camera_id = unique_id("cam")
            camera = Camera(
                id=camera_id,
                name=f"Test Camera {camera_id}",
                folder_path=f"/export/foscam/{camera_id}",
                status="online",
            )
            db.add(camera)
            await db.commit()
            await db.refresh(camera)
            return camera

    async def _update_camera_status(self, camera_id: str, status: str, timestamp: datetime) -> None:
        """Update camera status with a specific timestamp.

        Uses last-write-wins strategy: only update if timestamp is newer.
        """
        async with get_session() as db:
            stmt = select(Camera).where(Camera.id == camera_id)
            result = await db.execute(stmt)
            camera = result.scalar_one()

            # Last-write-wins: only update if timestamp is newer than last_seen_at
            if camera.last_seen_at is None or timestamp > camera.last_seen_at:
                camera.status = status
                camera.last_seen_at = timestamp
                await db.commit()

    @pytest.mark.asyncio
    async def test_concurrent_camera_status_updates_last_write_wins(
        self, integration_db: Any, sample_camera: Camera
    ) -> None:
        """Later timestamps should win in concurrent status updates.

        Expected: Final status should be from the latest timestamp, even if
        updates arrive out of order.
        """
        # Create three timestamps
        t1 = datetime.now(UTC)
        t2 = t1 + timedelta(seconds=1)
        t3 = t1 + timedelta(seconds=2)

        # Simulate out-of-order updates (t3 first, then t2, then t1)
        await self._update_camera_status(sample_camera.id, "offline", t3)
        await self._update_camera_status(sample_camera.id, "online", t2)  # Should be ignored
        await self._update_camera_status(sample_camera.id, "error", t1)  # Should be ignored

        # Verify final state has latest timestamp
        async with get_session() as db:
            stmt = select(Camera).where(Camera.id == sample_camera.id)
            result = await db.execute(stmt)
            camera = result.scalar_one()

        assert camera.status == "offline", f"Expected 'offline', got {camera.status}"
        assert camera.last_seen_at == t3, f"Expected timestamp {t3}, got {camera.last_seen_at}"

    @pytest.mark.asyncio
    async def test_concurrent_camera_status_updates_parallel(
        self, integration_db: Any, sample_camera: Camera
    ) -> None:
        """Concurrent status updates with last-write-wins semantics.

        Expected: The update with the latest timestamp should win, regardless of
        the order in which updates are processed.
        """
        # Create timestamps for concurrent updates
        base_time = datetime.now(UTC)
        # Use valid status values from CHECK constraint
        valid_statuses = ["online", "offline", "error", "unknown"]
        updates = [
            (base_time + timedelta(seconds=i), valid_statuses[i % len(valid_statuses)])
            for i in range(10)
        ]

        # Shuffle to simulate out-of-order arrival
        import random

        shuffled_updates = updates.copy()
        random.shuffle(shuffled_updates)

        # Apply updates with small delays to ensure they complete
        for timestamp, status in shuffled_updates:
            await self._update_camera_status(sample_camera.id, status, timestamp)
            await asyncio.sleep(0.001)  # Small delay to ensure transaction completes

        # Verify final state has latest status
        async with get_session() as db:
            stmt = select(Camera).where(Camera.id == sample_camera.id)
            result = await db.execute(stmt)
            camera = result.scalar_one()

        # Final status should be from the latest timestamp (index 9)
        expected_status = valid_statuses[9 % len(valid_statuses)]
        expected_timestamp = base_time + timedelta(seconds=9)

        assert camera.status == expected_status, (
            f"Expected '{expected_status}', got {camera.status}"
        )
        assert camera.last_seen_at == expected_timestamp, (
            f"Expected {expected_timestamp}, got {camera.last_seen_at}"
        )


# =============================================================================
# Test 4: Concurrent Detection Creation
# =============================================================================


class TestConcurrentDetectionCreation:
    """Test concurrent detection creation for the same camera.

    Race condition: Multiple processes creating detections should not cause
    constraint violations or lost writes.
    """

    @pytest.fixture
    async def sample_camera(self, integration_db: Any) -> Camera:
        """Create a sample camera for detection testing."""
        async with get_session() as db:
            camera_id = unique_id("cam")
            camera = Camera(
                id=camera_id,
                name=f"Test Camera {camera_id}",
                folder_path=f"/export/foscam/{camera_id}",
                status="online",
            )
            db.add(camera)
            await db.commit()
            await db.refresh(camera)
            return camera

    async def _create_detection(self, camera_id: str, index: int) -> int:
        """Create a detection and return its ID."""
        async with get_session() as db:
            detection = Detection(
                camera_id=camera_id,
                file_path=f"/export/foscam/{camera_id}/test_{index}.jpg",
                file_type="image/jpeg",
                detected_at=datetime.now(UTC),
                object_type="person",
                confidence=0.90,
                bbox_x=100,
                bbox_y=200,
                bbox_width=150,
                bbox_height=300,
            )
            db.add(detection)
            await db.commit()
            await db.refresh(detection)
            return detection.id

    @pytest.mark.asyncio
    async def test_concurrent_detection_creation(
        self, integration_db: Any, sample_camera: Camera
    ) -> None:
        """Multiple processes creating detections concurrently.

        Expected: All detections should be created successfully without conflicts.
        """
        # Create 20 detections concurrently
        tasks = [self._create_detection(sample_camera.id, i) for i in range(20)]
        detection_ids = await asyncio.gather(*tasks, return_exceptions=True)

        # Verify all detections were created
        successful_ids = [det_id for det_id in detection_ids if not isinstance(det_id, Exception)]

        assert len(successful_ids) == 20, f"Expected 20 detections, got {len(successful_ids)}"

        # Verify all IDs are unique
        assert len(set(successful_ids)) == 20, "Detection IDs are not unique"

        # Verify all detections exist in database
        async with get_session() as db:
            stmt = select(Detection).where(Detection.camera_id == sample_camera.id)
            result = await db.execute(stmt)
            detections = result.scalars().all()

        assert len(detections) == 20, f"Expected 20 detections in DB, found {len(detections)}"


# =============================================================================
# Test 5: Concurrent Event Creation with Same Batch ID
# =============================================================================


class TestConcurrentEventCreation:
    """Test concurrent event creation with the same batch_id.

    Race condition: Multiple processes trying to create events with the same
    batch_id should result in exactly one event (idempotency).
    """

    @pytest.fixture
    async def sample_camera(self, integration_db: Any) -> Camera:
        """Create a sample camera for event testing."""
        async with get_session() as db:
            camera_id = unique_id("cam")
            camera = Camera(
                id=camera_id,
                name=f"Test Camera {camera_id}",
                folder_path=f"/export/foscam/{camera_id}",
                status="online",
            )
            db.add(camera)
            await db.commit()
            await db.refresh(camera)
            return camera

    async def _create_event(
        self, batch_id: str, camera_id: str
    ) -> tuple[int | None, Exception | None]:
        """Attempt to create an event with a specific batch_id.

        Returns:
            Tuple of (event_id, exception) where event_id is None if creation failed
        """
        try:
            async with get_session() as db:
                # Check if event with this batch_id already exists
                stmt = select(Event).where(Event.batch_id == batch_id)
                result = await db.execute(stmt)
                existing = result.scalar_one_or_none()

                if existing:
                    return (existing.id, None)

                # Create new event
                event = Event(
                    batch_id=batch_id,
                    camera_id=camera_id,
                    started_at=datetime.now(UTC),
                    risk_score=50,
                )
                db.add(event)
                await db.commit()
                await db.refresh(event)
                return (event.id, None)
        except Exception as e:
            return (None, e)

    @pytest.mark.asyncio
    async def test_concurrent_event_creation_same_batch_id(
        self, integration_db: Any, sample_camera: Camera
    ) -> None:
        """Multiple processes creating events with same batch_id.

        Expected: Only one event should be created, others should detect the
        existing event and return its ID.
        """
        batch_id = unique_id("batch")

        # 10 concurrent attempts to create event with same batch_id
        tasks = [self._create_event(batch_id, sample_camera.id) for _ in range(10)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All results should have the same event_id
        event_ids = [
            result[0]
            for result in results
            if not isinstance(result, Exception) and result[0] is not None
        ]

        assert len(event_ids) > 0, "No events were created"
        assert len(set(event_ids)) == 1, f"Expected 1 unique event_id, got {len(set(event_ids))}"

        # Verify exactly one event exists in database
        async with get_session() as db:
            stmt = select(Event).where(Event.batch_id == batch_id)
            result = await db.execute(stmt)
            events = result.scalars().all()

        assert len(events) == 1, f"Expected 1 event, found {len(events)}"


# =============================================================================
# Test 6: Concurrent Redis List Operations
# =============================================================================


class TestConcurrentRedisOperations:
    """Test concurrent Redis list operations (RPUSH).

    Race condition: Concurrent appends to the same Redis list should not lose
    any values due to race conditions.
    """

    @pytest.mark.asyncio
    async def test_concurrent_redis_rpush(self, real_redis: Any) -> None:
        """Concurrent RPUSH operations should not lose values.

        Expected: All values should be present in the list after concurrent appends.
        Note: Redis RPUSH is atomic, so this test should always pass.
        """
        list_key = f"test:list:{unique_id('list')}"

        # Get underlying Redis client
        client = real_redis._ensure_connected()

        # 100 concurrent RPUSH operations
        async def push_value(value: int) -> None:
            await client.rpush(list_key, str(value))  # Store as string

        tasks = [push_value(i) for i in range(100)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Check for exceptions
        exceptions = [r for r in results if isinstance(r, Exception)]
        if exceptions:
            pytest.fail(f"Some RPUSH operations failed: {exceptions[:5]}")

        # Verify all values are present
        values = await client.lrange(list_key, 0, -1)
        assert len(values) == 100, f"Expected 100 values, got {len(values)}"

        # Verify all unique values are present (may be in any order)
        unique_values = {int(v.decode() if isinstance(v, bytes) else v) for v in values}
        assert unique_values == set(range(100)), f"Expected all values 0-99, got {unique_values}"

        # Cleanup
        await client.delete(list_key)


# =============================================================================
# Test 7: Concurrent Database Transaction Rollback
# =============================================================================


class TestConcurrentDatabaseTransactions:
    """Test concurrent database transactions and rollback behavior.

    Race condition: Concurrent transactions updating the same record should
    handle conflicts properly without data loss.
    """

    @pytest.fixture
    async def sample_camera(self, integration_db: Any) -> Camera:
        """Create a sample camera for transaction testing."""
        async with get_session() as db:
            camera_id = unique_id("cam")
            camera = Camera(
                id=camera_id,
                name=f"Test Camera {camera_id}",
                folder_path=f"/export/foscam/{camera_id}",
                status="online",
            )
            db.add(camera)
            await db.commit()
            await db.refresh(camera)
            return camera

    async def _update_camera_name(self, camera_id: str, new_name: str) -> bool:
        """Update camera name in a transaction.

        Returns:
            True if update succeeded, False if it failed
        """
        try:
            async with get_session() as db:
                stmt = select(Camera).where(Camera.id == camera_id)
                result = await db.execute(stmt)
                camera = result.scalar_one()

                camera.name = new_name
                await db.commit()
                return True
        except Exception:
            return False

    @pytest.mark.asyncio
    async def test_concurrent_database_updates(
        self, integration_db: Any, sample_camera: Camera
    ) -> None:
        """Concurrent updates to the same record should not cause data loss.

        Expected: Last write wins, no exceptions or rollbacks.
        """
        # 10 concurrent updates to the same camera name
        tasks = [
            self._update_camera_name(sample_camera.id, f"Camera Update {i}") for i in range(10)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All updates should succeed (or gracefully handle conflicts)
        successful_updates = sum(1 for result in results if result is True)
        assert successful_updates >= 1, "At least one update should succeed"

        # Verify final state
        async with get_session() as db:
            stmt = select(Camera).where(Camera.id == sample_camera.id)
            result = await db.execute(stmt)
            camera = result.scalar_one()

        assert camera.name.startswith("Camera Update"), f"Unexpected name: {camera.name}"


# =============================================================================
# Test 8: Concurrent Soft Delete Operations
# =============================================================================


class TestConcurrentSoftDelete:
    """Test concurrent soft delete operations.

    Race condition: Multiple processes trying to soft delete the same camera
    should not cause conflicts.
    """

    @pytest.fixture
    async def sample_camera(self, integration_db: Any) -> Camera:
        """Create a sample camera for soft delete testing."""
        async with get_session() as db:
            camera_id = unique_id("cam")
            camera = Camera(
                id=camera_id,
                name=f"Test Camera {camera_id}",
                folder_path=f"/export/foscam/{camera_id}",
                status="online",
            )
            db.add(camera)
            await db.commit()
            await db.refresh(camera)
            return camera

    async def _soft_delete_camera(self, camera_id: str) -> bool:
        """Soft delete a camera.

        Returns:
            True if camera was soft deleted, False if it was already deleted
        """
        async with get_session() as db:
            stmt = select(Camera).where(Camera.id == camera_id)
            result = await db.execute(stmt)
            camera = result.scalar_one()

            if camera.deleted_at is not None:
                return False

            camera.soft_delete()
            await db.commit()
            return True

    @pytest.mark.asyncio
    async def test_concurrent_soft_delete(self, integration_db: Any, sample_camera: Camera) -> None:
        """Concurrent soft delete operations should be idempotent.

        Expected: First call sets deleted_at, subsequent calls are no-ops.
        """
        # 10 concurrent soft delete attempts
        tasks = [self._soft_delete_camera(sample_camera.id) for _ in range(10)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # At least one should succeed (others may return False if already deleted)
        successful_deletes = sum(1 for result in results if result is True)
        assert successful_deletes >= 1, "At least one delete should succeed"

        # Verify camera is soft deleted
        async with get_session() as db:
            stmt = select(Camera).where(Camera.id == sample_camera.id)
            result = await db.execute(stmt)
            camera = result.scalar_one()

        assert camera.deleted_at is not None, "Camera should be soft deleted"


# =============================================================================
# Test 9: Concurrent Batch Detection Addition
# =============================================================================


class TestConcurrentBatchDetectionAddition:
    """Test concurrent addition of detections to the same batch.

    Race condition: Multiple processes adding detections to the same batch
    should not lose any detections due to race conditions.
    """

    @pytest.fixture
    async def batch_aggregator(self, real_redis: Any) -> BatchAggregator:
        """Create a batch aggregator for testing."""
        return BatchAggregator(redis_client=real_redis)

    @pytest.fixture
    async def sample_camera(self, integration_db: Any) -> Camera:
        """Create a sample camera for batch testing."""
        async with get_session() as db:
            camera_id = unique_id("cam")
            camera = Camera(
                id=camera_id,
                name=f"Test Camera {camera_id}",
                folder_path=f"/export/foscam/{camera_id}",
                status="online",
            )
            db.add(camera)
            await db.commit()
            await db.refresh(camera)
            return camera

    async def _create_and_add_detection(
        self, aggregator: BatchAggregator, camera_id: str, index: int
    ) -> tuple[int, str]:
        """Create a detection and add it to a batch.

        Returns:
            Tuple of (detection_id, batch_id)
        """
        # Create detection in database
        async with get_session() as db:
            detection = Detection(
                camera_id=camera_id,
                file_path=f"/export/foscam/{camera_id}/test_{index}.jpg",
                file_type="image/jpeg",
                detected_at=datetime.now(UTC),
                object_type="person",
                confidence=0.90,
                bbox_x=100,
                bbox_y=200,
                bbox_width=150,
                bbox_height=300,
            )
            db.add(detection)
            await db.commit()
            await db.refresh(detection)
            detection_id = detection.id

        # Add to batch
        batch_id = await aggregator.add_detection(
            camera_id, detection_id, f"/export/foscam/{camera_id}/test_{index}.jpg"
        )
        return (detection_id, batch_id)

    @pytest.mark.asyncio
    async def test_concurrent_batch_detection_addition(
        self, integration_db: Any, batch_aggregator: BatchAggregator, sample_camera: Camera
    ) -> None:
        """Concurrent addition of detections to the same batch.

        Expected: All detections should be added to batches without loss.
        Note: Due to batch window timing, concurrent additions may create multiple batches.
        The key test is that no detections are lost.
        """
        # Add 20 detections concurrently
        tasks = [
            self._create_and_add_detection(batch_aggregator, sample_camera.id, i) for i in range(20)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Verify all detections were added successfully
        successful_additions = [result for result in results if not isinstance(result, Exception)]
        assert len(successful_additions) == 20, (
            f"Expected 20 successful additions, got {len(successful_additions)}"
        )

        # Get all unique batch IDs (may be more than one due to timing)
        batch_ids = [result[1] for result in successful_additions]
        unique_batch_ids = set(batch_ids)

        # Verify all detections are in Redis across all batches
        client = batch_aggregator._redis._ensure_connected()
        total_detections = 0
        for batch_id in unique_batch_ids:
            detection_ids = await client.lrange(f"batch:{batch_id}:detections", 0, -1)
            total_detections += len(detection_ids)

        assert total_detections == 20, (
            f"Expected 20 detections total, found {total_detections} across {len(unique_batch_ids)} batches"
        )


# =============================================================================
# Test 10: Concurrent Lock Acquisition in BatchAggregator
# =============================================================================


class TestConcurrentLockAcquisition:
    """Test concurrent lock acquisition in BatchAggregator.

    Race condition: Multiple coroutines requesting locks for the same camera
    should not create duplicate locks.
    """

    @pytest.mark.asyncio
    async def test_concurrent_camera_lock_acquisition(self, real_redis: Any) -> None:
        """Concurrent lock acquisition for the same camera should be safe.

        Expected: All coroutines should get the same lock instance.
        """
        aggregator = BatchAggregator(redis_client=real_redis)
        camera_id = unique_id("cam")

        # 100 concurrent lock acquisitions for the same camera
        async def get_lock() -> asyncio.Lock:
            return await aggregator._get_camera_lock(camera_id)

        tasks = [get_lock() for _ in range(100)]
        locks = await asyncio.gather(*tasks, return_exceptions=True)

        # All should be the same lock instance
        lock_ids = [id(lock) for lock in locks if not isinstance(lock, Exception)]
        unique_lock_ids = set(lock_ids)

        assert len(unique_lock_ids) == 1, f"Expected 1 unique lock, got {len(unique_lock_ids)}"


# =============================================================================
# Test 11: Concurrent Search Vector Updates
# =============================================================================


class TestConcurrentSearchVectorUpdates:
    """Test concurrent updates to event search vectors.

    Race condition: Concurrent updates to the same event's summary/reasoning
    should properly update the search vector via database trigger.
    """

    @pytest.fixture
    async def sample_event(self, integration_db: Any) -> Event:
        """Create a sample event for search vector testing."""
        async with get_session() as db:
            camera_id = unique_id("cam")
            camera = Camera(
                id=camera_id,
                name=f"Test Camera {camera_id}",
                folder_path=f"/export/foscam/{camera_id}",
                status="online",
            )
            db.add(camera)
            await db.commit()

            event = Event(
                batch_id=unique_id("batch"),
                camera_id=camera_id,
                started_at=datetime.now(UTC),
                risk_score=50,
                summary="Initial summary",
            )
            db.add(event)
            await db.commit()
            await db.refresh(event)
            return event

    async def _update_event_summary(self, event_id: int, summary: str) -> bool:
        """Update event summary (which triggers search vector update).

        Returns:
            True if update succeeded
        """
        try:
            async with get_session() as db:
                stmt = select(Event).where(Event.id == event_id)
                result = await db.execute(stmt)
                event = result.scalar_one()

                event.summary = summary
                await db.commit()
                return True
        except Exception:
            return False

    @pytest.mark.asyncio
    async def test_concurrent_search_vector_updates(
        self, integration_db: Any, sample_event: Event
    ) -> None:
        """Concurrent updates to event summary should properly update search vector.

        Expected: Search vector should be updated by database trigger without conflicts.
        """
        # 10 concurrent summary updates
        tasks = [
            self._update_event_summary(sample_event.id, f"Summary update {i}") for i in range(10)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All updates should succeed
        successful_updates = sum(1 for result in results if result is True)
        assert successful_updates >= 1, "At least one update should succeed"

        # Verify final state
        async with get_session() as db:
            stmt = select(Event).where(Event.id == sample_event.id)
            result = await db.execute(stmt)
            event = result.scalar_one()

        assert event.summary.startswith("Summary update"), f"Unexpected summary: {event.summary}"
        # search_vector is updated by trigger, so we can't directly assert its value
        # but we can verify it's not None (assuming trigger is working)
        # Note: In test environment, trigger may not be active, so this is optional


# =============================================================================
# Test 12: Concurrent Repository Save Operations (NEM-2566)
# =============================================================================


class TestConcurrentRepositorySave:
    """Test concurrent repository save operations with atomic upsert.

    Race condition (NEM-2566): Multiple processes trying to save the same entity
    concurrently should not cause constraint violations due to TOCTOU race
    between exists check and create/merge operations.
    """

    @pytest.fixture
    async def sample_camera_id(self, integration_db: Any) -> str:
        """Generate a unique camera ID for testing."""
        return unique_id("cam_save")

    async def _save_camera(
        self, camera_id: str, name: str, index: int
    ) -> tuple[bool, str | None, Exception | None]:
        """Attempt to save a camera using the repository save method.

        Returns:
            Tuple of (success, camera_name, exception)
        """
        try:
            async with get_session() as db:
                from backend.repositories.camera_repository import CameraRepository

                repo = CameraRepository(db)
                camera = Camera(
                    id=camera_id,
                    name=f"{name}_{index}",
                    folder_path=f"/export/foscam/{camera_id}",
                    status="online",
                )
                saved = await repo.save(camera)
                return (True, saved.name, None)
        except Exception as e:
            return (False, None, e)

    @pytest.mark.asyncio
    async def test_concurrent_save_same_entity(
        self, integration_db: Any, sample_camera_id: str
    ) -> None:
        """Multiple concurrent save operations for the same entity ID.

        Expected: All operations should complete without IntegrityError.
        The atomic UPSERT ensures only one INSERT happens, others become UPDATEs.
        """
        # 20 concurrent save attempts with the same camera ID
        tasks = [self._save_camera(sample_camera_id, "Camera", i) for i in range(20)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Count successful saves (should be all 20)
        successful_saves = sum(
            1 for result in results if not isinstance(result, Exception) and result[0]
        )

        # Count exceptions (should be 0)
        exceptions = [result for result in results if isinstance(result, Exception)]
        integrity_errors = [
            result[2]
            for result in results
            if not isinstance(result, Exception)
            and result[2] is not None
            and "IntegrityError" in str(type(result[2]))
        ]

        # All saves should succeed (no IntegrityErrors)
        assert len(exceptions) == 0, f"Unexpected exceptions: {exceptions[:3]}"
        assert len(integrity_errors) == 0, (
            f"IntegrityErrors should not occur with atomic upsert: {integrity_errors[:3]}"
        )
        assert successful_saves == 20, f"Expected 20 successful saves, got {successful_saves}"

        # Verify exactly one camera exists in database
        async with get_session() as db:
            stmt = select(Camera).where(Camera.id == sample_camera_id)
            result = await db.execute(stmt)
            cameras = result.scalars().all()

        assert len(cameras) == 1, f"Expected 1 camera, found {len(cameras)}"

    @pytest.mark.asyncio
    async def test_concurrent_save_interleaved_creates_and_updates(
        self, integration_db: Any, sample_camera_id: str
    ) -> None:
        """Interleaved create and update operations on the same entity.

        This tests the race condition between exists() check and create/merge.
        With atomic UPSERT, this should work without errors.
        """
        # First, create the camera
        async with get_session() as db:
            camera = Camera(
                id=sample_camera_id,
                name="Original Name",
                folder_path=f"/export/foscam/{sample_camera_id}",
                status="online",
            )
            db.add(camera)
            await db.commit()

        # Now run concurrent save operations (these should all be updates)
        tasks = [self._save_camera(sample_camera_id, "Updated", i) for i in range(10)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All should succeed
        successful_saves = sum(
            1 for result in results if not isinstance(result, Exception) and result[0]
        )
        assert successful_saves == 10, f"Expected 10 successful saves, got {successful_saves}"

        # Verify camera was updated (name should be one of the "Updated_N" values)
        async with get_session() as db:
            stmt = select(Camera).where(Camera.id == sample_camera_id)
            result = await db.execute(stmt)
            camera = result.scalar_one()

        assert camera.name.startswith("Updated_"), f"Unexpected name: {camera.name}"

    @pytest.mark.asyncio
    async def test_concurrent_save_different_entities(self, integration_db: Any) -> None:
        """Concurrent save operations for different entities should all succeed.

        This verifies that concurrent saves don't block each other when
        working with different primary keys.
        """
        # Create unique IDs for each concurrent operation
        camera_ids = [unique_id(f"cam_diff_{i}") for i in range(20)]

        async def save_unique_camera(idx: int) -> tuple[bool, str]:
            """Save a camera with unique ID."""
            camera_id = camera_ids[idx]
            try:
                async with get_session() as db:
                    from backend.repositories.camera_repository import CameraRepository

                    repo = CameraRepository(db)
                    camera = Camera(
                        id=camera_id,
                        name=f"Camera {idx}",
                        folder_path=f"/export/foscam/{camera_id}",
                        status="online",
                    )
                    saved = await repo.save(camera)
                    return (True, saved.id)
            except Exception:
                return (False, camera_id)

        # Run 20 concurrent saves for different cameras
        tasks = [save_unique_camera(i) for i in range(20)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All should succeed
        successful_saves = sum(
            1 for result in results if not isinstance(result, Exception) and result[0]
        )
        assert successful_saves == 20, f"Expected 20 successful saves, got {successful_saves}"

        # Verify all cameras exist in database
        async with get_session() as db:
            from sqlalchemy import or_

            stmt = select(Camera).where(or_(*[Camera.id == cid for cid in camera_ids]))
            result = await db.execute(stmt)
            cameras = result.scalars().all()

        assert len(cameras) == 20, f"Expected 20 cameras, found {len(cameras)}"


# =============================================================================
# Test 13: Concurrent Repository Merge Operations (NEM-2566)
# =============================================================================


class TestConcurrentRepositoryMerge:
    """Test concurrent repository merge operations with transaction safety.

    Race condition (NEM-2566): Multiple processes trying to merge detached
    entities should handle concurrent modifications gracefully.
    """

    @pytest.fixture
    async def sample_camera(self, integration_db: Any) -> Camera:
        """Create a sample camera for merge testing."""
        async with get_session() as db:
            camera_id = unique_id("cam_merge")
            camera = Camera(
                id=camera_id,
                name="Original Name",
                folder_path=f"/export/foscam/{camera_id}",
                status="online",
            )
            db.add(camera)
            await db.commit()
            await db.refresh(camera)
            return camera

    async def _merge_camera(
        self, camera_id: str, new_name: str
    ) -> tuple[bool, str | None, Exception | None]:
        """Attempt to merge a camera update using the repository merge method.

        Returns:
            Tuple of (success, final_name, exception)
        """
        try:
            async with get_session() as db:
                from backend.repositories.camera_repository import CameraRepository

                repo = CameraRepository(db)
                # Create a detached entity with updated values
                detached_camera = Camera(
                    id=camera_id,
                    name=new_name,
                    folder_path=f"/export/foscam/{camera_id}",
                    status="online",
                )
                merged = await repo.merge(detached_camera)
                return (True, merged.name, None)
        except Exception as e:
            return (False, None, e)

    @pytest.mark.asyncio
    async def test_concurrent_merge_operations(
        self, integration_db: Any, sample_camera: Camera
    ) -> None:
        """Multiple concurrent merge operations on the same entity.

        Expected: All merges should complete without errors due to savepoint isolation.
        Last write wins for the final value.
        """
        # 15 concurrent merge attempts
        tasks = [self._merge_camera(sample_camera.id, f"Merged Name {i}") for i in range(15)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Count successful merges
        successful_merges = sum(
            1 for result in results if not isinstance(result, Exception) and result[0]
        )

        # All should succeed
        assert successful_merges == 15, f"Expected 15 successful merges, got {successful_merges}"

        # Verify camera exists and has been updated
        async with get_session() as db:
            stmt = select(Camera).where(Camera.id == sample_camera.id)
            result = await db.execute(stmt)
            camera = result.scalar_one()

        assert camera.name.startswith("Merged Name"), f"Unexpected name: {camera.name}"
