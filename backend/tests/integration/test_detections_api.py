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
    """Create a sample camera in the database.

    Uses unique names and folder paths to prevent conflicts with unique constraints.
    """
    from backend.core.database import get_session
    from backend.models.camera import Camera

    camera_id = str(uuid.uuid4())
    unique_suffix = uuid.uuid4().hex[:8]
    async with get_session() as db:
        camera = Camera(
            id=camera_id,
            name=f"Front Door {unique_suffix}",
            folder_path=f"/export/foscam/front_door_{unique_suffix}",
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


class TestGetDetectionStats:
    """Tests for GET /api/detections/stats endpoint (NEM-1128).

    This endpoint returns aggregate statistics about detections including:
    - Total detection count
    - Detection counts grouped by object class (person, car, truck, etc.)
    - Average confidence score
    """

    async def test_get_detection_stats_empty(self, async_client, clean_detections):
        """Test getting stats when no detections exist."""
        response = await async_client.get("/api/detections/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total_detections"] == 0
        assert data["detections_by_class"] == {}
        assert data["average_confidence"] is None

    async def test_get_detection_stats_with_single_detection(self, async_client, sample_detection):
        """Test getting stats with a single detection."""
        response = await async_client.get("/api/detections/stats")
        assert response.status_code == 200
        data = response.json()
        # Should have at least the detection created by fixture
        assert data["total_detections"] >= 1
        assert "person" in data["detections_by_class"]
        assert data["detections_by_class"]["person"] >= 1
        assert data["average_confidence"] is not None
        assert 0 <= data["average_confidence"] <= 1

    async def test_get_detection_stats_class_distribution(
        self, async_client, clean_detections, integration_db
    ):
        """Test that stats correctly groups detections by class."""
        import uuid

        from backend.core.database import get_session
        from backend.models.camera import Camera
        from backend.models.detection import Detection

        # First verify database is empty after clean_detections
        response = await async_client.get("/api/detections/stats")
        assert response.status_code == 200
        assert response.json()["total_detections"] == 0

        # Create camera first (required for FK constraint)
        camera_id = str(uuid.uuid4())
        unique_suffix = uuid.uuid4().hex[:8]
        async with get_session() as db:
            camera = Camera(
                id=camera_id,
                name=f"Test Camera {unique_suffix}",
                folder_path=f"/export/foscam/test_{unique_suffix}",
                status="online",
            )
            db.add(camera)
            await db.commit()

        # Create detections with different object types
        async with get_session() as db:
            detections_data = [
                ("person", 0.95),
                ("person", 0.90),
                ("person", 0.85),
                ("car", 0.92),
                ("car", 0.88),
                ("truck", 0.80),
            ]
            for obj_type, conf in detections_data:
                detection = Detection(
                    camera_id=camera_id,
                    file_path=f"/export/foscam/test_{obj_type}_{conf}.jpg",
                    file_type="image/jpeg",
                    detected_at=datetime(2025, 12, 23, 12, 0, 0),
                    object_type=obj_type,
                    confidence=conf,
                    bbox_x=100,
                    bbox_y=150,
                    bbox_width=200,
                    bbox_height=400,
                )
                db.add(detection)
            await db.commit()

        response = await async_client.get("/api/detections/stats")
        assert response.status_code == 200
        data = response.json()

        # Verify total count
        assert data["total_detections"] == 6

        # Verify class distribution
        assert data["detections_by_class"]["person"] == 3
        assert data["detections_by_class"]["car"] == 2
        assert data["detections_by_class"]["truck"] == 1

        # Verify average confidence (sum: 0.95+0.90+0.85+0.92+0.88+0.80 = 5.30, avg = 0.883...)
        assert data["average_confidence"] is not None
        assert 0.88 <= data["average_confidence"] <= 0.89

    async def test_get_detection_stats_response_schema(self, async_client, sample_detection):
        """Test that the response conforms to the expected schema."""
        response = await async_client.get("/api/detections/stats")
        assert response.status_code == 200
        data = response.json()

        # Verify required fields exist
        assert "total_detections" in data
        assert "detections_by_class" in data
        assert "average_confidence" in data

        # Verify field types
        assert isinstance(data["total_detections"], int)
        assert isinstance(data["detections_by_class"], dict)
        assert data["average_confidence"] is None or isinstance(data["average_confidence"], float)
