"""Contract tests for critical API endpoints.

This module implements contract testing to verify that API responses conform to
their documented schemas. Contract tests ensure API compatibility is maintained
across changes.

Critical endpoints tested:
- GET /api/events - List events with pagination
- GET /api/events/{id} - Get single event
- GET /api/cameras - List cameras
- GET /api/cameras/{id} - Get single camera
- GET /api/system/health - System health check
- GET /api/system/gpu - GPU statistics
- GET /api/system/stats - System statistics
- GET /api/detections - List detections with pagination
- GET /api/detections/{id} - Get single detection
- GET /api/ai-audit/stats - AI audit statistics
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


# Set test environment before importing app
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/security_test",  # pragma: allowlist secret
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")


# =============================================================================
# Mock Data Factories
# =============================================================================


def create_mock_event(event_id: int = 1) -> MagicMock:
    """Create a mock Event object for testing."""
    event = MagicMock()
    event.id = event_id
    event.camera_id = "front_door"
    event.started_at = datetime.now(UTC)
    event.ended_at = datetime.now(UTC)
    event.risk_score = 75
    event.risk_level = "high"
    event.summary = "Person detected at front door"
    event.reasoning = "Motion detected with high confidence"
    event.reviewed = False
    event.notes = None
    event.detection_ids = "[1, 2, 3]"
    event.object_types = "person"
    event.clip_path = None
    event.llm_prompt = None
    return event


def create_mock_camera(camera_id: str = "front_door") -> MagicMock:
    """Create a mock Camera object for testing."""
    camera = MagicMock()
    camera.id = camera_id
    camera.name = "Front Door"
    camera.folder_path = f"/cameras/{camera_id}"
    camera.status = "online"
    camera.created_at = datetime.now(UTC)
    camera.last_seen_at = datetime.now(UTC)
    return camera


def create_mock_detection(detection_id: int = 1) -> MagicMock:
    """Create a mock Detection object for testing."""
    detection = MagicMock()
    detection.id = detection_id
    detection.camera_id = "front_door"
    detection.detected_at = datetime.now(UTC)
    detection.object_type = "person"
    detection.confidence = 0.95
    detection.bbox_x = 100
    detection.bbox_y = 200
    detection.bbox_width = 150
    detection.bbox_height = 300
    detection.file_path = "/cameras/front_door/image.jpg"
    detection.thumbnail_path = None
    detection.media_type = "image"
    detection.file_type = "image/jpeg"
    detection.enrichment_data = None
    # Video-specific fields (optional)
    detection.duration = None
    detection.video_codec = None
    detection.video_width = None
    detection.video_height = None
    return detection


def create_mock_gpu_stats() -> MagicMock:
    """Create mock GPU statistics."""
    stats = MagicMock()
    stats.recorded_at = datetime.now(UTC)
    stats.gpu_name = "NVIDIA RTX A5500"
    stats.gpu_utilization = 45.0
    stats.memory_used = 8192
    stats.memory_total = 24576
    stats.temperature = 65.0
    stats.power_usage = 120.0
    stats.inference_fps = 30.0
    return stats


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_session() -> MagicMock:
    """Create a mock database session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Create a mock Redis client."""
    redis = AsyncMock()
    redis.ping = AsyncMock(return_value=True)
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.llen = AsyncMock(return_value=0)
    redis.health_check = AsyncMock(
        return_value={"status": "healthy", "connected": True, "redis_version": "7.0.0"}
    )
    return redis


@pytest.fixture
async def client(mock_session: MagicMock, mock_redis: AsyncMock) -> AsyncGenerator[AsyncClient]:
    """Create async HTTP client with mocked dependencies."""
    from backend.core.database import get_db
    from backend.core.redis import get_redis, get_redis_optional
    from backend.main import app

    # Create mock database dependency
    async def mock_get_db():
        yield mock_session

    # Create mock Redis dependencies
    async def mock_get_redis():
        return mock_redis

    async def mock_get_redis_optional():
        yield mock_redis

    # Override dependencies at the app level
    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_redis] = mock_get_redis
    app.dependency_overrides[get_redis_optional] = mock_get_redis_optional

    # Override lifespan to skip actual service initialization
    original_lifespan = app.router.lifespan_context

    async def mock_lifespan(_app):
        yield

    app.router.lifespan_context = mock_lifespan

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            yield client
    finally:
        app.router.lifespan_context = original_lifespan
        app.dependency_overrides.clear()


# =============================================================================
# Events API Contract Tests
# =============================================================================


class TestEventsAPIContract:
    """Contract tests for the Events API endpoints."""

    @pytest.mark.asyncio
    async def test_list_events_returns_valid_schema(
        self, client: AsyncClient, mock_session: MagicMock
    ):
        """Test GET /api/events returns valid EventListResponse schema."""
        mock_event = create_mock_event()

        # Mock count query
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1

        # Mock events query
        mock_events_result = MagicMock()
        mock_events_result.scalars.return_value.all.return_value = [mock_event]

        mock_session.execute = AsyncMock(side_effect=[mock_count_result, mock_events_result])

        response = await client.get("/api/events")

        assert response.status_code == 200
        data = response.json()
        assert "events" in data
        assert "count" in data
        assert "limit" in data
        assert "offset" in data
        assert isinstance(data["events"], list)
        assert isinstance(data["count"], int)
        assert isinstance(data["limit"], int)
        assert isinstance(data["offset"], int)

    @pytest.mark.asyncio
    async def test_list_events_with_filters(self, client: AsyncClient, mock_session: MagicMock):
        """Test GET /api/events with query parameters."""
        mock_event = create_mock_event()

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1

        mock_events_result = MagicMock()
        mock_events_result.scalars.return_value.all.return_value = [mock_event]

        mock_session.execute = AsyncMock(side_effect=[mock_count_result, mock_events_result])

        response = await client.get(
            "/api/events",
            params={
                "camera_id": "front_door",
                "risk_level": "high",
                "reviewed": "false",
                "limit": 10,
                "offset": 0,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "events" in data
        assert data["limit"] == 10
        assert data["offset"] == 0

    @pytest.mark.asyncio
    async def test_get_event_returns_valid_schema(
        self, client: AsyncClient, mock_session: MagicMock
    ):
        """Test GET /api/events/{id} returns valid EventResponse schema."""
        mock_event = create_mock_event(event_id=1)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_event
        mock_session.execute = AsyncMock(return_value=mock_result)

        response = await client.get("/api/events/1")

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "camera_id" in data
        assert "started_at" in data
        assert "risk_score" in data
        assert "risk_level" in data
        assert "summary" in data
        assert "reviewed" in data
        assert "detection_count" in data
        assert "detection_ids" in data

    @pytest.mark.asyncio
    async def test_get_event_not_found_returns_404(
        self, client: AsyncClient, mock_session: MagicMock
    ):
        """Test GET /api/events/{id} returns 404 for non-existent event."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        response = await client.get("/api/events/99999")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data


# =============================================================================
# Cameras API Contract Tests
# =============================================================================


class TestCamerasAPIContract:
    """Contract tests for the Cameras API endpoints."""

    @pytest.mark.asyncio
    async def test_list_cameras_returns_valid_schema(
        self, client: AsyncClient, mock_session: MagicMock
    ):
        """Test GET /api/cameras returns valid CameraListResponse schema."""
        mock_camera = create_mock_camera()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_camera]
        mock_session.execute = AsyncMock(return_value=mock_result)

        response = await client.get("/api/cameras")

        assert response.status_code == 200
        data = response.json()
        assert "cameras" in data
        assert "count" in data
        assert isinstance(data["cameras"], list)
        assert isinstance(data["count"], int)

    @pytest.mark.asyncio
    async def test_list_cameras_with_status_filter(
        self, client: AsyncClient, mock_session: MagicMock
    ):
        """Test GET /api/cameras with status query parameter."""
        mock_camera = create_mock_camera()
        mock_camera.status = "online"

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_camera]
        mock_session.execute = AsyncMock(return_value=mock_result)

        response = await client.get("/api/cameras", params={"status": "online"})

        assert response.status_code == 200
        data = response.json()
        assert "cameras" in data

    @pytest.mark.asyncio
    async def test_get_camera_returns_valid_schema(
        self, client: AsyncClient, mock_session: MagicMock
    ):
        """Test GET /api/cameras/{id} returns valid CameraResponse schema."""
        mock_camera = create_mock_camera()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_camera
        mock_session.execute = AsyncMock(return_value=mock_result)

        response = await client.get("/api/cameras/front_door")

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "name" in data
        assert "folder_path" in data
        assert "status" in data

    @pytest.mark.asyncio
    async def test_get_camera_not_found_returns_404(
        self, client: AsyncClient, mock_session: MagicMock
    ):
        """Test GET /api/cameras/{id} returns 404 for non-existent camera."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        response = await client.get("/api/cameras/nonexistent")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data


# =============================================================================
# System API Contract Tests
# =============================================================================


class TestSystemAPIContract:
    """Contract tests for the System API endpoints."""

    @pytest.mark.asyncio
    async def test_health_endpoint_returns_valid_schema(self, client: AsyncClient):
        """Test GET /health returns valid health response."""
        response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "alive"

    @pytest.mark.asyncio
    async def test_root_endpoint_returns_valid_schema(self, client: AsyncClient):
        """Test GET / returns valid root response."""
        response = await client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "message" in data


# =============================================================================
# Detections API Contract Tests
# =============================================================================


class TestDetectionsAPIContract:
    """Contract tests for the Detections API endpoints."""

    @pytest.mark.asyncio
    async def test_list_detections_returns_valid_schema(
        self, client: AsyncClient, mock_session: MagicMock
    ):
        """Test GET /api/detections returns valid DetectionListResponse schema."""
        mock_detection = create_mock_detection()

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1

        mock_detections_result = MagicMock()
        mock_detections_result.scalars.return_value.all.return_value = [mock_detection]

        mock_session.execute = AsyncMock(side_effect=[mock_count_result, mock_detections_result])

        response = await client.get("/api/detections")

        assert response.status_code == 200
        data = response.json()
        assert "detections" in data
        assert "count" in data
        assert "limit" in data
        assert "offset" in data
        assert isinstance(data["detections"], list)

    @pytest.mark.asyncio
    async def test_list_detections_with_filters(self, client: AsyncClient, mock_session: MagicMock):
        """Test GET /api/detections with query parameters."""
        mock_detection = create_mock_detection()

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1

        mock_detections_result = MagicMock()
        mock_detections_result.scalars.return_value.all.return_value = [mock_detection]

        mock_session.execute = AsyncMock(side_effect=[mock_count_result, mock_detections_result])

        response = await client.get(
            "/api/detections",
            params={
                "camera_id": "front_door",
                "object_type": "person",
                "min_confidence": "0.8",
                "limit": 20,
                "offset": 0,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "detections" in data
        assert data["limit"] == 20

    @pytest.mark.asyncio
    async def test_get_detection_returns_valid_schema(
        self, client: AsyncClient, mock_session: MagicMock
    ):
        """Test GET /api/detections/{id} returns valid DetectionResponse schema."""
        mock_detection = create_mock_detection()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_detection
        mock_session.execute = AsyncMock(return_value=mock_result)

        response = await client.get("/api/detections/1")

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "camera_id" in data
        assert "detected_at" in data
        assert "object_type" in data
        assert "confidence" in data

    @pytest.mark.asyncio
    async def test_get_detection_not_found_returns_404(
        self, client: AsyncClient, mock_session: MagicMock
    ):
        """Test GET /api/detections/{id} returns 404 for non-existent detection."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        response = await client.get("/api/detections/99999")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data


# =============================================================================
# AI Audit API Contract Tests
# =============================================================================


class TestAIAuditAPIContract:
    """Contract tests for the AI Audit API endpoints."""

    @pytest.mark.asyncio
    async def test_get_all_prompts_returns_valid_schema(self, client: AsyncClient):
        """Test GET /api/ai-audit/prompts returns valid AllPromptsResponse schema."""
        response = await client.get("/api/ai-audit/prompts")

        assert response.status_code == 200
        data = response.json()
        assert "prompts" in data
        assert isinstance(data["prompts"], dict)


# =============================================================================
# Error Response Contract Tests
# =============================================================================


class TestErrorResponseContracts:
    """Contract tests for error response formats."""

    @pytest.mark.asyncio
    async def test_404_error_format_events(self, client: AsyncClient, mock_session: MagicMock):
        """Test 404 errors return consistent format with 'detail' field."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        response = await client.get("/api/events/99999")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert isinstance(data["detail"], str)

    @pytest.mark.asyncio
    async def test_404_error_format_cameras(self, client: AsyncClient, mock_session: MagicMock):
        """Test 404 errors return consistent format for cameras."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        response = await client.get("/api/cameras/nonexistent")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert isinstance(data["detail"], str)

    @pytest.mark.asyncio
    async def test_404_error_format_detections(self, client: AsyncClient, mock_session: MagicMock):
        """Test 404 errors return consistent format for detections."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        response = await client.get("/api/detections/99999")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert isinstance(data["detail"], str)

    @pytest.mark.asyncio
    async def test_422_validation_error_format(self, client: AsyncClient):
        """Test 422 validation errors return consistent format."""
        # Test with invalid pagination parameter
        response = await client.get("/api/events", params={"limit": -1})

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data


# =============================================================================
# Pagination Contract Tests
# =============================================================================


class TestPaginationContracts:
    """Contract tests for pagination behavior."""

    @pytest.mark.asyncio
    async def test_pagination_defaults(self, client: AsyncClient, mock_session: MagicMock):
        """Test default pagination values are applied correctly."""
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0

        mock_events_result = MagicMock()
        mock_events_result.scalars.return_value.all.return_value = []

        mock_session.execute = AsyncMock(side_effect=[mock_count_result, mock_events_result])

        response = await client.get("/api/events")

        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 50  # Default limit
        assert data["offset"] == 0  # Default offset

    @pytest.mark.asyncio
    async def test_pagination_max_limit_enforced(self, client: AsyncClient):
        """Test maximum limit is enforced."""
        # Attempt to request more than max allowed
        response = await client.get("/api/events", params={"limit": 2000})

        # Should fail validation (max is 1000)
        assert response.status_code == 422
