"""Integration tests for action recognition service and ActionEvent model.

Tests use PostgreSQL via the session fixture since models use
PostgreSQL-specific features like JSONB.

Linear issue: NEM-3714
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from backend.models import Camera, Track
from backend.models.action_event import ActionEvent
from backend.services.action_recognition_service import ActionRecognitionService
from backend.tests.conftest import unique_id

# Mark as integration since these tests require real PostgreSQL database
pytestmark = pytest.mark.integration


class TestActionEventModel:
    """Tests for the ActionEvent database model."""

    @pytest.mark.asyncio
    async def test_create_action_event(self, session):
        """Test creating an action event with required fields."""
        camera_id = unique_id("cam_action_ev")
        camera = Camera(
            id=camera_id,
            name=f"Camera {camera_id[-8:]}",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        action_event = ActionEvent(
            camera_id=camera_id,
            action="walking normally",
            confidence=0.89,
            is_suspicious=False,
            frame_count=8,
        )
        session.add(action_event)
        await session.flush()

        assert action_event.id is not None
        assert action_event.camera_id == camera_id
        assert action_event.action == "walking normally"
        assert action_event.confidence == 0.89
        assert action_event.is_suspicious is False
        assert action_event.frame_count == 8
        assert isinstance(action_event.timestamp, datetime)
        assert isinstance(action_event.created_at, datetime)

    @pytest.mark.asyncio
    async def test_action_event_with_all_scores(self, session):
        """Test creating an action event with all candidate scores."""
        camera_id = unique_id("cam_action_scores")
        camera = Camera(
            id=camera_id,
            name=f"Camera {camera_id[-8:]}",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        all_scores = {
            "walking normally": 0.65,
            "loitering": 0.20,
            "climbing": 0.10,
            "running": 0.05,
        }

        action_event = ActionEvent(
            camera_id=camera_id,
            action="walking normally",
            confidence=0.65,
            is_suspicious=False,
            frame_count=8,
            all_scores=all_scores,
        )
        session.add(action_event)
        await session.flush()

        assert action_event.all_scores == all_scores
        assert action_event.all_scores["loitering"] == 0.20

    @pytest.mark.asyncio
    async def test_action_event_suspicious(self, session):
        """Test creating a suspicious action event."""
        camera_id = unique_id("cam_action_susp")
        camera = Camera(
            id=camera_id,
            name=f"Camera {camera_id[-8:]}",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        action_event = ActionEvent(
            camera_id=camera_id,
            action="climbing",
            confidence=0.92,
            is_suspicious=True,
            frame_count=8,
        )
        session.add(action_event)
        await session.flush()

        assert action_event.is_suspicious is True

    @pytest.mark.asyncio
    async def test_action_event_with_track(self, session):
        """Test creating an action event linked to a track."""
        camera_id = unique_id("cam_action_track")
        camera = Camera(
            id=camera_id,
            name=f"Camera {camera_id[-8:]}",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        track = Track(
            camera_id=camera_id,
            track_id=42,
            object_type="person",
        )
        session.add(track)
        await session.flush()

        action_event = ActionEvent(
            camera_id=camera_id,
            track_id=track.id,
            action="loitering",
            confidence=0.75,
            is_suspicious=True,
            frame_count=8,
        )
        session.add(action_event)
        await session.flush()

        assert action_event.track_id == track.id

        # Test relationship loading
        await session.refresh(action_event, ["track"])
        assert action_event.track is not None
        assert action_event.track.track_id == 42

    @pytest.mark.asyncio
    async def test_action_event_camera_relationship(self, session):
        """Test the relationship between ActionEvent and Camera."""
        camera_id = unique_id("cam_action_rel")
        camera = Camera(
            id=camera_id,
            name=f"Camera {camera_id[-8:]}",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        action_event = ActionEvent(
            camera_id=camera_id,
            action="running",
            confidence=0.88,
            is_suspicious=False,
        )
        session.add(action_event)
        await session.flush()

        # Test forward relationship
        await session.refresh(action_event, ["camera"])
        assert action_event.camera is not None
        assert action_event.camera.id == camera_id

        # Test reverse relationship
        await session.refresh(camera, ["action_events"])
        assert len(camera.action_events) == 1
        assert camera.action_events[0].id == action_event.id

    @pytest.mark.asyncio
    async def test_action_event_cascade_delete_on_camera(self, session):
        """Test that action events are deleted when camera is deleted."""
        camera_id = unique_id("cam_action_cascade")
        camera = Camera(
            id=camera_id,
            name=f"Camera {camera_id[-8:]}",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        action_event = ActionEvent(
            camera_id=camera_id,
            action="walking normally",
            confidence=0.9,
        )
        session.add(action_event)
        await session.flush()

        event_id = action_event.id

        # Delete the camera
        await session.delete(camera)
        await session.flush()

        # Verify action event is deleted
        deleted_event = await session.get(ActionEvent, event_id)
        assert deleted_event is None

    @pytest.mark.asyncio
    async def test_action_event_track_set_null_on_delete(self, session):
        """Test that track_id is set to NULL when track is deleted."""
        camera_id = unique_id("cam_action_setnull")
        camera = Camera(
            id=camera_id,
            name=f"Camera {camera_id[-8:]}",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        track = Track(
            camera_id=camera_id,
            track_id=100,
            object_type="person",
        )
        session.add(track)
        await session.flush()

        action_event = ActionEvent(
            camera_id=camera_id,
            track_id=track.id,
            action="running",
            confidence=0.85,
        )
        session.add(action_event)
        await session.flush()

        event_id = action_event.id
        track_id = track.id

        # Delete the track
        await session.delete(track)
        await session.flush()

        # Refresh and verify track_id is NULL
        await session.refresh(action_event)
        assert action_event.track_id is None

    @pytest.mark.asyncio
    async def test_action_event_confidence_constraint(self, session):
        """Test that confidence must be between 0 and 1."""
        camera_id = unique_id("cam_action_conf")
        camera = Camera(
            id=camera_id,
            name=f"Camera {camera_id[-8:]}",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        # Try to create with invalid confidence > 1
        action_event = ActionEvent(
            camera_id=camera_id,
            action="walking",
            confidence=1.5,  # Invalid
        )
        session.add(action_event)

        with pytest.raises(IntegrityError):
            await session.flush()

    @pytest.mark.asyncio
    async def test_action_event_to_dict(self, session):
        """Test the to_dict method for API serialization."""
        camera_id = unique_id("cam_action_dict")
        camera = Camera(
            id=camera_id,
            name=f"Camera {camera_id[-8:]}",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        action_event = ActionEvent(
            camera_id=camera_id,
            action="loitering",
            confidence=0.77,
            is_suspicious=True,
            frame_count=8,
            all_scores={"loitering": 0.77, "walking": 0.23},
        )
        session.add(action_event)
        await session.flush()

        result = action_event.to_dict()

        assert result["id"] == action_event.id
        assert result["camera_id"] == camera_id
        assert result["action"] == "loitering"
        assert result["confidence"] == 0.77
        assert result["is_suspicious"] is True
        assert result["frame_count"] == 8
        assert result["all_scores"] == {"loitering": 0.77, "walking": 0.23}
        assert "timestamp" in result
        assert "created_at" in result

    @pytest.mark.asyncio
    async def test_action_event_repr(self, session):
        """Test action event string representation."""
        camera_id = unique_id("cam_action_repr")
        camera = Camera(
            id=camera_id,
            name=f"Camera {camera_id[-8:]}",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        action_event = ActionEvent(
            camera_id=camera_id,
            action="climbing",
            confidence=0.95,
            is_suspicious=True,
        )
        session.add(action_event)
        await session.flush()

        repr_str = repr(action_event)
        assert "ActionEvent" in repr_str
        assert "climbing" in repr_str
        assert "is_suspicious=True" in repr_str


class TestActionRecognitionService:
    """Tests for the ActionRecognitionService."""

    @pytest.mark.asyncio
    async def test_create_action_event_via_service(self, session):
        """Test creating an action event through the service."""
        camera_id = unique_id("cam_svc_create")
        camera = Camera(
            id=camera_id,
            name=f"Camera {camera_id[-8:]}",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        service = ActionRecognitionService(session=session)

        event = await service.create_action_event(
            camera_id=camera_id,
            action="walking normally",
            confidence=0.88,
            is_suspicious=False,
            frame_count=8,
            all_scores={"walking normally": 0.88, "running": 0.12},
        )

        assert event.id is not None
        assert event.camera_id == camera_id
        assert event.action == "walking normally"
        assert event.confidence == 0.88

    @pytest.mark.asyncio
    async def test_get_action_event(self, session):
        """Test retrieving an action event by ID."""
        camera_id = unique_id("cam_svc_get")
        camera = Camera(
            id=camera_id,
            name=f"Camera {camera_id[-8:]}",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        service = ActionRecognitionService(session=session)

        event = await service.create_action_event(
            camera_id=camera_id,
            action="loitering",
            confidence=0.72,
        )

        # Retrieve by ID
        retrieved = await service.get_action_event(event.id)

        assert retrieved is not None
        assert retrieved.id == event.id
        assert retrieved.action == "loitering"

    @pytest.mark.asyncio
    async def test_get_action_event_not_found(self, session):
        """Test retrieving a non-existent action event."""
        service = ActionRecognitionService(session=session)

        result = await service.get_action_event(99999)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_action_events_with_filters(self, session):
        """Test retrieving action events with various filters."""
        camera_id = unique_id("cam_svc_filter")
        camera = Camera(
            id=camera_id,
            name=f"Camera {camera_id[-8:]}",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        service = ActionRecognitionService(session=session)

        # Create multiple events
        await service.create_action_event(
            camera_id=camera_id,
            action="walking normally",
            confidence=0.85,
            is_suspicious=False,
        )
        await service.create_action_event(
            camera_id=camera_id,
            action="climbing",
            confidence=0.92,
            is_suspicious=True,
        )
        await service.create_action_event(
            camera_id=camera_id,
            action="loitering",
            confidence=0.65,
            is_suspicious=True,
        )

        # Filter by camera_id
        _events, total = await service.get_action_events(camera_id=camera_id)
        assert total == 3

        # Filter by is_suspicious
        _suspicious_events, suspicious_total = await service.get_action_events(
            camera_id=camera_id,
            is_suspicious=True,
        )
        assert suspicious_total == 2

        # Filter by action
        climbing_events, climbing_total = await service.get_action_events(
            camera_id=camera_id,
            action="climbing",
        )
        assert climbing_total == 1
        assert climbing_events[0].action == "climbing"

        # Filter by min_confidence
        _high_conf_events, high_conf_total = await service.get_action_events(
            camera_id=camera_id,
            min_confidence=0.9,
        )
        assert high_conf_total == 1

    @pytest.mark.asyncio
    async def test_get_action_events_pagination(self, session):
        """Test pagination of action events."""
        camera_id = unique_id("cam_svc_page")
        camera = Camera(
            id=camera_id,
            name=f"Camera {camera_id[-8:]}",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        service = ActionRecognitionService(session=session)

        # Create 5 events
        for i in range(5):
            await service.create_action_event(
                camera_id=camera_id,
                action=f"action_{i}",
                confidence=0.5 + i * 0.1,
            )

        # Get first page
        page1, total = await service.get_action_events(
            camera_id=camera_id,
            limit=2,
            offset=0,
        )
        assert len(page1) == 2
        assert total == 5

        # Get second page
        page2, _ = await service.get_action_events(
            camera_id=camera_id,
            limit=2,
            offset=2,
        )
        assert len(page2) == 2

        # Get last page
        page3, _ = await service.get_action_events(
            camera_id=camera_id,
            limit=2,
            offset=4,
        )
        assert len(page3) == 1

    @pytest.mark.asyncio
    async def test_get_suspicious_actions(self, session):
        """Test retrieving suspicious actions only."""
        camera_id = unique_id("cam_svc_susp")
        camera = Camera(
            id=camera_id,
            name=f"Camera {camera_id[-8:]}",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        service = ActionRecognitionService(session=session)

        # Create mixed events
        await service.create_action_event(
            camera_id=camera_id,
            action="walking normally",
            confidence=0.9,
            is_suspicious=False,
        )
        await service.create_action_event(
            camera_id=camera_id,
            action="climbing",
            confidence=0.85,
            is_suspicious=True,
        )
        await service.create_action_event(
            camera_id=camera_id,
            action="loitering",
            confidence=0.75,
            is_suspicious=True,
        )

        events, suspicious_count, total_count = await service.get_suspicious_actions(
            camera_id=camera_id,
        )

        assert len(events) == 2
        assert suspicious_count == 2
        assert total_count == 3
        for event in events:
            assert event.is_suspicious is True

    @pytest.mark.asyncio
    async def test_delete_action_event(self, session):
        """Test deleting an action event."""
        camera_id = unique_id("cam_svc_del")
        camera = Camera(
            id=camera_id,
            name=f"Camera {camera_id[-8:]}",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        service = ActionRecognitionService(session=session)

        event = await service.create_action_event(
            camera_id=camera_id,
            action="running",
            confidence=0.8,
        )
        event_id = event.id

        # Delete
        deleted = await service.delete_action_event(event_id)
        assert deleted is True

        # Verify deleted
        result = await service.get_action_event(event_id)
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_action_event_not_found(self, session):
        """Test deleting a non-existent action event."""
        service = ActionRecognitionService(session=session)

        deleted = await service.delete_action_event(99999)
        assert deleted is False

    @pytest.mark.asyncio
    async def test_get_action_events_for_camera(self, session):
        """Test the convenience method for camera-specific queries."""
        camera_id = unique_id("cam_svc_cam")
        camera = Camera(
            id=camera_id,
            name=f"Camera {camera_id[-8:]}",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        service = ActionRecognitionService(session=session)

        # Create events
        await service.create_action_event(
            camera_id=camera_id,
            action="walking",
            confidence=0.9,
        )
        await service.create_action_event(
            camera_id=camera_id,
            action="running",
            confidence=0.85,
        )

        events, total = await service.get_action_events_for_camera(
            camera_id=camera_id,
        )

        assert total == 2
        assert len(events) == 2

    @pytest.mark.asyncio
    async def test_get_action_events_time_filter(self, session):
        """Test filtering action events by time range."""
        camera_id = unique_id("cam_svc_time")
        camera = Camera(
            id=camera_id,
            name=f"Camera {camera_id[-8:]}",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        service = ActionRecognitionService(session=session)

        now = datetime.now(UTC)
        one_hour_ago = now - timedelta(hours=1)
        two_hours_ago = now - timedelta(hours=2)

        # Create events at different times
        await service.create_action_event(
            camera_id=camera_id,
            action="old_action",
            confidence=0.8,
            timestamp=two_hours_ago,
        )
        await service.create_action_event(
            camera_id=camera_id,
            action="recent_action",
            confidence=0.9,
            timestamp=now,
        )

        # Filter by time range
        events, total = await service.get_action_events(
            camera_id=camera_id,
            start_time=one_hour_ago,
        )

        assert total == 1
        assert events[0].action == "recent_action"

    @pytest.mark.asyncio
    async def test_get_action_statistics(self, session):
        """Test getting action statistics."""
        camera_id = unique_id("cam_svc_stats")
        camera = Camera(
            id=camera_id,
            name=f"Camera {camera_id[-8:]}",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        service = ActionRecognitionService(session=session)

        # Create events
        await service.create_action_event(
            camera_id=camera_id,
            action="walking normally",
            confidence=0.9,
            is_suspicious=False,
        )
        await service.create_action_event(
            camera_id=camera_id,
            action="walking normally",
            confidence=0.85,
            is_suspicious=False,
        )
        await service.create_action_event(
            camera_id=camera_id,
            action="climbing",
            confidence=0.95,
            is_suspicious=True,
        )

        stats = await service.get_action_statistics(camera_id=camera_id)

        assert stats["total_events"] == 3
        assert stats["suspicious_events"] == 1
        assert stats["action_counts"]["walking normally"] == 2
        assert stats["action_counts"]["climbing"] == 1
        assert stats["avg_confidence"] == pytest.approx(0.9, rel=0.01)

    @pytest.mark.asyncio
    async def test_create_action_event_auto_suspicious_detection(self, session):
        """Test that is_suspicious is auto-determined when not provided."""
        camera_id = unique_id("cam_svc_auto")
        camera = Camera(
            id=camera_id,
            name=f"Camera {camera_id[-8:]}",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        service = ActionRecognitionService(session=session)

        # Create event with suspicious action - is_suspicious should be auto-set
        event = await service.create_action_event(
            camera_id=camera_id,
            action="a person loitering",
            confidence=0.85,
            # is_suspicious not provided, should be auto-determined
        )

        # "loitering" is a suspicious keyword
        assert event.is_suspicious is True

        # Create event with normal action
        event2 = await service.create_action_event(
            camera_id=camera_id,
            action="a person walking normally",
            confidence=0.9,
        )

        assert event2.is_suspicious is False
