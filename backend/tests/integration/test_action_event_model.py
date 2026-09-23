"""Integration tests for the ActionEvent database model.

The X-CLIP ActionRecognitionService these tests once shared was archived
(NEM-5563 full retirement, 2026-09-23); its CRUD moved inline into
backend/api/routes/action_events.py, whose route behavior is covered by
test_action_events.py. What remains here is the model itself.

Tests use PostgreSQL via the session fixture since models use
PostgreSQL-specific features like JSONB.

Linear issue: NEM-3714
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError

from backend.models import Camera, Track
from backend.models.action_event import ActionEvent
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

        # Shipped Track model (models/track.py:53): column is object_class,
        # and first_seen/last_seen are NOT NULL required fields — there is
        # no object_type kwarg (ledger R-T9-ACTIONEVENT).
        now = datetime.now(UTC)
        track = Track(
            camera_id=camera_id,
            track_id=42,
            object_class="person",
            first_seen=now,
            last_seen=now,
            trajectory=[],
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

        # The FK ships ondelete="CASCADE" (models/action_event.py:64) so
        # Postgres removes the child row, but the ORM never saw that DELETE —
        # session.get would answer from the identity map with the stale row.
        # Expire first, then get re-SELECTs (same shipped-FK/identity-map
        # interaction as ledger R-T9-ENRICHCASCADE; wave I-4 'is None').
        session.expire_all()

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

        now = datetime.now(UTC)
        track = Track(
            camera_id=camera_id,
            track_id=100,
            object_class="person",
            first_seen=now,
            last_seen=now,
            trajectory=[],
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
