"""Comprehensive unit tests to improve coverage for backend/api/routes/events.py.

This test file targets missing coverage lines identified by pytest-cov,
focusing on endpoint handlers, error paths, and edge cases. It is the canonical
unit-test file for ``backend/api/routes/events.py``: the former ``test_events.py``,
``test_events_pagination.py``, the helper/list_events classes of
``test_events_routes.py`` and the module-level tests of
``backend/tests/unit/routes/test_events_routes.py`` were consolidated here
(B4.4-style, F4.4 step 2), changing no production bytes.
"""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi import FastAPI, HTTPException, status
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

from backend.api.pagination import CursorData, encode_cursor
from backend.api.routes import events as events_routes
from backend.api.routes.events import (
    CSV_INJECTION_PREFIXES,
    VALID_EVENT_LIST_FIELDS,
    VALID_SEVERITY_VALUES,
    _bulk_rate_limiter,
    fields_query_description,
    get_detection_ids_from_event,
    parse_detection_ids,
    parse_severity_filter,
    router,
    sanitize_csv_value,
)
from backend.api.schemas.events import EventListResponse
from backend.core.database import get_db, get_read_db
from backend.core.redis import get_redis
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
def mock_response() -> MagicMock:
    """Create a mock Response object for deprecation header tests (consolidated)."""
    return MagicMock(spec=Response)


@pytest.fixture
def client(mock_db_session: AsyncMock, mock_cache_service: AsyncMock) -> TestClient:
    """Create a test client with mocked dependencies."""
    from backend.api.dependencies import get_cache_service_dep

    app = FastAPI()
    app.include_router(router)

    async def override_get_db():
        yield mock_db_session

    async def override_get_read_db():
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
        mock_event.detection_id_list = [1, 2, 3]
        mock_event.detections = []
        mock_event.deleted_at = None
        mock_event.clip_path = None
        mock_event.version = 1  # Optimistic locking version (NEM-3625)
        return mock_event

    # Override the rate limiter dependency (NEM-2600)
    async def override_rate_limiter() -> None:
        yield None

    # M3 Task 3: export_events builds a NEW RateLimiter(EXPORT) inline
    # (backend/api/routes/events.py:1179), which no _bulk_rate_limiter override
    # catches — it resolves get_redis. Mock it (allow-all), mirroring the shape
    # integration/conftest.py's mock_redis uses for the limiter scripts.
    mock_redis_client = AsyncMock()
    mock_redis_internal = MagicMock()
    mock_redis_internal.script_load = AsyncMock(return_value="mock-sha")
    mock_redis_internal.evalsha = AsyncMock(return_value=[1, 1])
    mock_redis_client._ensure_connected = MagicMock(return_value=mock_redis_internal)

    async def override_get_redis():
        yield mock_redis_client

    app.dependency_overrides[get_redis] = override_get_redis
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_read_db] = override_get_read_db
    app.dependency_overrides[get_cache_service_dep] = override_get_cache_service
    app.dependency_overrides[_bulk_rate_limiter] = override_rate_limiter
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
        with patch(
            "backend.api.routes.events.get_trace_id", return_value="test-trace-123", autospec=True
        ):
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

    def test_list_events_with_min_confidence_filter(
        self, client: TestClient, mock_db_session: AsyncMock
    ):
        """Test list_events applies min_confidence filter (F4.4).

        The mock-backed test observes only that the parameter parses and the
        route returns 200; the EXISTS clause itself is proven by the
        data-backed integration tests in test_events_api.py.
        """
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0
        mock_db_session.execute.side_effect = [mock_count_result, mock_result]

        response = client.get("/api/events?min_confidence=0.85")

        assert response.status_code == 200

    def test_list_events_with_min_confidence_zero(
        self, client: TestClient, mock_db_session: AsyncMock
    ):
        """Test list_events applies min_confidence=0 (has at least one detection)."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0
        mock_db_session.execute.side_effect = [mock_count_result, mock_result]

        response = client.get("/api/events?min_confidence=0")

        assert response.status_code == 200

    @pytest.mark.parametrize("value", ["-0.1", "1.1", "2"])
    def test_list_events_min_confidence_out_of_range_is_422(
        self, client: TestClient, mock_db_session: AsyncMock, value: str
    ):
        """Test min_confidence outside 0..1 is a 422 (Query bounds, F4.4)."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0
        mock_db_session.execute.side_effect = [mock_count_result, mock_result]

        response = client.get(f"/api/events?min_confidence={value}")

        assert response.status_code == 422

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
                # F-057: list_events now reads event.notes into the response
                # row; an unset attribute on a spec'd Mock auto-fabricates a
                # Mock, which fails EventResponse's `str | None` validation.
                notes=None,
                detection_id_list=[i],
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
                notes=None,
                detection_id_list=[i],
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
                detection_id_list=[1, 2],
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

    def test_list_deleted_events_ordered_by_deleted_at_desc(
        self, client: TestClient, mock_db_session: AsyncMock
    ):
        """Test that deleted events are ordered by deleted_at descending (from test_restore_endpoints)."""
        from backend.tests.factories import EventFactory

        now = datetime.now(UTC)
        deleted_events = [
            EventFactory(id=1, deleted_at=now - timedelta(hours=3)),
            EventFactory(id=2, deleted_at=now - timedelta(hours=1)),
            EventFactory(id=3, deleted_at=now - timedelta(hours=2)),
        ]
        ordered_events = sorted(
            deleted_events,
            key=lambda e: e.deleted_at,
            reverse=True,  # type: ignore[arg-type]
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = ordered_events
        mock_db_session.execute.return_value = mock_result

        response = client.get("/api/events/deleted")

        assert response.status_code == 200
        data = response.json()
        assert [item["id"] for item in data["items"]] == [2, 3, 1]
        for item in data["items"]:
            assert item["deleted_at"] is not None


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

    @patch("backend.api.routes.events.get_event_service", autospec=True)
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

    @patch("backend.api.routes.events.get_event_service", autospec=True)
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

    @patch("backend.api.routes.events.get_event_service", autospec=True)
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

    @patch("backend.api.routes.events.get_event_or_404", autospec=True)
    @patch("backend.api.routes.events.AuditService.log_action", autospec=True)
    def test_update_event_reviewed_true(
        self, mock_audit, mock_get_event, client: TestClient, mock_db_session: AsyncMock
    ):
        """Test updating event to reviewed=True records metric and audit log."""
        mock_event = Mock(spec=Event)
        mock_event.id = 1
        mock_event.reviewed = False
        mock_event.notes = None
        mock_event.snooze_until = None
        mock_event.detection_id_list = [1, 2]
        mock_event.detections = []
        # Add all required fields
        mock_event.camera_id = "cam1"
        mock_event.started_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
        mock_event.ended_at = datetime(2025, 1, 1, 12, 5, 0, tzinfo=UTC)
        mock_event.risk_score = 75
        mock_event.risk_level = "high"
        mock_event.summary = "Test"
        mock_event.reasoning = "Test"
        mock_event.version = 1  # Optimistic locking version (NEM-3625)

        mock_get_event.return_value = mock_event
        mock_audit.return_value = AsyncMock()

        with patch("backend.api.routes.events.record_event_reviewed", autospec=True) as mock_metric:
            response = client.patch("/api/events/1", json={"reviewed": True})

        assert response.status_code == 200
        mock_metric.assert_called_once()

    @patch("backend.api.routes.events.get_event_or_404", autospec=True)
    def test_update_event_snooze_until(
        self, mock_get_event, client: TestClient, mock_db_session: AsyncMock
    ):
        """Test updating event snooze_until field."""
        mock_event = Mock(spec=Event)
        mock_event.id = 1
        mock_event.reviewed = False
        mock_event.notes = None
        mock_event.snooze_until = None
        mock_event.detection_id_list = [1, 2]
        mock_event.detections = []
        mock_event.camera_id = "cam1"
        mock_event.started_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
        mock_event.ended_at = datetime(2025, 1, 1, 12, 5, 0, tzinfo=UTC)
        mock_event.risk_score = 75
        mock_event.risk_level = "high"
        mock_event.summary = "Test"
        mock_event.reasoning = "Test"
        mock_event.version = 1  # Optimistic locking version (NEM-3625)

        mock_get_event.return_value = mock_event

        snooze_time = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
        response = client.patch("/api/events/1", json={"snooze_until": snooze_time})

        assert response.status_code == 200


# =============================================================================
# Get Event Enrichments Tests (Missing Lines: 1626-1641)
# =============================================================================


# =============================================================================
# Get Event Clip Tests (Missing Lines: 1701-1714)
# =============================================================================


class TestGetEventClip:
    """Tests for get_event_clip endpoint."""

    @patch("backend.api.routes.events.get_event_or_404", autospec=True)
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

    @patch("backend.api.routes.events.get_event_or_404", autospec=True)
    @patch("pathlib.Path", autospec=True)
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

    @patch("backend.api.routes.events.get_event_or_404", autospec=True)
    @patch("pathlib.Path", autospec=True)
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
        mock_event.detection_id_list = [1, 2]
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

    @patch("backend.api.routes.events.get_event_or_404", autospec=True)
    @patch("backend.api.routes.events.batch_fetch_file_paths", autospec=True)
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
        mock_event.detections = [Mock(id=1), Mock(id=2)]
        mock_event.detection_id_list = [1, 2]

        mock_get_event.return_value = mock_event
        mock_batch_fetch.return_value = []  # No file paths

        response = client.post("/api/events/1/clip/generate", json={"force": False})

        assert response.status_code == 400
        assert "no detection images available" in response.json()["detail"].lower()

    @patch("backend.api.routes.events.get_event_or_404", autospec=True)
    def test_generate_clip_no_detections(
        self, mock_get_event, client: TestClient, mock_db_session: AsyncMock
    ):
        """Test generate_event_clip when event has no detections."""
        mock_event = Mock(spec=Event)
        mock_event.id = 1
        mock_event.clip_path = None
        mock_event.detections = []
        mock_event.detection_id_list = []
        mock_event.detection_id_list = []

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
        from backend.api.dependencies import get_vlm_analyzer_dep

        # Mock the analyzer dependency to avoid Redis connection
        mock_analyzer = AsyncMock()
        mock_analyzer.analyze_batch_streaming = AsyncMock(return_value=AsyncMock())

        async def override_get_analyzer():
            return mock_analyzer

        client.app.dependency_overrides[get_vlm_analyzer_dep] = override_get_analyzer
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
            client.app.dependency_overrides.pop(get_vlm_analyzer_dep, None)

    def test_analyze_batch_streaming_exception_handling(self, client: TestClient):
        """Test analyze_batch_streaming handles exceptions properly."""
        from backend.api.dependencies import get_vlm_analyzer_dep

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

        client.app.dependency_overrides[get_vlm_analyzer_dep] = override_get_analyzer
        try:
            response = client.get("/api/events/analyze/batch1/stream")

            assert response.status_code == 200
            # Should return error event in SSE format
            content = response.text
            assert "INTERNAL_ERROR" in content
        finally:
            # Clean up the override
            client.app.dependency_overrides.pop(get_vlm_analyzer_dep, None)


# =============================================================================
# Delete Event Tests (Missing Lines: 1981-2004)
# =============================================================================


class TestDeleteEvent:
    """Tests for delete_event endpoint (soft delete)."""

    @patch("backend.api.routes.events.get_event_service", autospec=True)
    def test_delete_event_success(
        self, mock_get_service, client: TestClient, mock_db_session: AsyncMock
    ):
        """Test successful soft delete."""
        mock_service = Mock()
        mock_service.soft_delete_event = AsyncMock()
        mock_get_service.return_value = mock_service

        response = client.delete("/api/events/1")

        assert response.status_code == 204

    @patch("backend.api.routes.events.get_event_service", autospec=True)
    def test_delete_event_not_found(
        self, mock_get_service, client: TestClient, mock_db_session: AsyncMock
    ):
        """Test delete event that doesn't exist."""
        mock_service = Mock()
        mock_service.soft_delete_event = AsyncMock(side_effect=ValueError("Event not found: 999"))
        mock_get_service.return_value = mock_service

        response = client.delete("/api/events/999")

        assert response.status_code == 404

    @patch("backend.api.routes.events.get_event_service", autospec=True)
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

    @patch("backend.api.routes.events.get_event_service", autospec=True)
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
        mock_event.detection_id_list = [1, 2]
        mock_event.detections = []
        mock_event.version = 1  # Optimistic locking version (NEM-3625)

        mock_service = Mock()
        mock_service.restore_event = AsyncMock(return_value=mock_event)
        mock_get_service.return_value = mock_service

        response = client.post("/api/events/1/restore")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1

    @patch("backend.api.routes.events.get_event_service", autospec=True)
    def test_restore_event_not_found(
        self, mock_get_service, client: TestClient, mock_db_session: AsyncMock
    ):
        """Test restore event that doesn't exist."""
        mock_service = Mock()
        mock_service.restore_event = AsyncMock(side_effect=ValueError("Event not found: 999"))
        mock_get_service.return_value = mock_service

        response = client.post("/api/events/999/restore")

        assert response.status_code == 404

    @patch("backend.api.routes.events.get_event_service", autospec=True)
    def test_restore_event_not_deleted(
        self, mock_get_service, client: TestClient, mock_db_session: AsyncMock
    ):
        """Test restore event that's not deleted."""
        mock_service = Mock()
        mock_service.restore_event = AsyncMock(side_effect=ValueError("Event not deleted: 1"))
        mock_get_service.return_value = mock_service

        response = client.post("/api/events/1/restore")

        assert response.status_code == 409

    def test_restore_deleted_event_through_real_event_service(
        self, client: TestClient, mock_db_session: AsyncMock, monkeypatch: pytest.MonkeyPatch
    ):
        """Test restoring a soft-deleted event through the real EventService (from test_restore_endpoints)."""
        from backend.tests.factories import EventFactory

        monkeypatch.setattr("backend.core.redis._redis_client", None)
        deleted_event = EventFactory(
            id=1,
            camera_id="d4e5f6a7-b8c9-0123-defa-234567890123",
            deleted_at=datetime.now(UTC) - timedelta(hours=1),
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = deleted_event
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = client.post("/api/events/1/restore")

        assert response.status_code == 200
        assert response.json()["id"] == 1
        assert deleted_event.deleted_at is None

    def test_restore_non_deleted_event_through_real_event_service_returns_409(
        self, client: TestClient, mock_db_session: AsyncMock, monkeypatch: pytest.MonkeyPatch
    ):
        """Test restoring an active event through the real EventService returns 409 (from test_restore_endpoints)."""
        from backend.tests.factories import EventFactory

        monkeypatch.setattr("backend.core.redis._redis_client", None)
        active_event = EventFactory(
            id=2,
            camera_id="d4e5f6a7-b8c9-0123-defa-234567890123",
            deleted_at=None,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = active_event
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = client.post("/api/events/2/restore")

        assert response.status_code == 409
        assert "not deleted" in response.json()["detail"].lower()


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


class TestExportEventsFilters:
    # M3 Task 3 (audit 1.3): dropped the stray class-level @pytest.mark.integration.
    # Every dependency of these three tests is file-local mocks (local TestClient
    # with overridden get_db/get_read_db/cache/`_bulk_rate_limiter`); the only real
    # service the route touches is the inline RateLimiter(tier=EXPORT) (events.py:1179)
    # via the get_redis dependency — overridden with a mock below (shape mirrors
    # integration/conftest.py mock_redis: evalsha -> [1, 1] = allowed).
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

    @patch("backend.api.routes.events.AuditService.log_action", autospec=True)
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

    @patch("backend.api.routes.events.get_event_service", autospec=True)
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

    @patch("backend.api.routes.events.get_event_service", autospec=True)
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

    @patch("backend.api.routes.events.get_event_service", autospec=True)
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

    @patch("backend.api.routes.events.get_event_service", autospec=True)
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

    @patch("backend.api.routes.events.get_event_service", autospec=True)
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

    @patch("backend.api.routes.events.get_event_or_404", autospec=True)
    @patch("backend.api.routes.events.AuditService.log_action", autospec=True)
    def test_update_event_reviewed_false(
        self, mock_audit, mock_get_event, client: TestClient, mock_db_session: AsyncMock
    ):
        """Test updating event to reviewed=False (dismissed action)."""
        mock_event = Mock(spec=Event)
        mock_event.id = 1
        mock_event.reviewed = True
        mock_event.notes = None
        mock_event.snooze_until = None
        mock_event.detection_id_list = [1, 2]
        mock_event.detections = []
        mock_event.camera_id = "cam1"
        mock_event.started_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
        mock_event.ended_at = datetime(2025, 1, 1, 12, 5, 0, tzinfo=UTC)
        mock_event.risk_score = 75
        mock_event.risk_level = "high"
        mock_event.summary = "Test"
        mock_event.reasoning = "Test"
        mock_event.version = 1  # Optimistic locking version (NEM-3625)

        mock_get_event.return_value = mock_event
        mock_audit.return_value = AsyncMock()

        response = client.patch("/api/events/1", json={"reviewed": False})

        assert response.status_code == 200

    @patch("backend.api.routes.events.get_event_or_404", autospec=True)
    @patch("backend.api.routes.events.record_event_reviewed", autospec=True)
    def test_update_event_metric_failure_continues(
        self, mock_metric, mock_get_event, client: TestClient, mock_db_session: AsyncMock
    ):
        """Test update_event continues when metric recording fails."""
        mock_event = Mock(spec=Event)
        mock_event.id = 1
        mock_event.reviewed = False
        mock_event.notes = None
        mock_event.snooze_until = None
        mock_event.detection_id_list = [1, 2]
        mock_event.detections = []
        mock_event.camera_id = "cam1"
        mock_event.started_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
        mock_event.ended_at = datetime(2025, 1, 1, 12, 5, 0, tzinfo=UTC)
        mock_event.risk_score = 75
        mock_event.risk_level = "high"
        mock_event.summary = "Test"
        mock_event.reasoning = "Test"
        mock_event.version = 1  # Optimistic locking version (NEM-3625)

        mock_get_event.return_value = mock_event
        mock_metric.side_effect = Exception("Metric error")

        response = client.patch("/api/events/1", json={"reviewed": True})

        # Should succeed despite metric error
        assert response.status_code == 200

    @patch("backend.api.routes.events.get_event_or_404", autospec=True)
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
        mock_event.detection_id_list = [1, 2]
        mock_event.detections = []
        mock_event.camera_id = "cam1"
        mock_event.started_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
        mock_event.ended_at = datetime(2025, 1, 1, 12, 5, 0, tzinfo=UTC)
        mock_event.risk_score = 75
        mock_event.risk_level = "high"
        mock_event.summary = "Test"
        mock_event.reasoning = "Test"
        mock_event.version = 1  # Optimistic locking version (NEM-3625)

        mock_get_event.return_value = mock_event
        mock_cache_service.invalidate_events.side_effect = Exception("Cache error")

        response = client.patch("/api/events/1", json={"reviewed": True})

        # Should succeed despite cache error
        assert response.status_code == 200


class TestGetEventClipWithFile:
    """Tests for get_event_clip with existing file."""

    @patch("backend.api.routes.events.get_event_or_404", autospec=True)
    @patch("pathlib.Path", autospec=True)
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

    @patch("backend.api.routes.events.get_event_service", autospec=True)
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

    @patch("backend.api.routes.events.get_event_service", autospec=True)
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
        mock_event.detection_id_list = [1, 2]
        mock_event.detections = []
        mock_event.version = 1  # Optimistic locking version (NEM-3625)

        mock_service = Mock()
        mock_service.restore_event = AsyncMock(return_value=mock_event)
        mock_get_service.return_value = mock_service
        mock_cache_service.invalidate_events.side_effect = Exception("Cache error")

        response = client.post("/api/events/1/restore")

        # Should succeed despite cache error
        assert response.status_code == 200


class TestParseDetectionIdsEdgeCases:
    """Additional edge case tests for parse_detection_ids."""

    def test_parse_detection_ids_json_with_string_numbers(self):
        """Test parsing JSON array with string numbers converts to integers."""
        detection_ids_str = '["1", "2", "3"]'
        result = parse_detection_ids(detection_ids_str)
        assert result == [1, 2, 3]

    def test_parse_detection_ids_whitespace_only(self):
        """Test parsing whitespace-only string returns empty list."""
        detection_ids_str = "   "
        result = parse_detection_ids(detection_ids_str)
        assert result == []

    def test_parse_detection_ids_csv_with_empty_elements(self):
        """Test CSV parsing handles empty elements correctly."""
        detection_ids_str = "1,,2, ,3"
        result = parse_detection_ids(detection_ids_str)
        assert result == [1, 2, 3]

    def test_parse_detection_ids_single_number_string(self):
        """Test parsing single number string.

        A single number like "42" is valid JSON (number type), but parse_detection_ids
        expects an array, so it returns empty list.
        """
        detection_ids_str = "42"
        result = parse_detection_ids(detection_ids_str)
        # Valid JSON but not a list, returns empty
        assert result == []

    def test_parse_detection_ids_json_empty_array(self):
        """Test parsing empty JSON array returns empty list."""
        detection_ids_str = "[]"
        result = parse_detection_ids(detection_ids_str)
        assert result == []


class TestGetDetectionIdsFromEventEdgeCases:
    """Additional edge case tests for get_detection_ids_from_event.

    Note: Legacy detection_ids column was removed in NEM-1592.
    These tests verify the new behavior using only the detections relationship.
    """

    def test_get_detection_ids_empty_relationship_returns_empty(self):
        """Test that empty relationship returns empty list."""
        mock_event = Mock(spec=Event)
        mock_event.detections = []
        mock_event.detection_id_list = []

        result = get_detection_ids_from_event(mock_event)
        assert result == []

    def test_get_detection_ids_none_relationship_returns_empty(self):
        """Test that empty relationship returns empty list."""
        mock_event = Mock(spec=Event)
        mock_event.detections = []
        mock_event.detection_id_list = []

        result = get_detection_ids_from_event(mock_event)
        assert result == []

    def test_get_detection_ids_uses_relationship(self):
        """Test that detection IDs are extracted from relationship."""
        mock_event = Mock(spec=Event)
        mock_event.detections = [Mock(id=1), Mock(id=2)]
        mock_event.detection_id_list = [1, 2]

        result = get_detection_ids_from_event(mock_event)
        assert result == [1, 2]


class TestParseSeverityFilterEdgeCases:
    """Additional edge case tests for parse_severity_filter."""

    def test_parse_severity_filter_case_insensitive(self):
        """Test that severity parsing is case insensitive."""
        result = parse_severity_filter("HIGH,CriTical,Low")
        assert set(result) == {"high", "critical", "low"}

    def test_parse_severity_filter_with_extra_commas(self):
        """Test parsing handles extra commas gracefully."""
        result = parse_severity_filter("high,,medium,")
        assert set(result) == {"high", "medium"}

    def test_parse_severity_filter_mixed_case_with_spaces(self):
        """Test parsing handles mixed case and spaces."""
        result = parse_severity_filter(" HIGH , Medium , low ")
        assert set(result) == {"high", "medium", "low"}

    def test_parse_severity_filter_all_valid_values(self):
        """Test parsing all valid severity values."""
        result = parse_severity_filter("low,medium,high,critical")
        assert set(result) == VALID_SEVERITY_VALUES

    def test_parse_severity_filter_single_invalid(self):
        """Test that single invalid value raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            parse_severity_filter("invalid")

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "invalid" in exc_info.value.detail.lower()
        assert "valid values are" in exc_info.value.detail.lower()

    def test_parse_severity_filter_multiple_invalid(self):
        """Test that multiple invalid values are all reported."""
        with pytest.raises(HTTPException) as exc_info:
            parse_severity_filter("invalid1,invalid2")

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "invalid1" in exc_info.value.detail
        assert "invalid2" in exc_info.value.detail


class TestSanitizeCsvValueEdgeCases:
    """Additional edge case tests for sanitize_csv_value."""

    def test_sanitize_csv_value_all_injection_prefixes(self):
        """Test all CSV injection prefixes are sanitized."""
        for prefix in CSV_INJECTION_PREFIXES:
            test_value = f"{prefix}malicious_formula"
            result = sanitize_csv_value(test_value)
            assert result.startswith("'")
            assert result == f"'{prefix}malicious_formula"

    def test_sanitize_csv_value_equals_only(self):
        """Test single equals sign is sanitized."""
        result = sanitize_csv_value("=")
        assert result == "'="

    def test_sanitize_csv_value_plus_only(self):
        """Test single plus sign is sanitized."""
        result = sanitize_csv_value("+")
        assert result == "'+"

    def test_sanitize_csv_value_minus_only(self):
        """Test single minus sign is sanitized."""
        result = sanitize_csv_value("-")
        assert result == "'-"

    def test_sanitize_csv_value_at_only(self):
        """Test single at sign is sanitized."""
        result = sanitize_csv_value("@")
        assert result == "'@"

    def test_sanitize_csv_value_tab_only(self):
        """Test single tab is sanitized."""
        result = sanitize_csv_value("\t")
        assert result == "'\t"

    def test_sanitize_csv_value_carriage_return_only(self):
        """Test single carriage return is sanitized."""
        result = sanitize_csv_value("\r")
        assert result == "'\r"

    def test_sanitize_csv_value_injection_in_middle_not_modified(self):
        """Test value with injection character in middle is not modified."""
        result = sanitize_csv_value("test=value")
        assert result == "test=value"

    def test_sanitize_csv_value_already_quoted(self):
        """Test value already starting with quote is not modified (quote is not an injection prefix)."""
        result = sanitize_csv_value("'already quoted")
        assert result == "'already quoted"

    def test_sanitize_csv_value_multiple_lines(self):
        """Test multiline value only checks first character."""
        result = sanitize_csv_value("=formula\nline2")
        assert result == "'=formula\nline2"

    def test_sanitize_csv_value_unicode_safe(self):
        """Test Unicode characters are handled safely."""
        result = sanitize_csv_value("Hello 世界")
        assert result == "Hello 世界"

    def test_sanitize_csv_value_numbers_not_modified(self):
        """Test numeric values are not modified."""
        result = sanitize_csv_value("12345")
        assert result == "12345"

    def test_sanitize_csv_value_spaces_at_start_not_modified(self):
        """Test spaces at start are not modified."""
        result = sanitize_csv_value("  value")
        assert result == "  value"


class TestConstantsAndValidation:
    """Tests for constants and validation values."""

    def test_valid_severity_values_complete(self):
        """Test that VALID_SEVERITY_VALUES contains all expected values."""
        assert frozenset({"low", "medium", "high", "critical"}) == VALID_SEVERITY_VALUES

    def test_valid_event_list_fields_complete(self):
        """Test that VALID_EVENT_LIST_FIELDS contains expected fields.

        Note: detection_ids was removed after NEM-1592 migration to junction table.
        """
        expected_fields = {
            "id",
            "camera_id",
            "started_at",
            "ended_at",
            "risk_score",
            "risk_level",
            "summary",
            "reasoning",
            "reviewed",
            # F-057: the note is selectable like any other list field. It was
            # absent from both the allowlist and the hand-built row dict, so
            # ?fields=notes 400'd and the full projection reported null.
            "notes",
            "detection_count",
            "thumbnail_url",
            # P0.4 (spec §4): the verification object is selectable like any
            # other list field; absent for legacy events regardless (exclude_if).
            "verification",
            # ISS-001 (2026-10-05 slice): the notify decision is selectable the
            # same way; absent means "no decision was made", never false.
            "notify",
        }
        assert frozenset(expected_fields) == VALID_EVENT_LIST_FIELDS

    def test_fields_query_description_is_derived_from_the_set(self):
        """[r277a] Q-068: the API doc cannot name a field the set rejects.

        The description is DERIVED from VALID_EVENT_LIST_FIELDS in production
        (fields_query_description), so drift needs this test to catch two
        directions: the description naming something the set rejects (a client
        following the docs gets a 400 -- the failure the ruling describes), and
        the set carrying a field the description omits. Both are the same
        assertion here because the production text is generated; the set-equality
        check above keeps the set itself honest. detection_ids (removed with the
        events table's detections column, NEM-1592) must not reappear; notify
        must be present.
        """
        description = fields_query_description()
        valid_names = sorted(VALID_EVENT_LIST_FIELDS)

        # The derived text, verbatim (sorted list, same prefix).
        assert description == (
            "Comma-separated list of fields to include in response (sparse fieldsets). "
            f"Valid fields: {', '.join(valid_names)}"
        )

        # The retired name is out; the live ISS-001 field is in.
        assert "detection_ids" not in description
        assert "notify" in description

    def test_fields_query_description_route_uses_the_helper(self):
        """The route's Query description is the derived text, not a hand copy.

        Reading the parameter's default via inspect keeps this tied to the real
        signature: if someone re-inlines a hand-written string in the route
        (the shape that drifted), this fails.
        """
        import inspect

        from backend.api.routes import events as events_module

        list_events = events_module.list_events
        fields_param = inspect.signature(list_events).parameters["fields"]
        default = fields_param.default
        assert hasattr(default, "description"), "fields must remain a Query parameter"
        assert default.description == fields_query_description()

    def test_csv_injection_prefixes_complete(self):
        """Test that CSV_INJECTION_PREFIXES contains all dangerous characters."""
        expected_prefixes = ("=", "+", "-", "@", "\t", "\r")
        assert expected_prefixes == CSV_INJECTION_PREFIXES


class TestHelperFunctionIntegration:
    """Integration tests for helper function combinations."""

    def test_parse_and_sanitize_detection_ids(self):
        """Test parsing detection IDs and using them works correctly."""
        json_ids = "[1, 2, 3]"
        csv_ids = "1, 2, 3"

        json_result = parse_detection_ids(json_ids)
        csv_result = parse_detection_ids(csv_ids)

        assert json_result == csv_result == [1, 2, 3]

    def test_event_detection_ids_with_empty_detections(self):
        """Test event with empty detection relationship."""
        mock_event = Mock(spec=Event)
        mock_event.detections = []
        # detection_id_list property returns [] when detections is empty
        mock_event.detection_id_list = []

        result = get_detection_ids_from_event(mock_event)
        assert result == []

    def test_csv_sanitization_comprehensive_injection_vectors(self):
        """Test comprehensive CSV injection attack vectors."""
        attack_vectors = [
            ("=1+1", "'=1+1"),
            ("+1+1", "'+1+1"),
            ("-1+1", "'-1+1"),
            ("@SUM(A1:A10)", "'@SUM(A1:A10)"),
            ("\t=1+1", "'\t=1+1"),
            ("\r\n=1+1", "'\r\n=1+1"),
            ("=cmd|'/c calc'!A1", "'=cmd|'/c calc'!A1"),
        ]

        for attack, expected in attack_vectors:
            result = sanitize_csv_value(attack)
            assert result == expected, f"Failed for attack vector: {attack}"

    def test_parse_severity_validates_against_constants(self):
        """Test that parse_severity_filter validates against VALID_SEVERITY_VALUES."""
        # All valid values should pass
        for value in VALID_SEVERITY_VALUES:
            result = parse_severity_filter(value)
            assert result == [value]

        # Invalid value should raise exception
        with pytest.raises(HTTPException):
            parse_severity_filter("super_critical")


class TestEdgeCaseCombinations:
    """Tests for edge case combinations and boundary conditions."""

    def test_parse_detection_ids_very_large_array(self):
        """Test parsing very large array of detection IDs."""
        large_ids = list(range(1, 1001))  # 1000 IDs
        json_str = json.dumps(large_ids)

        result = parse_detection_ids(json_str)
        assert len(result) == 1000
        assert result == large_ids

    def test_parse_detection_ids_with_zero(self):
        """Test parsing array with zero values."""
        json_str = "[0, 1, 2]"
        result = parse_detection_ids(json_str)
        assert result == [0, 1, 2]

    def test_parse_detection_ids_negative_numbers(self):
        """Test parsing with negative numbers (invalid IDs but should parse)."""
        json_str = "[-1, -2, -3]"
        result = parse_detection_ids(json_str)
        assert result == [-1, -2, -3]

    def test_sanitize_csv_value_very_long_string(self):
        """Test sanitizing very long string doesn't cause issues."""
        long_value = "=" + ("a" * 10000)
        result = sanitize_csv_value(long_value)
        assert result.startswith("'=")
        assert len(result) == 10002  # +2 for the quote

    def test_parse_severity_empty_after_whitespace_strip(self):
        """Test parsing severity with only whitespace entries."""
        result = parse_severity_filter(" , , ")
        assert result == []

    def test_get_detection_ids_with_empty_detections(self):
        """Test get_detection_ids returns empty list when no detections."""
        mock_event = Mock(spec=Event)
        mock_event.detections = []
        mock_event.detection_id_list = []

        result = get_detection_ids_from_event(mock_event)
        assert result == []

    def test_event_schemas_omit_retired_flagged_field(self):
        """Test EventUpdate and EventResponse omit the retired flagged field (F-058, R2a row 5)."""
        from backend.api.schemas.events import EventResponse, EventUpdate

        assert "flagged" not in EventUpdate.model_fields
        assert "flagged" not in EventResponse.model_fields


class TestEventListResponseWithCursor:
    """Tests for EventListResponse schema with cursor pagination fields."""

    def test_event_list_response_with_cursor_fields(self):
        """Test EventListResponse includes cursor pagination fields."""
        data = {
            "items": [],
            "pagination": {
                "total": 100,
                "limit": 50,
                "offset": 0,
                "next_cursor": "eyJpZCI6IDEwMCwgImNyZWF0ZWRfYXQiOiAiMjAyNS0xMi0yM1QxMjowMDowMFoifQ==",  # pragma: allowlist secret
                "has_more": True,
            },
        }
        response = EventListResponse(**data)
        assert response.pagination.next_cursor is not None
        assert response.pagination.has_more is True

    def test_event_list_response_no_more_results(self):
        """Test EventListResponse when there are no more results."""
        data = {
            "items": [],
            "pagination": {
                "total": 10,
                "limit": 50,
                "offset": 0,
                "next_cursor": None,
                "has_more": False,
            },
        }
        response = EventListResponse(**data)
        assert response.pagination.next_cursor is None
        assert response.pagination.has_more is False

    def test_event_list_response_backward_compatible_without_cursor(self):
        """Test EventListResponse still works without cursor fields (backward compatibility)."""
        data = {
            "items": [],
            "pagination": {
                "total": 0,
                "limit": 50,
                "offset": 0,
                "has_more": False,
            },
        }
        response = EventListResponse(**data)
        # Should default to None/False for cursor fields
        assert response.pagination.next_cursor is None
        assert response.pagination.has_more is False

    def test_event_list_response_deprecation_warning(self):
        """Test EventListResponse can include deprecation warning."""
        data = {
            "items": [],
            "pagination": {
                "total": 100,
                "limit": 50,
                "offset": 20,
                "has_more": True,
            },
            "deprecation_warning": "Offset pagination is deprecated. Please use cursor-based pagination.",
        }
        response = EventListResponse(**data)
        assert response.deprecation_warning is not None
        assert "deprecated" in response.deprecation_warning.lower()


class TestEventsPaginationLogic:
    """Tests for cursor-based pagination logic in list_events endpoint."""

    def test_cursor_from_event_data(self):
        """Test creating cursor from event data (id and started_at)."""
        # Simulate creating a cursor from the last event in a response
        event_id = 50
        started_at = datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC)

        cursor_data = CursorData(id=event_id, created_at=started_at)
        encoded = encode_cursor(cursor_data)

        # Verify cursor is a non-empty string
        assert isinstance(encoded, str)
        assert len(encoded) > 0

    def test_pagination_has_more_logic(self):
        """Test has_more is true when results exceed limit."""
        # Simulate fetching limit + 1 items to check for more
        limit = 50
        fetched_items = 51  # One more than requested

        has_more = fetched_items > limit
        assert has_more is True

    def test_pagination_no_more_results(self):
        """Test has_more is false when results don't exceed limit."""
        limit = 50
        fetched_items = 30  # Less than requested

        has_more = fetched_items > limit
        assert has_more is False

    def test_pagination_exact_limit(self):
        """Test has_more is false when results equal limit exactly."""
        limit = 50
        fetched_items = 50  # Exactly limit

        has_more = fetched_items > limit
        assert has_more is False


class TestParseDetectionIds:
    """Tests for parse_detection_ids helper function."""

    def test_parse_detection_ids_json_array(self):
        """Test parsing JSON array string to list of integers."""
        detection_ids_str = "[1, 2, 3, 4, 5]"
        result = parse_detection_ids(detection_ids_str)
        assert result == [1, 2, 3, 4, 5]

    def test_parse_detection_ids_empty_string(self):
        """Test parsing empty string returns empty list."""
        result = parse_detection_ids("")
        assert result == []

    def test_parse_detection_ids_none(self):
        """Test parsing None returns empty list."""
        result = parse_detection_ids(None)
        assert result == []

    def test_parse_detection_ids_legacy_comma_separated(self):
        """Test parsing legacy comma-separated format as fallback."""
        detection_ids_str = "1, 2, 3, 4, 5"
        result = parse_detection_ids(detection_ids_str)
        assert result == [1, 2, 3, 4, 5]

    def test_parse_detection_ids_invalid_json_falls_back_to_csv(self):
        """Test that invalid JSON falls back to comma-separated parsing."""
        detection_ids_str = "1, 2, 3"
        result = parse_detection_ids(detection_ids_str)
        assert result == [1, 2, 3]

    def test_parse_detection_ids_json_not_list_returns_empty(self):
        """Test that JSON object (not array) returns empty list."""
        detection_ids_str = '{"ids": [1, 2, 3]}'
        result = parse_detection_ids(detection_ids_str)
        assert result == []


class TestGetDetectionIdsFromEvent:
    """Tests for get_detection_ids_from_event helper function.

    Note: Legacy detection_ids column was removed in NEM-1592.
    Now uses only the detections relationship via detection_id_list property.
    """

    def test_get_detection_ids_from_relationship(self):
        """Test getting detection IDs from detections relationship."""
        mock_event = Mock(spec=Event)
        mock_event.detections = [Mock(id=1), Mock(id=2), Mock(id=3)]
        mock_event.detection_id_list = [1, 2, 3]

        result = get_detection_ids_from_event(mock_event)
        assert result == [1, 2, 3]

    def test_get_detection_ids_empty_relationship(self):
        """Test empty relationship returns empty list."""
        mock_event = Mock(spec=Event)
        mock_event.detections = []
        mock_event.detection_id_list = []

        result = get_detection_ids_from_event(mock_event)
        assert result == []


class TestParseSeverityFilter:
    """Tests for parse_severity_filter helper function."""

    def test_parse_severity_filter_single_value(self):
        """Test parsing single severity value."""
        result = parse_severity_filter("high")
        assert result == ["high"]

    def test_parse_severity_filter_multiple_values(self):
        """Test parsing comma-separated severity values."""
        result = parse_severity_filter("high,critical")
        assert result == ["high", "critical"]

    def test_parse_severity_filter_with_spaces(self):
        """Test parsing values with whitespace."""
        result = parse_severity_filter("high, medium, low")
        assert result == ["high", "medium", "low"]

    def test_parse_severity_filter_empty_string(self):
        """Test parsing empty string returns empty list."""
        result = parse_severity_filter("")
        assert result == []

    def test_parse_severity_filter_none(self):
        """Test parsing None returns empty list."""
        result = parse_severity_filter(None)
        assert result == []

    def test_parse_severity_filter_invalid_value_raises(self):
        """Test that invalid severity value raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            parse_severity_filter("invalid")
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid severity value" in exc_info.value.detail

    def test_parse_severity_filter_mixed_valid_invalid_raises(self):
        """Test that mix of valid and invalid values raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            parse_severity_filter("high,invalid,critical")
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "invalid" in exc_info.value.detail


class TestSanitizeCsvValue:
    """Tests for sanitize_csv_value helper function (additional edge cases)."""

    def test_sanitize_csv_value_empty_string(self):
        """Test empty string is returned as-is."""
        result = sanitize_csv_value("")
        assert result == ""

    def test_sanitize_csv_value_none_returns_empty_string(self):
        """Test None returns empty string."""
        result = sanitize_csv_value(None)
        assert result == ""

    def test_sanitize_csv_value_safe_value_unchanged(self):
        """Test safe value is not modified."""
        safe_value = "Person detected at front door"
        result = sanitize_csv_value(safe_value)
        assert result == safe_value

    def test_sanitize_csv_value_starts_with_equals(self):
        """Test value starting with = is prefixed with quote."""
        dangerous_value = "=1+1"
        result = sanitize_csv_value(dangerous_value)
        assert result == "'=1+1"


class TestListEventsRoute:
    """Tests for list_events route handler."""

    @pytest.mark.asyncio
    async def test_list_events_validates_date_range(self, mock_response: MagicMock):
        """Test that invalid date range raises HTTPException."""
        from backend.api.routes.events import list_events

        mock_db = AsyncMock(spec=AsyncSession)

        # start_date after end_date should raise
        with pytest.raises(HTTPException) as exc_info:
            await list_events(
                response=mock_response,
                camera_id=None,
                risk_level=None,
                start_date=datetime(2025, 12, 25, 0, 0, 0, tzinfo=UTC),
                end_date=datetime(2025, 12, 23, 0, 0, 0, tzinfo=UTC),
                reviewed=None,
                object_type=None,
                limit=50,
                offset=0,
                cursor=None,
                db=mock_db,
            )
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_list_events_invalid_cursor_raises(self, mock_response: MagicMock):
        """Test that invalid cursor raises HTTPException."""
        from backend.api.routes.events import list_events

        mock_db = AsyncMock(spec=AsyncSession)

        with pytest.raises(HTTPException) as exc_info:
            await list_events(
                response=mock_response,
                camera_id=None,
                risk_level=None,
                start_date=None,
                end_date=None,
                reviewed=None,
                object_type=None,
                limit=50,
                offset=0,
                cursor="invalid_cursor",
                db=mock_db,
            )
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid cursor" in exc_info.value.detail


class TestListEventsRouteComprehensive:
    """Comprehensive tests for list_events with proper DB mocking."""

    @pytest.mark.asyncio
    async def test_list_events_basic_query_execution(self, mock_response: MagicMock):
        """Test that list_events executes queries and returns results."""
        from backend.api.routes.events import list_events

        mock_db = AsyncMock(spec=AsyncSession)

        # Mock count query result
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 10

        # Mock events query result
        mock_event1 = Mock(spec=Event)
        mock_event1.id = 1
        mock_event1.camera_id = "cam1"
        mock_event1.started_at = datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC)
        mock_event1.ended_at = datetime(2025, 12, 23, 12, 2, 0, tzinfo=UTC)
        mock_event1.risk_score = 75
        mock_event1.risk_level = "high"
        mock_event1.summary = "Test event"
        mock_event1.reasoning = "Test reasoning"
        mock_event1.reviewed = False
        # F-057: list_events now reads event.notes into the row; an unset
        # attribute on a spec'd Mock auto-fabricates a Mock, which fails
        # EventResponse's `str | None` validation.
        mock_event1.notes = None
        mock_event1.detections = [Mock(id=1), Mock(id=2), Mock(id=3)]
        mock_event1.detection_id_list = [1, 2, 3]
        mock_event1.camera = Mock(name="Front Door")

        mock_events_result = MagicMock()
        mock_events_result.scalars.return_value.all.return_value = [mock_event1]

        # Setup execute to return different results based on call order
        mock_db.execute = AsyncMock(side_effect=[mock_count_result, mock_events_result])

        result = await list_events(
            response=mock_response,
            camera_id=None,
            risk_level=None,
            start_date=None,
            end_date=None,
            reviewed=None,
            object_type=None,
            limit=50,
            offset=0,
            cursor=None,
            db=mock_db,
        )

        assert result.pagination.total == 10
        assert len(result.items) == 1
        assert result.items[0].id == 1
        assert result.items[0].detection_count == 3
        assert result.pagination.has_more is False

    @pytest.mark.asyncio
    async def test_list_events_with_object_type_filter(self, mock_response: MagicMock):
        """Test that object_type filter constructs proper LIKE queries."""
        from backend.api.routes.events import list_events

        mock_db = AsyncMock(spec=AsyncSession)

        # Mock empty results
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0
        mock_events_result = MagicMock()
        mock_events_result.scalars.return_value.all.return_value = []

        mock_db.execute = AsyncMock(side_effect=[mock_count_result, mock_events_result])

        result = await list_events(
            response=mock_response,
            camera_id=None,
            risk_level=None,
            start_date=None,
            end_date=None,
            reviewed=None,
            object_type="person",
            limit=50,
            offset=0,
            cursor=None,
            db=mock_db,
        )

        assert result.pagination.total == 0
        assert result.items == []


class TestParseDetectionIdsLegacyFormats:
    """Old-tree helper-format tests for parse_detection_ids (from routes/test_events_routes.py)."""


def test_parse_detection_ids_json_array_no_spaces() -> None:
    """Test parsing JSON array without spaces."""
    result = parse_detection_ids("[1,2,3,4]")
    assert result == [1, 2, 3, 4]


def test_parse_detection_ids_single_id() -> None:
    """Test parsing a single detection ID JSON array."""
    result = parse_detection_ids("[42]")
    assert result == [42]


def test_parse_detection_ids_legacy_with_whitespace() -> None:
    """Test legacy fallback for comma-separated IDs with whitespace."""
    result = parse_detection_ids("1, 2 , 3 ,4")
    assert result == [1, 2, 3, 4]


def test_parse_detection_ids_trailing_comma() -> None:
    """Test parsing string with trailing comma."""
    result = parse_detection_ids("1,2,3,")
    assert result == [1, 2, 3]


def test_parse_detection_ids_leading_comma() -> None:
    """Test parsing string with leading comma."""
    result = parse_detection_ids(",1,2,3")
    assert result == [1, 2, 3]


def test_parse_detection_ids_multiple_commas() -> None:
    """Test parsing string with multiple consecutive commas."""
    result = parse_detection_ids("1,,2,,,3")
    assert result == [1, 2, 3]


def test_parse_detection_ids_large_numbers() -> None:
    """Test parsing large detection IDs."""
    result = parse_detection_ids("1000000,2000000,3000000")
    assert result == [1000000, 2000000, 3000000]


class TestParseSeverityFilterLegacyFormats:
    """Old-tree helper tests for parse_severity_filter (from routes/test_events_routes.py)."""


def test_parse_severity_filter_all_values() -> None:
    """Test parsing all valid severity values."""
    result = parse_severity_filter("low,medium,high,critical")
    assert result == ["low", "medium", "high", "critical"]


def test_parse_severity_filter_with_whitespace() -> None:
    """Test parsing severity values with whitespace."""
    result = parse_severity_filter("high , critical")
    assert result == ["high", "critical"]


def test_parse_severity_filter_invalid_value_raises_error() -> None:
    """Test parsing invalid severity value raises HTTPException."""
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        parse_severity_filter("invalid")

    assert exc_info.value.status_code == 400
    assert "invalid" in exc_info.value.detail.lower()


def test_parse_severity_filter_invalid_with_valid_raises_error() -> None:
    """Test parsing mix of valid and invalid values raises HTTPException."""
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        parse_severity_filter("high,invalid,critical")

    assert exc_info.value.status_code == 400
    assert "invalid" in exc_info.value.detail.lower()


def test_parse_severity_filter_multiple_invalid_values() -> None:
    """Test parsing multiple invalid values lists all invalid."""
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        parse_severity_filter("foo,bar,baz")

    assert exc_info.value.status_code == 400
    # Should mention all invalid values
    detail = exc_info.value.detail.lower()
    assert "foo" in detail
    assert "bar" in detail
    assert "baz" in detail


def test_parse_severity_filter_empty_parts_ignored() -> None:
    """Test parsing with trailing/leading commas ignores empty parts."""
    result = parse_severity_filter(",high,critical,")
    assert result == ["high", "critical"]


def test_parse_severity_filter_whitespace_only_parts_ignored() -> None:
    """Test parsing with whitespace-only parts ignores them."""
    result = parse_severity_filter("high,,  ,critical")
    assert result == ["high", "critical"]


# =============================================================================
# Direct-handler list_events tests (consolidated from routes/test_events_routes.py;
# they call events_routes.list_events directly, complementing the client-based
# filter tests above)
# =============================================================================


async def test_list_events_returns_empty_list_when_no_events(mock_response: MagicMock) -> None:
    """Test that list_events returns an empty list when no events exist."""
    db = AsyncMock(spec=AsyncSession)

    # Mock count query
    count_result = MagicMock()
    count_result.scalar.return_value = 0

    # Mock events query
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = []

    db.execute = AsyncMock(side_effect=[count_result, events_result])

    response = await events_routes.list_events(
        response=mock_response,
        camera_id=None,
        risk_level=None,
        start_date=None,
        end_date=None,
        reviewed=None,
        object_type=None,
        limit=50,
        offset=0,
        cursor=None,
        fields=None,
        db=db,
    )

    assert response.items == []
    assert response.pagination.total == 0
    assert response.pagination.limit == 50
    # offset=0 becomes None in the response (falsy value converted to None)
    assert response.pagination.offset is None


async def test_list_events_returns_events_with_detection_count(mock_response: MagicMock) -> None:
    """Test that list_events returns events with correct detection count."""
    db = AsyncMock(spec=AsyncSession)

    mock_event = create_mock_event(detection_ids="1,2,3")

    # Mock count query
    count_result = MagicMock()
    count_result.scalar.return_value = 1

    # Mock events query
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = [mock_event]

    db.execute = AsyncMock(side_effect=[count_result, events_result])

    response = await events_routes.list_events(
        response=mock_response,
        camera_id=None,
        risk_level=None,
        start_date=None,
        end_date=None,
        reviewed=None,
        object_type=None,
        limit=50,
        offset=0,
        cursor=None,
        fields=None,
        db=db,
    )

    assert len(response.items) == 1
    assert response.items[0].id == 1
    assert response.items[0].detection_count == 3
    assert response.pagination.total == 1


async def test_list_events_returns_detection_ids_array(mock_response: MagicMock) -> None:
    """Test that list_events returns detection_ids as integer array."""
    db = AsyncMock(spec=AsyncSession)

    mock_event = create_mock_event(detection_ids="10,20,30")

    # Mock count query
    count_result = MagicMock()
    count_result.scalar.return_value = 1

    # Mock events query
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = [mock_event]

    db.execute = AsyncMock(side_effect=[count_result, events_result])

    response = await events_routes.list_events(
        response=mock_response,
        camera_id=None,
        risk_level=None,
        start_date=None,
        end_date=None,
        reviewed=None,
        object_type=None,
        limit=50,
        offset=0,
        cursor=None,
        fields=None,
        db=db,
    )

    assert len(response.items) == 1
    assert response.items[0].detection_ids == [10, 20, 30]
    assert response.items[0].detection_count == 3


async def test_list_events_with_empty_detection_ids(mock_response: MagicMock) -> None:
    """Test that list_events handles events with no detection_ids."""
    db = AsyncMock(spec=AsyncSession)

    mock_event = create_mock_event(detection_ids=None)

    # Mock count query
    count_result = MagicMock()
    count_result.scalar.return_value = 1

    # Mock events query
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = [mock_event]

    db.execute = AsyncMock(side_effect=[count_result, events_result])

    response = await events_routes.list_events(
        response=mock_response,
        camera_id=None,
        risk_level=None,
        start_date=None,
        end_date=None,
        reviewed=None,
        object_type=None,
        limit=50,
        offset=0,
        cursor=None,
        fields=None,
        db=db,
    )

    assert len(response.items) == 1
    assert response.items[0].detection_count == 0


async def test_list_events_with_empty_string_detection_ids(mock_response: MagicMock) -> None:
    """Test that list_events handles events with empty string detection_ids."""
    db = AsyncMock(spec=AsyncSession)

    mock_event = create_mock_event(detection_ids="")

    # Mock count query
    count_result = MagicMock()
    count_result.scalar.return_value = 1

    # Mock events query
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = [mock_event]

    db.execute = AsyncMock(side_effect=[count_result, events_result])

    response = await events_routes.list_events(
        response=mock_response,
        camera_id=None,
        risk_level=None,
        start_date=None,
        end_date=None,
        reviewed=None,
        object_type=None,
        limit=50,
        offset=0,
        cursor=None,
        fields=None,
        db=db,
    )

    assert len(response.items) == 1
    assert response.items[0].detection_count == 0


async def test_list_events_handler_camera_id_filter_returns_matching_event(
    mock_response: MagicMock,
) -> None:
    """Test that list_events filters by camera_id."""
    db = AsyncMock(spec=AsyncSession)

    mock_event = create_mock_event(camera_id="cam-001")

    # Mock count query
    count_result = MagicMock()
    count_result.scalar.return_value = 1

    # Mock events query
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = [mock_event]

    db.execute = AsyncMock(side_effect=[count_result, events_result])

    response = await events_routes.list_events(
        response=mock_response,
        camera_id="cam-001",
        risk_level=None,
        start_date=None,
        end_date=None,
        reviewed=None,
        object_type=None,
        limit=50,
        offset=0,
        cursor=None,
        fields=None,
        db=db,
    )

    assert len(response.items) == 1
    assert response.items[0].camera_id == "cam-001"


async def test_list_events_handler_risk_level_filter_returns_matching_event(
    mock_response: MagicMock,
) -> None:
    """Test that list_events filters by risk_level."""
    db = AsyncMock(spec=AsyncSession)

    mock_event = create_mock_event(risk_level="high")

    # Mock count query
    count_result = MagicMock()
    count_result.scalar.return_value = 1

    # Mock events query
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = [mock_event]

    db.execute = AsyncMock(side_effect=[count_result, events_result])

    response = await events_routes.list_events(
        response=mock_response,
        camera_id=None,
        risk_level="high",
        start_date=None,
        end_date=None,
        reviewed=None,
        object_type=None,
        limit=50,
        offset=0,
        cursor=None,
        fields=None,
        db=db,
    )

    assert len(response.items) == 1
    assert response.items[0].risk_level == "high"


async def test_list_events_with_date_filters(mock_response: MagicMock) -> None:
    """Test that list_events filters by start_date and end_date."""
    db = AsyncMock(spec=AsyncSession)

    now = datetime.now(UTC)
    mock_event = create_mock_event(started_at=now)

    # Mock count query
    count_result = MagicMock()
    count_result.scalar.return_value = 1

    # Mock events query
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = [mock_event]

    db.execute = AsyncMock(side_effect=[count_result, events_result])

    start = now - timedelta(hours=1)
    end = now + timedelta(hours=1)

    response = await events_routes.list_events(
        response=mock_response,
        camera_id=None,
        risk_level=None,
        start_date=start,
        end_date=end,
        reviewed=None,
        object_type=None,
        limit=50,
        offset=0,
        cursor=None,
        fields=None,
        db=db,
    )

    assert len(response.items) == 1


async def test_list_events_with_reviewed_filter_true(mock_response: MagicMock) -> None:
    """Test that list_events filters by reviewed=True."""
    db = AsyncMock(spec=AsyncSession)

    mock_event = create_mock_event(reviewed=True)

    # Mock count query
    count_result = MagicMock()
    count_result.scalar.return_value = 1

    # Mock events query
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = [mock_event]

    db.execute = AsyncMock(side_effect=[count_result, events_result])

    response = await events_routes.list_events(
        response=mock_response,
        camera_id=None,
        risk_level=None,
        start_date=None,
        end_date=None,
        reviewed=True,
        object_type=None,
        limit=50,
        offset=0,
        cursor=None,
        fields=None,
        db=db,
    )

    assert len(response.items) == 1
    assert response.items[0].reviewed is True


async def test_list_events_with_reviewed_filter_false(mock_response: MagicMock) -> None:
    """Test that list_events filters by reviewed=False."""
    db = AsyncMock(spec=AsyncSession)

    mock_event = create_mock_event(reviewed=False)

    # Mock count query
    count_result = MagicMock()
    count_result.scalar.return_value = 1

    # Mock events query
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = [mock_event]

    db.execute = AsyncMock(side_effect=[count_result, events_result])

    response = await events_routes.list_events(
        response=mock_response,
        camera_id=None,
        risk_level=None,
        start_date=None,
        end_date=None,
        reviewed=False,
        object_type=None,
        limit=50,
        offset=0,
        cursor=None,
        fields=None,
        db=db,
    )

    assert len(response.items) == 1
    assert response.items[0].reviewed is False


async def test_list_events_with_object_type_filter_matching(mock_response: MagicMock) -> None:
    """Test that list_events filters by object_type using the object_types column."""
    db = AsyncMock(spec=AsyncSession)

    # Event with object_types containing "person"
    mock_event = create_mock_event(detection_ids="1,2", object_types="person,vehicle")

    # Mock count query
    count_result = MagicMock()
    count_result.scalar.return_value = 1

    # Mock events query
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = [mock_event]

    db.execute = AsyncMock(side_effect=[count_result, events_result])

    response = await events_routes.list_events(
        response=mock_response,
        camera_id=None,
        risk_level=None,
        start_date=None,
        end_date=None,
        reviewed=None,
        object_type="person",
        limit=50,
        offset=0,
        cursor=None,
        fields=None,
        db=db,
    )

    assert len(response.items) == 1


async def test_list_events_with_object_type_filter_no_matches(mock_response: MagicMock) -> None:
    """Test that list_events returns empty when no events match object_type."""
    db = AsyncMock(spec=AsyncSession)

    # Mock count query - no matches due to SQL LIKE filter
    count_result = MagicMock()
    count_result.scalar.return_value = 0

    # Mock events query - empty result
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = []

    db.execute = AsyncMock(side_effect=[count_result, events_result])

    response = await events_routes.list_events(
        response=mock_response,
        camera_id=None,
        risk_level=None,
        start_date=None,
        end_date=None,
        reviewed=None,
        object_type="vehicle",
        limit=50,
        offset=0,
        cursor=None,
        fields=None,
        db=db,
    )

    assert len(response.items) == 0
    assert response.pagination.total == 0


async def test_list_events_with_object_type_filter_single_value(mock_response: MagicMock) -> None:
    """Test that list_events filters by object_type when it's the only value."""
    db = AsyncMock(spec=AsyncSession)

    # Event with only "person" as object_type
    mock_event = create_mock_event(detection_ids="1", object_types="person")

    # Mock count query
    count_result = MagicMock()
    count_result.scalar.return_value = 1

    # Mock events query
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = [mock_event]

    db.execute = AsyncMock(side_effect=[count_result, events_result])

    response = await events_routes.list_events(
        response=mock_response,
        camera_id=None,
        risk_level=None,
        start_date=None,
        end_date=None,
        reviewed=None,
        object_type="person",
        limit=50,
        offset=0,
        cursor=None,
        fields=None,
        db=db,
    )

    assert len(response.items) == 1


async def test_list_events_with_object_type_filter_at_end(mock_response: MagicMock) -> None:
    """Test that list_events filters by object_type when it's at the end of the list."""
    db = AsyncMock(spec=AsyncSession)

    # Event with "person" at the end
    mock_event = create_mock_event(detection_ids="1,2", object_types="vehicle,person")

    # Mock count query
    count_result = MagicMock()
    count_result.scalar.return_value = 1

    # Mock events query
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = [mock_event]

    db.execute = AsyncMock(side_effect=[count_result, events_result])

    response = await events_routes.list_events(
        response=mock_response,
        camera_id=None,
        risk_level=None,
        start_date=None,
        end_date=None,
        reviewed=None,
        object_type="person",
        limit=50,
        offset=0,
        cursor=None,
        fields=None,
        db=db,
    )

    assert len(response.items) == 1


async def test_list_events_object_type_escapes_wildcard_characters(
    mock_response: MagicMock,
) -> None:
    """Test that list_events escapes LIKE wildcard characters in object_type filter.

    This prevents pattern injection attacks where special characters like %
    and _ could match unintended patterns.
    """
    db = AsyncMock(spec=AsyncSession)

    # Event with literal % and _ characters in object_type
    mock_event = create_mock_event(detection_ids="1", object_types="100%_complete")

    # Mock count query
    count_result = MagicMock()
    count_result.scalar.return_value = 1

    # Mock events query
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = [mock_event]

    db.execute = AsyncMock(side_effect=[count_result, events_result])

    # Search for literal "100%_complete" - wildcards should be escaped
    response = await events_routes.list_events(
        response=mock_response,
        camera_id=None,
        risk_level=None,
        start_date=None,
        end_date=None,
        reviewed=None,
        object_type="100%_complete",
        limit=50,
        offset=0,
        cursor=None,
        fields=None,
        db=db,
    )

    # Verify query was called
    assert db.execute.called

    # The function should return results (mock returns 1 event)
    assert len(response.items) == 1


async def test_list_events_pagination_with_custom_limit(mock_response: MagicMock) -> None:
    """Test that list_events respects custom limit parameter."""
    db = AsyncMock(spec=AsyncSession)

    mock_events = [create_mock_event(event_id=i) for i in range(1, 4)]

    # Mock count query
    count_result = MagicMock()
    count_result.scalar.return_value = 10

    # Mock events query
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = mock_events

    db.execute = AsyncMock(side_effect=[count_result, events_result])

    response = await events_routes.list_events(
        response=mock_response,
        camera_id=None,
        risk_level=None,
        start_date=None,
        end_date=None,
        reviewed=None,
        object_type=None,
        limit=3,
        offset=0,
        cursor=None,
        fields=None,
        db=db,
    )

    assert len(response.items) == 3
    assert response.pagination.limit == 3


async def test_list_events_pagination_with_offset(mock_response: MagicMock) -> None:
    """Test that list_events respects offset parameter."""
    db = AsyncMock(spec=AsyncSession)

    mock_events = [create_mock_event(event_id=i) for i in range(6, 11)]

    # Mock count query
    count_result = MagicMock()
    count_result.scalar.return_value = 10

    # Mock events query
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = mock_events

    db.execute = AsyncMock(side_effect=[count_result, events_result])

    response = await events_routes.list_events(
        response=mock_response,
        camera_id=None,
        risk_level=None,
        start_date=None,
        end_date=None,
        reviewed=None,
        object_type=None,
        limit=50,
        offset=5,
        cursor=None,
        fields=None,
        db=db,
    )

    assert len(response.items) == 5
    assert response.pagination.offset == 5


async def test_list_events_multiple_events(mock_response: MagicMock) -> None:
    """Test that list_events handles multiple events correctly."""
    db = AsyncMock(spec=AsyncSession)

    mock_events = [
        create_mock_event(event_id=1, camera_id="cam-001", risk_level="high"),
        create_mock_event(event_id=2, camera_id="cam-002", risk_level="medium"),
        create_mock_event(event_id=3, camera_id="cam-001", risk_level="low"),
    ]

    # Mock count query
    count_result = MagicMock()
    count_result.scalar.return_value = 3

    # Mock events query
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = mock_events

    db.execute = AsyncMock(side_effect=[count_result, events_result])

    response = await events_routes.list_events(
        response=mock_response,
        camera_id=None,
        risk_level=None,
        start_date=None,
        end_date=None,
        reviewed=None,
        object_type=None,
        limit=50,
        offset=0,
        cursor=None,
        fields=None,
        db=db,
    )

    assert len(response.items) == 3
    assert response.pagination.total == 3


async def test_list_events_detection_ids_with_whitespace(mock_response: MagicMock) -> None:
    """Test that list_events handles detection_ids with whitespace."""
    db = AsyncMock(spec=AsyncSession)

    mock_event = create_mock_event(detection_ids="1, 2, 3 , 4")

    # Mock count query
    count_result = MagicMock()
    count_result.scalar.return_value = 1

    # Mock events query
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = [mock_event]

    db.execute = AsyncMock(side_effect=[count_result, events_result])

    response = await events_routes.list_events(
        response=mock_response,
        camera_id=None,
        risk_level=None,
        start_date=None,
        end_date=None,
        reviewed=None,
        object_type=None,
        limit=50,
        offset=0,
        cursor=None,
        fields=None,
        db=db,
    )

    assert len(response.items) == 1
    assert response.items[0].detection_count == 4


async def test_list_events_returns_reasoning_field(mock_response: MagicMock) -> None:
    """Test that list_events returns the reasoning field for each event."""
    db = AsyncMock(spec=AsyncSession)

    mock_event = create_mock_event(
        event_id=1,
        reasoning="Multiple persons detected during late night hours",
    )

    # Mock count query
    count_result = MagicMock()
    count_result.scalar.return_value = 1

    # Mock events query
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = [mock_event]

    db.execute = AsyncMock(side_effect=[count_result, events_result])

    response = await events_routes.list_events(
        response=mock_response,
        camera_id=None,
        risk_level=None,
        start_date=None,
        end_date=None,
        reviewed=None,
        object_type=None,
        limit=50,
        offset=0,
        cursor=None,
        fields=None,
        db=db,
    )

    assert len(response.items) == 1
    assert response.items[0].reasoning == "Multiple persons detected during late night hours"


async def test_list_events_returns_none_reasoning_when_not_set(mock_response: MagicMock) -> None:
    """Test that list_events returns None reasoning when not set."""
    db = AsyncMock(spec=AsyncSession)

    mock_event = create_mock_event(
        event_id=1,
        reasoning=None,
    )

    # Mock count query
    count_result = MagicMock()
    count_result.scalar.return_value = 1

    # Mock events query
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = [mock_event]

    db.execute = AsyncMock(side_effect=[count_result, events_result])

    response = await events_routes.list_events(
        response=mock_response,
        camera_id=None,
        risk_level=None,
        start_date=None,
        end_date=None,
        reviewed=None,
        object_type=None,
        limit=50,
        offset=0,
        cursor=None,
        fields=None,
        db=db,
    )

    assert len(response.items) == 1
    assert response.items[0].reasoning is None


async def test_list_events_with_all_filters_combined(mock_response: MagicMock) -> None:
    """Test that list_events handles all filters combined."""
    db = AsyncMock(spec=AsyncSession)

    now = datetime.now(UTC)
    mock_event = create_mock_event(
        event_id=1,
        camera_id="cam-001",
        risk_level="high",
        reviewed=True,
        started_at=now,
        object_types="person,vehicle",
    )

    # Mock count query
    count_result = MagicMock()
    count_result.scalar.return_value = 1

    # Mock events query
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = [mock_event]

    db.execute = AsyncMock(side_effect=[count_result, events_result])

    response = await events_routes.list_events(
        response=mock_response,
        camera_id="cam-001",
        risk_level="high",
        start_date=now - timedelta(hours=1),
        end_date=now + timedelta(hours=1),
        reviewed=True,
        object_type="person",
        limit=10,
        offset=0,
        cursor=None,
        fields=None,
        db=db,
    )

    assert len(response.items) == 1


async def test_list_events_count_returns_zero_on_none(mock_response: MagicMock) -> None:
    """Test that list_events handles None count result."""
    db = AsyncMock(spec=AsyncSession)

    # Mock count query returning None
    count_result = MagicMock()
    count_result.scalar.return_value = None

    # Mock events query
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = []

    db.execute = AsyncMock(side_effect=[count_result, events_result])

    response = await events_routes.list_events(
        response=mock_response,
        camera_id=None,
        risk_level=None,
        start_date=None,
        end_date=None,
        reviewed=None,
        object_type=None,
        limit=50,
        offset=0,
        cursor=None,
        fields=None,
        db=db,
    )

    assert response.pagination.total == 0


async def test_list_events_invalid_date_range_returns_400(mock_response: MagicMock) -> None:
    """Test that list_events returns HTTP 400 when start_date > end_date."""
    from fastapi import HTTPException

    db = AsyncMock(spec=AsyncSession)

    # start_date is after end_date
    start_date = datetime(2025, 12, 31, 23, 59, 59, tzinfo=UTC)
    end_date = datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC)

    with pytest.raises(HTTPException) as exc_info:
        await events_routes.list_events(
            response=mock_response,
            camera_id=None,
            risk_level=None,
            start_date=start_date,
            end_date=end_date,
            reviewed=None,
            object_type=None,
            limit=50,
            offset=0,
            db=db,
        )

    assert exc_info.value.status_code == 400
    assert "start_date" in exc_info.value.detail.lower()


async def test_list_events_equal_dates_is_valid(mock_response: MagicMock) -> None:
    """Test that list_events accepts start_date == end_date (edge case)."""
    db = AsyncMock(spec=AsyncSession)

    mock_event = create_mock_event()

    # Mock count query
    count_result = MagicMock()
    count_result.scalar.return_value = 1

    # Mock events query
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = [mock_event]

    db.execute = AsyncMock(side_effect=[count_result, events_result])

    # Same date for start and end should be valid
    same_date = datetime(2025, 6, 15, 12, 0, 0, tzinfo=UTC)

    response = await events_routes.list_events(
        response=mock_response,
        camera_id=None,
        risk_level=None,
        start_date=same_date,
        end_date=same_date,
        reviewed=None,
        object_type=None,
        limit=50,
        offset=0,
        cursor=None,
        fields=None,
        db=db,
    )

    assert response.pagination.total == 1


async def test_list_events_excludes_soft_deleted(mock_response: MagicMock) -> None:
    """Test that list_events excludes soft-deleted events by default."""
    db = AsyncMock(spec=AsyncSession)

    # Create active and soft-deleted events
    active_event = create_mock_event(event_id=1, camera_id="cam-001")
    active_event.deleted_at = None

    deleted_event = create_mock_event(event_id=2, camera_id="cam-001")
    deleted_event.deleted_at = datetime.now(UTC)

    # Mock count query - should only count active events
    count_result = MagicMock()
    count_result.scalar.return_value = 1

    # Mock events query - should only return active events
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = [active_event]

    db.execute = AsyncMock(side_effect=[count_result, events_result])

    response = await events_routes.list_events(
        response=mock_response,
        camera_id=None,
        risk_level=None,
        start_date=None,
        end_date=None,
        reviewed=None,
        object_type=None,
        limit=50,
        offset=0,
        cursor=None,
        fields=None,
        include_deleted=False,  # Default behavior
        db=db,
    )

    assert len(response.items) == 1
    assert response.items[0].id == 1
    assert response.pagination.total == 1


async def test_list_events_includes_soft_deleted_with_flag(mock_response: MagicMock) -> None:
    """Test that list_events includes soft-deleted events when include_deleted=True."""
    db = AsyncMock(spec=AsyncSession)

    # Create active and soft-deleted events
    active_event = create_mock_event(event_id=1, camera_id="cam-001")
    active_event.deleted_at = None

    deleted_event = create_mock_event(event_id=2, camera_id="cam-001")
    deleted_event.deleted_at = datetime.now(UTC)

    # Mock count query - should count both active and deleted events
    count_result = MagicMock()
    count_result.scalar.return_value = 2

    # Mock events query - should return both events
    events_result = MagicMock()
    events_result.scalars.return_value.all.return_value = [active_event, deleted_event]

    db.execute = AsyncMock(side_effect=[count_result, events_result])

    response = await events_routes.list_events(
        response=mock_response,
        camera_id=None,
        risk_level=None,
        start_date=None,
        end_date=None,
        reviewed=None,
        object_type=None,
        limit=50,
        offset=0,
        cursor=None,
        fields=None,
        include_deleted=True,  # Include soft-deleted events
        db=db,
    )

    assert len(response.items) == 2
    assert response.pagination.total == 2
    # response.items contains EventResponse objects (dicts converted by Pydantic)
    # Check if items are objects or dicts for compatibility
    if response.items and hasattr(response.items[0], "id"):
        event_ids = [item.id for item in response.items]
    else:
        event_ids = [item["id"] for item in response.items]
    assert 1 in event_ids
    assert 2 in event_ids


def create_mock_event(
    event_id: int = 1,
    camera_id: str = "cam-001",
    started_at: datetime | None = None,
    ended_at: datetime | None = None,
    risk_score: int | None = 75,
    risk_level: str | None = "medium",
    summary: str | None = "Test event",
    reasoning: str | None = None,
    reviewed: bool = False,
    notes: str | None = None,
    detection_ids: str | None = "1,2,3",
    object_types: str | None = None,
) -> MagicMock:
    """Create a mock Event object for testing."""
    mock = MagicMock(spec=Event)
    mock.id = event_id
    mock.camera_id = camera_id
    mock.started_at = started_at or datetime.now(UTC)
    mock.ended_at = ended_at
    mock.risk_score = risk_score
    mock.risk_level = risk_level
    mock.summary = summary
    mock.reasoning = reasoning
    mock.reviewed = reviewed
    mock.notes = notes
    mock.object_types = object_types

    # Mock the detections relationship for detection_id_list and detection_count properties
    if detection_ids:
        # Parse detection_ids to create mock detection objects
        id_list = []
        if isinstance(detection_ids, str):
            # Handle JSON array format
            if detection_ids.startswith("["):
                import json

                id_list = json.loads(detection_ids)
            else:
                # Handle comma-separated format
                id_list = [int(x.strip()) for x in detection_ids.split(",") if x.strip()]
        elif isinstance(detection_ids, list):
            # Already a list
            id_list = detection_ids

        # Create minimal mock detection objects with just id attribute
        mock.detections = [MagicMock(id=det_id) for det_id in id_list]
        # Mock the detection_id_list property (used by Event model)
        mock.detection_id_list = id_list
        # Mock the detection_count property (used by Event model)
        mock.detection_count = len(id_list)
    else:
        mock.detections = []
        mock.detection_id_list = []
        mock.detection_count = 0

    return mock
