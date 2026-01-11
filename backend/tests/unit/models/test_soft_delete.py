"""Unit tests for soft delete functionality on Camera and Event models.

Tests cover:
- Adding deleted_at column to models
- is_deleted property
- Soft delete sets deleted_at timestamp
- Restore clears deleted_at
- Hard delete actually removes record
- Queries exclude soft-deleted records by default
- Direct access to soft-deleted records when explicitly queried
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from backend.models.camera import Camera
from backend.models.event import Event
from backend.tests.conftest import unique_id
from backend.tests.factories import CameraFactory, EventFactory

# Mark as unit tests
# Note: These tests are automatically configured to run serially via conftest.py
# to avoid database deadlocks during parallel execution (see conftest.py for details)
pytestmark = pytest.mark.unit


# =============================================================================
# Camera Model Soft Delete Tests
# =============================================================================


class TestCameraSoftDeleteModel:
    """Tests for Camera model soft delete fields and properties."""

    def test_camera_has_deleted_at_field(self):
        """Test that Camera model has deleted_at field."""
        camera = CameraFactory(id=unique_id("cam"), name=unique_id("name"))
        assert hasattr(camera, "deleted_at")

    def test_camera_deleted_at_defaults_to_none(self):
        """Test that deleted_at defaults to None for new cameras."""
        camera = CameraFactory(id=unique_id("cam"), name=unique_id("name"))
        assert camera.deleted_at is None

    def test_camera_has_is_deleted_property(self):
        """Test that Camera model has is_deleted property."""
        camera = CameraFactory(id=unique_id("cam"), name=unique_id("name"))
        assert hasattr(camera, "is_deleted")

    def test_camera_is_deleted_false_when_deleted_at_none(self):
        """Test is_deleted returns False when deleted_at is None."""
        camera = CameraFactory(id=unique_id("cam"), name=unique_id("name"))
        assert camera.is_deleted is False

    def test_camera_is_deleted_true_when_deleted_at_set(self):
        """Test is_deleted returns True when deleted_at is set."""
        camera = CameraFactory(
            id=unique_id("cam"), name=unique_id("name"), deleted_at=datetime.now(UTC)
        )
        assert camera.is_deleted is True

    def test_camera_can_set_deleted_at_timestamp(self):
        """Test that deleted_at can be set to a timestamp."""
        now = datetime.now(UTC)
        camera = CameraFactory(id=unique_id("cam"), name=unique_id("name"), deleted_at=now)
        assert camera.deleted_at == now


class TestCameraSoftDeleteMethods:
    """Tests for Camera soft delete, restore, and hard delete methods."""

    @pytest.mark.asyncio
    async def test_camera_soft_delete_sets_deleted_at(self, session):
        """Test that soft_delete() sets deleted_at timestamp."""
        camera_id = unique_id("cam")
        camera = Camera(
            id=camera_id,
            name=unique_id("name"),
            folder_path=f"/path/{unique_id('folder')}",
        )
        session.add(camera)
        await session.flush()

        # Verify initial state
        assert camera.deleted_at is None
        assert camera.is_deleted is False

        # Perform soft delete
        camera.soft_delete()
        await session.flush()

        # Verify soft delete
        await session.refresh(camera)
        assert camera.deleted_at is not None
        assert camera.is_deleted is True
        assert isinstance(camera.deleted_at, datetime)

    @pytest.mark.asyncio
    async def test_camera_restore_clears_deleted_at(self, session):
        """Test that restore() clears deleted_at timestamp."""
        camera_id = unique_id("cam")
        # Create soft-deleted camera
        camera = Camera(
            id=camera_id,
            name=unique_id("name"),
            folder_path=f"/path/{unique_id('folder')}",
            deleted_at=datetime.now(UTC),
        )
        session.add(camera)
        await session.flush()

        # Verify initial soft-deleted state
        assert camera.is_deleted is True

        # Restore camera
        camera.restore()
        await session.flush()

        # Verify restored state
        await session.refresh(camera)
        assert camera.deleted_at is None
        assert camera.is_deleted is False

    @pytest.mark.asyncio
    async def test_camera_hard_delete_removes_record(self, session):
        """Test that hard_delete() actually removes the record from database."""
        camera_id = unique_id("cam")
        # Create camera
        camera = Camera(
            id=camera_id,
            name=unique_id("name"),
            folder_path=f"/path/{unique_id('folder')}",
        )
        session.add(camera)
        await session.flush()

        # Refresh to ensure we have the latest state
        await session.refresh(camera)

        # Perform hard delete
        await camera.hard_delete(session)
        await session.flush()

        # Verify camera is completely removed
        result = await session.execute(select(Camera).where(Camera.id == camera_id))
        deleted_camera = result.scalar_one_or_none()
        assert deleted_camera is None

    @pytest.mark.asyncio
    async def test_camera_soft_delete_preserves_relationships(self, session):
        """Test that soft delete preserves relationships and doesn't cascade delete."""
        from backend.models.detection import Detection

        camera_id = unique_id("cam")
        # Create camera with detection
        camera = Camera(
            id=camera_id,
            name=unique_id("name"),
            folder_path=f"/path/{unique_id('folder')}",
        )
        detection = Detection(
            camera_id=camera_id,
            file_path="/test/image.jpg",
            file_type="image/jpeg",
            detected_at=datetime.now(UTC),
            object_type="person",
            confidence=0.95,
            bbox_x=100,
            bbox_y=100,
            bbox_width=100,
            bbox_height=100,
        )
        session.add(camera)
        session.add(detection)
        await session.flush()

        # Soft delete camera
        camera.soft_delete()
        await session.flush()

        # Verify detection still exists (relationships preserved)
        from backend.models.detection import Detection as DetectionModel

        det_result = await session.execute(
            select(DetectionModel).where(DetectionModel.camera_id == camera_id)
        )
        assert det_result.scalar_one_or_none() is not None


class TestCameraQueryFiltering:
    """Tests for automatic filtering of soft-deleted cameras in queries."""

    @pytest.mark.asyncio
    async def test_query_excludes_soft_deleted_cameras_by_default(self, session):
        """Test that queries exclude soft-deleted cameras by default."""
        active_id = unique_id("cam_active")
        deleted_id = unique_id("cam_deleted")

        # Create active and soft-deleted cameras
        active_camera = Camera(
            id=active_id,
            name=unique_id("active"),
            folder_path=f"/path/{unique_id('folder')}",
        )
        deleted_camera = Camera(
            id=deleted_id,
            name=unique_id("deleted"),
            folder_path=f"/path/{unique_id('folder2')}",
            deleted_at=datetime.now(UTC),
        )
        session.add(active_camera)
        session.add(deleted_camera)
        await session.flush()

        # Query without explicit filter should exclude soft-deleted
        query = select(Camera).where(Camera.deleted_at.is_(None))
        result = await session.execute(query)
        cameras = result.scalars().all()

        # Only active camera should be returned
        camera_ids = [c.id for c in cameras]
        assert active_id in camera_ids
        assert deleted_id not in camera_ids

    @pytest.mark.asyncio
    async def test_query_can_explicitly_include_soft_deleted(self, session):
        """Test that soft-deleted cameras can be explicitly queried."""
        deleted_id = unique_id("cam_deleted")

        # Create soft-deleted camera
        deleted_camera = Camera(
            id=deleted_id,
            name=unique_id("deleted"),
            folder_path=f"/path/{unique_id('folder')}",
            deleted_at=datetime.now(UTC),
        )
        session.add(deleted_camera)
        await session.flush()

        # Explicitly query for soft-deleted cameras
        query = select(Camera).where(Camera.id == deleted_id)
        result = await session.execute(query)
        camera = result.scalar_one_or_none()

        assert camera is not None
        assert camera.is_deleted is True

    @pytest.mark.asyncio
    async def test_query_all_including_deleted(self, session):
        """Test querying all cameras including soft-deleted ones."""
        active_id = unique_id("cam_active")
        deleted_id = unique_id("cam_deleted")

        # Create both types
        active_camera = Camera(
            id=active_id,
            name=unique_id("active"),
            folder_path=f"/path/{unique_id('folder')}",
        )
        deleted_camera = Camera(
            id=deleted_id,
            name=unique_id("deleted"),
            folder_path=f"/path/{unique_id('folder2')}",
            deleted_at=datetime.now(UTC),
        )
        session.add(active_camera)
        session.add(deleted_camera)
        await session.flush()

        # Query all (without deleted_at filter)
        query = select(Camera)
        result = await session.execute(query)
        cameras = result.scalars().all()

        # Both should be returned
        camera_ids = [c.id for c in cameras]
        assert active_id in camera_ids
        assert deleted_id in camera_ids


# =============================================================================
# Event Model Soft Delete Tests
# =============================================================================


class TestEventSoftDeleteModel:
    """Tests for Event model soft delete fields and properties."""

    def test_event_has_deleted_at_field(self):
        """Test that Event model has deleted_at field."""
        event = EventFactory()
        assert hasattr(event, "deleted_at")

    def test_event_deleted_at_defaults_to_none(self):
        """Test that deleted_at defaults to None for new events."""
        event = EventFactory()
        assert event.deleted_at is None

    def test_event_has_is_deleted_property(self):
        """Test that Event model has is_deleted property."""
        event = EventFactory()
        assert hasattr(event, "is_deleted")

    def test_event_is_deleted_false_when_deleted_at_none(self):
        """Test is_deleted returns False when deleted_at is None."""
        event = EventFactory()
        assert event.is_deleted is False

    def test_event_is_deleted_true_when_deleted_at_set(self):
        """Test is_deleted returns True when deleted_at is set."""
        event = EventFactory(deleted_at=datetime.now(UTC))
        assert event.is_deleted is True


class TestEventSoftDeleteMethods:
    """Tests for Event soft delete, restore, and hard delete methods."""

    @pytest.mark.asyncio
    async def test_event_soft_delete_sets_deleted_at(self, session):
        """Test that soft_delete() sets deleted_at timestamp."""
        camera_id = unique_id("cam")
        batch_id = unique_id("batch")

        # Create camera first
        camera = Camera(
            id=camera_id,
            name=unique_id("name"),
            folder_path=f"/path/{unique_id('folder')}",
        )
        session.add(camera)
        await session.flush()

        # Create event
        event = Event(
            camera_id=camera_id,
            batch_id=batch_id,
            started_at=datetime.now(UTC),
        )
        session.add(event)
        await session.flush()

        # Verify initial state
        assert event.deleted_at is None
        assert event.is_deleted is False

        # Perform soft delete
        event.soft_delete()
        await session.flush()

        # Verify soft delete
        await session.refresh(event)
        assert event.deleted_at is not None
        assert event.is_deleted is True

    @pytest.mark.asyncio
    async def test_event_restore_clears_deleted_at(self, session):
        """Test that restore() clears deleted_at timestamp."""
        camera_id = unique_id("cam")
        batch_id = unique_id("batch")

        # Create camera
        camera = Camera(
            id=camera_id,
            name=unique_id("name"),
            folder_path=f"/path/{unique_id('folder')}",
        )
        session.add(camera)
        await session.flush()

        # Create soft-deleted event
        event = Event(
            camera_id=camera_id,
            batch_id=batch_id,
            started_at=datetime.now(UTC),
            deleted_at=datetime.now(UTC),
        )
        session.add(event)
        await session.flush()

        # Verify initial soft-deleted state
        assert event.is_deleted is True

        # Restore event
        event.restore()
        await session.flush()

        # Verify restored state
        await session.refresh(event)
        assert event.deleted_at is None
        assert event.is_deleted is False

    @pytest.mark.asyncio
    async def test_event_hard_delete_removes_record(self, session):
        """Test that hard_delete() actually removes the record from database."""
        camera_id = unique_id("cam")
        batch_id = unique_id("batch")

        # Create camera
        camera = Camera(
            id=camera_id,
            name=unique_id("name"),
            folder_path=f"/path/{unique_id('folder')}",
        )
        session.add(camera)
        await session.flush()

        # Create event
        event = Event(
            camera_id=camera_id,
            batch_id=batch_id,
            started_at=datetime.now(UTC),
        )
        session.add(event)
        await session.flush()

        event_id = event.id

        # Refresh to ensure we have the latest state
        await session.refresh(event)

        # Perform hard delete
        await event.hard_delete(session)
        await session.flush()

        # Verify event is completely removed
        result = await session.execute(select(Event).where(Event.id == event_id))
        deleted_event = result.scalar_one_or_none()
        assert deleted_event is None


class TestEventQueryFiltering:
    """Tests for automatic filtering of soft-deleted events in queries."""

    @pytest.mark.asyncio
    async def test_query_excludes_soft_deleted_events_by_default(self, session):
        """Test that queries exclude soft-deleted events by default."""
        camera_id = unique_id("cam")
        active_batch = unique_id("batch_active")
        deleted_batch = unique_id("batch_deleted")

        # Create camera
        camera = Camera(
            id=camera_id,
            name=unique_id("name"),
            folder_path=f"/path/{unique_id('folder')}",
        )
        session.add(camera)
        await session.flush()

        # Create active and soft-deleted events
        active_event = Event(
            camera_id=camera_id,
            batch_id=active_batch,
            started_at=datetime.now(UTC),
        )
        deleted_event = Event(
            camera_id=camera_id,
            batch_id=deleted_batch,
            started_at=datetime.now(UTC),
            deleted_at=datetime.now(UTC),
        )
        session.add(active_event)
        session.add(deleted_event)
        await session.flush()

        # Query without explicit filter should exclude soft-deleted
        query = select(Event).where(Event.deleted_at.is_(None))
        result = await session.execute(query)
        events = result.scalars().all()

        # Only active event should be returned
        batch_ids = [e.batch_id for e in events]
        assert active_batch in batch_ids
        assert deleted_batch not in batch_ids

    @pytest.mark.asyncio
    async def test_query_can_explicitly_include_soft_deleted_events(self, session):
        """Test that soft-deleted events can be explicitly queried."""
        camera_id = unique_id("cam")
        deleted_batch = unique_id("batch_deleted")

        # Create camera
        camera = Camera(
            id=camera_id,
            name=unique_id("name"),
            folder_path=f"/path/{unique_id('folder')}",
        )
        session.add(camera)
        await session.flush()

        # Create soft-deleted event
        deleted_event = Event(
            camera_id=camera_id,
            batch_id=deleted_batch,
            started_at=datetime.now(UTC),
            deleted_at=datetime.now(UTC),
        )
        session.add(deleted_event)
        await session.flush()

        # Explicitly query for soft-deleted event
        query = select(Event).where(Event.batch_id == deleted_batch)
        result = await session.execute(query)
        event = result.scalar_one_or_none()

        assert event is not None
        assert event.is_deleted is True


# =============================================================================
# Edge Cases and Integration Tests
# =============================================================================


class TestSoftDeleteEdgeCases:
    """Tests for edge cases and complex scenarios."""

    @pytest.mark.asyncio
    async def test_soft_delete_idempotent(self, session):
        """Test that calling soft_delete() multiple times is safe."""
        camera_id = unique_id("cam")

        camera = Camera(
            id=camera_id,
            name=unique_id("name"),
            folder_path=f"/path/{unique_id('folder')}",
        )
        session.add(camera)
        await session.flush()

        # First soft delete
        camera.soft_delete()
        await session.flush()
        await session.refresh(camera)

        first_deleted_at = camera.deleted_at

        # Second soft delete (should be idempotent)
        camera.soft_delete()
        await session.flush()
        await session.refresh(camera)

        # deleted_at should be updated to new timestamp
        assert camera.deleted_at is not None
        assert camera.deleted_at >= first_deleted_at

    @pytest.mark.asyncio
    async def test_restore_idempotent(self, session):
        """Test that calling restore() on non-deleted record is safe."""
        camera_id = unique_id("cam")

        camera = Camera(
            id=camera_id,
            name=unique_id("name"),
            folder_path=f"/path/{unique_id('folder')}",
        )
        session.add(camera)
        await session.flush()

        # Restore a non-deleted camera (should be no-op)
        camera.restore()
        await session.flush()
        await session.refresh(camera)

        assert camera.deleted_at is None
        assert camera.is_deleted is False

    @pytest.mark.asyncio
    async def test_soft_delete_and_restore_cycle(self, session):
        """Test multiple soft delete and restore cycles."""
        camera_id = unique_id("cam")

        camera = Camera(
            id=camera_id,
            name=unique_id("name"),
            folder_path=f"/path/{unique_id('folder')}",
        )
        session.add(camera)
        await session.flush()

        # Cycle 1: Delete and restore
        camera.soft_delete()
        await session.flush()
        await session.refresh(camera)
        assert camera.is_deleted is True

        camera.restore()
        await session.flush()
        await session.refresh(camera)
        assert camera.is_deleted is False

        # Cycle 2: Delete and restore again
        camera.soft_delete()
        await session.flush()
        await session.refresh(camera)
        assert camera.is_deleted is True

        camera.restore()
        await session.flush()
        await session.refresh(camera)
        assert camera.is_deleted is False
