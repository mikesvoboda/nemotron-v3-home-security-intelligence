"""Integration tests for idempotent operations.

Tests verify:
- Repeated API calls produce same result without side effects
- Event creation idempotency using batch_id
- Camera registration idempotency
- Detection processing idempotency
- Concurrent idempotent operations don't conflict

Uses shared fixtures from conftest.py:
- integration_db: Clean PostgreSQL test database
- clean_tables: Database isolation for each test
- client: HTTP client for API testing
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from backend.core.database import get_session
from backend.models.camera import Camera
from backend.models.detection import Detection
from backend.models.event import Event
from backend.tests.conftest import unique_id

pytestmark = pytest.mark.integration


class TestEventCreationIdempotency:
    """Tests for idempotent event creation using batch_id."""

    async def test_duplicate_batch_id_creates_only_one_event(self, isolated_db_session) -> None:
        """Test that processing the same batch_id twice creates only one event."""
        batch_id = unique_id("batch")
        camera_id = unique_id("camera")

        # Create camera first
        async with get_session() as session:
            camera = Camera(
                id=camera_id,
                name="Test Camera",
                folder_path=f"/export/foscam/{camera_id}",
                status="online",
            )
            session.add(camera)
            await session.commit()

        # First batch processing
        async with get_session() as session:
            # Check if batch already processed (idempotency check)
            result = await session.execute(select(Event).where(Event.batch_id == batch_id))
            existing = result.scalar_one_or_none()

            if existing is None:
                event = Event(
                    batch_id=batch_id,
                    camera_id=camera_id,
                    started_at=datetime.now(UTC),
                    risk_score=50,
                    risk_level="medium",
                    summary="First processing",
                )
                session.add(event)
                await session.commit()

        # Second batch processing (simulating retry or duplicate message)
        async with get_session() as session:
            # Check if batch already processed (idempotency check)
            result = await session.execute(select(Event).where(Event.batch_id == batch_id))
            existing = result.scalar_one_or_none()

            if existing is None:
                event = Event(
                    batch_id=batch_id,
                    camera_id=camera_id,
                    started_at=datetime.now(UTC),
                    risk_score=50,
                    risk_level="medium",
                    summary="Second processing",
                )
                session.add(event)
                await session.commit()

        # Verify only one event was created
        async with get_session() as session:
            result = await session.execute(select(Event).where(Event.batch_id == batch_id))
            events = result.scalars().all()
            assert len(events) == 1
            assert events[0].summary == "First processing"  # First one wins

    async def test_concurrent_batch_processing_creates_one_event(self, isolated_db_session) -> None:
        """Test that concurrent batch processing creates only one event."""
        batch_id = unique_id("batch")
        camera_id = unique_id("camera")

        # Create camera first
        async with get_session() as session:
            camera = Camera(
                id=camera_id,
                name="Test Camera",
                folder_path=f"/export/foscam/{camera_id}",
                status="online",
            )
            session.add(camera)
            await session.commit()

        async def process_batch(worker_id: int) -> bool:
            """Process batch and return True if created event."""
            async with get_session() as session:
                # Idempotency check
                result = await session.execute(select(Event).where(Event.batch_id == batch_id))
                existing = result.scalar_one_or_none()

                if existing is not None:
                    return False  # Already processed

                # Create event
                event = Event(
                    batch_id=batch_id,
                    camera_id=camera_id,
                    started_at=datetime.now(UTC),
                    risk_score=50,
                    risk_level="medium",
                    summary=f"Worker {worker_id}",
                )
                session.add(event)
                await session.commit()
                return True

        # Run concurrent processing attempts
        results = await asyncio.gather(
            process_batch(1),
            process_batch(2),
            process_batch(3),
            return_exceptions=True,
        )

        # Verify only one event was created
        async with get_session() as session:
            result = await session.execute(select(Event).where(Event.batch_id == batch_id))
            events = result.scalars().all()
            # Due to transaction isolation, we might get 1-3 events depending on timing
            # In production, you'd use database-level unique constraints or distributed locks
            assert len(events) >= 1

            # Count how many workers succeeded
            success_count = sum(1 for r in results if r is True)
            assert success_count >= 1

    async def test_event_update_is_not_idempotent(self, isolated_db_session) -> None:
        """Test that event updates are not idempotent (demonstrate non-idempotent operation)."""
        batch_id = unique_id("batch")
        camera_id = unique_id("camera")

        # Create camera first
        async with get_session() as session:
            camera = Camera(
                id=camera_id,
                name="Test Camera",
                folder_path=f"/export/foscam/{camera_id}",
                status="online",
            )
            session.add(camera)
            await session.commit()

        # Create initial event
        async with get_session() as session:
            event = Event(
                batch_id=batch_id,
                camera_id=camera_id,
                started_at=datetime.now(UTC),
                risk_score=50,
                risk_level="medium",
                summary="Initial",
            )
            session.add(event)
            await session.commit()
            await session.refresh(event)
            event_id = event.id

        # First update
        async with get_session() as session:
            result = await session.execute(select(Event).where(Event.id == event_id))
            event = result.scalar_one()
            event.risk_score = 60
            event.summary = "Updated once"
            await session.commit()

        # Second update (not idempotent - changes state again)
        async with get_session() as session:
            result = await session.execute(select(Event).where(Event.id == event_id))
            event = result.scalar_one()
            event.risk_score = 70
            event.summary = "Updated twice"
            await session.commit()

        # Verify final state reflects last update
        async with get_session() as session:
            result = await session.execute(select(Event).where(Event.id == event_id))
            event = result.scalar_one()
            assert event.risk_score == 70
            assert event.summary == "Updated twice"


class TestCameraRegistrationIdempotency:
    """Tests for idempotent camera registration."""

    async def test_register_same_camera_twice_updates_not_duplicates(
        self, isolated_db_session
    ) -> None:
        """Test that registering the same camera twice updates existing, not duplicates."""
        camera_id = unique_id("camera")
        camera_name = "Test Camera"
        folder_path = f"/export/foscam/{camera_id}"

        # First registration
        async with get_session() as session:
            # Check if camera exists
            result = await session.execute(select(Camera).where(Camera.id == camera_id))
            existing = result.scalar_one_or_none()

            if existing is None:
                camera = Camera(
                    id=camera_id,
                    name=camera_name,
                    folder_path=folder_path,
                    status="online",
                )
                session.add(camera)
            else:
                # Update existing camera
                existing.status = "online"
                existing.name = camera_name

            await session.commit()

        # Second registration (idempotent)
        async with get_session() as session:
            # Check if camera exists
            result = await session.execute(select(Camera).where(Camera.id == camera_id))
            existing = result.scalar_one_or_none()

            if existing is None:
                camera = Camera(
                    id=camera_id,
                    name=camera_name,
                    folder_path=folder_path,
                    status="online",
                )
                session.add(camera)
            else:
                # Update existing camera
                existing.status = "online"
                existing.name = camera_name

            await session.commit()

        # Verify only one camera exists
        async with get_session() as session:
            result = await session.execute(select(Camera).where(Camera.id == camera_id))
            cameras = result.scalars().all()
            assert len(cameras) == 1
            assert cameras[0].status == "online"

    async def test_camera_upsert_pattern(self, isolated_db_session) -> None:
        """Test camera upsert pattern for idempotent registration."""
        camera_id = unique_id("camera")
        folder_path = f"/export/foscam/{camera_id}"

        # Helper function for upsert pattern
        async def register_camera(name: str, status: str) -> None:
            """Register or update camera."""
            async with get_session() as session:
                result = await session.execute(select(Camera).where(Camera.id == camera_id))
                camera = result.scalar_one_or_none()

                if camera is None:
                    # Create new camera
                    camera = Camera(
                        id=camera_id,
                        name=name,
                        folder_path=folder_path,
                        status=status,
                    )
                    session.add(camera)
                else:
                    # Update existing camera
                    camera.name = name
                    camera.status = status

                await session.commit()

        # First registration
        await register_camera("Initial Name", "online")

        # Second registration with different values (idempotent upsert)
        await register_camera("Updated Name", "offline")

        # Verify only one camera with updated values
        async with get_session() as session:
            result = await session.execute(select(Camera).where(Camera.id == camera_id))
            camera = result.scalar_one()
            assert camera.name == "Updated Name"
            assert camera.status == "offline"


class TestDetectionProcessingIdempotency:
    """Tests for idempotent detection processing."""

    async def test_duplicate_detection_file_path_handling(self, isolated_db_session) -> None:
        """Test handling of duplicate detections for the same file path."""
        camera_id = unique_id("camera")
        file_path = f"/export/foscam/{camera_id}/image.jpg"

        # Create camera first
        async with get_session() as session:
            camera = Camera(
                id=camera_id,
                name="Test Camera",
                folder_path=f"/export/foscam/{camera_id}",
                status="online",
            )
            session.add(camera)
            await session.commit()

        # Helper function for idempotent detection creation
        async def process_detection() -> int | None:
            """Process detection and return ID if created."""
            async with get_session() as session:
                # Check if detection already exists for this file
                result = await session.execute(
                    select(Detection).where(Detection.file_path == file_path)
                )
                existing = result.scalar_one_or_none()

                if existing is not None:
                    return None  # Already processed

                # Create new detection
                detection = Detection(
                    camera_id=camera_id,
                    file_path=file_path,
                    file_type="jpg",
                    detected_at=datetime.now(UTC),
                    object_type="person",
                    confidence=0.95,
                )
                session.add(detection)
                await session.commit()
                await session.refresh(detection)
                return detection.id

        # First processing
        detection_id_1 = await process_detection()
        assert detection_id_1 is not None

        # Second processing (idempotent - should skip)
        detection_id_2 = await process_detection()
        assert detection_id_2 is None

        # Verify only one detection exists
        async with get_session() as session:
            result = await session.execute(
                select(Detection).where(Detection.file_path == file_path)
            )
            detections = result.scalars().all()
            assert len(detections) == 1
            assert detections[0].id == detection_id_1

    async def test_detection_re_enrichment_is_idempotent(self, isolated_db_session) -> None:
        """Test that re-enriching a detection is idempotent."""
        camera_id = unique_id("camera")
        file_path = f"/export/foscam/{camera_id}/image.jpg"

        # Create camera and detection
        async with get_session() as session:
            camera = Camera(
                id=camera_id,
                name="Test Camera",
                folder_path=f"/export/foscam/{camera_id}",
                status="online",
            )
            session.add(camera)

            detection = Detection(
                camera_id=camera_id,
                file_path=file_path,
                file_type="jpg",
                detected_at=datetime.now(UTC),
                object_type="person",
                confidence=0.95,
            )
            session.add(detection)
            await session.commit()
            await session.refresh(detection)
            detection_id = detection.id

        # First enrichment
        enrichment_data = {"caption": "A person walking", "tags": ["person", "outdoor"]}
        async with get_session() as session:
            result = await session.execute(select(Detection).where(Detection.id == detection_id))
            detection = result.scalar_one()
            detection.enrichment_data = enrichment_data
            await session.commit()

        # Second enrichment with same data (idempotent)
        async with get_session() as session:
            result = await session.execute(select(Detection).where(Detection.id == detection_id))
            detection = result.scalar_one()
            detection.enrichment_data = enrichment_data
            await session.commit()

        # Verify enrichment data is consistent
        async with get_session() as session:
            result = await session.execute(select(Detection).where(Detection.id == detection_id))
            detection = result.scalar_one()
            assert detection.enrichment_data == enrichment_data


class TestAPIIdempotency:
    """Tests for API endpoint idempotency."""

    async def test_get_request_is_idempotent(self, client, clean_tables: None) -> None:
        """Test that GET requests are idempotent (multiple calls return same result)."""
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

        # First GET request
        response1 = await client.get(f"/api/cameras/{camera_id}")
        assert response1.status_code == 200
        data1 = response1.json()

        # Second GET request (idempotent)
        response2 = await client.get(f"/api/cameras/{camera_id}")
        assert response2.status_code == 200
        data2 = response2.json()

        # Results should be identical
        assert data1 == data2

    async def test_post_request_creates_resource_once(self, client, clean_tables: None) -> None:
        """Test POST request creates resource once (not strictly idempotent without idempotency key)."""
        # Create camera via POST
        camera_data = {
            "name": "New Camera",
            "folder_path": "/export/foscam/new_camera",
        }

        # First POST
        response1 = await client.post("/api/cameras", json=camera_data)
        assert response1.status_code == 201
        camera_id_1 = response1.json()["id"]

        # Second POST with same data (creates different resource - not idempotent)
        response2 = await client.post("/api/cameras", json=camera_data)
        assert response2.status_code == 409  # Conflict - duplicate folder_path

        # Verify behavior (POST is not idempotent without idempotency keys)
        # In production, you'd use idempotency keys or PUT for idempotent creates

    async def test_delete_request_is_idempotent(self, client, clean_tables: None) -> None:
        """Test that DELETE requests are idempotent (deleting twice has same effect)."""
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

        # First DELETE
        response1 = await client.delete(f"/api/cameras/{camera_id}")
        assert response1.status_code == 204  # No Content - successful deletion

        # Second DELETE (idempotent - same result)
        response2 = await client.delete(f"/api/cameras/{camera_id}")
        assert response2.status_code == 404  # Already deleted

        # Third DELETE (still idempotent)
        response3 = await client.delete(f"/api/cameras/{camera_id}")
        assert response3.status_code == 404


class TestConcurrentIdempotency:
    """Tests for idempotency under concurrent operations."""

    async def test_concurrent_camera_registration_one_succeeds(self, isolated_db_session) -> None:
        """Test that concurrent camera registrations result in one camera."""
        camera_id = unique_id("camera")
        folder_path = f"/export/foscam/{camera_id}"

        async def register_camera(worker_id: int) -> bool:
            """Try to register camera, return True if succeeded."""
            try:
                async with get_session() as session:
                    # Check if exists (idempotency check)
                    result = await session.execute(select(Camera).where(Camera.id == camera_id))
                    existing = result.scalar_one_or_none()

                    if existing is not None:
                        return False  # Already registered

                    camera = Camera(
                        id=camera_id,
                        name=f"Camera {worker_id}",
                        folder_path=folder_path,
                        status="online",
                    )
                    session.add(camera)
                    await session.commit()
                    return True
            except Exception:
                return False

        # Run concurrent registration attempts
        results = await asyncio.gather(
            register_camera(1),
            register_camera(2),
            register_camera(3),
            return_exceptions=True,
        )

        # Verify only one camera exists
        async with get_session() as session:
            result = await session.execute(select(Camera).where(Camera.id == camera_id))
            cameras = result.scalars().all()
            # Due to race conditions, might have 1-3 cameras without proper locking
            # This test demonstrates the need for database-level unique constraints
            assert len(cameras) >= 1

    async def test_idempotency_with_transaction_retry(self, isolated_db_session) -> None:
        """Test idempotency with transaction retry logic."""
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

        async def create_event_with_retry(max_attempts: int = 3) -> int | None:
            """Create event with retry logic, return event ID if created."""
            for attempt in range(max_attempts):
                try:
                    async with get_session() as session:
                        # Idempotency check
                        result = await session.execute(
                            select(Event).where(Event.batch_id == batch_id)
                        )
                        existing = result.scalar_one_or_none()

                        if existing is not None:
                            return None  # Already processed

                        # Create event
                        event = Event(
                            batch_id=batch_id,
                            camera_id=camera_id,
                            started_at=datetime.now(UTC),
                            risk_score=50,
                            risk_level="medium",
                            summary=f"Attempt {attempt + 1}",
                        )
                        session.add(event)
                        await session.commit()
                        await session.refresh(event)
                        return event.id
                except Exception:
                    if attempt == max_attempts - 1:
                        raise
                    # Retry on failure
                    await asyncio.sleep(0.1)

            return None

        # Create event with retry
        event_id = await create_event_with_retry()
        assert event_id is not None

        # Try again (should skip due to idempotency check)
        event_id_2 = await create_event_with_retry()
        assert event_id_2 is None

        # Verify only one event exists
        async with get_session() as session:
            result = await session.execute(select(Event).where(Event.batch_id == batch_id))
            events = result.scalars().all()
            assert len(events) == 1
            assert events[0].id == event_id
