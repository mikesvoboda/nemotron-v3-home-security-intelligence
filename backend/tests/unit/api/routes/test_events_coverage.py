"""Comprehensive unit tests to improve coverage for backend/api/routes/events.py.

This test file targets missing coverage lines identified by pytest-cov,
focusing on endpoint handlers, error paths, and edge cases.
"""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routes.events import router
from backend.core.database import get_db
from backend.models.detection import Detection
from backend.models.event import Event

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Create a mock database session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    session.flush = AsyncMock()
    session.add = Mock()
    session.delete = AsyncMock()
    return session


@pytest.fixture
def mock_cache_service() -> AsyncMock:
    """Create a mock cache service."""
    cache = AsyncMock()
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock()
    cache.invalidate_events = AsyncMock()
    cache.invalidate_event_stats = AsyncMock()
    return cache


@pytest.fixture
def client(mock_db_session: AsyncMock, mock_cache_service: AsyncMock) -> TestClient:
    """Create a test client with mocked dependencies."""
    from backend.api.dependencies import get_cache_service_dep

    app = FastAPI()
    app.include_router(router)

    async def override_get_db():
        yield mock_db_session

    async def override_get_cache_service():
        return mock_cache_service

    async def override_get_event_or_404(event_id: int, db):
        # Return a mock event for testing
        mock_event = Mock(spec=Event)
        mock_event.id = event_id
        mock_event.camera_id = "cam1"
        mock_event.started_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
        mock_event.ended_at = datetime(2025, 1, 1, 12, 5, 0, tzinfo=UTC)
        mock_event.risk_score = 75
        mock_event.risk_level = "high"
        mock_event.summary = "Test event"
        mock_event.reasoning = "Test reasoning"
        mock_event.reviewed = False
        mock_event.notes = None
        mock_event.snooze_until = None
        mock_event.detection_ids = "[1, 2, 3]"
        mock_event.detections = []
        mock_event.deleted_at = None
        mock_event.clip_path = None
        return mock_event

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_cache_service_dep] = override_get_cache_service
    # Note: get_event_or_404 is not directly injectable, so we'll mock it in tests

    with TestClient(app) as test_client:
        yield test_client


# =============================================================================
# List Events Tests (Missing Lines: 273, 290-291, 312, 314, 316, 318, 320, etc.)
# =============================================================================


class TestListEventsFilters:
    """Tests for list_events with various filter combinations."""

    def test_list_events_with_trace_id(self, client: TestClient, mock_db_session: AsyncMock):
        """Test list_events logs with trace_id when present."""
        # Mock the query execution
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0
        mock_db_session.execute.side_effect = [mock_count_result, mock_result]

        # Set trace_id in request headers
        with patch("backend.api.routes.events.get_trace_id", return_value="test-trace-123"):
            response = client.get("/api/events")

        assert response.status_code == 200

    def test_list_events_with_camera_id_filter(
        self, client: TestClient, mock_db_session: AsyncMock
    ):
        """Test list_events applies camera_id filter."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0
        mock_db_session.execute.side_effect = [mock_count_result, mock_result]

        response = client.get("/api/events?camera_id=cam1")

        assert response.status_code == 200

    def test_list_events_with_risk_level_filter(
        self, client: TestClient, mock_db_session: AsyncMock
    ):
        """Test list_events applies risk_level filter."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0
        mock_db_session.execute.side_effect = [mock_count_result, mock_result]

        response = client.get("/api/events?risk_level=high")

        assert response.status_code == 200

    def test_list_events_with_start_date_filter(
        self, client: TestClient, mock_db_session: AsyncMock
    ):
        """Test list_events applies start_date filter."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0
        mock_db_session.execute.side_effect = [mock_count_result, mock_result]

        response = client.get("/api/events?start_date=2025-01-01T00:00:00Z")

        assert response.status_code == 200

    def test_list_events_with_end_date_filter(self, client: TestClient, mock_db_session: AsyncMock):
        """Test list_events applies end_date filter."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0
        mock_db_session.execute.side_effect = [mock_count_result, mock_result]

        response = client.get("/api/events?end_date=2025-01-31T23:59:59Z")

        assert response.status_code == 200

    def test_list_events_with_reviewed_filter(self, client: TestClient, mock_db_session: AsyncMock):
        """Test list_events applies reviewed filter."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0
        mock_db_session.execute.side_effect = [mock_count_result, mock_result]

        response = client.get("/api/events?reviewed=true")

        assert response.status_code == 200

    def test_list_events_with_cursor_pagination(
        self, client: TestClient, mock_db_session: AsyncMock
    ):
        """Test list_events uses cursor pagination when cursor is provided."""
        # Create a cursor
        from backend.api.pagination import CursorData, encode_cursor

        cursor_data = CursorData(id=100, created_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC))
        cursor = encode_cursor(cursor_data)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        response = client.get(f"/api/events?cursor={cursor}")

        assert response.status_code == 200
        # Should not compute total_count with cursor pagination
        data = response.json()
        assert data["pagination"]["total"] == 0

    def test_list_events_with_has_more_true(self, client: TestClient, mock_db_session: AsyncMock):
        """Test list_events sets has_more=True when more results exist."""
        # Create mock events - limit+1 to trigger has_more
        mock_events = [
            Mock(
                spec=Event,
                id=i,
                camera_id="cam1",
                started_at=datetime(2025, 1, 1, 12, i, 0, tzinfo=UTC),
                ended_at=datetime(2025, 1, 1, 12, i, 30, tzinfo=UTC),
                risk_score=50 + i,
                risk_level="medium",
                summary=f"Event {i}",
                reasoning=f"Reasoning {i}",
                reviewed=False,
                detection_ids=f"[{i}]",
                detections=[],
            )
            for i in range(51)  # One more than default limit of 50
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_events
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 51
        mock_db_session.execute.side_effect = [mock_count_result, mock_result]

        response = client.get("/api/events?limit=50")

        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["has_more"] is True
        assert len(data["items"]) == 50  # Should be trimmed to limit

    def test_list_events_generates_next_cursor_when_has_more(
        self, client: TestClient, mock_db_session: AsyncMock
    ):
        """Test list_events generates next_cursor when has_more is true."""
        mock_events = [
            Mock(
                spec=Event,
                id=i,
                camera_id="cam1",
                started_at=datetime(2025, 1, 1, 12, i, 0, tzinfo=UTC),
                ended_at=datetime(2025, 1, 1, 12, i, 30, tzinfo=UTC),
                risk_score=50 + i,
                risk_level="medium",
                summary=f"Event {i}",
                reasoning=f"Reasoning {i}",
                reviewed=False,
                detection_ids=f"[{i}]",
                detections=[],
            )
            for i in range(51)
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_events
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 51
        mock_db_session.execute.side_effect = [mock_count_result, mock_result]

        response = client.get("/api/events?limit=50")

        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["next_cursor"] is not None


# =============================================================================
# List Deleted Events Tests (Missing Lines: 882-913)
# =============================================================================


class TestListDeletedEvents:
    """Tests for list_deleted_events endpoint."""

    def test_list_deleted_events_returns_deleted_events(
        self, client: TestClient, mock_db_session: AsyncMock
    ):
        """Test list_deleted_events returns events with deleted_at set."""
        deleted_time = datetime(2025, 1, 10, 10, 0, 0, tzinfo=UTC)
        mock_events = [
            Mock(
                spec=Event,
                id=1,
                camera_id="cam1",
                started_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
                ended_at=datetime(2025, 1, 1, 12, 5, 0, tzinfo=UTC),
                risk_score=75,
                risk_level="high",
                summary="Deleted event",
                reasoning="Test",
                llm_prompt="Test prompt",
                reviewed=False,
                notes=None,
                detection_ids="[1, 2]",
                detections=[],
                deleted_at=deleted_time,
            )
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_events
        mock_db_session.execute.return_value = mock_result

        response = client.get("/api/events/deleted")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["id"] == 1
        assert data["pagination"]["total"] == 1

    def test_list_deleted_events_empty(self, client: TestClient, mock_db_session: AsyncMock):
        """Test list_deleted_events with no deleted events."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        response = client.get("/api/events/deleted")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 0
        assert data["pagination"]["total"] == 0


# =============================================================================
# Bulk Create Events Tests (Missing Lines: 966-1050)
# =============================================================================


class TestBulkCreateEvents:
    """Tests for bulk_create_events endpoint."""

    def test_bulk_create_success(self, client: TestClient, mock_db_session: AsyncMock):
        """Test successful bulk create with all valid events."""
        # Mock camera validation
        mock_camera_result = MagicMock()
        mock_camera_result.all.return_value = [("cam1",)]

        mock_db_session.execute.return_value = mock_camera_result

        request_data = {
            "events": [
                {
                    "batch_id": "batch1",
                    "camera_id": "cam1",
                    "started_at": "2025-01-01T12:00:00Z",
                    "ended_at": "2025-01-01T12:05:00Z",
                    "risk_score": 75,
                    "risk_level": "high",
                    "summary": "Test event",
                    "reasoning": "Test reasoning",
                }
            ]
        }

        response = client.post("/api/events/bulk", json=request_data)

        assert response.status_code == 207
        data = response.json()
        assert data["total"] == 1
        assert data["succeeded"] == 1
        assert data["failed"] == 0

    def test_bulk_create_invalid_camera(self, client: TestClient, mock_db_session: AsyncMock):
        """Test bulk create with invalid camera ID."""
        # Mock camera validation - empty result
        mock_camera_result = MagicMock()
        mock_camera_result.all.return_value = []

        mock_db_session.execute.return_value = mock_camera_result

        request_data = {
            "events": [
                {
                    "batch_id": "batch1",
                    "camera_id": "invalid_cam",
                    "started_at": "2025-01-01T12:00:00Z",
                    "ended_at": "2025-01-01T12:05:00Z",
                    "risk_score": 75,
                    "risk_level": "high",
                    "summary": "Test event",
                    "reasoning": "Test reasoning",
                }
            ]
        }

        response = client.post("/api/events/bulk", json=request_data)

        assert response.status_code == 207
        data = response.json()
        assert data["failed"] == 1
        assert "Camera not found" in data["results"][0]["error"]

    def test_bulk_create_commit_failure(self, client: TestClient, mock_db_session: AsyncMock):
        """Test bulk create with commit failure marks all as failed."""
        # Mock camera validation
        mock_camera_result = MagicMock()
        mock_camera_result.all.return_value = [("cam1",)]

        mock_db_session.execute.return_value = mock_camera_result
        mock_db_session.commit.side_effect = Exception("Database error")

        request_data = {
            "events": [
                {
                    "batch_id": "batch1",
                    "camera_id": "cam1",
                    "started_at": "2025-01-01T12:00:00Z",
                    "ended_at": "2025-01-01T12:05:00Z",
                    "risk_score": 75,
                    "risk_level": "high",
                    "summary": "Test event",
                    "reasoning": "Test reasoning",
                }
            ]
        }

        response = client.post("/api/events/bulk", json=request_data)

        assert response.status_code == 207
        data = response.json()
        assert data["failed"] == 1


# =============================================================================
# Bulk Update Events Tests (Missing Lines: 1089-1164)
# =============================================================================


class TestBulkUpdateEvents:
    """Tests for bulk_update_events endpoint."""

    def test_bulk_update_success(self, client: TestClient, mock_db_session: AsyncMock):
        """Test successful bulk update."""
        mock_event = Mock(spec=Event, id=1, reviewed=False, notes=None)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_event]

        mock_db_session.execute.return_value = mock_result

        request_data = {"events": [{"id": 1, "reviewed": True, "notes": "Updated"}]}

        response = client.patch("/api/events/bulk", json=request_data)

        assert response.status_code == 207
        data = response.json()
        assert data["succeeded"] == 1
        assert mock_event.reviewed is True
        assert mock_event.notes == "Updated"

    def test_bulk_update_event_not_found(self, client: TestClient, mock_db_session: AsyncMock):
        """Test bulk update with non-existent event."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []

        mock_db_session.execute.return_value = mock_result

        request_data = {"events": [{"id": 999, "reviewed": True}]}

        response = client.patch("/api/events/bulk", json=request_data)

        assert response.status_code == 207
        data = response.json()
        assert data["failed"] == 1
        assert "Event not found" in data["results"][0]["error"]

    def test_bulk_update_commit_failure(self, client: TestClient, mock_db_session: AsyncMock):
        """Test bulk update with commit failure."""
        mock_event = Mock(spec=Event, id=1, reviewed=False, notes=None)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_event]

        mock_db_session.execute.return_value = mock_result
        mock_db_session.commit.side_effect = Exception("Database error")

        request_data = {"events": [{"id": 1, "reviewed": True}]}

        response = client.patch("/api/events/bulk", json=request_data)

        assert response.status_code == 207
        data = response.json()
        assert data["failed"] == 1


# =============================================================================
# Bulk Delete Events Tests (Missing Lines: 1208-1299)
# =============================================================================


class TestBulkDeleteEvents:
    """Tests for bulk_delete_events endpoint."""

    @patch("backend.api.routes.events.get_event_service")
    def test_bulk_delete_soft_delete(
        self, mock_get_service, client: TestClient, mock_db_session: AsyncMock
    ):
        """Test bulk soft delete."""
        mock_service = Mock()
        mock_service.soft_delete_event = AsyncMock()
        mock_get_service.return_value = mock_service

        request_data = {"event_ids": [1, 2], "soft_delete": True}

        response = client.request("DELETE", "/api/events/bulk", json=request_data)

        assert response.status_code == 207
        data = response.json()
        assert data["succeeded"] == 2

    @patch("backend.api.routes.events.get_event_service")
    def test_bulk_delete_hard_delete(
        self, mock_get_service, client: TestClient, mock_db_session: AsyncMock
    ):
        """Test bulk hard delete."""
        mock_service = Mock()
        mock_service.hard_delete_event = AsyncMock(return_value=(5, 0))
        mock_get_service.return_value = mock_service

        # Mock the query to return events
        mock_event = Mock(spec=Event, id=1)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_event
        mock_db_session.execute.return_value = mock_result

        request_data = {"event_ids": [1], "soft_delete": False}

        response = client.request("DELETE", "/api/events/bulk", json=request_data)

        assert response.status_code == 207
        data = response.json()
        assert data["succeeded"] == 1

    @patch("backend.api.routes.events.get_event_service")
    def test_bulk_delete_event_not_found(
        self, mock_get_service, client: TestClient, mock_db_session: AsyncMock
    ):
        """Test bulk delete with non-existent event."""
        mock_service = Mock()
        mock_service.soft_delete_event = AsyncMock(side_effect=ValueError("Event not found: 999"))
        mock_get_service.return_value = mock_service

        request_data = {"event_ids": [999], "soft_delete": True}

        response = client.request("DELETE", "/api/events/bulk", json=request_data)

        assert response.status_code == 207
        data = response.json()
        assert data["failed"] == 1


# =============================================================================
# Update Event Tests (Missing Lines: 1392-1417, 1454)
# =============================================================================


class TestUpdateEvent:
    """Tests for update_event endpoint."""

    @patch("backend.api.routes.events.get_event_or_404")
    @patch("backend.api.routes.events.AuditService.log_action")
    def test_update_event_reviewed_true(
        self, mock_audit, mock_get_event, client: TestClient, mock_db_session: AsyncMock
    ):
        """Test updating event to reviewed=True records metric and audit log."""
        mock_event = Mock(spec=Event)
        mock_event.id = 1
        mock_event.reviewed = False
        mock_event.notes = None
        mock_event.snooze_until = None
        mock_event.detection_ids = "[1, 2]"
        mock_event.detections = []
        # Add all required fields
        mock_event.camera_id = "cam1"
        mock_event.started_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
        mock_event.ended_at = datetime(2025, 1, 1, 12, 5, 0, tzinfo=UTC)
        mock_event.risk_score = 75
        mock_event.risk_level = "high"
        mock_event.summary = "Test"
        mock_event.reasoning = "Test"

        mock_get_event.return_value = mock_event
        mock_audit.return_value = AsyncMock()

        with patch("backend.api.routes.events.record_event_reviewed") as mock_metric:
            response = client.patch("/api/events/1", json={"reviewed": True})

        assert response.status_code == 200
        mock_metric.assert_called_once()

    @patch("backend.api.routes.events.get_event_or_404")
    def test_update_event_snooze_until(
        self, mock_get_event, client: TestClient, mock_db_session: AsyncMock
    ):
        """Test updating event snooze_until field."""
        mock_event = Mock(spec=Event)
        mock_event.id = 1
        mock_event.reviewed = False
        mock_event.notes = None
        mock_event.snooze_until = None
        mock_event.detection_ids = "[1, 2]"
        mock_event.detections = []
        mock_event.camera_id = "cam1"
        mock_event.started_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
        mock_event.ended_at = datetime(2025, 1, 1, 12, 5, 0, tzinfo=UTC)
        mock_event.risk_score = 75
        mock_event.risk_level = "high"
        mock_event.summary = "Test"
        mock_event.reasoning = "Test"

        mock_get_event.return_value = mock_event

        snooze_time = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
        response = client.patch("/api/events/1", json={"snooze_until": snooze_time})

        assert response.status_code == 200


# =============================================================================
# Get Event Enrichments Tests (Missing Lines: 1626-1641)
# =============================================================================


class TestGetEventEnrichments:
    """Tests for get_event_enrichments endpoint."""

    @patch("backend.api.routes.events.get_event_or_404")
    @patch("backend.api.routes.events.batch_fetch_detections")
    def test_get_enrichments_with_pagination(
        self, mock_batch_fetch, mock_get_event, client: TestClient, mock_db_session: AsyncMock
    ):
        """Test get_event_enrichments with pagination."""
        mock_event = Mock(spec=Event)
        mock_event.id = 1
        mock_event.detection_ids = json.dumps(list(range(1, 101)))  # 100 detections
        mock_event.detections = []

        mock_get_event.return_value = mock_event

        # Mock batch fetch
        mock_detections = [
            Mock(
                spec=Detection,
                id=i,
                enrichment_data={"test": "data"},
                detected_at=datetime(2025, 1, 1, 12, i, 0, tzinfo=UTC),
            )
            for i in range(1, 51)
        ]
        mock_batch_fetch.return_value = mock_detections

        response = client.get("/api/events/1/enrichments?limit=50&offset=0")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 50
        assert data["total"] == 100
        assert data["has_more"] is True

    @patch("backend.api.routes.events.get_event_or_404")
    def test_get_enrichments_empty(
        self, mock_get_event, client: TestClient, mock_db_session: AsyncMock
    ):
        """Test get_event_enrichments with no detections."""
        mock_event = Mock(spec=Event)
        mock_event.id = 1
        mock_event.detection_ids = "[]"
        mock_event.detections = []

        mock_get_event.return_value = mock_event

        response = client.get("/api/events/1/enrichments")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert data["total"] == 0
        assert data["has_more"] is False

    @patch("backend.api.routes.events.get_event_or_404")
    def test_get_enrichments_offset_beyond_range(
        self, mock_get_event, client: TestClient, mock_db_session: AsyncMock
    ):
        """Test get_event_enrichments with offset beyond available detections."""
        mock_event = Mock(spec=Event)
        mock_event.id = 1
        mock_event.detection_ids = "[1, 2, 3]"
        mock_event.detections = []

        mock_get_event.return_value = mock_event

        response = client.get("/api/events/1/enrichments?offset=100")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert data["total"] == 3


# =============================================================================
# Get Event Clip Tests (Missing Lines: 1701-1714)
# =============================================================================


class TestGetEventClip:
    """Tests for get_event_clip endpoint."""

    @patch("backend.api.routes.events.get_event_or_404")
    def test_get_clip_no_clip_path(
        self, mock_get_event, client: TestClient, mock_db_session: AsyncMock
    ):
        """Test get_event_clip when event has no clip_path."""
        mock_event = Mock(spec=Event)
        mock_event.id = 1
        mock_event.clip_path = None

        mock_get_event.return_value = mock_event

        response = client.get("/api/events/1/clip")

        assert response.status_code == 200
        data = response.json()
        assert data["clip_available"] is False
        assert data["clip_url"] is None

    @patch("backend.api.routes.events.get_event_or_404")
    @patch("pathlib.Path")
    def test_get_clip_file_not_exists(
        self, mock_path_class, mock_get_event, client: TestClient, mock_db_session: AsyncMock
    ):
        """Test get_event_clip when clip file doesn't exist on disk."""
        mock_event = Mock(spec=Event)
        mock_event.id = 1
        mock_event.clip_path = "/path/to/missing/clip.mp4"

        mock_get_event.return_value = mock_event

        # Mock Path to return non-existent file
        mock_path = Mock()
        mock_path.exists.return_value = False
        mock_path_class.return_value = mock_path

        response = client.get("/api/events/1/clip")

        assert response.status_code == 200
        data = response.json()
        assert data["clip_available"] is False


# =============================================================================
# Generate Event Clip Tests (Missing Lines: 1771-1780, 1798-1855)
# =============================================================================


class TestGenerateEventClip:
    """Tests for generate_event_clip endpoint."""

    @patch("backend.api.routes.events.get_event_or_404")
    @patch("pathlib.Path")
    def test_generate_clip_already_exists_no_force(
        self,
        mock_path_class,
        mock_get_event,
        client: TestClient,
        mock_db_session: AsyncMock,
    ):
        """Test generate_event_clip returns existing clip when force=False."""
        mock_event = Mock(spec=Event)
        mock_event.id = 1
        mock_event.clip_path = "/path/to/clip.mp4"
        mock_event.detection_ids = "[1, 2]"
        mock_event.detections = []

        mock_get_event.return_value = mock_event

        # Mock Path to return existing file
        mock_path = Mock()
        mock_path.exists.return_value = True
        mock_path.name = "clip.mp4"
        mock_stat = Mock()
        mock_stat.st_mtime = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC).timestamp()
        mock_path.stat.return_value = mock_stat
        mock_path_class.return_value = mock_path

        response = client.post("/api/events/1/clip/generate", json={"force": False})

        assert response.status_code == 200  # Existing clip, not creating new
        data = response.json()
        assert data["status"] == "completed"
        assert "already exists" in data["message"].lower()

    @patch("backend.api.routes.events.get_event_or_404")
    @patch("backend.api.routes.events.batch_fetch_file_paths")
    def test_generate_clip_no_detection_images(
        self,
        mock_batch_fetch,
        mock_get_event,
        client: TestClient,
        mock_db_session: AsyncMock,
    ):
        """Test generate_event_clip with no detection images available."""
        mock_event = Mock(spec=Event)
        mock_event.id = 1
        mock_event.clip_path = None
        mock_event.detection_ids = "[1, 2]"
        mock_event.detections = []

        mock_get_event.return_value = mock_event
        mock_batch_fetch.return_value = []  # No file paths

        response = client.post("/api/events/1/clip/generate", json={"force": False})

        assert response.status_code == 400
        assert "no detection images available" in response.json()["detail"].lower()

    @patch("backend.api.routes.events.get_event_or_404")
    def test_generate_clip_no_detections(
        self, mock_get_event, client: TestClient, mock_db_session: AsyncMock
    ):
        """Test generate_event_clip when event has no detections."""
        mock_event = Mock(spec=Event)
        mock_event.id = 1
        mock_event.clip_path = None
        mock_event.detection_ids = "[]"
        mock_event.detections = []

        mock_get_event.return_value = mock_event

        response = client.post("/api/events/1/clip/generate", json={"force": False})

        assert response.status_code == 400
        assert "no detections" in response.json()["detail"].lower()


# =============================================================================
# Analyze Batch Streaming Tests (Missing Lines: 1923-1938)
# =============================================================================


class TestAnalyzeBatchStreaming:
    """Tests for analyze_batch_streaming endpoint."""

    def test_analyze_batch_streaming_invalid_detection_ids(self, client: TestClient):
        """Test analyze_batch_streaming with invalid detection IDs format."""
        from backend.api.dependencies import get_nemotron_analyzer_dep

        # Mock the analyzer dependency to avoid Redis connection
        mock_analyzer = AsyncMock()
        mock_analyzer.analyze_batch_streaming = AsyncMock(return_value=AsyncMock())

        async def override_get_analyzer():
            return mock_analyzer

        client.app.dependency_overrides[get_nemotron_analyzer_dep] = override_get_analyzer
        try:
            # This will be handled by the event_generator (invalid detection_ids parsing)
            response = client.get(
                "/api/events/analyze/batch1/stream?detection_ids=invalid,not_numbers"
            )

            assert response.status_code == 200
            # SSE response, check content type
            assert "text/event-stream" in response.headers["content-type"]
            # Verify error event is returned for invalid detection IDs
            content = response.text
            assert "INVALID_DETECTION_IDS" in content
        finally:
            # Clean up the override
            client.app.dependency_overrides.pop(get_nemotron_analyzer_dep, None)

    def test_analyze_batch_streaming_exception_handling(self, client: TestClient):
        """Test analyze_batch_streaming handles exceptions properly."""
        from backend.api.dependencies import get_nemotron_analyzer_dep

        # Create an async generator that raises an exception
        # Note: yield after raise is required for async generator syntax
        # The _always_raise flag ensures vulture doesn't report unreachable code
        _always_raise = True

        async def mock_streaming_generator(*args, **kwargs):
            if _always_raise:
                raise Exception("Test exception")
            yield {}

        mock_analyzer = Mock()
        mock_analyzer.analyze_batch_streaming = mock_streaming_generator

        async def override_get_analyzer():
            return mock_analyzer

        client.app.dependency_overrides[get_nemotron_analyzer_dep] = override_get_analyzer
        try:
            response = client.get("/api/events/analyze/batch1/stream")

            assert response.status_code == 200
            # Should return error event in SSE format
            content = response.text
            assert "INTERNAL_ERROR" in content
        finally:
            # Clean up the override
            client.app.dependency_overrides.pop(get_nemotron_analyzer_dep, None)


# =============================================================================
# Delete Event Tests (Missing Lines: 1981-2004)
# =============================================================================


class TestDeleteEvent:
    """Tests for delete_event endpoint (soft delete)."""

    @patch("backend.api.routes.events.get_event_service")
    def test_delete_event_success(
        self, mock_get_service, client: TestClient, mock_db_session: AsyncMock
    ):
        """Test successful soft delete."""
        mock_service = Mock()
        mock_service.soft_delete_event = AsyncMock()
        mock_get_service.return_value = mock_service

        response = client.delete("/api/events/1")

        assert response.status_code == 204

    @patch("backend.api.routes.events.get_event_service")
    def test_delete_event_not_found(
        self, mock_get_service, client: TestClient, mock_db_session: AsyncMock
    ):
        """Test delete event that doesn't exist."""
        mock_service = Mock()
        mock_service.soft_delete_event = AsyncMock(side_effect=ValueError("Event not found: 999"))
        mock_get_service.return_value = mock_service

        response = client.delete("/api/events/999")

        assert response.status_code == 404

    @patch("backend.api.routes.events.get_event_service")
    def test_delete_event_already_deleted(
        self, mock_get_service, client: TestClient, mock_db_session: AsyncMock
    ):
        """Test delete event that's already deleted."""
        mock_service = Mock()
        mock_service.soft_delete_event = AsyncMock(
            side_effect=ValueError("Event already deleted: 1")
        )
        mock_get_service.return_value = mock_service

        response = client.delete("/api/events/1")

        assert response.status_code == 409


# =============================================================================
# Restore Event Tests (Missing Lines: 2041-2086)
# =============================================================================


class TestRestoreEvent:
    """Tests for restore_event endpoint."""

    @patch("backend.api.routes.events.get_event_service")
    def test_restore_event_success(
        self, mock_get_service, client: TestClient, mock_db_session: AsyncMock
    ):
        """Test successful event restore."""
        mock_event = Mock(spec=Event)
        mock_event.id = 1
        mock_event.camera_id = "cam1"
        mock_event.started_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
        mock_event.ended_at = datetime(2025, 1, 1, 12, 5, 0, tzinfo=UTC)
        mock_event.risk_score = 75
        mock_event.risk_level = "high"
        mock_event.summary = "Restored event"
        mock_event.reasoning = "Test"
        mock_event.llm_prompt = "Test prompt"
        mock_event.reviewed = False
        mock_event.notes = None
        mock_event.detection_ids = "[1, 2]"
        mock_event.detections = []

        mock_service = Mock()
        mock_service.restore_event = AsyncMock(return_value=mock_event)
        mock_get_service.return_value = mock_service

        response = client.post("/api/events/1/restore")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1

    @patch("backend.api.routes.events.get_event_service")
    def test_restore_event_not_found(
        self, mock_get_service, client: TestClient, mock_db_session: AsyncMock
    ):
        """Test restore event that doesn't exist."""
        mock_service = Mock()
        mock_service.restore_event = AsyncMock(side_effect=ValueError("Event not found: 999"))
        mock_get_service.return_value = mock_service

        response = client.post("/api/events/999/restore")

        assert response.status_code == 404

    @patch("backend.api.routes.events.get_event_service")
    def test_restore_event_not_deleted(
        self, mock_get_service, client: TestClient, mock_db_session: AsyncMock
    ):
        """Test restore event that's not deleted."""
        mock_service = Mock()
        mock_service.restore_event = AsyncMock(side_effect=ValueError("Event not deleted: 1"))
        mock_get_service.return_value = mock_service

        response = client.post("/api/events/1/restore")

        assert response.status_code == 409


# =============================================================================
# Additional Coverage Tests for Missing Lines
# =============================================================================


class TestListEventsFieldValidation:
    """Tests for list_events field validation error paths."""

    def test_list_events_invalid_fields_param(self, client: TestClient, mock_db_session: AsyncMock):
        """Test list_events with invalid fields parameter."""
        response = client.get("/api/events?fields=invalid_field")

        assert response.status_code == 400
        assert "invalid" in response.json()["detail"].lower()


@pytest.mark.integration  # Requires Redis connection
class TestExportEventsFilters:
    """Tests for export_events with various filters."""

    def test_export_events_with_all_filters(self, client: TestClient, mock_db_session: AsyncMock):
        """Test export_events with all filter combinations."""

        # Mock event query result
        mock_event_result = MagicMock()
        mock_event_result.scalars.return_value.all.return_value = []

        # Mock camera query result
        mock_camera_result = MagicMock()
        mock_camera_result.scalars.return_value.all.return_value = []

        mock_db_session.execute.side_effect = [mock_event_result, mock_camera_result]

        response = client.get(
            "/api/events/export?camera_id=cam1&risk_level=high&"
            "start_date=2025-01-01T00:00:00Z&end_date=2025-01-31T23:59:59Z&reviewed=true"
        )

        assert response.status_code == 200

    @patch("backend.api.routes.events.AuditService.log_action")
    def test_export_events_audit_logging_exception(
        self, mock_audit, client: TestClient, mock_db_session: AsyncMock
    ):
        """Test export_events continues when audit logging fails."""

        mock_audit.side_effect = Exception("Audit error")

        # Mock event query result
        mock_event_result = MagicMock()
        mock_event_result.scalars.return_value.all.return_value = []

        # Mock camera query result
        mock_camera_result = MagicMock()
        mock_camera_result.scalars.return_value.all.return_value = []

        mock_db_session.execute.side_effect = [mock_event_result, mock_camera_result]

        response = client.get("/api/events/export")

        # Should still succeed despite audit failure
        assert response.status_code == 200

    def test_export_events_excel_format(self, client: TestClient, mock_db_session: AsyncMock):
        """Test export_events with Excel format via Accept header."""

        # Mock event query result
        mock_event_result = MagicMock()
        mock_event_result.scalars.return_value.all.return_value = []

        # Mock camera query result
        mock_camera_result = MagicMock()
        mock_camera_result.scalars.return_value.all.return_value = []

        mock_db_session.execute.side_effect = [mock_event_result, mock_camera_result]

        response = client.get(
            "/api/events/export",
            headers={"Accept": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
        )

        assert response.status_code == 200


class TestBulkOperationsErrorPaths:
    """Tests for bulk operations error handling."""

    @patch("backend.api.routes.events.get_event_service")
    def test_bulk_create_exception_during_processing(
        self, mock_get_service, client: TestClient, mock_db_session: AsyncMock
    ):
        """Test bulk create handles exceptions during event processing."""
        # Mock camera validation
        mock_camera_result = MagicMock()
        mock_camera_result.all.return_value = [("cam1",)]

        mock_db_session.execute.return_value = mock_camera_result
        mock_db_session.add.side_effect = Exception("Database error")

        request_data = {
            "events": [
                {
                    "batch_id": "batch1",
                    "camera_id": "cam1",
                    "started_at": "2025-01-01T12:00:00Z",
                    "ended_at": "2025-01-01T12:05:00Z",
                    "risk_score": 75,
                    "risk_level": "high",
                    "summary": "Test event",
                    "reasoning": "Test reasoning",
                }
            ]
        }

        response = client.post("/api/events/bulk", json=request_data)

        assert response.status_code == 207
        data = response.json()
        assert data["failed"] == 1

    def test_bulk_create_cache_invalidation_failure(
        self, client: TestClient, mock_db_session: AsyncMock, mock_cache_service: AsyncMock
    ):
        """Test bulk create continues when cache invalidation fails."""
        # Mock camera validation
        mock_camera_result = MagicMock()
        mock_camera_result.all.return_value = [("cam1",)]

        mock_db_session.execute.return_value = mock_camera_result
        mock_cache_service.invalidate_events.side_effect = Exception("Cache error")

        request_data = {
            "events": [
                {
                    "batch_id": "batch1",
                    "camera_id": "cam1",
                    "started_at": "2025-01-01T12:00:00Z",
                    "ended_at": "2025-01-01T12:05:00Z",
                    "risk_score": 75,
                    "risk_level": "high",
                    "summary": "Test event",
                    "reasoning": "Test reasoning",
                }
            ]
        }

        response = client.post("/api/events/bulk", json=request_data)

        # Should succeed despite cache error
        assert response.status_code == 207

    def test_bulk_update_exception_during_processing(
        self, client: TestClient, mock_db_session: AsyncMock
    ):
        """Test bulk update handles exceptions during processing."""
        mock_event = Mock(spec=Event, id=1, reviewed=False, notes=None)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_event]

        mock_db_session.execute.return_value = mock_result

        # Make setting attribute raise exception
        type(mock_event).reviewed = property(
            lambda _: False, lambda _, __: (_ for _ in ()).throw(Exception("Update error"))
        )

        request_data = {"events": [{"id": 1, "reviewed": True}]}

        response = client.patch("/api/events/bulk", json=request_data)

        assert response.status_code == 207
        data = response.json()
        assert data["failed"] == 1

    def test_bulk_update_cache_invalidation_failure(
        self, client: TestClient, mock_db_session: AsyncMock, mock_cache_service: AsyncMock
    ):
        """Test bulk update continues when cache invalidation fails."""
        mock_event = Mock(spec=Event, id=1, reviewed=False, notes=None)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_event]

        mock_db_session.execute.return_value = mock_result
        mock_cache_service.invalidate_events.side_effect = Exception("Cache error")

        request_data = {"events": [{"id": 1, "reviewed": True}]}

        response = client.patch("/api/events/bulk", json=request_data)

        # Should succeed despite cache error
        assert response.status_code == 207

    @patch("backend.api.routes.events.get_event_service")
    def test_bulk_delete_hard_delete_with_file_failures(
        self, mock_get_service, client: TestClient, mock_db_session: AsyncMock
    ):
        """Test bulk hard delete when some files fail to delete."""
        mock_service = Mock()
        # Return (files_deleted=5, files_failed=2)
        mock_service.hard_delete_event = AsyncMock(return_value=(5, 2))
        mock_get_service.return_value = mock_service

        # Mock the query to return event
        mock_event = Mock(spec=Event, id=1)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_event
        mock_db_session.execute.return_value = mock_result

        request_data = {"event_ids": [1], "soft_delete": False}

        response = client.request("DELETE", "/api/events/bulk", json=request_data)

        assert response.status_code == 207
        data = response.json()
        assert data["succeeded"] == 1

    @patch("backend.api.routes.events.get_event_service")
    def test_bulk_delete_hard_delete_event_not_found_after_files(
        self, mock_get_service, client: TestClient, mock_db_session: AsyncMock
    ):
        """Test bulk hard delete when event not found after file deletion."""
        mock_service = Mock()
        mock_service.hard_delete_event = AsyncMock(return_value=(5, 0))
        mock_get_service.return_value = mock_service

        # Mock the query to return None (event not found)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        request_data = {"event_ids": [999], "soft_delete": False}

        response = client.request("DELETE", "/api/events/bulk", json=request_data)

        assert response.status_code == 207
        data = response.json()
        assert data["failed"] == 1

    @patch("backend.api.routes.events.get_event_service")
    def test_bulk_delete_exception_during_processing(
        self, mock_get_service, client: TestClient, mock_db_session: AsyncMock
    ):
        """Test bulk delete handles exceptions during processing."""
        mock_service = Mock()
        mock_service.soft_delete_event = AsyncMock(side_effect=Exception("Delete error"))
        mock_get_service.return_value = mock_service

        request_data = {"event_ids": [1], "soft_delete": True}

        response = client.request("DELETE", "/api/events/bulk", json=request_data)

        assert response.status_code == 207
        data = response.json()
        assert data["failed"] == 1

    @patch("backend.api.routes.events.get_event_service")
    def test_bulk_delete_cache_invalidation_failure(
        self,
        mock_get_service,
        client: TestClient,
        mock_db_session: AsyncMock,
        mock_cache_service: AsyncMock,
    ):
        """Test bulk delete continues when cache invalidation fails."""
        mock_service = Mock()
        mock_service.soft_delete_event = AsyncMock()
        mock_get_service.return_value = mock_service
        mock_cache_service.invalidate_events.side_effect = Exception("Cache error")

        request_data = {"event_ids": [1], "soft_delete": True}

        response = client.request("DELETE", "/api/events/bulk", json=request_data)

        # Should succeed despite cache error
        assert response.status_code == 207


class TestUpdateEventBranches:
    """Tests for update_event conditional branches."""

    @patch("backend.api.routes.events.get_event_or_404")
    @patch("backend.api.routes.events.AuditService.log_action")
    def test_update_event_reviewed_false(
        self, mock_audit, mock_get_event, client: TestClient, mock_db_session: AsyncMock
    ):
        """Test updating event to reviewed=False (dismissed action)."""
        mock_event = Mock(spec=Event)
        mock_event.id = 1
        mock_event.reviewed = True
        mock_event.notes = None
        mock_event.snooze_until = None
        mock_event.detection_ids = "[1, 2]"
        mock_event.detections = []
        mock_event.camera_id = "cam1"
        mock_event.started_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
        mock_event.ended_at = datetime(2025, 1, 1, 12, 5, 0, tzinfo=UTC)
        mock_event.risk_score = 75
        mock_event.risk_level = "high"
        mock_event.summary = "Test"
        mock_event.reasoning = "Test"

        mock_get_event.return_value = mock_event
        mock_audit.return_value = AsyncMock()

        response = client.patch("/api/events/1", json={"reviewed": False})

        assert response.status_code == 200

    @patch("backend.api.routes.events.get_event_or_404")
    @patch("backend.api.routes.events.record_event_reviewed")
    def test_update_event_metric_failure_continues(
        self, mock_metric, mock_get_event, client: TestClient, mock_db_session: AsyncMock
    ):
        """Test update_event continues when metric recording fails."""
        mock_event = Mock(spec=Event)
        mock_event.id = 1
        mock_event.reviewed = False
        mock_event.notes = None
        mock_event.snooze_until = None
        mock_event.detection_ids = "[1, 2]"
        mock_event.detections = []
        mock_event.camera_id = "cam1"
        mock_event.started_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
        mock_event.ended_at = datetime(2025, 1, 1, 12, 5, 0, tzinfo=UTC)
        mock_event.risk_score = 75
        mock_event.risk_level = "high"
        mock_event.summary = "Test"
        mock_event.reasoning = "Test"

        mock_get_event.return_value = mock_event
        mock_metric.side_effect = Exception("Metric error")

        response = client.patch("/api/events/1", json={"reviewed": True})

        # Should succeed despite metric error
        assert response.status_code == 200

    @patch("backend.api.routes.events.get_event_or_404")
    def test_update_event_cache_invalidation_failure(
        self,
        mock_get_event,
        client: TestClient,
        mock_db_session: AsyncMock,
        mock_cache_service: AsyncMock,
    ):
        """Test update_event continues when cache invalidation fails."""
        mock_event = Mock(spec=Event)
        mock_event.id = 1
        mock_event.reviewed = False
        mock_event.notes = None
        mock_event.snooze_until = None
        mock_event.detection_ids = "[1, 2]"
        mock_event.detections = []
        mock_event.camera_id = "cam1"
        mock_event.started_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
        mock_event.ended_at = datetime(2025, 1, 1, 12, 5, 0, tzinfo=UTC)
        mock_event.risk_score = 75
        mock_event.risk_level = "high"
        mock_event.summary = "Test"
        mock_event.reasoning = "Test"

        mock_get_event.return_value = mock_event
        mock_cache_service.invalidate_events.side_effect = Exception("Cache error")

        response = client.patch("/api/events/1", json={"reviewed": True})

        # Should succeed despite cache error
        assert response.status_code == 200


class TestGetEventClipWithFile:
    """Tests for get_event_clip with existing file."""

    @patch("backend.api.routes.events.get_event_or_404")
    @patch("pathlib.Path")
    def test_get_clip_file_exists(
        self, mock_path_class, mock_get_event, client: TestClient, mock_db_session: AsyncMock
    ):
        """Test get_event_clip when clip file exists."""
        mock_event = Mock(spec=Event)
        mock_event.id = 1
        mock_event.clip_path = "/path/to/clip.mp4"
        mock_event.started_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
        mock_event.ended_at = datetime(2025, 1, 1, 12, 5, 0, tzinfo=UTC)

        mock_get_event.return_value = mock_event

        # Mock Path to return existing file
        mock_path = Mock()
        mock_path.exists.return_value = True
        mock_path.name = "clip.mp4"
        mock_stat = Mock()
        mock_stat.st_size = 1024000
        mock_stat.st_mtime = datetime(2025, 1, 1, 13, 0, 0, tzinfo=UTC).timestamp()
        mock_path.stat.return_value = mock_stat
        mock_path_class.return_value = mock_path

        response = client.get("/api/events/1/clip")

        assert response.status_code == 200
        data = response.json()
        assert data["clip_available"] is True
        assert data["clip_url"] == "/api/media/clips/clip.mp4"
        assert data["file_size_bytes"] == 1024000


class TestDeleteRestoreCacheFailures:
    """Tests for delete/restore cache invalidation failures."""

    @patch("backend.api.routes.events.get_event_service")
    def test_delete_event_cache_invalidation_failure(
        self,
        mock_get_service,
        client: TestClient,
        mock_db_session: AsyncMock,
        mock_cache_service: AsyncMock,
    ):
        """Test delete_event continues when cache invalidation fails."""
        mock_service = Mock()
        mock_service.soft_delete_event = AsyncMock()
        mock_get_service.return_value = mock_service
        mock_cache_service.invalidate_events.side_effect = Exception("Cache error")

        response = client.delete("/api/events/1")

        # Should succeed despite cache error
        assert response.status_code == 204

    @patch("backend.api.routes.events.get_event_service")
    def test_restore_event_cache_invalidation_failure(
        self,
        mock_get_service,
        client: TestClient,
        mock_db_session: AsyncMock,
        mock_cache_service: AsyncMock,
    ):
        """Test restore_event continues when cache invalidation fails."""
        mock_event = Mock(spec=Event)
        mock_event.id = 1
        mock_event.camera_id = "cam1"
        mock_event.started_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
        mock_event.ended_at = datetime(2025, 1, 1, 12, 5, 0, tzinfo=UTC)
        mock_event.risk_score = 75
        mock_event.risk_level = "high"
        mock_event.summary = "Restored event"
        mock_event.reasoning = "Test"
        mock_event.llm_prompt = "Test prompt"
        mock_event.reviewed = False
        mock_event.notes = None
        mock_event.detection_ids = "[1, 2]"
        mock_event.detections = []

        mock_service = Mock()
        mock_service.restore_event = AsyncMock(return_value=mock_event)
        mock_get_service.return_value = mock_service
        mock_cache_service.invalidate_events.side_effect = Exception("Cache error")

        response = client.post("/api/events/1/restore")

        # Should succeed despite cache error
        assert response.status_code == 200
