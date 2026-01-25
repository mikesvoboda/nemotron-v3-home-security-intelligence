"""Unit tests for zone anomaly API routes.

Tests the zone anomaly endpoints for listing and acknowledging anomalies.

Related: NEM-3495 (Zone Anomalies widget error)
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routes.zone_anomalies import router
from backend.core.database import get_db
from backend.models.zone_anomaly import ZoneAnomaly

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

    # Override the database dependency
    async def override_get_db():
        yield mock_db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client


# Fixed UUIDs for consistent testing
SAMPLE_ZONE_UUID = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
SAMPLE_ANOMALY_UUID = "b2c3d4e5-f6a7-8901-bcde-f12345678901"


@pytest.fixture
def sample_anomaly() -> ZoneAnomaly:
    """Create a sample zone anomaly object for testing."""
    anomaly = ZoneAnomaly(
        id=SAMPLE_ANOMALY_UUID,
        zone_id=SAMPLE_ZONE_UUID,
        camera_id="front_door",
        anomaly_type="unusual_time",
        severity="warning",
        title="Unusual activity at 03:15",
        description="Activity detected in Front Door at 03:15 when typical activity is 0.1.",
        expected_value=0.1,
        actual_value=1.0,
        deviation=3.5,
        detection_id=12345,
        thumbnail_url="/api/detections/12345/image",
        acknowledged=False,
        acknowledged_at=None,
        acknowledged_by=None,
        timestamp=datetime(2025, 1, 24, 3, 15, 0, tzinfo=UTC),
        created_at=datetime(2025, 1, 24, 3, 15, 0, tzinfo=UTC),
        updated_at=datetime(2025, 1, 24, 3, 15, 0, tzinfo=UTC),
    )
    return anomaly


@pytest.fixture
def sample_anomaly_list(sample_anomaly: ZoneAnomaly) -> list[ZoneAnomaly]:
    """Create a list of sample anomalies for testing."""
    anomaly2 = ZoneAnomaly(
        id=str(uuid4()),
        zone_id=SAMPLE_ZONE_UUID,
        camera_id="front_door",
        anomaly_type="unusual_frequency",
        severity="critical",
        title="High activity frequency in Front Door",
        description="Detected 25 crossings in the last hour.",
        expected_value=10.0,
        actual_value=25.0,
        deviation=4.5,
        detection_id=12346,
        thumbnail_url="/api/detections/12346/image",
        acknowledged=False,
        acknowledged_at=None,
        acknowledged_by=None,
        timestamp=datetime(2025, 1, 24, 4, 0, 0, tzinfo=UTC),
        created_at=datetime(2025, 1, 24, 4, 0, 0, tzinfo=UTC),
        updated_at=datetime(2025, 1, 24, 4, 0, 0, tzinfo=UTC),
    )
    return [sample_anomaly, anomaly2]


# =============================================================================
# List All Anomalies Tests (GET /api/zones/anomalies)
# =============================================================================


class TestListAllAnomalies:
    """Tests for GET /api/zones/anomalies endpoint."""

    def test_list_all_anomalies_empty(self, client: TestClient, mock_db_session: AsyncMock) -> None:
        """Test listing anomalies when none exist."""
        # Mock count query returning 0
        count_result = MagicMock()
        count_result.scalar.return_value = 0

        # Mock items query returning empty list
        items_result = MagicMock()
        items_result.scalars.return_value.all.return_value = []

        mock_db_session.execute = AsyncMock(side_effect=[count_result, items_result])

        response = client.get("/api/zones/anomalies")

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["pagination"]["total"] == 0
        assert data["pagination"]["has_more"] is False

    def test_list_all_anomalies_with_results(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
        sample_anomaly_list: list[ZoneAnomaly],
    ) -> None:
        """Test listing anomalies with results."""
        count_result = MagicMock()
        count_result.scalar.return_value = 2

        items_result = MagicMock()
        items_result.scalars.return_value.all.return_value = sample_anomaly_list

        mock_db_session.execute = AsyncMock(side_effect=[count_result, items_result])

        response = client.get("/api/zones/anomalies")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["pagination"]["total"] == 2

    def test_list_anomalies_with_severity_filter(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
        sample_anomaly: ZoneAnomaly,
    ) -> None:
        """Test filtering anomalies by severity."""
        count_result = MagicMock()
        count_result.scalar.return_value = 1

        items_result = MagicMock()
        items_result.scalars.return_value.all.return_value = [sample_anomaly]

        mock_db_session.execute = AsyncMock(side_effect=[count_result, items_result])

        response = client.get("/api/zones/anomalies?severity=warning")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1

    def test_list_anomalies_unacknowledged_only(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
        sample_anomaly: ZoneAnomaly,
    ) -> None:
        """Test filtering for unacknowledged anomalies only."""
        count_result = MagicMock()
        count_result.scalar.return_value = 1

        items_result = MagicMock()
        items_result.scalars.return_value.all.return_value = [sample_anomaly]

        mock_db_session.execute = AsyncMock(side_effect=[count_result, items_result])

        response = client.get("/api/zones/anomalies?unacknowledged_only=true")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1

    def test_list_anomalies_with_pagination(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
        sample_anomaly: ZoneAnomaly,
    ) -> None:
        """Test pagination parameters are applied."""
        count_result = MagicMock()
        count_result.scalar.return_value = 100  # 100 total anomalies

        items_result = MagicMock()
        items_result.scalars.return_value.all.return_value = [sample_anomaly]

        mock_db_session.execute = AsyncMock(side_effect=[count_result, items_result])

        response = client.get("/api/zones/anomalies?limit=10&offset=20")

        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["limit"] == 10
        assert data["pagination"]["offset"] == 20
        assert data["pagination"]["total"] == 100
        assert data["pagination"]["has_more"] is True  # 20 + 1 < 100


# =============================================================================
# List Zone Anomalies Tests (GET /api/zones/{zone_id}/anomalies)
# =============================================================================


class TestListZoneAnomalies:
    """Tests for GET /api/zones/{zone_id}/anomalies endpoint."""

    def test_list_zone_anomalies_empty(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test listing zone anomalies when none exist."""
        count_result = MagicMock()
        count_result.scalar.return_value = 0

        items_result = MagicMock()
        items_result.scalars.return_value.all.return_value = []

        mock_db_session.execute = AsyncMock(side_effect=[count_result, items_result])

        response = client.get(f"/api/zones/{SAMPLE_ZONE_UUID}/anomalies")

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["pagination"]["total"] == 0

    def test_list_zone_anomalies_with_results(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
        sample_anomaly: ZoneAnomaly,
    ) -> None:
        """Test listing zone anomalies with results."""
        count_result = MagicMock()
        count_result.scalar.return_value = 1

        items_result = MagicMock()
        items_result.scalars.return_value.all.return_value = [sample_anomaly]

        mock_db_session.execute = AsyncMock(side_effect=[count_result, items_result])

        response = client.get(f"/api/zones/{SAMPLE_ZONE_UUID}/anomalies")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["zone_id"] == SAMPLE_ZONE_UUID

    def test_list_zone_anomalies_with_severity_filter(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
        sample_anomaly: ZoneAnomaly,
    ) -> None:
        """Test filtering zone anomalies by severity."""
        count_result = MagicMock()
        count_result.scalar.return_value = 1

        items_result = MagicMock()
        items_result.scalars.return_value.all.return_value = [sample_anomaly]

        mock_db_session.execute = AsyncMock(side_effect=[count_result, items_result])

        response = client.get(f"/api/zones/{SAMPLE_ZONE_UUID}/anomalies?severity=warning")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1


# =============================================================================
# Acknowledge Anomaly Tests (POST /api/zones/anomalies/{anomaly_id}/acknowledge)
# =============================================================================


class TestAcknowledgeAnomaly:
    """Tests for POST /api/zones/anomalies/{anomaly_id}/acknowledge endpoint."""

    def test_acknowledge_anomaly_success(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
        sample_anomaly: ZoneAnomaly,
    ) -> None:
        """Test successfully acknowledging an anomaly."""
        # Create a copy to simulate state change
        acknowledged_anomaly = ZoneAnomaly(
            id=sample_anomaly.id,
            zone_id=sample_anomaly.zone_id,
            camera_id=sample_anomaly.camera_id,
            anomaly_type=sample_anomaly.anomaly_type,
            severity=sample_anomaly.severity,
            title=sample_anomaly.title,
            description=sample_anomaly.description,
            expected_value=sample_anomaly.expected_value,
            actual_value=sample_anomaly.actual_value,
            deviation=sample_anomaly.deviation,
            detection_id=sample_anomaly.detection_id,
            thumbnail_url=sample_anomaly.thumbnail_url,
            acknowledged=True,
            acknowledged_at=datetime.now(UTC),
            acknowledged_by=None,
            timestamp=sample_anomaly.timestamp,
            created_at=sample_anomaly.created_at,
            updated_at=datetime.now(UTC),
        )

        result = MagicMock()
        result.scalar_one_or_none.return_value = acknowledged_anomaly

        mock_db_session.execute = AsyncMock(return_value=result)

        response = client.post(f"/api/zones/anomalies/{sample_anomaly.id}/acknowledge")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_anomaly.id
        assert data["acknowledged"] is True
        assert data["acknowledged_at"] is not None

    def test_acknowledge_anomaly_not_found(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test acknowledging a non-existent anomaly returns 404."""
        result = MagicMock()
        result.scalar_one_or_none.return_value = None

        mock_db_session.execute = AsyncMock(return_value=result)

        nonexistent_id = str(uuid4())
        response = client.post(f"/api/zones/anomalies/{nonexistent_id}/acknowledge")

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()


# =============================================================================
# Schema Validation Tests
# =============================================================================


class TestZoneAnomalySchemas:
    """Tests for zone anomaly schemas."""

    def test_zone_anomaly_response_valid(self) -> None:
        """Test ZoneAnomalyResponse with valid data."""
        from backend.api.schemas.zone_anomaly import ZoneAnomalyResponse

        data = {
            "id": SAMPLE_ANOMALY_UUID,
            "zone_id": SAMPLE_ZONE_UUID,
            "camera_id": "front_door",
            "anomaly_type": "unusual_time",
            "severity": "warning",
            "title": "Test anomaly",
            "description": "Test description",
            "expected_value": 0.1,
            "actual_value": 1.0,
            "deviation": 3.5,
            "detection_id": 12345,
            "thumbnail_url": "/api/detections/12345/image",
            "acknowledged": False,
            "acknowledged_at": None,
            "acknowledged_by": None,
            "timestamp": datetime(2025, 1, 24, 3, 15, 0, tzinfo=UTC),
            "created_at": datetime(2025, 1, 24, 3, 15, 0, tzinfo=UTC),
            "updated_at": datetime(2025, 1, 24, 3, 15, 0, tzinfo=UTC),
        }
        schema = ZoneAnomalyResponse(**data)
        assert schema.id == SAMPLE_ANOMALY_UUID
        assert schema.severity == "warning"
        assert schema.acknowledged is False

    def test_zone_anomaly_list_response_valid(self) -> None:
        """Test ZoneAnomalyListResponse with valid data."""
        from backend.api.schemas.zone_anomaly import ZoneAnomalyListResponse

        data = {
            "items": [
                {
                    "id": SAMPLE_ANOMALY_UUID,
                    "zone_id": SAMPLE_ZONE_UUID,
                    "camera_id": "front_door",
                    "anomaly_type": "unusual_time",
                    "severity": "warning",
                    "title": "Test anomaly",
                    "description": None,
                    "expected_value": None,
                    "actual_value": None,
                    "deviation": None,
                    "detection_id": None,
                    "thumbnail_url": None,
                    "acknowledged": False,
                    "acknowledged_at": None,
                    "acknowledged_by": None,
                    "timestamp": datetime(2025, 1, 24, 3, 15, 0, tzinfo=UTC),
                    "created_at": datetime(2025, 1, 24, 3, 15, 0, tzinfo=UTC),
                    "updated_at": datetime(2025, 1, 24, 3, 15, 0, tzinfo=UTC),
                }
            ],
            "pagination": {"total": 1, "limit": 50, "offset": 0, "has_more": False},
        }
        schema = ZoneAnomalyListResponse(**data)
        assert len(schema.items) == 1
        assert schema.pagination.total == 1

    def test_zone_anomaly_acknowledge_response_valid(self) -> None:
        """Test ZoneAnomalyAcknowledgeResponse with valid data."""
        from backend.api.schemas.zone_anomaly import ZoneAnomalyAcknowledgeResponse

        data = {
            "id": SAMPLE_ANOMALY_UUID,
            "acknowledged": True,
            "acknowledged_at": datetime(2025, 1, 24, 4, 0, 0, tzinfo=UTC),
            "acknowledged_by": None,
        }
        schema = ZoneAnomalyAcknowledgeResponse(**data)
        assert schema.id == SAMPLE_ANOMALY_UUID
        assert schema.acknowledged is True


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_list_anomalies_multiple_severity_filters(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
        sample_anomaly_list: list[ZoneAnomaly],
    ) -> None:
        """Test filtering by multiple severity levels."""
        count_result = MagicMock()
        count_result.scalar.return_value = 2

        items_result = MagicMock()
        items_result.scalars.return_value.all.return_value = sample_anomaly_list

        mock_db_session.execute = AsyncMock(side_effect=[count_result, items_result])

        response = client.get("/api/zones/anomalies?severity=warning&severity=critical")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2

    def test_list_anomalies_with_time_range(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
        sample_anomaly: ZoneAnomaly,
    ) -> None:
        """Test filtering by time range."""
        count_result = MagicMock()
        count_result.scalar.return_value = 1

        items_result = MagicMock()
        items_result.scalars.return_value.all.return_value = [sample_anomaly]

        mock_db_session.execute = AsyncMock(side_effect=[count_result, items_result])

        response = client.get(
            "/api/zones/anomalies?since=2025-01-24T00:00:00Z&until=2025-01-24T23:59:59Z"
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
