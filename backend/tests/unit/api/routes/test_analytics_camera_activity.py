"""Unit tests for camera activity heatmap analytics API route.

Tests the camera activity aggregation endpoint:
- GET /api/analytics/camera-activity - Event aggregation per camera

This endpoint supports the Camera Activity Heatmap feature (NEM-5388/5389/5390/5391).
Returns: camera_id, camera_name, event_count, max_risk_score, thumbnail_path

These tests follow TDD methodology - comprehensive coverage of happy paths,
error cases, and edge cases with proper mocking of database operations.
"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.api.routes.analytics import get_camera_activity
from backend.api.schemas.analytics import CameraActivityResponse


class TestCameraActivity:
    """Tests for GET /api/analytics/camera-activity endpoint."""

    @pytest.mark.asyncio
    async def test_camera_activity_with_data(self, mock_db_session: AsyncMock) -> None:
        """Test camera activity returns aggregated event data with thumbnails."""
        start_date = date(2026, 1, 1)
        end_date = date(2026, 1, 7)

        # Mock database query result with camera activity data
        mock_row_1 = MagicMock()
        mock_row_1.camera_id = "front_door"
        mock_row_1.camera_name = "Front Door"
        mock_row_1.event_count = 45
        mock_row_1.max_risk_score = 87
        mock_row_1.thumbnail_path = "/data/thumbnails/2026/01/front_door_high_risk.jpg"

        mock_row_2 = MagicMock()
        mock_row_2.camera_id = "back_door"
        mock_row_2.camera_name = "Back Door"
        mock_row_2.event_count = 12
        mock_row_2.max_risk_score = 45
        mock_row_2.thumbnail_path = "/data/thumbnails/2026/01/back_door_high_risk.jpg"

        mock_row_3 = MagicMock()
        mock_row_3.camera_id = "garage"
        mock_row_3.camera_name = "Garage"
        mock_row_3.event_count = 3
        mock_row_3.max_risk_score = 25
        mock_row_3.thumbnail_path = None  # No high-risk detection with thumbnail

        mock_result = MagicMock()
        mock_result.all.return_value = [mock_row_1, mock_row_2, mock_row_3]
        mock_db_session.execute.return_value = mock_result

        result = await get_camera_activity(
            start_date=start_date, end_date=end_date, db=mock_db_session
        )

        # Verify response structure
        assert isinstance(result, CameraActivityResponse)
        assert result.start_date == start_date
        assert result.end_date == end_date
        assert len(result.cameras) == 3

        # Verify camera 1 (highest activity)
        assert result.cameras[0].camera_id == "front_door"
        assert result.cameras[0].camera_name == "Front Door"
        assert result.cameras[0].event_count == 45
        assert result.cameras[0].max_risk_score == 87
        assert (
            result.cameras[0].thumbnail_path == "/data/thumbnails/2026/01/front_door_high_risk.jpg"
        )

        # Verify camera 2
        assert result.cameras[1].camera_id == "back_door"
        assert result.cameras[1].camera_name == "Back Door"
        assert result.cameras[1].event_count == 12
        assert result.cameras[1].max_risk_score == 45

        # Verify camera 3 (no thumbnail)
        assert result.cameras[2].camera_id == "garage"
        assert result.cameras[2].thumbnail_path is None

    @pytest.mark.asyncio
    async def test_camera_activity_no_events(self, mock_db_session: AsyncMock) -> None:
        """Test camera activity handles cameras with no events (returns 0 counts)."""
        start_date = date(2026, 1, 1)
        end_date = date(2026, 1, 7)

        # Mock camera with no events
        mock_row = MagicMock()
        mock_row.camera_id = "garage"
        mock_row.camera_name = "Garage"
        mock_row.event_count = 0
        mock_row.max_risk_score = None  # No events, so no risk score
        mock_row.thumbnail_path = None

        mock_result = MagicMock()
        mock_result.all.return_value = [mock_row]
        mock_db_session.execute.return_value = mock_result

        result = await get_camera_activity(
            start_date=start_date, end_date=end_date, db=mock_db_session
        )

        # Verify zero counts are handled
        assert len(result.cameras) == 1
        assert result.cameras[0].event_count == 0
        assert result.cameras[0].max_risk_score is None
        assert result.cameras[0].thumbnail_path is None

    @pytest.mark.asyncio
    async def test_camera_activity_no_cameras(self, mock_db_session: AsyncMock) -> None:
        """Test camera activity returns empty list when no cameras exist."""
        start_date = date(2026, 1, 1)
        end_date = date(2026, 1, 7)

        # Mock empty database query result
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        result = await get_camera_activity(
            start_date=start_date, end_date=end_date, db=mock_db_session
        )

        # Verify empty response
        assert len(result.cameras) == 0

    @pytest.mark.asyncio
    async def test_camera_activity_single_day(self, mock_db_session: AsyncMock) -> None:
        """Test camera activity works for single day date range."""
        start_date = date(2026, 1, 15)
        end_date = date(2026, 1, 15)

        mock_row = MagicMock()
        mock_row.camera_id = "front_door"
        mock_row.camera_name = "Front Door"
        mock_row.event_count = 10
        mock_row.max_risk_score = 65
        mock_row.thumbnail_path = "/data/thumbnails/2026/01/front_door_single.jpg"

        mock_result = MagicMock()
        mock_result.all.return_value = [mock_row]
        mock_db_session.execute.return_value = mock_result

        result = await get_camera_activity(
            start_date=start_date, end_date=end_date, db=mock_db_session
        )

        assert len(result.cameras) == 1
        assert result.cameras[0].event_count == 10
        assert result.start_date == end_date

    @pytest.mark.asyncio
    async def test_camera_activity_invalid_date_range(self, mock_db_session: AsyncMock) -> None:
        """Test camera activity raises 400 when start_date is after end_date."""
        start_date = date(2026, 1, 10)
        end_date = date(2026, 1, 1)

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await get_camera_activity(start_date=start_date, end_date=end_date, db=mock_db_session)

        assert exc_info.value.status_code == 400
        assert "start_date must be before or equal to end_date" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_camera_activity_unbounded_date_range(self, mock_db_session: AsyncMock) -> None:
        """Test camera activity raises 400 when date range exceeds maximum allowed (NEM-4484)."""
        from datetime import timedelta

        from backend.api.routes.analytics import MAX_DATE_RANGE_DAYS

        start_date = date(2025, 1, 1)
        end_date = start_date + timedelta(days=MAX_DATE_RANGE_DAYS + 1)

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await get_camera_activity(start_date=start_date, end_date=end_date, db=mock_db_session)

        assert exc_info.value.status_code == 400
        assert "Date range exceeds maximum allowed" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_camera_activity_returns_highest_risk_thumbnail(
        self, mock_db_session: AsyncMock
    ) -> None:
        """Test that thumbnail_path corresponds to the highest-risk detection."""
        start_date = date(2026, 1, 1)
        end_date = date(2026, 1, 7)

        # Mock camera with multiple detections; thumbnail should be from highest risk
        mock_row = MagicMock()
        mock_row.camera_id = "driveway"
        mock_row.camera_name = "Driveway"
        mock_row.event_count = 25
        mock_row.max_risk_score = 92  # Critical risk
        mock_row.thumbnail_path = "/data/thumbnails/2026/01/driveway_92_risk.jpg"

        mock_result = MagicMock()
        mock_result.all.return_value = [mock_row]
        mock_db_session.execute.return_value = mock_result

        result = await get_camera_activity(
            start_date=start_date, end_date=end_date, db=mock_db_session
        )

        # Verify the thumbnail is from the highest-risk event
        assert result.cameras[0].max_risk_score == 92
        assert "92_risk" in result.cameras[0].thumbnail_path

    @pytest.mark.asyncio
    async def test_camera_activity_sorted_by_event_count(self, mock_db_session: AsyncMock) -> None:
        """Test cameras are returned sorted by event count (highest first).

        Note: Sorting happens at the SQL level, so mock should return data
        in the expected order (matching what the DB would return).
        """
        start_date = date(2026, 1, 1)
        end_date = date(2026, 1, 7)

        # Mock cameras in sorted order (as SQL would return with ORDER BY event_count DESC)
        mock_row_1 = MagicMock()
        mock_row_1.camera_id = "front_door"
        mock_row_1.camera_name = "Front Door"
        mock_row_1.event_count = 100
        mock_row_1.max_risk_score = 85
        mock_row_1.thumbnail_path = "/data/thumbnails/front.jpg"

        mock_row_2 = MagicMock()
        mock_row_2.camera_id = "back_door"
        mock_row_2.camera_name = "Back Door"
        mock_row_2.event_count = 50
        mock_row_2.max_risk_score = 60
        mock_row_2.thumbnail_path = "/data/thumbnails/back.jpg"

        mock_row_3 = MagicMock()
        mock_row_3.camera_id = "garage"
        mock_row_3.camera_name = "Garage"
        mock_row_3.event_count = 5
        mock_row_3.max_risk_score = 30
        mock_row_3.thumbnail_path = None

        mock_result = MagicMock()
        mock_result.all.return_value = [mock_row_1, mock_row_2, mock_row_3]
        mock_db_session.execute.return_value = mock_result

        result = await get_camera_activity(
            start_date=start_date, end_date=end_date, db=mock_db_session
        )

        # Verify sorting by event_count descending is preserved
        assert result.cameras[0].camera_id == "front_door"
        assert result.cameras[0].event_count == 100
        assert result.cameras[1].camera_id == "back_door"
        assert result.cameras[1].event_count == 50
        assert result.cameras[2].camera_id == "garage"
        assert result.cameras[2].event_count == 5

    @pytest.mark.asyncio
    async def test_camera_activity_risk_level_calculation(self, mock_db_session: AsyncMock) -> None:
        """Test that risk_level is computed from max_risk_score."""
        start_date = date(2026, 1, 1)
        end_date = date(2026, 1, 7)

        # Mock cameras with various risk scores
        mock_rows = []
        for camera_id, name, risk_score in [
            ("cam1", "Low Risk", 25),  # low: 0-29
            ("cam2", "Medium Risk", 45),  # medium: 30-59
            ("cam3", "High Risk", 75),  # high: 60-84
            ("cam4", "Critical Risk", 95),  # critical: 85-100
        ]:
            mock_row = MagicMock()
            mock_row.camera_id = camera_id
            mock_row.camera_name = name
            mock_row.event_count = 10
            mock_row.max_risk_score = risk_score
            mock_row.thumbnail_path = f"/data/thumbnails/{camera_id}.jpg"
            mock_rows.append(mock_row)

        mock_result = MagicMock()
        mock_result.all.return_value = mock_rows
        mock_db_session.execute.return_value = mock_result

        result = await get_camera_activity(
            start_date=start_date, end_date=end_date, db=mock_db_session
        )

        # Verify risk levels are computed correctly
        # Find cameras by ID (they may be sorted differently)
        cam_by_id = {cam.camera_id: cam for cam in result.cameras}

        assert cam_by_id["cam1"].risk_level == "low"
        assert cam_by_id["cam2"].risk_level == "medium"
        assert cam_by_id["cam3"].risk_level == "high"
        assert cam_by_id["cam4"].risk_level == "critical"

    @pytest.mark.asyncio
    async def test_camera_activity_null_risk_score_has_no_risk_level(
        self, mock_db_session: AsyncMock
    ) -> None:
        """Test that cameras with no events have null risk_level."""
        start_date = date(2026, 1, 1)
        end_date = date(2026, 1, 7)

        mock_row = MagicMock()
        mock_row.camera_id = "inactive"
        mock_row.camera_name = "Inactive Camera"
        mock_row.event_count = 0
        mock_row.max_risk_score = None
        mock_row.thumbnail_path = None

        mock_result = MagicMock()
        mock_result.all.return_value = [mock_row]
        mock_db_session.execute.return_value = mock_result

        result = await get_camera_activity(
            start_date=start_date, end_date=end_date, db=mock_db_session
        )

        assert result.cameras[0].risk_level is None
        assert result.cameras[0].max_risk_score is None
