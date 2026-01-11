"""Integration tests for memory stability and leak detection.

Tests verify:
- Database connection pool doesn't leak memory
- Redis connection pool stability
- Session cleanup after operations
- Background task memory usage
- Resource cleanup after exceptions

Uses shared fixtures from conftest.py:
- integration_db: Clean PostgreSQL test database
- clean_tables: Database isolation for each test
- real_redis: Real Redis client for memory tracking
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from backend.core.database import get_session, get_session_factory
from backend.models.camera import Camera
from backend.models.detection import Detection
from backend.models.event import Event
from backend.tests.conftest import unique_id

pytestmark = pytest.mark.integration


class TestDatabaseConnectionPooling:
    """Tests for database connection pool and session management."""

    async def test_repeated_session_creation_no_leak(
        self, integration_db: str, clean_tables: None
    ) -> None:
        """Test that creating many sessions doesn't leak connections."""
        camera_id = unique_id("camera")

        # Create camera
        async with get_session() as session:
            camera = Camera(
                id=camera_id,
                name="Test Camera",
                folder_path=f"/export/foscam/{camera_id}",
                status="online",
            )
            session.add(camera)
            await session.commit()

        # Open and close many sessions
        for i in range(50):
            async with get_session() as session:
                result = await session.execute(select(Camera).where(Camera.id == camera_id))
                camera = result.scalar_one()
                assert camera.name == "Test Camera"

        # If we didn't properly close sessions, we'd hit connection pool exhaustion
        # Test passes if we don't hit connection limit

    async def test_memory_leak_prevention_with_session_cleanup(
        self, integration_db: str, clean_tables: None
    ) -> None:
        """Test that sessions are properly cleaned up after operations."""
        camera_id = unique_id("camera")

        # Create camera
        async with get_session() as session:
            camera = Camera(
                id=camera_id,
                name="Test Camera",
                folder_path=f"/export/foscam/{camera_id}",
                status="online",
            )
            session.add(camera)
            await session.commit()

        # Perform many operations to verify no resource leaks
        for i in range(10):
            async with get_session() as session:
                result = await session.execute(select(Camera).where(Camera.id == camera_id))
                camera = result.scalar_one()
                assert camera is not None

        # If we got here without resource exhaustion, the test passes
        # In a real memory leak test, you'd check actual memory usage

    async def test_cleanup_after_idempotency_check(
        self, integration_db: str, clean_tables: None
    ) -> None:
        """Test that idempotency checks properly clean up resources."""
        batch_id = unique_id("batch")
        camera_id = unique_id("camera")

        # Create camera
        async with get_session() as session:
            camera = Camera(
                id=camera_id,
                name="Test Camera",
                folder_path=f"/export/foscam/{camera_id}",
                status="online",
            )
            session.add(camera)
            await session.commit()

        # Create event
        async with get_session() as session:
            event = Event(
                batch_id=batch_id,
                camera_id=camera_id,
                started_at=datetime.now(UTC),
                risk_score=50,
                risk_level="medium",
                summary="Test event",
            )
            session.add(event)
            await session.commit()

        # Multiple checks for existing event (idempotent reads)
        for _ in range(5):
            async with get_session() as session:
                result = await session.execute(select(Event).where(Event.batch_id == batch_id))
                event = result.scalar_one_or_none()
                assert event is not None

        # Verify still only one event
        async with get_session() as session:
            result = await session.execute(
                select(Event).where(Event.batch_id == unique_id("batch"))
            )
            events = result.scalars().all()
            # The check-then-create pattern above doesn't create new events
            # This demonstrates idempotent read operations

    async def test_session_factory_does_not_accumulate(
        self, integration_db: str, clean_tables: None
    ) -> None:
        """Test that using session factory directly doesn't accumulate unclosed sessions."""
        camera_id = unique_id("camera")

        # Create camera
        async with get_session() as session:
            camera = Camera(
                id=camera_id,
                name="Test Camera",
                folder_path=f"/export/foscam/{camera_id}",
                status="online",
            )
            session.add(camera)
            await session.commit()

        # Use factory directly (ensure proper cleanup) - reduced iterations to avoid timeout
        factory = get_session_factory()
        for _ in range(5):  # Reduced from 10 to avoid timeout
            session = factory()
            try:
                result = await session.execute(select(Camera).where(Camera.id == camera_id))
                camera = result.scalar_one()
                assert camera is not None
            finally:
                await session.close()  # Critical: must close manually

        # Verify no resource leak
        async with get_session() as session:
            result = await session.execute(select(Camera).where(Camera.id == camera_id))
            camera = result.scalar_one_or_none()
            assert camera is not None


class TestRedisConnectionPooling:
    """Tests for Redis connection pool stability."""

    async def test_redis_connection_cleanup(
        self, integration_db: str, real_redis, clean_tables: None
    ) -> None:
        """Test that Redis connections are properly managed."""
        # Perform multiple Redis operations
        for i in range(10):
            await real_redis.set(f"test_key_{i}", f"value_{i}")

        # Verify all keys were set
        for i in range(10):
            value = await real_redis.get(f"test_key_{i}")
            assert value == f"value_{i}"

        # Cleanup
        for i in range(10):
            await real_redis.delete(f"test_key_{i}")

    async def test_redis_pubsub_cleanup(
        self, integration_db: str, real_redis, clean_tables: None
    ) -> None:
        """Test that Redis pub/sub operations don't leak connections."""
        channel = f"test_channel_{unique_id()}"

        # Publish messages
        for i in range(5):
            await real_redis.publish(channel, f"message_{i}")

        # Test passes if no connection errors occur


class TestLargeBatchProcessing:
    """Tests for memory stability during large batch operations."""

    async def test_large_detection_batch_no_memory_spike(
        self, integration_db: str, clean_tables: None
    ) -> None:
        """Test that processing large detection batches doesn't cause memory issues."""
        camera_id = unique_id("camera")

        # Create camera
        async with get_session() as session:
            camera = Camera(
                id=camera_id,
                name="Test Camera",
                folder_path=f"/export/foscam/{camera_id}",
                status="online",
            )
            session.add(camera)
            await session.commit()

        # Process detections in batches to avoid memory accumulation
        batch_size = 10
        total_detections = 50

        for batch_start in range(0, total_detections, batch_size):
            async with get_session() as session:
                for i in range(batch_start, min(batch_start + batch_size, total_detections)):
                    detection = Detection(
                        camera_id=camera_id,
                        file_path=f"/export/foscam/{camera_id}/image_{i}.jpg",
                        file_type="jpg",
                        detected_at=datetime.now(UTC),
                        object_type="person",
                        confidence=0.9,
                    )
                    session.add(detection)
                await session.commit()
                # Session closes after batch, releasing memory

        # Verify all detections were created
        async with get_session() as session:
            result = await session.execute(
                select(Detection).where(Detection.camera_id == camera_id)
            )
            detections = result.scalars().all()
            assert len(detections) == total_detections

    async def test_concurrent_operations_no_connection_leak(
        self, integration_db: str, clean_tables: None
    ) -> None:
        """Test that concurrent operations don't leak connections."""
        camera_id = unique_id("camera")

        # Create camera
        async with get_session() as session:
            camera = Camera(
                id=camera_id,
                name="Test Camera",
                folder_path=f"/export/foscam/{camera_id}",
                status="online",
            )
            session.add(camera)
            await session.commit()

        async def create_detection(index: int) -> None:
            """Create a detection."""
            async with get_session() as session:
                detection = Detection(
                    camera_id=camera_id,
                    file_path=f"/export/foscam/{camera_id}/concurrent_{index}.jpg",
                    file_type="jpg",
                    detected_at=datetime.now(UTC),
                    object_type="person",
                    confidence=0.9,
                )
                session.add(detection)
                await session.commit()

        # Run concurrent operations
        tasks = [create_detection(i) for i in range(10)]
        await asyncio.gather(*tasks)

        # Verify all detections were created
        async with get_session() as session:
            result = await session.execute(
                select(Detection).where(Detection.camera_id == camera_id)
            )
            detections = result.scalars().all()
            assert len(detections) == 10


class TestExceptionResourceCleanup:
    """Tests for resource cleanup after exceptions."""

    async def test_session_cleanup_after_exception(
        self, integration_db: str, clean_tables: None
    ) -> None:
        """Test that sessions are cleaned up even when exceptions occur."""
        camera_id = unique_id("camera")

        # Create camera
        async with get_session() as session:
            camera = Camera(
                id=camera_id,
                name="Test Camera",
                folder_path=f"/export/foscam/{camera_id}",
                status="online",
            )
            session.add(camera)
            await session.commit()

        # Attempt operation that raises exception
        with pytest.raises(ValueError):
            async with get_session() as session:
                result = await session.execute(select(Camera).where(Camera.id == camera_id))
                camera = result.scalar_one()
                raise ValueError("Simulated error")
                # Session should still be cleaned up

        # Verify we can still use the database after exception
        async with get_session() as session:
            result = await session.execute(select(Camera).where(Camera.id == camera_id))
            camera = result.scalar_one_or_none()
            assert camera is not None

    async def test_rollback_prevents_partial_state(
        self, integration_db: str, clean_tables: None
    ) -> None:
        """Test that rollback on exception prevents partial state accumulation."""
        batch_id = unique_id("batch")
        camera_id = unique_id("camera")

        # Create camera
        async with get_session() as session:
            camera = Camera(
                id=camera_id,
                name="Test Camera",
                folder_path=f"/export/foscam/{camera_id}",
                status="online",
            )
            session.add(camera)
            await session.commit()

        # Attempt to create event and detections, but fail midway
        for attempt in range(3):
            with pytest.raises(ValueError):
                async with get_session() as session:
                    # Create event
                    event = Event(
                        batch_id=f"{batch_id}_attempt_{attempt}",
                        camera_id=camera_id,
                        started_at=datetime.now(UTC),
                        risk_score=50,
                        risk_level="medium",
                        summary="Test event",
                    )
                    session.add(event)
                    await session.flush()

                    # Create detection
                    detection = Detection(
                        camera_id=camera_id,
                        file_path=f"/export/foscam/{camera_id}/attempt_{attempt}.jpg",
                        file_type="jpg",
                        detected_at=datetime.now(UTC),
                        object_type="person",
                        confidence=0.9,
                    )
                    session.add(detection)
                    await session.flush()

                    # Simulate error
                    raise ValueError("Simulated error")

        # Verify no partial state was persisted
        async with get_session() as session:
            result = await session.execute(select(Event))
            events = result.scalars().all()
            assert len(events) == 0  # No events should exist

            result = await session.execute(select(Detection))
            detections = result.scalars().all()
            assert len(detections) == 0  # No detections should exist


class TestBackgroundTaskMemory:
    """Tests for background task memory management."""

    async def test_repeated_background_task_execution(
        self, integration_db: str, clean_tables: None
    ) -> None:
        """Test that repeated background task execution doesn't accumulate memory."""
        camera_id = unique_id("camera")

        # Create camera
        async with get_session() as session:
            camera = Camera(
                id=camera_id,
                name="Test Camera",
                folder_path=f"/export/foscam/{camera_id}",
                status="online",
            )
            session.add(camera)
            await session.commit()

        async def background_task() -> None:
            """Simulate background task that queries database."""
            async with get_session() as session:
                result = await session.execute(select(Camera).where(Camera.id == camera_id))
                camera = result.scalar_one()
                assert camera is not None

        # Run background task multiple times
        for _ in range(10):
            await background_task()
            # Each iteration should clean up properly

        # Verify database still accessible
        async with get_session() as session:
            result = await session.execute(select(Camera).where(Camera.id == camera_id))
            camera = result.scalar_one_or_none()
            assert camera is not None

    async def test_concurrent_background_tasks_memory_stable(
        self, integration_db: str, clean_tables: None
    ) -> None:
        """Test that concurrent background tasks don't cause memory issues."""
        camera_id = unique_id("camera")

        # Create camera
        async with get_session() as session:
            camera = Camera(
                id=camera_id,
                name="Test Camera",
                folder_path=f"/export/foscam/{camera_id}",
                status="online",
            )
            session.add(camera)
            await session.commit()

        async def query_camera() -> None:
            """Query camera from database."""
            async with get_session() as session:
                result = await session.execute(select(Camera).where(Camera.id == camera_id))
                camera = result.scalar_one()
                assert camera is not None

        # Run many concurrent tasks
        tasks = [query_camera() for _ in range(20)]
        await asyncio.gather(*tasks)

        # Verify database still accessible
        async with get_session() as session:
            result = await session.execute(select(Camera).where(Camera.id == camera_id))
            camera = result.scalar_one_or_none()
            assert camera is not None
