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

# UUID constants for contract tests (NEM-2563)
NONEXISTENT_CAMERA_UUID = "c3d4e5f6-a7b8-9012-cdef-123456789012"
SAMPLE_CAMERA_UUID = "d4e5f6a7-b8c9-0123-defa-234567890123"


def create_mock_event(event_id: int = 1) -> MagicMock:
    """Create a mock Event object for testing."""
    event = MagicMock()
    event.id = event_id
    event.camera_id = SAMPLE_CAMERA_UUID
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


def create_mock_camera(camera_id: str = SAMPLE_CAMERA_UUID) -> MagicMock:
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
    detection.camera_id = SAMPLE_CAMERA_UUID
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
    # Configure execute to return a result with scalar_one_or_none() = None
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_result.scalar.return_value = None
    session.execute = AsyncMock(return_value=mock_result)
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
        assert "items" in data
        assert "pagination" in data
        assert "limit" in data["pagination"]
        assert "offset" in data["pagination"]
        assert isinstance(data["items"], list)
        assert isinstance(data["pagination"]["total"], int)
        assert isinstance(data["pagination"]["limit"], int)
        # offset can be None for cursor-based pagination
        assert data["pagination"]["offset"] is None or isinstance(data["pagination"]["offset"], int)

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
                "camera_id": SAMPLE_CAMERA_UUID,
                "risk_level": "high",
                "reviewed": "false",
                "limit": 10,
                "offset": 0,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert data["pagination"]["limit"] == 10
        # offset=0 may be returned as None due to cursor-based pagination preference
        assert data["pagination"]["offset"] in (0, None)

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
        """Test GET /api/events/{id} returns 404 for non-existent event (RFC 7807 format)."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        response = await client.get("/api/events/99999")

        assert response.status_code == 404
        data = response.json()
        # RFC 7807 Problem Details format
        assert "type" in data
        assert "title" in data
        assert "status" in data
        assert "detail" in data
        assert data["status"] == 404


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
        assert "items" in data
        assert "pagination" in data
        assert isinstance(data["items"], list)
        assert isinstance(data["pagination"]["total"], int)

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
        assert "items" in data

    @pytest.mark.asyncio
    async def test_get_camera_returns_valid_schema(
        self, client: AsyncClient, mock_session: MagicMock
    ):
        """Test GET /api/cameras/{id} returns valid CameraResponse schema."""
        mock_camera = create_mock_camera()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_camera
        mock_session.execute = AsyncMock(return_value=mock_result)

        response = await client.get(f"/api/cameras/{SAMPLE_CAMERA_UUID}")

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
        """Test GET /api/cameras/{id} returns 404 for non-existent camera (RFC 7807 format)."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        response = await client.get(f"/api/cameras/{NONEXISTENT_CAMERA_UUID}")

        assert response.status_code == 404
        data = response.json()
        # RFC 7807 Problem Details format
        assert "type" in data
        assert "title" in data
        assert "status" in data
        assert "detail" in data
        assert data["status"] == 404


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
        assert "items" in data
        assert "pagination" in data
        assert "limit" in data["pagination"]
        assert "offset" in data["pagination"]
        assert isinstance(data["items"], list)

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
                "camera_id": SAMPLE_CAMERA_UUID,
                "object_type": "person",
                "min_confidence": "0.8",
                "limit": 20,
                "offset": 0,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert data["pagination"]["limit"] == 20

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
        # RFC 7807 Problem Details format
        assert "type" in data
        assert "title" in data
        assert "status" in data
        assert "detail" in data
        assert data["status"] == 404


# =============================================================================
# AI Audit API Contract Tests
# =============================================================================


class TestPromptManagementAPIContract:
    """Contract tests for the Prompt Management API endpoints.

    Note: Prompt endpoints moved from /api/ai-audit/prompts to /api/prompts (NEM-2695).
    """

    @pytest.mark.asyncio
    async def test_get_all_prompts_returns_valid_schema(self, client: AsyncClient):
        """Test GET /api/prompts returns valid AllPromptsResponse schema."""
        response = await client.get("/api/prompts")

        assert response.status_code == 200
        data = response.json()
        assert "prompts" in data
        assert isinstance(data["prompts"], dict)


# =============================================================================
# Error Response Contract Tests
# =============================================================================


class TestErrorResponseContracts:
    """Contract tests for error response formats.

    Note: 404/403/401 errors use RFC 7807 Problem Details format,
    while 422 validation errors use the legacy error format.
    """

    @pytest.mark.asyncio
    async def test_404_error_format_events(self, client: AsyncClient, mock_session: MagicMock):
        """Test 404 errors return RFC 7807 Problem Details format."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        response = await client.get("/api/events/99999")

        assert response.status_code == 404
        # RFC 7807 uses application/problem+json
        content_type = response.headers.get("content-type", "")
        assert "json" in content_type
        data = response.json()
        # RFC 7807 Problem Details format
        assert "type" in data
        assert "title" in data
        assert "status" in data
        assert "detail" in data
        assert isinstance(data["type"], str)
        assert isinstance(data["title"], str)
        assert data["status"] == 404
        assert isinstance(data["detail"], str)

    @pytest.mark.asyncio
    async def test_404_error_format_cameras(self, client: AsyncClient, mock_session: MagicMock):
        """Test 404 errors return RFC 7807 Problem Details format for cameras."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        response = await client.get(f"/api/cameras/{NONEXISTENT_CAMERA_UUID}")

        assert response.status_code == 404
        data = response.json()
        # RFC 7807 Problem Details format
        assert "type" in data
        assert "title" in data
        assert "status" in data
        assert "detail" in data
        assert isinstance(data["type"], str)
        assert isinstance(data["title"], str)
        assert data["status"] == 404
        assert isinstance(data["detail"], str)

    @pytest.mark.asyncio
    async def test_404_error_format_detections(self, client: AsyncClient, mock_session: MagicMock):
        """Test 404 errors return RFC 7807 Problem Details format for detections."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        response = await client.get("/api/detections/99999")

        assert response.status_code == 404
        data = response.json()
        # RFC 7807 Problem Details format
        assert "type" in data
        assert "title" in data
        assert "status" in data
        assert "detail" in data
        assert isinstance(data["type"], str)
        assert isinstance(data["title"], str)
        assert data["status"] == 404
        assert isinstance(data["detail"], str)

    @pytest.mark.asyncio
    async def test_422_validation_error_format(self, client: AsyncClient):
        """Test 422 validation errors return consistent standardized error format."""
        # Test with invalid pagination parameter
        response = await client.get("/api/events", params={"limit": -1})

        assert response.status_code == 422
        data = response.json()
        assert "error" in data
        assert "code" in data["error"]
        assert "message" in data["error"]
        assert "errors" in data["error"]
        assert isinstance(data["error"]["errors"], list)


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
        assert data["pagination"]["limit"] == 50  # Default limit
        # Default offset=0 may be returned as None due to cursor-based pagination preference
        assert data["pagination"]["offset"] in (0, None)

    @pytest.mark.asyncio
    async def test_pagination_max_limit_enforced(self, client: AsyncClient):
        """Test maximum limit is enforced."""
        # Attempt to request more than max allowed
        response = await client.get("/api/events", params={"limit": 2000})

        # Should fail validation (max is 1000)
        assert response.status_code == 422


# =============================================================================
# WebSocket Message Contract Tests
# =============================================================================


class TestWebSocketMessageContracts:
    """Contract tests for WebSocket message formats.

    These tests verify that the backend WebSocket schemas match the
    documented frontend contract. They test schema structure rather
    than actual WebSocket connections.
    """

    def test_event_message_schema_structure(self):
        """Test WebSocketEventMessage schema has all required fields."""
        from backend.api.schemas.websocket import WebSocketEventMessage

        # Get schema from the model
        schema = WebSocketEventMessage.model_json_schema()

        # Verify top-level structure
        assert "properties" in schema
        properties = schema["properties"]
        assert "type" in properties
        assert "data" in properties

        # Verify type is literal "event"
        assert properties["type"]["const"] == "event"

    def test_event_data_schema_structure(self):
        """Test WebSocketEventData schema matches frontend expectations."""
        from backend.api.schemas.websocket import WebSocketEventData

        schema = WebSocketEventData.model_json_schema()
        properties = schema["properties"]

        # Required fields expected by frontend SecurityEventData type
        required_fields = [
            "id",
            "event_id",
            "batch_id",
            "camera_id",
            "risk_score",
            "risk_level",
            "summary",
            "reasoning",
        ]

        for field in required_fields:
            assert field in properties, f"Missing required field: {field}"

        # Verify risk_score constraints
        assert properties["risk_score"]["minimum"] == 0
        assert properties["risk_score"]["maximum"] == 100

    def test_service_status_message_schema_structure(self):
        """Test WebSocketServiceStatusMessage schema matches frontend."""
        from backend.api.schemas.websocket import WebSocketServiceStatusMessage

        schema = WebSocketServiceStatusMessage.model_json_schema()
        properties = schema["properties"]

        # Required fields
        assert "type" in properties
        assert "data" in properties
        assert "timestamp" in properties

        # Verify type discriminant
        assert properties["type"]["const"] == "service_status"

    def test_service_status_data_schema_structure(self):
        """Test WebSocketServiceStatusData schema matches frontend."""
        from backend.api.schemas.websocket import WebSocketServiceStatusData

        schema = WebSocketServiceStatusData.model_json_schema()
        properties = schema["properties"]

        # Required fields expected by frontend ServiceStatusData type
        assert "service" in properties
        assert "status" in properties

        # Optional fields
        assert "message" in properties

    def test_scene_change_message_schema_structure(self):
        """Test WebSocketSceneChangeMessage schema matches frontend."""
        from backend.api.schemas.websocket import WebSocketSceneChangeMessage

        schema = WebSocketSceneChangeMessage.model_json_schema()
        properties = schema["properties"]

        # Required fields
        assert "type" in properties
        assert "data" in properties

        # Verify type discriminant
        assert properties["type"]["const"] == "scene_change"

    def test_scene_change_data_schema_structure(self):
        """Test WebSocketSceneChangeData schema matches frontend."""
        from backend.api.schemas.websocket import WebSocketSceneChangeData

        schema = WebSocketSceneChangeData.model_json_schema()
        properties = schema["properties"]

        # Required fields
        required_fields = [
            "id",
            "camera_id",
            "detected_at",
            "change_type",
            "similarity_score",
        ]

        for field in required_fields:
            assert field in properties, f"Missing required field: {field}"

        # Verify similarity_score constraints
        assert properties["similarity_score"]["minimum"] == 0.0
        assert properties["similarity_score"]["maximum"] == 1.0

    def test_error_response_schema_structure(self):
        """Test WebSocketErrorResponse schema matches frontend ErrorMessage."""
        from backend.api.schemas.websocket import WebSocketErrorResponse

        schema = WebSocketErrorResponse.model_json_schema()
        properties = schema["properties"]

        # Required fields expected by frontend ErrorMessage type
        assert "type" in properties
        assert "error" in properties
        assert "message" in properties

        # Verify type discriminant
        assert properties["type"]["const"] == "error"

    def test_pong_response_schema_structure(self):
        """Test WebSocketPongResponse schema matches frontend PongMessage."""
        from backend.api.schemas.websocket import WebSocketPongResponse

        schema = WebSocketPongResponse.model_json_schema()
        properties = schema["properties"]

        # Verify type discriminant
        assert "type" in properties
        assert properties["type"]["const"] == "pong"

    def test_risk_level_enum_values(self):
        """Test RiskLevel enum has all values expected by frontend."""
        from backend.api.schemas.websocket import RiskLevel

        # Frontend expects these exact values (lowercase)
        expected_values = {"low", "medium", "high", "critical"}
        actual_values = {level.value for level in RiskLevel}

        assert actual_values == expected_values, (
            f"RiskLevel enum mismatch. Expected: {expected_values}, Actual: {actual_values}"
        )


# =============================================================================
# Health API Contract Tests
# =============================================================================


class TestHealthAPIContract:
    """Contract tests for Health API endpoints."""

    @pytest.mark.asyncio
    async def test_system_health_response_schema(self, client: AsyncClient):
        """Test GET /api/system/health returns valid HealthResponse schema."""
        response = await client.get("/api/system/health")

        # Health endpoint may return 200 or 503 based on service status
        assert response.status_code in [200, 503]
        data = response.json()

        # Verify required fields
        assert "status" in data
        assert "services" in data
        assert "timestamp" in data

        # Verify status is one of the expected values
        assert data["status"] in ["healthy", "degraded", "unhealthy"]

        # Verify services is a dict
        assert isinstance(data["services"], dict)

    @pytest.mark.asyncio
    async def test_system_ready_response_schema(self, client: AsyncClient):
        """Test GET /api/system/health/ready returns valid ReadinessResponse."""
        response = await client.get("/api/system/health/ready")

        # Readiness endpoint may return 200 or 503
        assert response.status_code in [200, 503]
        data = response.json()

        # Verify required fields
        assert "ready" in data
        assert "status" in data
        assert "timestamp" in data

        # Verify types
        assert isinstance(data["ready"], bool)
        assert data["status"] in ["ready", "degraded", "not_ready"]
