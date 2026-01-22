"""Integration test for NEM-3262: Bug fix for entities showing "0 cameras".

This test reproduces the bug where entities show "0 cameras" even though they
have detections and appearance counts.

The root cause is that legacy entities don't have cameras_seen populated in
entity_metadata, and the fallback to primary_detection doesn't work properly.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from backend.models.detection import Detection
from backend.models.entity import Entity


@pytest.fixture
async def legacy_entity_without_cameras_seen(db_session):
    """Create a legacy entity without cameras_seen in metadata.

    This simulates entities created before NEM-2453 which don't have
    the cameras_seen field in entity_metadata.
    """
    # Create a detection first
    detection = Detection(
        camera_id="front_door",
        object_type="person",
        detected_at=datetime(2025, 12, 23, 10, 0, 0, tzinfo=UTC),
        confidence=0.95,
        bounding_box={"x": 100, "y": 100, "width": 200, "height": 300},
    )
    db_session.add(detection)
    await db_session.flush()
    await db_session.refresh(detection)

    # Create entity with detection_count > 0 but NO cameras_seen
    entity = Entity(
        id=uuid4(),
        entity_type="person",
        first_seen_at=datetime(2025, 12, 23, 10, 0, 0, tzinfo=UTC),
        last_seen_at=datetime(2025, 12, 23, 14, 30, 0, tzinfo=UTC),
        detection_count=5,  # Entity has detections!
        primary_detection_id=detection.id,  # Link to detection
        entity_metadata={"clothing_color": "blue"},  # No camera_id or cameras_seen!
    )
    db_session.add(entity)
    await db_session.commit()
    await db_session.refresh(entity)

    return entity, detection


class TestNEM3262CameraCountFix:
    """Test fix for NEM-3262: Entities showing "0 cameras" bug."""

    async def test_legacy_entity_shows_camera_from_primary_detection(
        self, async_client, legacy_entity_without_cameras_seen
    ):
        """Test that entities without cameras_seen fall back to primary_detection.

        This tests the fix for NEM-3262 where entities with detections were
        showing "0 cameras" because cameras_seen wasn't populated.
        """
        entity, detection = legacy_entity_without_cameras_seen

        # Get entities list from API
        response = await async_client.get("/api/entities")
        assert response.status_code == 200
        data = response.json()

        # Find our entity in the response
        matching_entities = [item for item in data["items"] if item["id"] == str(entity.id)]
        assert len(matching_entities) == 1, f"Entity {entity.id} not found in response"

        entity_data = matching_entities[0]

        # BUG: Before fix, cameras_seen would be []
        # FIX: Should fall back to primary_detection.camera_id
        assert "cameras_seen" in entity_data
        cameras = entity_data["cameras_seen"]
        assert isinstance(cameras, list)
        assert len(cameras) > 0, (
            f"Entity has {entity_data['appearance_count']} appearances "
            "but cameras_seen is empty (NEM-3262 bug)"
        )
        assert detection.camera_id in cameras, (
            f"Expected camera '{detection.camera_id}' from primary_detection "
            f"not in cameras_seen: {cameras}"
        )

    async def test_entity_with_camera_id_only(self, async_client, db_session):
        """Test entities with only camera_id (no cameras_seen list) work correctly."""
        # Create entity with camera_id but not cameras_seen (legacy format)
        entity = Entity(
            id=uuid4(),
            entity_type="person",
            first_seen_at=datetime(2025, 12, 23, 10, 0, 0, tzinfo=UTC),
            last_seen_at=datetime(2025, 12, 23, 14, 30, 0, tzinfo=UTC),
            detection_count=3,
            entity_metadata={"camera_id": "backyard", "clothing": "red jacket"},
        )
        db_session.add(entity)
        await db_session.commit()

        # Get entities list
        response = await async_client.get("/api/entities")
        assert response.status_code == 200
        data = response.json()

        # Find our entity
        matching_entities = [item for item in data["items"] if item["id"] == str(entity.id)]
        assert len(matching_entities) == 1

        entity_data = matching_entities[0]

        # Should convert camera_id to cameras_seen list
        assert entity_data["cameras_seen"] == ["backyard"]

    async def test_entity_with_empty_cameras_seen(self, async_client, db_session):
        """Test entity with empty cameras_seen list shows no cameras gracefully."""
        # Create entity with explicitly empty cameras_seen
        entity = Entity(
            id=uuid4(),
            entity_type="vehicle",
            first_seen_at=datetime(2025, 12, 23, 10, 0, 0, tzinfo=UTC),
            last_seen_at=datetime(2025, 12, 23, 14, 30, 0, tzinfo=UTC),
            detection_count=0,  # No detections yet
            entity_metadata={"cameras_seen": [], "color": "red"},
        )
        db_session.add(entity)
        await db_session.commit()

        # Get entities list
        response = await async_client.get("/api/entities")
        assert response.status_code == 200
        data = response.json()

        # Find our entity
        matching_entities = [item for item in data["items"] if item["id"] == str(entity.id)]
        assert len(matching_entities) == 1

        entity_data = matching_entities[0]

        # Empty list is valid for entities with no detections
        assert entity_data["cameras_seen"] == []
        assert entity_data["appearance_count"] == 0

    async def test_entity_with_multiple_cameras(self, async_client, db_session):
        """Test entity seen on multiple cameras shows all cameras."""
        # Create entity with multiple cameras in cameras_seen
        entity = Entity(
            id=uuid4(),
            entity_type="person",
            first_seen_at=datetime(2025, 12, 23, 10, 0, 0, tzinfo=UTC),
            last_seen_at=datetime(2025, 12, 23, 14, 30, 0, tzinfo=UTC),
            detection_count=8,
            entity_metadata={
                "camera_id": "front_door",
                "cameras_seen": ["front_door", "backyard", "driveway"],
            },
        )
        db_session.add(entity)
        await db_session.commit()

        # Get entities list
        response = await async_client.get("/api/entities")
        assert response.status_code == 200
        data = response.json()

        # Find our entity
        matching_entities = [item for item in data["items"] if item["id"] == str(entity.id)]
        assert len(matching_entities) == 1

        entity_data = matching_entities[0]

        # Should show all three cameras
        assert len(entity_data["cameras_seen"]) == 3
        assert "front_door" in entity_data["cameras_seen"]
        assert "backyard" in entity_data["cameras_seen"]
        assert "driveway" in entity_data["cameras_seen"]
