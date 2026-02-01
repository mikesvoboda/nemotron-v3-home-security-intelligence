"""Unit tests for anomaly context API endpoint.

Tests the GET /api/zones/anomalies/{anomaly_id}/context endpoint for
retrieving anomalies with full investigation context.

Related: NEM-4714 (Backend Anomaly Context Endpoint)
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routes.zone_anomalies import router
from backend.core.database import get_db

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Create a mock database session."""
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.delete = AsyncMock()
    return session


@pytest.fixture
def client(mock_db_session: AsyncMock) -> TestClient:
    """Create a test client with mocked dependencies."""
    app = FastAPI()
    app.include_router(router)

    async def override_get_db():
        yield mock_db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client


# Fixed UUIDs for consistent testing
SAMPLE_ZONE_UUID = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
SAMPLE_ANOMALY_UUID = "b2c3d4e5-f6a7-8901-bcde-f12345678901"


@pytest.fixture
def sample_anomaly_context() -> dict:
    """Create sample anomaly context response data."""
    return {
        "id": SAMPLE_ANOMALY_UUID,
        "zone_id": SAMPLE_ZONE_UUID,
        "zone_name": "Front Door",
        "anomaly_type": "unusual_time",
        "severity": "warning",
        "timestamp": datetime(2025, 1, 24, 3, 15, 0, tzinfo=UTC),
        "expected_value": 0.1,
        "actual_value": 1.0,
        "explanation": "Activity detected in Front Door at 03:15 when typical activity is 0.1.",
        "detections": [
            {
                "id": "12345",
                "camera_id": "front_door",
                "timestamp": datetime(2025, 1, 24, 3, 15, 0, tzinfo=UTC),
                "object_class": "person",
                "confidence": 0.95,
                "risk_score": 75,
                "thumbnail_url": "/api/detections/12345/image",
            }
        ],
        "acknowledged": False,
        "acknowledged_at": None,
    }


@pytest.fixture
def sample_anomaly_context_no_detections() -> dict:
    """Create sample anomaly context with no associated detections."""
    return {
        "id": SAMPLE_ANOMALY_UUID,
        "zone_id": SAMPLE_ZONE_UUID,
        "zone_name": "Back Yard",
        "anomaly_type": "unusual_frequency",
        "severity": "critical",
        "timestamp": datetime(2025, 1, 24, 4, 0, 0, tzinfo=UTC),
        "expected_value": 10.0,
        "actual_value": 25.0,
        "explanation": "Detected 25 crossings in the last hour.",
        "detections": [],
        "acknowledged": True,
        "acknowledged_at": datetime(2025, 1, 24, 5, 0, 0, tzinfo=UTC),
    }


# =============================================================================
# Get Anomaly Context Tests (GET /api/zones/anomalies/{anomaly_id}/context)
# =============================================================================


class TestGetAnomalyContext:
    """Tests for GET /api/zones/anomalies/{anomaly_id}/context endpoint."""

    def test_get_anomaly_context_success(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
        sample_anomaly_context: dict,
    ) -> None:
        """Test successfully retrieving anomaly context."""
        with patch(
            "backend.api.routes.zone_anomalies.get_zone_anomaly_service"
        ) as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_anomaly_with_context = AsyncMock(return_value=sample_anomaly_context)
            mock_get_service.return_value = mock_service

            response = client.get(f"/api/zones/anomalies/{SAMPLE_ANOMALY_UUID}/context")

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == SAMPLE_ANOMALY_UUID
            assert data["zone_id"] == SAMPLE_ZONE_UUID
            assert data["zone_name"] == "Front Door"
            assert data["anomaly_type"] == "unusual_time"
            assert data["severity"] == "warning"
            assert data["expected_value"] == 0.1
            assert data["actual_value"] == 1.0
            assert data["explanation"] == sample_anomaly_context["explanation"]
            assert len(data["detections"]) == 1
            assert data["detections"][0]["id"] == "12345"
            assert data["detections"][0]["object_class"] == "person"
            assert data["detections"][0]["confidence"] == 0.95
            assert data["acknowledged"] is False

            # Verify service was called with correct arguments
            mock_service.get_anomaly_with_context.assert_called_once_with(
                SAMPLE_ANOMALY_UUID, session=mock_db_session
            )

    def test_get_anomaly_context_not_found(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test 404 when anomaly does not exist."""
        with patch(
            "backend.api.routes.zone_anomalies.get_zone_anomaly_service"
        ) as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_anomaly_with_context = AsyncMock(return_value=None)
            mock_get_service.return_value = mock_service

            nonexistent_id = "00000000-0000-0000-0000-000000000000"
            response = client.get(f"/api/zones/anomalies/{nonexistent_id}/context")

            assert response.status_code == 404
            data = response.json()
            assert "not found" in data["detail"].lower()

    def test_get_anomaly_context_no_detections(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
        sample_anomaly_context_no_detections: dict,
    ) -> None:
        """Test retrieving anomaly context with no associated detections."""
        with patch(
            "backend.api.routes.zone_anomalies.get_zone_anomaly_service"
        ) as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_anomaly_with_context = AsyncMock(
                return_value=sample_anomaly_context_no_detections
            )
            mock_get_service.return_value = mock_service

            response = client.get(f"/api/zones/anomalies/{SAMPLE_ANOMALY_UUID}/context")

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == SAMPLE_ANOMALY_UUID
            assert data["zone_name"] == "Back Yard"
            assert data["anomaly_type"] == "unusual_frequency"
            assert data["severity"] == "critical"
            assert data["detections"] == []
            assert data["acknowledged"] is True
            assert data["acknowledged_at"] is not None

    def test_get_anomaly_context_acknowledged(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
        sample_anomaly_context: dict,
    ) -> None:
        """Test retrieving acknowledged anomaly context."""
        acknowledged_context = sample_anomaly_context.copy()
        acknowledged_context["acknowledged"] = True
        acknowledged_context["acknowledged_at"] = datetime(2025, 1, 24, 4, 0, 0, tzinfo=UTC)

        with patch(
            "backend.api.routes.zone_anomalies.get_zone_anomaly_service"
        ) as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_anomaly_with_context = AsyncMock(return_value=acknowledged_context)
            mock_get_service.return_value = mock_service

            response = client.get(f"/api/zones/anomalies/{SAMPLE_ANOMALY_UUID}/context")

            assert response.status_code == 200
            data = response.json()
            assert data["acknowledged"] is True
            assert data["acknowledged_at"] is not None


# =============================================================================
# Schema Validation Tests
# =============================================================================


class TestAnomalyContextSchemas:
    """Tests for anomaly context schemas."""

    def test_associated_detection_valid(self) -> None:
        """Test AssociatedDetection with valid data."""
        from backend.api.schemas.zone_anomaly import AssociatedDetection

        data = {
            "id": "12345",
            "camera_id": "front_door",
            "timestamp": datetime(2025, 1, 24, 3, 15, 0, tzinfo=UTC),
            "object_class": "person",
            "confidence": 0.95,
            "risk_score": 75,
            "thumbnail_url": "/api/detections/12345/image",
        }
        schema = AssociatedDetection(**data)
        assert schema.id == "12345"
        assert schema.camera_id == "front_door"
        assert schema.object_class == "person"
        assert schema.confidence == 0.95
        assert schema.risk_score == 75

    def test_associated_detection_minimal(self) -> None:
        """Test AssociatedDetection with minimal required data."""
        from backend.api.schemas.zone_anomaly import AssociatedDetection

        data = {
            "id": "12345",
            "camera_id": "front_door",
            "timestamp": datetime(2025, 1, 24, 3, 15, 0, tzinfo=UTC),
            "object_class": "person",
            "confidence": 0.95,
        }
        schema = AssociatedDetection(**data)
        assert schema.id == "12345"
        assert schema.risk_score is None
        assert schema.thumbnail_url is None

    def test_anomaly_context_response_valid(self) -> None:
        """Test AnomalyContextResponse with valid data."""
        from backend.api.schemas.zone_anomaly import AnomalyContextResponse

        data = {
            "id": SAMPLE_ANOMALY_UUID,
            "zone_id": SAMPLE_ZONE_UUID,
            "zone_name": "Front Door",
            "anomaly_type": "unusual_time",
            "severity": "warning",
            "timestamp": datetime(2025, 1, 24, 3, 15, 0, tzinfo=UTC),
            "expected_value": 0.1,
            "actual_value": 1.0,
            "explanation": "Activity detected at unusual time.",
            "detections": [
                {
                    "id": "12345",
                    "camera_id": "front_door",
                    "timestamp": datetime(2025, 1, 24, 3, 15, 0, tzinfo=UTC),
                    "object_class": "person",
                    "confidence": 0.95,
                    "risk_score": None,
                    "thumbnail_url": None,
                }
            ],
            "acknowledged": False,
            "acknowledged_at": None,
        }
        schema = AnomalyContextResponse(**data)
        assert schema.id == SAMPLE_ANOMALY_UUID
        assert schema.zone_name == "Front Door"
        assert len(schema.detections) == 1
        assert schema.acknowledged is False

    def test_anomaly_context_response_empty_detections(self) -> None:
        """Test AnomalyContextResponse with no detections."""
        from backend.api.schemas.zone_anomaly import AnomalyContextResponse

        data = {
            "id": SAMPLE_ANOMALY_UUID,
            "zone_id": SAMPLE_ZONE_UUID,
            "zone_name": "Back Yard",
            "anomaly_type": "unusual_frequency",
            "severity": "critical",
            "timestamp": datetime(2025, 1, 24, 3, 15, 0, tzinfo=UTC),
            "expected_value": None,
            "actual_value": None,
            "explanation": None,
            "detections": [],
            "acknowledged": True,
            "acknowledged_at": datetime(2025, 1, 24, 4, 0, 0, tzinfo=UTC),
        }
        schema = AnomalyContextResponse(**data)
        assert schema.detections == []
        assert schema.expected_value is None
        assert schema.explanation is None
        assert schema.acknowledged is True
        assert schema.acknowledged_at is not None

    def test_anomaly_context_response_multiple_detections(self) -> None:
        """Test AnomalyContextResponse with multiple detections."""
        from backend.api.schemas.zone_anomaly import AnomalyContextResponse

        data = {
            "id": SAMPLE_ANOMALY_UUID,
            "zone_id": SAMPLE_ZONE_UUID,
            "zone_name": "Front Door",
            "anomaly_type": "unusual_frequency",
            "severity": "critical",
            "timestamp": datetime(2025, 1, 24, 3, 15, 0, tzinfo=UTC),
            "expected_value": 5.0,
            "actual_value": 20.0,
            "explanation": "High activity burst detected.",
            "detections": [
                {
                    "id": "12345",
                    "camera_id": "front_door",
                    "timestamp": datetime(2025, 1, 24, 3, 15, 0, tzinfo=UTC),
                    "object_class": "person",
                    "confidence": 0.95,
                    "risk_score": 75,
                    "thumbnail_url": "/api/detections/12345/image",
                },
                {
                    "id": "12346",
                    "camera_id": "front_door",
                    "timestamp": datetime(2025, 1, 24, 3, 16, 0, tzinfo=UTC),
                    "object_class": "person",
                    "confidence": 0.87,
                    "risk_score": 65,
                    "thumbnail_url": "/api/detections/12346/image",
                },
            ],
            "acknowledged": False,
            "acknowledged_at": None,
        }
        schema = AnomalyContextResponse(**data)
        assert len(schema.detections) == 2
        assert schema.detections[0].id == "12345"
        assert schema.detections[1].id == "12346"
