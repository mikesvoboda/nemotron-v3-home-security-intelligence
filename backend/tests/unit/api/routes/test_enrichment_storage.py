"""Unit tests for enrichment data storage and API retrieval.

These tests verify that enrichment data (vehicle classification, pet identification,
person attributes, license plates, etc.) is correctly persisted to detections
and returned in API responses.

These are UNIT tests using mocks - no real database connections required.
Integration tests with real database are in backend/tests/integration/.
"""

import json
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def sample_camera_data():
    """Return camera data for creating test cameras."""
    return {
        "id": str(uuid.uuid4()),
        "name": f"Enrichment Test Camera {uuid.uuid4().hex[:8]}",
        "folder_path": f"/export/foscam/enrichment_test_{uuid.uuid4().hex[:8]}",
        "status": "online",
    }


@pytest.fixture
def sample_enrichment_data():
    """Sample enrichment data structure for tests."""
    return {
        "vehicle": {
            "type": "sedan",
            "color": "blue",
            "damage": [],
            "confidence": 0.92,
        },
        "pet": {
            "type": "dog",
            "breed": "labrador",
            "confidence": 0.88,
        },
        "person": {
            "clothing": "dark jacket",
            "action": "walking",
            "carrying": "backpack",
            "confidence": 0.95,
        },
        "license_plate": {
            "text": "ABC123",
            "confidence": 0.91,
        },
        "weather": {
            "condition": "cloudy",
            "confidence": 0.87,
        },
        "image_quality": {
            "score": 0.85,
            "issues": [],
        },
    }


class TestDetectionModelEnrichmentData:
    """Tests for Detection model enrichment_data column."""

    def test_detection_model_has_enrichment_data_column(self):
        """Test that Detection model has enrichment_data column."""
        from backend.models.detection import Detection

        # Verify the model class has the enrichment_data attribute
        assert hasattr(Detection, "enrichment_data")

        # Create an instance with enrichment_data=None
        detection = Detection(
            camera_id=str(uuid.uuid4()),
            file_path="/export/foscam/test/image.jpg",
            file_type="image/jpeg",
            detected_at=datetime.now(UTC),
            object_type="person",
            confidence=0.95,
            bbox_x=100,
            bbox_y=150,
            bbox_width=200,
            bbox_height=400,
            enrichment_data=None,
        )

        assert hasattr(detection, "enrichment_data")
        assert detection.enrichment_data is None

    def test_detection_stores_enrichment_data_json(self, sample_enrichment_data):
        """Test that enrichment data can be assigned to Detection model."""
        from backend.models.detection import Detection

        detection = Detection(
            camera_id=str(uuid.uuid4()),
            file_path="/export/foscam/test/image.jpg",
            file_type="image/jpeg",
            detected_at=datetime.now(UTC),
            object_type="car",
            confidence=0.92,
            bbox_x=300,
            bbox_y=200,
            bbox_width=400,
            bbox_height=300,
            enrichment_data=sample_enrichment_data,
        )

        # Verify enrichment_data is set correctly
        assert detection.enrichment_data is not None
        assert detection.enrichment_data["vehicle"]["type"] == "sedan"
        assert detection.enrichment_data["pet"]["breed"] == "labrador"
        assert detection.enrichment_data["license_plate"]["text"] == "ABC123"

    def test_detection_enrichment_data_is_dict_type(self, sample_enrichment_data):
        """Test that enrichment data maintains dict type."""
        from backend.models.detection import Detection

        detection = Detection(
            camera_id=str(uuid.uuid4()),
            file_path="/export/foscam/test/retrieve_test.jpg",
            file_type="image/jpeg",
            detected_at=datetime.now(UTC),
            object_type="person",
            confidence=0.95,
            bbox_x=100,
            bbox_y=150,
            bbox_width=200,
            bbox_height=400,
            enrichment_data=sample_enrichment_data,
        )

        # Verify it's a dict and can be accessed properly
        assert isinstance(detection.enrichment_data, dict)
        assert detection.enrichment_data == sample_enrichment_data


class TestDetectionResponseSchema:
    """Tests for DetectionResponse schema enrichment_data field."""

    def test_detection_response_includes_enrichment_data_field(self):
        """Test that DetectionResponse schema has enrichment_data field."""
        from backend.api.schemas.detections import DetectionResponse

        schema_fields = DetectionResponse.model_fields
        assert "enrichment_data" in schema_fields

    def test_detection_response_serializes_enrichment_data(self, sample_enrichment_data):
        """Test that DetectionResponse correctly serializes enrichment data."""
        from backend.api.schemas.detections import DetectionResponse

        response = DetectionResponse(
            id=1,
            camera_id="test-camera",
            file_path="/test/image.jpg",
            file_type="image/jpeg",
            detected_at=datetime.now(UTC),
            object_type="person",
            confidence=0.95,
            bbox_x=100,
            bbox_y=150,
            bbox_width=200,
            bbox_height=400,
            thumbnail_path=None,
            media_type="image",
            duration=None,
            video_codec=None,
            video_width=None,
            video_height=None,
            enrichment_data=sample_enrichment_data,
        )

        # Convert to dict to verify serialization
        response_dict = response.model_dump()
        assert "enrichment_data" in response_dict
        assert response_dict["enrichment_data"] == sample_enrichment_data

    def test_detection_response_handles_null_enrichment_data(self):
        """Test that DetectionResponse handles null enrichment data."""
        from backend.api.schemas.detections import DetectionResponse

        response = DetectionResponse(
            id=1,
            camera_id="test-camera",
            file_path="/test/image.jpg",
            file_type="image/jpeg",
            detected_at=datetime.now(UTC),
            object_type="person",
            confidence=0.95,
            bbox_x=100,
            bbox_y=150,
            bbox_width=200,
            bbox_height=400,
            thumbnail_path=None,
            media_type="image",
            duration=None,
            video_codec=None,
            video_width=None,
            video_height=None,
            enrichment_data=None,
        )

        response_dict = response.model_dump()
        assert response_dict["enrichment_data"] is None


class TestDetectionsAPIEnrichmentData:
    """Tests for Detections API endpoints returning enrichment data."""

    @pytest.mark.asyncio
    async def test_get_detection_returns_enrichment_data(
        self, sample_camera_data, sample_enrichment_data
    ):
        """Test that GET /api/detections/{id} returns enrichment_data."""
        from httpx import ASGITransport, AsyncClient

        from backend.core.database import get_db
        from backend.main import app
        from backend.models.detection import Detection

        detection_id = 12345
        camera_id = sample_camera_data["id"]

        # Create mock detection with enrichment data
        mock_detection = MagicMock(spec=Detection)
        mock_detection.id = detection_id
        mock_detection.camera_id = camera_id
        mock_detection.file_path = "/export/foscam/test/api_test.jpg"
        mock_detection.file_type = "image/jpeg"
        mock_detection.detected_at = datetime.now(UTC)
        mock_detection.object_type = "car"
        mock_detection.confidence = 0.92
        mock_detection.bbox_x = 300
        mock_detection.bbox_y = 200
        mock_detection.bbox_width = 400
        mock_detection.bbox_height = 300
        mock_detection.thumbnail_path = None
        mock_detection.media_type = "image"
        mock_detection.duration = None
        mock_detection.video_codec = None
        mock_detection.video_width = None
        mock_detection.video_height = None
        mock_detection.enrichment_data = sample_enrichment_data

        # Create mock result that behaves like SQLAlchemy result
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_detection

        # Mock the session
        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        # Override FastAPI dependency
        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(f"/api/detections/{detection_id}")
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert "enrichment_data" in data
        assert data["enrichment_data"] == sample_enrichment_data

    @pytest.mark.asyncio
    async def test_list_detections_returns_enrichment_data(
        self, sample_camera_data, sample_enrichment_data
    ):
        """Test that GET /api/detections returns enrichment_data for each detection."""
        from httpx import ASGITransport, AsyncClient

        from backend.core.database import get_db
        from backend.main import app
        from backend.models.detection import Detection

        camera_id = sample_camera_data["id"]

        # Create mock detection with enrichment data
        mock_detection = MagicMock(spec=Detection)
        mock_detection.id = 12345
        mock_detection.camera_id = camera_id
        mock_detection.file_path = "/export/foscam/test/list_api_test.jpg"
        mock_detection.file_type = "image/jpeg"
        mock_detection.detected_at = datetime.now(UTC)
        mock_detection.object_type = "person"
        mock_detection.confidence = 0.95
        mock_detection.bbox_x = 100
        mock_detection.bbox_y = 150
        mock_detection.bbox_width = 200
        mock_detection.bbox_height = 400
        mock_detection.thumbnail_path = None
        mock_detection.media_type = "image"
        mock_detection.duration = None
        mock_detection.video_codec = None
        mock_detection.video_width = None
        mock_detection.video_height = None
        mock_detection.enrichment_data = sample_enrichment_data

        # Mock the scalars result
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_detection]

        # Mock count result
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 1

        # Mock the session
        mock_session = AsyncMock()
        mock_session.execute.side_effect = [mock_count_result, mock_result]

        # Override FastAPI dependency
        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(f"/api/detections?camera_id={camera_id}")
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert len(data["items"]) == 1
        assert "enrichment_data" in data["items"][0]
        assert data["items"][0]["enrichment_data"] == sample_enrichment_data


class TestEventDetectionsEnrichmentData:
    """Tests for event detections endpoint returning enrichment data."""

    @pytest.mark.asyncio
    async def test_get_event_detections_includes_enrichment_data(
        self, sample_camera_data, sample_enrichment_data
    ):
        """Test that GET /api/events/{id}/detections returns enrichment_data."""
        from httpx import ASGITransport, AsyncClient

        from backend.core.database import get_db
        from backend.main import app
        from backend.models.detection import Detection
        from backend.models.event import Event

        event_id = 99999
        detection_id = 12345
        camera_id = sample_camera_data["id"]

        # Create mock detection with enrichment data
        mock_detection = MagicMock(spec=Detection)
        mock_detection.id = detection_id
        mock_detection.camera_id = camera_id
        mock_detection.file_path = "/export/foscam/test/event_detection.jpg"
        mock_detection.file_type = "image/jpeg"
        mock_detection.detected_at = datetime.now(UTC)
        mock_detection.object_type = "person"
        mock_detection.confidence = 0.95
        mock_detection.bbox_x = 100
        mock_detection.bbox_y = 150
        mock_detection.bbox_width = 200
        mock_detection.bbox_height = 400
        mock_detection.thumbnail_path = None
        mock_detection.media_type = "image"
        mock_detection.duration = None
        mock_detection.video_codec = None
        mock_detection.video_width = None
        mock_detection.video_height = None
        mock_detection.enrichment_data = sample_enrichment_data

        # Create mock event
        mock_event = MagicMock(spec=Event)
        mock_event.id = event_id
        mock_event.batch_id = str(uuid.uuid4())
        mock_event.camera_id = camera_id
        mock_event.started_at = datetime.now(UTC)
        mock_event.ended_at = datetime.now(UTC)
        mock_event.risk_score = 50
        mock_event.risk_level = "medium"
        mock_event.summary = "Test event with enrichment"
        mock_event.detection_ids = json.dumps([detection_id])
        mock_event.reviewed = False

        # Mock event query result
        mock_event_result = MagicMock()
        mock_event_result.scalar_one_or_none.return_value = mock_event

        # Mock count query result
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1

        # Mock detections query result
        mock_detections_result = MagicMock()
        mock_detections_result.scalars.return_value.all.return_value = [mock_detection]

        # Mock the session - note: get_event_detections makes 3 db calls:
        # 1. select Event by id
        # 2. count detections
        # 3. select detections
        mock_session = AsyncMock()
        mock_session.execute.side_effect = [
            mock_event_result,
            mock_count_result,
            mock_detections_result,
        ]

        # Override FastAPI dependency
        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(f"/api/events/{event_id}/detections")
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert len(data["items"]) == 1
        assert "enrichment_data" in data["items"][0]
        assert data["items"][0]["enrichment_data"] == sample_enrichment_data
