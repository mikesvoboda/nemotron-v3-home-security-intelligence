"""Unit tests for feedback API routes.

Tests cover:
- POST /api/feedback - Submit event feedback
- GET /api/feedback/event/{event_id} - Get feedback for specific event
- GET /api/feedback/stats - Get aggregate feedback statistics

NEM-1908: Create EventFeedback API schemas and routes
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.schemas.feedback import FeedbackType
from backend.core.database import get_db

# Mark as unit tests - no database required
pytestmark = pytest.mark.unit


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Create a mock database session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.rollback = AsyncMock()
    return session


@pytest.fixture
def client(mock_db_session: AsyncMock) -> TestClient:
    """Create a test client with mocked dependencies."""
    from backend.api.routes.feedback import router

    app = FastAPI()
    app.include_router(router)

    async def override_get_db():
        yield mock_db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client


# =============================================================================
# POST /api/feedback Tests
# =============================================================================


class TestCreateFeedback:
    """Tests for POST /api/feedback endpoint."""

    def test_create_feedback_success(self, client: TestClient, mock_db_session: AsyncMock) -> None:
        """Test successfully creating feedback."""
        # Mock event exists
        mock_event = MagicMock()
        mock_event.id = 123
        mock_event.camera_id = "front_door"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_event

        # Mock no existing feedback
        mock_no_feedback = MagicMock()
        mock_no_feedback.scalar_one_or_none.return_value = None

        mock_db_session.execute.side_effect = [mock_result, mock_no_feedback]

        # Mock the feedback refresh to return proper values
        def mock_refresh(feedback):
            feedback.id = 1
            feedback.created_at = datetime.now(UTC)

        mock_db_session.refresh.side_effect = mock_refresh

        response = client.post(
            "/api/feedback",
            json={
                "event_id": 123,
                "feedback_type": "false_positive",
                "notes": "This was my neighbor.",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["event_id"] == 123
        assert data["feedback_type"] == "false_positive"
        assert data["notes"] == "This was my neighbor."

    def test_create_feedback_event_not_found(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test creating feedback for non-existent event returns 404."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        response = client.post(
            "/api/feedback",
            json={
                "event_id": 999,
                "feedback_type": "false_positive",
            },
        )

        assert response.status_code == 404
        detail = response.json()["detail"].lower()
        # Check for "event" and "999" or "not found" in error message
        assert ("event" in detail and "999" in detail) or "not found" in detail

    def test_create_feedback_duplicate_returns_409(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test creating duplicate feedback returns 409 conflict."""
        # Mock event exists
        mock_event = MagicMock()
        mock_event.id = 123
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_event

        # Mock existing feedback found
        mock_existing_feedback = MagicMock()
        mock_existing_feedback.id = 1
        mock_existing_feedback.event_id = 123
        mock_feedback_result = MagicMock()
        mock_feedback_result.scalar_one_or_none.return_value = mock_existing_feedback

        mock_db_session.execute.side_effect = [mock_result, mock_feedback_result]

        response = client.post(
            "/api/feedback",
            json={
                "event_id": 123,
                "feedback_type": "false_positive",
            },
        )

        assert response.status_code == 409
        assert "already exists" in response.json()["detail"].lower()

    def test_create_feedback_without_notes(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test creating feedback without notes."""
        # Mock event exists
        mock_event = MagicMock()
        mock_event.id = 456
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_event

        # Mock no existing feedback
        mock_no_feedback = MagicMock()
        mock_no_feedback.scalar_one_or_none.return_value = None

        mock_db_session.execute.side_effect = [mock_result, mock_no_feedback]

        def mock_refresh(feedback):
            feedback.id = 2
            feedback.created_at = datetime.now(UTC)

        mock_db_session.refresh.side_effect = mock_refresh

        response = client.post(
            "/api/feedback",
            json={
                "event_id": 456,
                "feedback_type": "correct",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["notes"] is None

    def test_create_feedback_invalid_type_returns_422(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test creating feedback with invalid type returns 422."""
        response = client.post(
            "/api/feedback",
            json={
                "event_id": 123,
                "feedback_type": "invalid_type",
            },
        )

        assert response.status_code == 422

    def test_create_feedback_missing_event_id_returns_422(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test creating feedback without event_id returns 422."""
        response = client.post(
            "/api/feedback",
            json={
                "feedback_type": "false_positive",
            },
        )

        assert response.status_code == 422

    def test_create_feedback_all_types(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test creating feedback with all valid feedback types."""
        for feedback_type in FeedbackType:
            # Reset mock for each iteration
            mock_db_session.reset_mock()

            # Mock event exists
            mock_event = MagicMock()
            mock_event.id = 100
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_event

            # Mock no existing feedback
            mock_no_feedback = MagicMock()
            mock_no_feedback.scalar_one_or_none.return_value = None

            mock_db_session.execute.side_effect = [mock_result, mock_no_feedback]

            def mock_refresh(feedback):
                feedback.id = 1
                feedback.created_at = datetime.now(UTC)

            mock_db_session.refresh.side_effect = mock_refresh

            response = client.post(
                "/api/feedback",
                json={
                    "event_id": 100,
                    "feedback_type": feedback_type.value,
                },
            )

            assert response.status_code == 201, f"Failed for type: {feedback_type}"


# =============================================================================
# GET /api/feedback/event/{event_id} Tests
# =============================================================================


class TestGetEventFeedback:
    """Tests for GET /api/feedback/event/{event_id} endpoint."""

    def test_get_feedback_success(self, client: TestClient, mock_db_session: AsyncMock) -> None:
        """Test successfully getting feedback for an event."""
        mock_feedback = MagicMock()
        mock_feedback.id = 1
        mock_feedback.event_id = 123
        mock_feedback.feedback_type = "false_positive"
        mock_feedback.notes = "Test notes"
        mock_feedback.created_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_feedback
        mock_db_session.execute.return_value = mock_result

        response = client.get("/api/feedback/event/123")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert data["event_id"] == 123
        assert data["feedback_type"] == "false_positive"
        assert data["notes"] == "Test notes"
        assert "created_at" in data

    def test_get_feedback_not_found(self, client: TestClient, mock_db_session: AsyncMock) -> None:
        """Test getting feedback for event with no feedback returns 404."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        response = client.get("/api/feedback/event/999")

        assert response.status_code == 404
        detail = response.json()["detail"].lower()
        # Check for "no feedback found" or similar message
        assert "feedback" in detail and "999" in detail

    def test_get_feedback_invalid_event_id(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test getting feedback with invalid event_id returns 422."""
        response = client.get("/api/feedback/event/invalid")

        assert response.status_code == 422


# =============================================================================
# GET /api/feedback/stats Tests
# =============================================================================


class TestGetFeedbackStats:
    """Tests for GET /api/feedback/stats endpoint."""

    def test_get_stats_success(self, client: TestClient, mock_db_session: AsyncMock) -> None:
        """Test successfully getting feedback statistics."""
        # Mock count query result
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 100

        # Mock by_type query result (returns list of tuples)
        mock_type_result = MagicMock()
        mock_type_result.all.return_value = [
            ("false_positive", 40),
            ("missed_detection", 30),
            ("wrong_severity", 20),
            ("correct", 10),
        ]

        # Mock by_camera query result (returns list of tuples)
        mock_camera_result = MagicMock()
        mock_camera_result.all.return_value = [
            ("front_door", 50),
            ("back_yard", 30),
            ("garage", 20),
        ]

        mock_db_session.execute.side_effect = [
            mock_count_result,
            mock_type_result,
            mock_camera_result,
        ]

        response = client.get("/api/feedback/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["total_feedback"] == 100
        assert data["by_type"]["false_positive"] == 40
        assert data["by_type"]["missed_detection"] == 30
        assert data["by_camera"]["front_door"] == 50
        assert data["by_camera"]["back_yard"] == 30

    def test_get_stats_empty_database(self, client: TestClient, mock_db_session: AsyncMock) -> None:
        """Test getting stats with no feedback in database."""
        # Mock empty results
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0

        mock_type_result = MagicMock()
        mock_type_result.all.return_value = []

        mock_camera_result = MagicMock()
        mock_camera_result.all.return_value = []

        mock_db_session.execute.side_effect = [
            mock_count_result,
            mock_type_result,
            mock_camera_result,
        ]

        response = client.get("/api/feedback/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["total_feedback"] == 0
        assert data["by_type"] == {}
        assert data["by_camera"] == {}

    def test_get_stats_partial_data(self, client: TestClient, mock_db_session: AsyncMock) -> None:
        """Test getting stats with only some feedback types."""
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 25

        mock_type_result = MagicMock()
        mock_type_result.all.return_value = [
            ("false_positive", 25),
        ]

        mock_camera_result = MagicMock()
        mock_camera_result.all.return_value = [
            ("front_door", 25),
        ]

        mock_db_session.execute.side_effect = [
            mock_count_result,
            mock_type_result,
            mock_camera_result,
        ]

        response = client.get("/api/feedback/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["total_feedback"] == 25
        # Only false_positive should be present
        assert len(data["by_type"]) == 1
        assert data["by_type"]["false_positive"] == 25

    def test_stats_executes_three_queries(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test that stats endpoint executes expected number of queries."""
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0

        mock_type_result = MagicMock()
        mock_type_result.all.return_value = []

        mock_camera_result = MagicMock()
        mock_camera_result.all.return_value = []

        mock_db_session.execute.side_effect = [
            mock_count_result,
            mock_type_result,
            mock_camera_result,
        ]

        response = client.get("/api/feedback/stats")

        assert response.status_code == 200
        # Should execute 3 queries: total count, by type, by camera
        assert mock_db_session.execute.call_count == 3


# =============================================================================
# OpenAPI Documentation Tests
# =============================================================================


class TestFeedbackOpenAPI:
    """Tests for feedback routes OpenAPI documentation."""

    def test_routes_have_tags(self, client: TestClient) -> None:
        """Test that routes are tagged for OpenAPI grouping."""
        from backend.api.routes.feedback import router

        # All routes should have the 'feedback' tag
        for route in router.routes:
            if hasattr(route, "tags"):
                assert "feedback" in route.tags

    def test_routes_have_response_models(self, client: TestClient) -> None:
        """Test that routes have response models defined."""
        from backend.api.routes.feedback import router

        for route in router.routes:
            if hasattr(route, "response_model"):
                # POST and GET routes should have response models
                assert route.response_model is not None or route.status_code == 204
