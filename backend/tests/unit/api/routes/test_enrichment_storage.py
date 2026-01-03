"""Unit tests for enrichment data storage and API retrieval.

These tests verify that enrichment data (vehicle classification, pet identification,
person attributes, license plates, etc.) is correctly persisted to detections
and returned in API responses.

Following TDD: These tests are written BEFORE implementation.
"""

import json
import uuid
from datetime import UTC, datetime

import pytest


@pytest.fixture
async def sample_camera_for_enrichment(test_db):
    """Create a sample camera for enrichment tests."""
    from backend.models.camera import Camera

    async with test_db() as session:
        camera = Camera(
            id=str(uuid.uuid4()),
            name=f"Enrichment Test Camera {uuid.uuid4().hex[:8]}",
            folder_path=f"/export/foscam/enrichment_test_{uuid.uuid4().hex[:8]}",
            status="online",
        )
        session.add(camera)
        await session.commit()
        await session.refresh(camera)
        return camera


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

    @pytest.mark.asyncio
    async def test_detection_model_has_enrichment_data_column(
        self, test_db, sample_camera_for_enrichment
    ):
        """Test that Detection model has enrichment_data column."""
        from backend.models.detection import Detection

        async with test_db() as session:
            detection = Detection(
                camera_id=sample_camera_for_enrichment.id,
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
            session.add(detection)
            await session.commit()
            await session.refresh(detection)

            assert hasattr(detection, "enrichment_data")
            assert detection.enrichment_data is None

    @pytest.mark.asyncio
    async def test_detection_stores_enrichment_data_json(
        self, test_db, sample_camera_for_enrichment, sample_enrichment_data
    ):
        """Test that enrichment data is stored as JSON in Detection model."""
        from backend.models.detection import Detection

        async with test_db() as session:
            detection = Detection(
                camera_id=sample_camera_for_enrichment.id,
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
            session.add(detection)
            await session.commit()
            await session.refresh(detection)

            # Verify enrichment_data is persisted correctly
            assert detection.enrichment_data is not None
            assert detection.enrichment_data["vehicle"]["type"] == "sedan"
            assert detection.enrichment_data["pet"]["breed"] == "labrador"
            assert detection.enrichment_data["license_plate"]["text"] == "ABC123"

    @pytest.mark.asyncio
    async def test_detection_enrichment_data_retrieved_from_database(
        self, test_db, sample_camera_for_enrichment, sample_enrichment_data
    ):
        """Test that enrichment data is correctly retrieved from database."""
        from sqlalchemy import select

        from backend.models.detection import Detection

        async with test_db() as session:
            detection = Detection(
                camera_id=sample_camera_for_enrichment.id,
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
            session.add(detection)
            await session.commit()
            detection_id = detection.id

        # Retrieve in a new session to verify persistence
        async with test_db() as session:
            result = await session.execute(select(Detection).where(Detection.id == detection_id))
            retrieved = result.scalar_one()

            assert retrieved.enrichment_data is not None
            assert retrieved.enrichment_data == sample_enrichment_data


class TestDetectionResponseSchema:
    """Tests for DetectionResponse schema enrichment_data field."""

    def test_detection_response_includes_enrichment_data_field(self):
        """Test that DetectionResponse schema has enrichment_data field."""
        from backend.api.schemas.detections import DetectionResponse

        schema_fields = DetectionResponse.model_fields
        assert "enrichment_data" in schema_fields

    def test_detection_response_serializes_enrichment_data(self, sample_enrichment_data):
        """Test that DetectionResponse correctly serializes enrichment data."""
        from datetime import datetime

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
        from datetime import datetime

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
        self, test_db, sample_camera_for_enrichment, sample_enrichment_data
    ):
        """Test that GET /api/detections/{id} returns enrichment_data."""
        from httpx import ASGITransport, AsyncClient

        from backend.main import app
        from backend.models.detection import Detection

        # Create detection with enrichment data
        async with test_db() as session:
            detection = Detection(
                camera_id=sample_camera_for_enrichment.id,
                file_path="/export/foscam/test/api_test.jpg",
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
            session.add(detection)
            await session.commit()
            detection_id = detection.id

        # Test API response
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/detections/{detection_id}")

        assert response.status_code == 200
        data = response.json()
        assert "enrichment_data" in data
        assert data["enrichment_data"] == sample_enrichment_data

    @pytest.mark.asyncio
    async def test_list_detections_returns_enrichment_data(
        self, test_db, sample_camera_for_enrichment, sample_enrichment_data
    ):
        """Test that GET /api/detections returns enrichment_data for each detection."""
        from httpx import ASGITransport, AsyncClient

        from backend.main import app
        from backend.models.detection import Detection

        # Create detection with enrichment data
        async with test_db() as session:
            detection = Detection(
                camera_id=sample_camera_for_enrichment.id,
                file_path="/export/foscam/test/list_api_test.jpg",
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
            session.add(detection)
            await session.commit()
            camera_id = sample_camera_for_enrichment.id

        # Test API response
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/detections?camera_id={camera_id}")

        assert response.status_code == 200
        data = response.json()
        assert "detections" in data
        # Find our detection in the list
        detection_found = False
        for det in data["detections"]:
            if (
                "enrichment_data" in det
                and det["enrichment_data"] is not None
                and det["enrichment_data"].get("license_plate", {}).get("text") == "ABC123"
            ):
                detection_found = True
                break
        assert detection_found, "Detection with enrichment data not found in API response"


class TestEventDetectionsEnrichmentData:
    """Tests for event detections endpoint returning enrichment data."""

    @pytest.mark.asyncio
    async def test_get_event_detections_includes_enrichment_data(
        self, test_db, sample_camera_for_enrichment, sample_enrichment_data
    ):
        """Test that GET /api/events/{id}/detections returns enrichment_data."""
        from httpx import ASGITransport, AsyncClient

        from backend.main import app
        from backend.models.detection import Detection
        from backend.models.event import Event

        # Create detection with enrichment data
        async with test_db() as session:
            detection = Detection(
                camera_id=sample_camera_for_enrichment.id,
                file_path="/export/foscam/test/event_detection.jpg",
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
            session.add(detection)
            await session.commit()
            detection_id = detection.id

            # Create event referencing this detection
            event = Event(
                batch_id=str(uuid.uuid4()),
                camera_id=sample_camera_for_enrichment.id,
                started_at=datetime.now(UTC),
                ended_at=datetime.now(UTC),
                risk_score=50,
                risk_level="medium",
                summary="Test event with enrichment",
                detection_ids=json.dumps([detection_id]),
                reviewed=False,
            )
            session.add(event)
            await session.commit()
            event_id = event.id

        # Test API response
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/events/{event_id}/detections")

        assert response.status_code == 200
        data = response.json()
        assert "detections" in data
        assert len(data["detections"]) == 1
        assert "enrichment_data" in data["detections"][0]
        assert data["detections"][0]["enrichment_data"] == sample_enrichment_data
