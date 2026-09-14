"""Unit tests for soft-delete model fields/properties (Camera, Event).

M3 Task 3 split: the DB-backed classes (query filtering, delete/restore
behavior, edge cases — 15 tests that were permanently skipped here behind
integration markers) moved to
`backend/tests/integration/models/test_soft_delete.py`.
"""

from datetime import UTC, datetime

import pytest

from backend.tests.conftest import unique_id
from backend.tests.factories import CameraFactory, EventFactory

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