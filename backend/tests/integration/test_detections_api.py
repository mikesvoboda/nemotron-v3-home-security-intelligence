"""Integration tests for detections API endpoints.

Uses shared fixtures from conftest.py:
- integration_db: Clean SQLite test database
- mock_redis: Mock Redis client
- db_session: AsyncSession for database
- client: httpx AsyncClient with test app
"""

import uuid
from datetime import datetime

import pytest


# Alias for backward compatibility - tests use async_client but conftest provides client
@pytest.fixture
async def async_client(client):
    """Alias for shared client fixture for backward compatibility."""
    yield client


@pytest.fixture
async def clean_detections(integration_db):
    """Delete detections and related tables data before test runs for proper isolation.

    This ensures tests that expect specific detection counts start with empty tables.
    Uses DELETE instead of TRUNCATE to avoid AccessExclusiveLock deadlocks
    when tests run in parallel with xdist.
    """
    from sqlalchemy import text

    from backend.core.database import get_engine

    async with get_engine().begin() as conn:
        # Delete in order respecting foreign key constraints
        await conn.execute(text("DELETE FROM detections"))
        await conn.execute(text("DELETE FROM events"))
        await conn.execute(text("DELETE FROM cameras"))

    yield

    # Cleanup after test too (best effort)
    try:
        async with get_engine().begin() as conn:
            await conn.execute(text("DELETE FROM detections"))
            await conn.execute(text("DELETE FROM events"))
            await conn.execute(text("DELETE FROM cameras"))
    except Exception:  # noqa: S110 - ignore cleanup errors
        pass


@pytest.fixture
async def sample_camera(integration_db):
    """Create a sample camera in the database."""
    from backend.core.database import get_session
    from backend.models.camera import Camera

    camera_id = str(uuid.uuid4())
    async with get_session() as db:
        camera = Camera(
            id=camera_id,
            name="Front Door",
            folder_path="/export/foscam/front_door",
            status="online",
        )
        db.add(camera)
        await db.commit()
        await db.refresh(camera)
        yield camera


@pytest.fixture
async def sample_detection(integration_db, sample_camera):
    """Create a sample detection in the database."""
    from backend.core.database import get_session
    from backend.models.detection import Detection

    async with get_session() as db:
        detection = Detection(
            camera_id=sample_camera.id,
            file_path="/export/foscam/front_door/test_image.jpg",
            file_type="image/jpeg",
            detected_at=datetime(2025, 12, 23, 12, 0, 0),
            object_type="person",
            confidence=0.95,
            bbox_x=100,
            bbox_y=150,
            bbox_width=200,
            bbox_height=400,
        )
        db.add(detection)
        await db.commit()
        await db.refresh(detection)
        yield detection


class TestListDetections:
    """Tests for GET /api/detections endpoint."""

    async def test_list_detections_empty(self, async_client, clean_detections):
        """Test listing detections when none exist."""
        response = await async_client.get("/api/detections")
        assert response.status_code == 200
        data = response.json()
        assert data["detections"] == []
        assert data["count"] == 0

    async def test_list_detections_with_data(self, async_client, sample_detection):
        """Test listing detections when data exists."""
        response = await async_client.get("/api/detections")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] >= 1
        assert len(data["detections"]) >= 1

    async def test_list_detections_filter_by_camera(self, async_client, sample_detection):
        """Test filtering detections by camera_id."""
        response = await async_client.get(f"/api/detections?camera_id={sample_detection.camera_id}")
        assert response.status_code == 200
        data = response.json()
        for detection in data["detections"]:
            assert detection["camera_id"] == sample_detection.camera_id

    async def test_list_detections_filter_by_object_type(self, async_client, sample_detection):
        """Test filtering detections by object_type."""
        response = await async_client.get("/api/detections?object_type=person")
        assert response.status_code == 200
        data = response.json()
        for detection in data["detections"]:
            assert detection["object_type"] == "person"

    async def test_list_detections_filter_by_min_confidence(self, async_client, sample_detection):
        """Test filtering detections by minimum confidence."""
        response = await async_client.get("/api/detections?min_confidence=0.9")
        assert response.status_code == 200
        data = response.json()
        for detection in data["detections"]:
            assert detection["confidence"] >= 0.9

    async def test_list_detections_pagination(self, async_client, sample_detection):
        """Test pagination parameters."""
        response = await async_client.get("/api/detections?limit=10&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 10
        assert data["offset"] == 0

    async def test_list_detections_invalid_confidence(self, async_client):
        """Test validation of confidence parameter."""
        response = await async_client.get("/api/detections?min_confidence=1.5")
        assert response.status_code == 422  # Validation error


class TestGetDetection:
    """Tests for GET /api/detections/{detection_id} endpoint."""

    async def test_get_detection_success(self, async_client, sample_detection):
        """Test getting a detection by ID."""
        response = await async_client.get(f"/api/detections/{sample_detection.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_detection.id
        assert data["camera_id"] == sample_detection.camera_id
        assert data["object_type"] == sample_detection.object_type

    async def test_get_detection_not_found(self, async_client):
        """Test getting a non-existent detection returns 404."""
        response = await async_client.get("/api/detections/99999")
        assert response.status_code == 404


class TestGetDetectionImage:
    """Tests for GET /api/detections/{detection_id}/image endpoint."""

    async def test_get_detection_image_not_found(self, async_client):
        """Test getting image for non-existent detection returns 404."""
        response = await async_client.get("/api/detections/99999/image")
        assert response.status_code == 404

    async def test_get_detection_image_no_file(self, async_client, sample_detection):
        """Test getting image when source file doesn't exist."""
        response = await async_client.get(f"/api/detections/{sample_detection.id}/image")
        # Should return 404 since the test file doesn't actually exist
        assert response.status_code == 404
