"""Unit tests for calibration API routes.

Tests cover:
- GET /api/calibration - Get current user's calibration (with auto-creation)
- PUT /api/calibration - Update calibration thresholds (full update)
- PATCH /api/calibration - Partial update calibration thresholds
- POST /api/calibration/reset - Reset to default thresholds
- GET /api/calibration/defaults - Get default threshold values

These tests target 95%+ coverage by testing:
- All endpoint handlers
- Auto-creation behavior on first GET
- Threshold validation (low < medium < high)
- Partial update semantics
- Error paths (HTTPException cases)
- Edge cases for threshold validation
- Helper function coverage
- Response model transformations

NEM-2316: Create UserCalibration API routes
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

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
    from backend.api.routes.calibration import router

    app = FastAPI()
    app.include_router(router)

    async def override_get_db():
        yield mock_db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def mock_calibration() -> MagicMock:
    """Create a mock UserCalibration instance with default values."""
    calibration = MagicMock()
    calibration.id = 1
    calibration.user_id = "default"
    calibration.low_threshold = 30
    calibration.medium_threshold = 60
    calibration.high_threshold = 85
    calibration.decay_factor = 0.1
    calibration.false_positive_count = 0
    calibration.missed_threat_count = 0
    calibration.created_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
    calibration.updated_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
    return calibration


# =============================================================================
# GET /api/calibration Tests
# =============================================================================


class TestGetCalibration:
    """Tests for GET /api/calibration endpoint."""

    def test_get_existing_calibration(
        self, client: TestClient, mock_db_session: AsyncMock, mock_calibration: MagicMock
    ) -> None:
        """Test getting existing calibration returns current settings."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_calibration
        mock_db_session.execute.return_value = mock_result

        response = client.get("/api/calibration")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert data["user_id"] == "default"
        assert data["low_threshold"] == 30
        assert data["medium_threshold"] == 60
        assert data["high_threshold"] == 85
        assert data["decay_factor"] == 0.1
        assert data["false_positive_count"] == 0
        assert data["missed_threat_count"] == 0
        assert "created_at" in data
        assert "updated_at" in data

    def test_get_calibration_auto_creates_when_not_exists(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test GET auto-creates calibration with defaults if not exists."""
        # First query returns None (no existing calibration)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        # Mock refresh to populate the new calibration object
        def mock_refresh(obj):
            obj.id = 1
            obj.user_id = "default"
            obj.low_threshold = 30
            obj.medium_threshold = 60
            obj.high_threshold = 85
            obj.decay_factor = 0.1
            obj.false_positive_count = 0
            obj.missed_threat_count = 0
            obj.created_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
            obj.updated_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)

        mock_db_session.refresh.side_effect = mock_refresh

        response = client.get("/api/calibration")

        assert response.status_code == 200
        data = response.json()
        assert data["low_threshold"] == 30
        assert data["medium_threshold"] == 60
        assert data["high_threshold"] == 85
        assert data["decay_factor"] == 0.1

        # Verify db operations for creation
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()
        mock_db_session.refresh.assert_called_once()


# =============================================================================
# PUT /api/calibration Tests
# =============================================================================


class TestUpdateCalibration:
    """Tests for PUT /api/calibration endpoint."""

    def test_put_update_all_thresholds(
        self, client: TestClient, mock_db_session: AsyncMock, mock_calibration: MagicMock
    ) -> None:
        """Test PUT updating all threshold values."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_calibration
        mock_db_session.execute.return_value = mock_result

        # Mock refresh to update the calibration object
        def mock_refresh(obj):
            obj.low_threshold = 25
            obj.medium_threshold = 55
            obj.high_threshold = 80
            obj.decay_factor = 0.15

        mock_db_session.refresh.side_effect = mock_refresh

        response = client.put(
            "/api/calibration",
            json={
                "low_threshold": 25,
                "medium_threshold": 55,
                "high_threshold": 80,
                "decay_factor": 0.15,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["low_threshold"] == 25
        assert data["medium_threshold"] == 55
        assert data["high_threshold"] == 80
        assert data["decay_factor"] == 0.15

        # Verify db commit
        mock_db_session.commit.assert_called_once()

    def test_put_partial_update_low_threshold_only(
        self, client: TestClient, mock_db_session: AsyncMock, mock_calibration: MagicMock
    ) -> None:
        """Test PUT with only low_threshold updates correctly."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_calibration
        mock_db_session.execute.return_value = mock_result

        def mock_refresh(obj):
            obj.low_threshold = 20

        mock_db_session.refresh.side_effect = mock_refresh

        response = client.put("/api/calibration", json={"low_threshold": 20})

        assert response.status_code == 200
        data = response.json()
        assert data["low_threshold"] == 20
        # Other values should remain unchanged
        assert mock_calibration.medium_threshold == 60
        assert mock_calibration.high_threshold == 85

    def test_put_partial_update_medium_threshold_only(
        self, client: TestClient, mock_db_session: AsyncMock, mock_calibration: MagicMock
    ) -> None:
        """Test PUT with only medium_threshold updates correctly."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_calibration
        mock_db_session.execute.return_value = mock_result

        def mock_refresh(obj):
            obj.medium_threshold = 50

        mock_db_session.refresh.side_effect = mock_refresh

        response = client.put("/api/calibration", json={"medium_threshold": 50})

        assert response.status_code == 200
        data = response.json()
        assert data["medium_threshold"] == 50

    def test_put_partial_update_high_threshold_only(
        self, client: TestClient, mock_db_session: AsyncMock, mock_calibration: MagicMock
    ) -> None:
        """Test PUT with only high_threshold updates correctly."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_calibration
        mock_db_session.execute.return_value = mock_result

        def mock_refresh(obj):
            obj.high_threshold = 90

        mock_db_session.refresh.side_effect = mock_refresh

        response = client.put("/api/calibration", json={"high_threshold": 90})

        assert response.status_code == 200
        data = response.json()
        assert data["high_threshold"] == 90

    def test_put_partial_update_decay_factor_only(
        self, client: TestClient, mock_db_session: AsyncMock, mock_calibration: MagicMock
    ) -> None:
        """Test PUT with only decay_factor updates correctly."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_calibration
        mock_db_session.execute.return_value = mock_result

        def mock_refresh(obj):
            obj.decay_factor = 0.2

        mock_db_session.refresh.side_effect = mock_refresh

        response = client.put("/api/calibration", json={"decay_factor": 0.2})

        assert response.status_code == 200
        data = response.json()
        assert data["decay_factor"] == 0.2

    def test_put_validation_low_equals_medium_returns_422(
        self, client: TestClient, mock_db_session: AsyncMock, mock_calibration: MagicMock
    ) -> None:
        """Test PUT with low_threshold equal to medium_threshold returns 422."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_calibration
        mock_db_session.execute.return_value = mock_result

        response = client.put(
            "/api/calibration",
            json={
                "low_threshold": 50,
                "medium_threshold": 50,
            },
        )

        assert response.status_code == 422
        detail = response.json()["detail"]
        assert "low_threshold" in detail
        assert "medium_threshold" in detail

    def test_put_validation_low_greater_than_medium_returns_422(
        self, client: TestClient, mock_db_session: AsyncMock, mock_calibration: MagicMock
    ) -> None:
        """Test PUT with low_threshold > medium_threshold returns 422."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_calibration
        mock_db_session.execute.return_value = mock_result

        response = client.put(
            "/api/calibration",
            json={
                "low_threshold": 70,
                "medium_threshold": 50,
            },
        )

        assert response.status_code == 422
        detail = response.json()["detail"]
        assert "low_threshold" in detail and "medium_threshold" in detail

    def test_put_validation_medium_equals_high_returns_422(
        self, client: TestClient, mock_db_session: AsyncMock, mock_calibration: MagicMock
    ) -> None:
        """Test PUT with medium_threshold equal to high_threshold returns 422."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_calibration
        mock_db_session.execute.return_value = mock_result

        response = client.put(
            "/api/calibration",
            json={
                "medium_threshold": 80,
                "high_threshold": 80,
            },
        )

        assert response.status_code == 422
        detail = response.json()["detail"]
        assert "medium_threshold" in detail
        assert "high_threshold" in detail

    def test_put_validation_medium_greater_than_high_returns_422(
        self, client: TestClient, mock_db_session: AsyncMock, mock_calibration: MagicMock
    ) -> None:
        """Test PUT with medium_threshold > high_threshold returns 422."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_calibration
        mock_db_session.execute.return_value = mock_result

        response = client.put(
            "/api/calibration",
            json={
                "medium_threshold": 90,
                "high_threshold": 80,
            },
        )

        assert response.status_code == 422
        detail = response.json()["detail"]
        assert "medium_threshold" in detail and "high_threshold" in detail

    def test_put_validation_with_existing_values(
        self, client: TestClient, mock_db_session: AsyncMock, mock_calibration: MagicMock
    ) -> None:
        """Test PUT validates against merged values (partial update + existing)."""
        # Current: low=30, medium=60, high=85
        # Update only low to 70 (should fail because 70 >= 60)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_calibration
        mock_db_session.execute.return_value = mock_result

        response = client.put("/api/calibration", json={"low_threshold": 70})

        assert response.status_code == 422

    def test_put_auto_creates_if_not_exists(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test PUT auto-creates calibration if it doesn't exist."""
        # First query returns None (no existing calibration)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        def mock_refresh(obj):
            obj.id = 1
            obj.user_id = "default"
            obj.low_threshold = 25
            obj.medium_threshold = 55
            obj.high_threshold = 80
            obj.decay_factor = 0.1
            obj.false_positive_count = 0
            obj.missed_threat_count = 0
            obj.created_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
            obj.updated_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)

        mock_db_session.refresh.side_effect = mock_refresh

        response = client.put(
            "/api/calibration",
            json={
                "low_threshold": 25,
                "medium_threshold": 55,
                "high_threshold": 80,
            },
        )

        assert response.status_code == 200
        # Auto-creation + update = 2 commits
        assert mock_db_session.commit.call_count == 2


# =============================================================================
# PATCH /api/calibration Tests
# =============================================================================


class TestPatchCalibration:
    """Tests for PATCH /api/calibration endpoint."""

    def test_patch_update_all_thresholds(
        self, client: TestClient, mock_db_session: AsyncMock, mock_calibration: MagicMock
    ) -> None:
        """Test PATCH updating all threshold values."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_calibration
        mock_db_session.execute.return_value = mock_result

        def mock_refresh(obj):
            obj.low_threshold = 25
            obj.medium_threshold = 55
            obj.high_threshold = 80
            obj.decay_factor = 0.15

        mock_db_session.refresh.side_effect = mock_refresh

        response = client.patch(
            "/api/calibration",
            json={
                "low_threshold": 25,
                "medium_threshold": 55,
                "high_threshold": 80,
                "decay_factor": 0.15,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["low_threshold"] == 25
        assert data["medium_threshold"] == 55
        assert data["high_threshold"] == 80
        assert data["decay_factor"] == 0.15

    def test_patch_partial_update_low_threshold(
        self, client: TestClient, mock_db_session: AsyncMock, mock_calibration: MagicMock
    ) -> None:
        """Test PATCH with only low_threshold."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_calibration
        mock_db_session.execute.return_value = mock_result

        def mock_refresh(obj):
            obj.low_threshold = 20

        mock_db_session.refresh.side_effect = mock_refresh

        response = client.patch("/api/calibration", json={"low_threshold": 20})

        assert response.status_code == 200
        data = response.json()
        assert data["low_threshold"] == 20

    def test_patch_validation_low_equals_medium_returns_422(
        self, client: TestClient, mock_db_session: AsyncMock, mock_calibration: MagicMock
    ) -> None:
        """Test PATCH with low_threshold equal to medium_threshold returns 422."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_calibration
        mock_db_session.execute.return_value = mock_result

        response = client.patch(
            "/api/calibration",
            json={
                "low_threshold": 50,
                "medium_threshold": 50,
            },
        )

        assert response.status_code == 422

    def test_patch_validation_medium_equals_high_returns_422(
        self, client: TestClient, mock_db_session: AsyncMock, mock_calibration: MagicMock
    ) -> None:
        """Test PATCH with medium_threshold equal to high_threshold returns 422."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_calibration
        mock_db_session.execute.return_value = mock_result

        response = client.patch(
            "/api/calibration",
            json={
                "medium_threshold": 80,
                "high_threshold": 80,
            },
        )

        assert response.status_code == 422

    def test_patch_empty_body_returns_200(
        self, client: TestClient, mock_db_session: AsyncMock, mock_calibration: MagicMock
    ) -> None:
        """Test PATCH with empty body returns current calibration unchanged."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_calibration
        mock_db_session.execute.return_value = mock_result

        response = client.patch("/api/calibration", json={})

        assert response.status_code == 200
        data = response.json()
        # Should return current values unchanged
        assert data["low_threshold"] == 30
        assert data["medium_threshold"] == 60
        assert data["high_threshold"] == 85


# =============================================================================
# POST /api/calibration/reset Tests
# =============================================================================


class TestResetCalibration:
    """Tests for POST /api/calibration/reset endpoint."""

    def test_reset_calibration_to_defaults(
        self, client: TestClient, mock_db_session: AsyncMock, mock_calibration: MagicMock
    ) -> None:
        """Test resetting calibration to default values."""
        # Set non-default values
        mock_calibration.low_threshold = 20
        mock_calibration.medium_threshold = 50
        mock_calibration.high_threshold = 80
        mock_calibration.decay_factor = 0.2

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_calibration
        mock_db_session.execute.return_value = mock_result

        def mock_refresh(obj):
            obj.low_threshold = 30
            obj.medium_threshold = 60
            obj.high_threshold = 85
            obj.decay_factor = 0.1

        mock_db_session.refresh.side_effect = mock_refresh

        response = client.post("/api/calibration/reset")

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Calibration reset to default values"
        assert data["calibration"]["low_threshold"] == 30
        assert data["calibration"]["medium_threshold"] == 60
        assert data["calibration"]["high_threshold"] == 85
        assert data["calibration"]["decay_factor"] == 0.1

        # Verify db commit
        mock_db_session.commit.assert_called_once()

    def test_reset_preserves_feedback_counts(
        self, client: TestClient, mock_db_session: AsyncMock, mock_calibration: MagicMock
    ) -> None:
        """Test that reset doesn't clear feedback counts."""
        mock_calibration.false_positive_count = 5
        mock_calibration.missed_threat_count = 3

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_calibration
        mock_db_session.execute.return_value = mock_result

        response = client.post("/api/calibration/reset")

        assert response.status_code == 200
        data = response.json()
        # Feedback counts should be preserved
        assert data["calibration"]["false_positive_count"] == 5
        assert data["calibration"]["missed_threat_count"] == 3

    def test_reset_auto_creates_if_not_exists(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test reset auto-creates calibration if it doesn't exist."""
        # First query returns None (no existing calibration)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        def mock_refresh(obj):
            obj.id = 1
            obj.user_id = "default"
            obj.low_threshold = 30
            obj.medium_threshold = 60
            obj.high_threshold = 85
            obj.decay_factor = 0.1
            obj.false_positive_count = 0
            obj.missed_threat_count = 0
            obj.created_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
            obj.updated_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)

        mock_db_session.refresh.side_effect = mock_refresh

        response = client.post("/api/calibration/reset")

        assert response.status_code == 200
        # Auto-creation + reset = 2 commits
        assert mock_db_session.commit.call_count == 2


# =============================================================================
# GET /api/calibration/defaults Tests
# =============================================================================


class TestGetCalibrationDefaults:
    """Tests for GET /api/calibration/defaults endpoint."""

    def test_get_defaults_returns_correct_values(self, client: TestClient) -> None:
        """Test getting default calibration values."""
        response = client.get("/api/calibration/defaults")

        assert response.status_code == 200
        data = response.json()
        assert data["low_threshold"] == 30
        assert data["medium_threshold"] == 60
        assert data["high_threshold"] == 85
        assert data["decay_factor"] == 0.1

    def test_get_defaults_no_database_access(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test that getting defaults doesn't access the database."""
        response = client.get("/api/calibration/defaults")

        assert response.status_code == 200
        # Should not execute any database queries
        mock_db_session.execute.assert_not_called()


# =============================================================================
# Helper Function Tests
# =============================================================================


class TestHelperFunctions:
    """Tests for internal helper functions."""

    def test_calibration_to_response_conversion(self) -> None:
        """Test _calibration_to_response converts model correctly."""
        from backend.api.routes.calibration import _calibration_to_response

        mock_cal = MagicMock()
        mock_cal.id = 1
        mock_cal.user_id = "default"
        mock_cal.low_threshold = 30
        mock_cal.medium_threshold = 60
        mock_cal.high_threshold = 85
        mock_cal.decay_factor = 0.1
        mock_cal.false_positive_count = 5
        mock_cal.missed_threat_count = 3
        mock_cal.created_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
        mock_cal.updated_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)

        result = _calibration_to_response(mock_cal)

        assert result["id"] == 1
        assert result["user_id"] == "default"
        assert result["low_threshold"] == 30
        assert result["medium_threshold"] == 60
        assert result["high_threshold"] == 85
        assert result["decay_factor"] == 0.1
        assert result["false_positive_count"] == 5
        assert result["missed_threat_count"] == 3
        assert result["created_at"] == datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
        assert result["updated_at"] == datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)

    def test_validate_threshold_ordering_valid(self) -> None:
        """Test _validate_threshold_ordering with valid ordering."""
        from backend.api.routes.calibration import _validate_threshold_ordering

        # Should not raise for valid ordering
        _validate_threshold_ordering(10, 50, 90)
        _validate_threshold_ordering(0, 1, 2)
        _validate_threshold_ordering(30, 60, 85)

    def test_validate_threshold_ordering_low_equals_medium(self) -> None:
        """Test _validate_threshold_ordering raises when low == medium."""
        from fastapi import HTTPException

        from backend.api.routes.calibration import _validate_threshold_ordering

        with pytest.raises(HTTPException) as exc_info:
            _validate_threshold_ordering(50, 50, 90)

        assert exc_info.value.status_code == 422
        assert "low_threshold" in exc_info.value.detail
        assert "medium_threshold" in exc_info.value.detail

    def test_validate_threshold_ordering_low_greater_than_medium(self) -> None:
        """Test _validate_threshold_ordering raises when low > medium."""
        from fastapi import HTTPException

        from backend.api.routes.calibration import _validate_threshold_ordering

        with pytest.raises(HTTPException) as exc_info:
            _validate_threshold_ordering(70, 50, 90)

        assert exc_info.value.status_code == 422
        assert "low_threshold" in exc_info.value.detail
        assert "medium_threshold" in exc_info.value.detail

    def test_validate_threshold_ordering_medium_equals_high(self) -> None:
        """Test _validate_threshold_ordering raises when medium == high."""
        from fastapi import HTTPException

        from backend.api.routes.calibration import _validate_threshold_ordering

        with pytest.raises(HTTPException) as exc_info:
            _validate_threshold_ordering(30, 80, 80)

        assert exc_info.value.status_code == 422
        assert "medium_threshold" in exc_info.value.detail
        assert "high_threshold" in exc_info.value.detail

    def test_validate_threshold_ordering_medium_greater_than_high(self) -> None:
        """Test _validate_threshold_ordering raises when medium > high."""
        from fastapi import HTTPException

        from backend.api.routes.calibration import _validate_threshold_ordering

        with pytest.raises(HTTPException) as exc_info:
            _validate_threshold_ordering(30, 90, 80)

        assert exc_info.value.status_code == 422
        assert "medium_threshold" in exc_info.value.detail
        assert "high_threshold" in exc_info.value.detail


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_update_with_boundary_values_min(
        self, client: TestClient, mock_db_session: AsyncMock, mock_calibration: MagicMock
    ) -> None:
        """Test updating with minimum valid boundary values."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_calibration
        mock_db_session.execute.return_value = mock_result

        def mock_refresh(obj):
            obj.low_threshold = 0
            obj.medium_threshold = 1
            obj.high_threshold = 2

        mock_db_session.refresh.side_effect = mock_refresh

        response = client.put(
            "/api/calibration",
            json={
                "low_threshold": 0,
                "medium_threshold": 1,
                "high_threshold": 2,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["low_threshold"] == 0
        assert data["medium_threshold"] == 1
        assert data["high_threshold"] == 2

    def test_update_with_boundary_values_max(
        self, client: TestClient, mock_db_session: AsyncMock, mock_calibration: MagicMock
    ) -> None:
        """Test updating with maximum valid boundary values."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_calibration
        mock_db_session.execute.return_value = mock_result

        def mock_refresh(obj):
            obj.low_threshold = 98
            obj.medium_threshold = 99
            obj.high_threshold = 100

        mock_db_session.refresh.side_effect = mock_refresh

        response = client.put(
            "/api/calibration",
            json={
                "low_threshold": 98,
                "medium_threshold": 99,
                "high_threshold": 100,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["low_threshold"] == 98
        assert data["medium_threshold"] == 99
        assert data["high_threshold"] == 100

    def test_update_decay_factor_boundary_min(
        self, client: TestClient, mock_db_session: AsyncMock, mock_calibration: MagicMock
    ) -> None:
        """Test updating decay_factor with minimum boundary value."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_calibration
        mock_db_session.execute.return_value = mock_result

        def mock_refresh(obj):
            obj.decay_factor = 0.0

        mock_db_session.refresh.side_effect = mock_refresh

        response = client.put("/api/calibration", json={"decay_factor": 0.0})

        assert response.status_code == 200
        data = response.json()
        assert data["decay_factor"] == 0.0

    def test_update_decay_factor_boundary_max(
        self, client: TestClient, mock_db_session: AsyncMock, mock_calibration: MagicMock
    ) -> None:
        """Test updating decay_factor with maximum boundary value."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_calibration
        mock_db_session.execute.return_value = mock_result

        def mock_refresh(obj):
            obj.decay_factor = 1.0

        mock_db_session.refresh.side_effect = mock_refresh

        response = client.put("/api/calibration", json={"decay_factor": 1.0})

        assert response.status_code == 200
        data = response.json()
        assert data["decay_factor"] == 1.0

    def test_validation_error_with_all_thresholds_equal(
        self, client: TestClient, mock_db_session: AsyncMock, mock_calibration: MagicMock
    ) -> None:
        """Test validation error when all thresholds are equal."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_calibration
        mock_db_session.execute.return_value = mock_result

        response = client.put(
            "/api/calibration",
            json={
                "low_threshold": 50,
                "medium_threshold": 50,
                "high_threshold": 50,
            },
        )

        assert response.status_code == 422


# =============================================================================
# OpenAPI Documentation Tests
# =============================================================================


class TestCalibrationOpenAPI:
    """Tests for calibration routes OpenAPI documentation."""

    def test_routes_have_tags(self, client: TestClient) -> None:
        """Test that routes are tagged for OpenAPI grouping."""
        from backend.api.routes.calibration import router

        for route in router.routes:
            if hasattr(route, "tags"):
                assert "calibration" in route.tags

    def test_routes_have_response_models(self, client: TestClient) -> None:
        """Test that routes have response models defined."""
        from backend.api.routes.calibration import router

        for route in router.routes:
            if hasattr(route, "response_model"):
                assert route.response_model is not None

    def test_routes_have_correct_prefix(self, client: TestClient) -> None:
        """Test that router has correct prefix."""
        from backend.api.routes.calibration import router

        assert router.prefix == "/api/calibration"
