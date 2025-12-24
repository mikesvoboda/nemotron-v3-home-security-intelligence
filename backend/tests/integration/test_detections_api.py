"""Integration tests for detections API endpoints."""

import os
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def test_db_setup():
    """Set up test database environment."""
    from backend.core.config import get_settings
    from backend.core.database import close_db, init_db

    # Close any existing database connections
    await close_db()

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_detections_api.db"
        test_db_url = f"sqlite+aiosqlite:///{db_path}"

        # Store original environment
        original_db_url = os.environ.get("DATABASE_URL")
        original_redis_url = os.environ.get("REDIS_URL")

        # Set test environment
        os.environ["DATABASE_URL"] = test_db_url
        os.environ["REDIS_URL"] = "redis://localhost:6379/15"  # Test DB

        # Clear settings cache to pick up new environment variables
        get_settings.cache_clear()

        # Initialize database explicitly
        await init_db()

        yield test_db_url

        # Cleanup
        await close_db()

        # Restore original environment
        if original_db_url:
            os.environ["DATABASE_URL"] = original_db_url
        else:
            os.environ.pop("DATABASE_URL", None)

        if original_redis_url:
            os.environ["REDIS_URL"] = original_redis_url
        else:
            os.environ.pop("REDIS_URL", None)

        # Clear settings cache again
        get_settings.cache_clear()


@pytest.fixture
async def mock_redis():
    """Mock Redis operations to avoid requiring Redis server."""
    mock_redis_client = AsyncMock()
    mock_redis_client.health_check.return_value = {
        "status": "healthy",
        "connected": True,
        "redis_version": "7.0.0",
    }

    with (
        patch("backend.core.redis._redis_client", mock_redis_client),
        patch("backend.core.redis.init_redis", return_value=None),
        patch("backend.core.redis.close_redis", return_value=None),
    ):
        yield mock_redis_client


@pytest.fixture
async def async_client(test_db_setup, mock_redis):
    """Create async HTTP client for testing."""
    from backend.main import app

    # Patch init_db and close_db in lifespan to avoid double initialization
    with (
        patch("backend.main.init_db", return_value=None),
        patch("backend.main.close_db", return_value=None),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


@pytest.fixture
async def sample_camera(test_db_setup):
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
async def sample_detection(test_db_setup, sample_camera):
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

    async def test_list_detections_empty(self, async_client):
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
