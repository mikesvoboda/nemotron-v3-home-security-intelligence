"""Unit tests for cascade soft delete service.

Tests cover:
- Camera cascade soft delete (camera -> events -> detections)
- Event cascade soft delete (event -> detections)
- Cascade restore operations
- Bulk operations
- Edge cases (shared detections, already deleted records)
"""

from datetime import UTC, datetime

import pytest

from backend.models.camera import Camera
from backend.models.detection import Detection
from backend.models.event import Event
from backend.models.event_detection import EventDetection
from backend.services.cascade_delete import (
    CascadeDeleteResult,
    CascadeSoftDeleteService,
)
from backend.tests.conftest import unique_id

# Mark as unit tests
pytestmark = pytest.mark.unit


class TestCascadeSoftDeleteService:
    """Tests for CascadeSoftDeleteService class."""

    @pytest.mark.asyncio
    async def test_soft_delete_camera_with_cascade(self, session):
        """Test soft deleting a camera cascades to events and detections."""
        camera_id = unique_id("cam")

        # Create camera
        camera = Camera(
            id=camera_id,
            name=unique_id("name"),
            folder_path=f"/path/{unique_id('folder')}",
        )
        session.add(camera)
        await session.flush()

        # Create events for the camera
        event1 = Event(
            camera_id=camera_id,
            batch_id=unique_id("batch1"),
            started_at=datetime.now(UTC),
        )
        event2 = Event(
            camera_id=camera_id,
            batch_id=unique_id("batch2"),
            started_at=datetime.now(UTC),
        )
        session.add(event1)
        session.add(event2)
        await session.flush()

        # Create detections for the camera
        det1 = Detection(
            camera_id=camera_id,
            file_path="/test/image1.jpg",
            file_type="image/jpeg",
            detected_at=datetime.now(UTC),
            object_type="person",
            confidence=0.95,
            bbox_x=100,
            bbox_y=100,
            bbox_width=100,
            bbox_height=100,
        )
        det2 = Detection(
            camera_id=camera_id,
            file_path="/test/image2.jpg",
            file_type="image/jpeg",
            detected_at=datetime.now(UTC),
            object_type="car",
            confidence=0.85,
            bbox_x=200,
            bbox_y=200,
            bbox_width=150,
            bbox_height=100,
        )
        session.add(det1)
        session.add(det2)
        await session.flush()

        # Perform cascade soft delete
        service = CascadeSoftDeleteService(session)
        result = await service.soft_delete_camera(camera_id, cascade=True)

        # Verify result
        assert result.parent_deleted is True
        assert result.events_deleted == 2
        assert result.detections_deleted == 2
        assert result.total_deleted == 5  # 1 camera + 2 events + 2 detections

        # Verify camera is soft deleted
        await session.refresh(camera)
        assert camera.is_deleted is True

        # Verify events are soft deleted
        await session.refresh(event1)
        await session.refresh(event2)
        assert event1.is_deleted is True
        assert event2.is_deleted is True

        # Verify detections are soft deleted
        await session.refresh(det1)
        await session.refresh(det2)
        assert det1.is_deleted is True
        assert det2.is_deleted is True

    @pytest.mark.asyncio
    async def test_soft_delete_camera_without_cascade(self, session):
        """Test soft deleting a camera without cascade leaves related records."""
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

        # Perform soft delete without cascade
        service = CascadeSoftDeleteService(session)
        result = await service.soft_delete_camera(camera_id, cascade=False)

        # Verify result
        assert result.parent_deleted is True
        assert result.events_deleted == 0
        assert result.detections_deleted == 0

        # Verify camera is soft deleted
        await session.refresh(camera)
        assert camera.is_deleted is True

        # Verify detection is NOT soft deleted
        await session.refresh(detection)
        assert detection.is_deleted is False

    @pytest.mark.asyncio
    async def test_soft_delete_camera_not_found(self, session):
        """Test soft delete raises ValueError for nonexistent camera."""
        service = CascadeSoftDeleteService(session)

        with pytest.raises(ValueError, match="not found"):
            await service.soft_delete_camera("nonexistent_camera")

    @pytest.mark.asyncio
    async def test_soft_delete_camera_already_deleted(self, session):
        """Test soft delete on already deleted camera returns no-op."""
        camera_id = unique_id("cam")

        # Create already deleted camera
        camera = Camera(
            id=camera_id,
            name=unique_id("name"),
            folder_path=f"/path/{unique_id('folder')}",
            deleted_at=datetime.now(UTC),
        )
        session.add(camera)
        await session.flush()

        # Perform soft delete
        service = CascadeSoftDeleteService(session)
        result = await service.soft_delete_camera(camera_id)

        # Verify no-op
        assert result.parent_deleted is False
        assert result.total_deleted == 0

    @pytest.mark.asyncio
    async def test_soft_delete_event_with_cascade(self, session):
        """Test soft deleting an event cascades to related detections."""
        camera_id = unique_id("cam")

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
            batch_id=unique_id("batch"),
            started_at=datetime.now(UTC),
        )
        session.add(event)
        await session.flush()

        # Create detection
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
        session.add(detection)
        await session.flush()

        # Create event-detection association
        event_detection = EventDetection(
            event_id=event.id,
            detection_id=detection.id,
        )
        session.add(event_detection)
        await session.flush()

        # Perform cascade soft delete
        service = CascadeSoftDeleteService(session)
        result = await service.soft_delete_event(event.id, cascade=True)

        # Verify result
        assert result.parent_deleted is True
        assert result.detections_deleted == 1

        # Verify event is soft deleted
        await session.refresh(event)
        assert event.is_deleted is True

        # Verify detection is soft deleted
        await session.refresh(detection)
        assert detection.is_deleted is True

    @pytest.mark.asyncio
    async def test_soft_delete_event_shared_detection_not_deleted(self, session):
        """Test that shared detections are not deleted when one event is deleted."""
        camera_id = unique_id("cam")

        # Create camera
        camera = Camera(
            id=camera_id,
            name=unique_id("name"),
            folder_path=f"/path/{unique_id('folder')}",
        )
        session.add(camera)
        await session.flush()

        # Create two events
        event1 = Event(
            camera_id=camera_id,
            batch_id=unique_id("batch1"),
            started_at=datetime.now(UTC),
        )
        event2 = Event(
            camera_id=camera_id,
            batch_id=unique_id("batch2"),
            started_at=datetime.now(UTC),
        )
        session.add(event1)
        session.add(event2)
        await session.flush()

        # Create detection shared by both events
        shared_detection = Detection(
            camera_id=camera_id,
            file_path="/test/shared.jpg",
            file_type="image/jpeg",
            detected_at=datetime.now(UTC),
            object_type="person",
            confidence=0.95,
            bbox_x=100,
            bbox_y=100,
            bbox_width=100,
            bbox_height=100,
        )
        session.add(shared_detection)
        await session.flush()

        # Associate detection with both events
        session.add(EventDetection(event_id=event1.id, detection_id=shared_detection.id))
        session.add(EventDetection(event_id=event2.id, detection_id=shared_detection.id))
        await session.flush()

        # Soft delete event1
        service = CascadeSoftDeleteService(session)
        result = await service.soft_delete_event(event1.id, cascade=True)

        # Verify result - detection should NOT be deleted (shared with event2)
        assert result.parent_deleted is True
        assert result.detections_deleted == 0

        # Verify event1 is soft deleted
        await session.refresh(event1)
        assert event1.is_deleted is True

        # Verify shared detection is NOT soft deleted
        await session.refresh(shared_detection)
        assert shared_detection.is_deleted is False

    @pytest.mark.asyncio
    async def test_restore_camera_with_cascade(self, session):
        """Test restoring a camera cascades to related records."""
        camera_id = unique_id("cam")
        now = datetime.now(UTC)

        # Create soft-deleted camera with soft-deleted related records
        camera = Camera(
            id=camera_id,
            name=unique_id("name"),
            folder_path=f"/path/{unique_id('folder')}",
            deleted_at=now,
        )
        session.add(camera)
        await session.flush()

        event = Event(
            camera_id=camera_id,
            batch_id=unique_id("batch"),
            started_at=datetime.now(UTC),
            deleted_at=now,
        )
        session.add(event)
        await session.flush()

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
            deleted_at=now,
        )
        session.add(detection)
        await session.flush()

        # Restore camera with cascade
        service = CascadeSoftDeleteService(session)
        result = await service.restore_camera(camera_id, cascade=True)

        # Verify result
        assert result.parent_deleted is True
        assert result.events_deleted >= 1  # Field reused for restore count

        # Verify camera is restored
        await session.refresh(camera)
        assert camera.is_deleted is False

        # Verify event is restored
        await session.refresh(event)
        assert event.is_deleted is False

        # Verify detection is restored
        await session.refresh(detection)
        assert detection.is_deleted is False

    @pytest.mark.asyncio
    async def test_bulk_soft_delete_events(self, session):
        """Test bulk soft delete of multiple events."""
        camera_id = unique_id("cam")

        # Create camera
        camera = Camera(
            id=camera_id,
            name=unique_id("name"),
            folder_path=f"/path/{unique_id('folder')}",
        )
        session.add(camera)
        await session.flush()

        # Create multiple events
        events = []
        for i in range(5):
            event = Event(
                camera_id=camera_id,
                batch_id=unique_id(f"batch{i}"),
                started_at=datetime.now(UTC),
            )
            session.add(event)
            events.append(event)
        await session.flush()

        event_ids = [e.id for e in events]

        # Bulk soft delete
        service = CascadeSoftDeleteService(session)
        result = await service.soft_delete_events_bulk(event_ids, cascade=False)

        # Verify result
        assert result.events_deleted == 5

        # Verify all events are soft deleted
        for event in events:
            await session.refresh(event)
            assert event.is_deleted is True


class TestCascadeDeleteResult:
    """Tests for CascadeDeleteResult dataclass."""

    def test_total_deleted_calculation(self):
        """Test total_deleted property calculation."""
        result = CascadeDeleteResult(
            parent_deleted=True,
            events_deleted=5,
            detections_deleted=10,
        )
        assert result.total_deleted == 16  # 1 + 5 + 10

    def test_total_deleted_no_parent(self):
        """Test total_deleted when parent not deleted."""
        result = CascadeDeleteResult(
            parent_deleted=False,
            events_deleted=0,
            detections_deleted=0,
        )
        assert result.total_deleted == 0


class TestDetectionSoftDelete:
    """Tests for Detection model soft delete functionality."""

    def test_detection_has_deleted_at_field(self):
        """Test that Detection model has deleted_at field."""
        detection = Detection(
            camera_id="test",
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
        assert hasattr(detection, "deleted_at")
        assert detection.deleted_at is None

    def test_detection_is_deleted_property(self):
        """Test Detection is_deleted property."""
        detection = Detection(
            camera_id="test",
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
        assert detection.is_deleted is False

        detection.deleted_at = datetime.now(UTC)
        assert detection.is_deleted is True

    def test_detection_soft_delete_method(self):
        """Test Detection soft_delete() method."""
        detection = Detection(
            camera_id="test",
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
        assert detection.deleted_at is None

        detection.soft_delete()
        assert detection.deleted_at is not None
        assert detection.is_deleted is True

    def test_detection_restore_method(self):
        """Test Detection restore() method."""
        detection = Detection(
            camera_id="test",
            file_path="/test/image.jpg",
            file_type="image/jpeg",
            detected_at=datetime.now(UTC),
            object_type="person",
            confidence=0.95,
            bbox_x=100,
            bbox_y=100,
            bbox_width=100,
            bbox_height=100,
            deleted_at=datetime.now(UTC),
        )
        assert detection.is_deleted is True

        detection.restore()
        assert detection.deleted_at is None
        assert detection.is_deleted is False
