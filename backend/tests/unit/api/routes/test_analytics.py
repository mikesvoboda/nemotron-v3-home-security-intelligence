"""Unit tests for analytics API routes.

Tests the analytics endpoints:
- GET /api/analytics/detection-trends - Detection counts aggregated by day
- GET /api/analytics/risk-history - Risk score distribution over time
- GET /api/analytics/camera-uptime - Uptime percentage per camera
- GET /api/analytics/object-distribution - Detection counts by object type

These tests follow TDD methodology - comprehensive coverage of happy paths,
error cases, and edge cases with proper mocking of database operations.
"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.api.routes.analytics import (
    get_camera_uptime,
    get_detection_trends,
    get_object_distribution,
    get_risk_history,
)
from backend.api.schemas.analytics import (
    CameraUptimeResponse,
    DetectionTrendsResponse,
    ObjectDistributionResponse,
    RiskHistoryResponse,
)


class TestDetectionTrends:
    """Tests for GET /api/analytics/detection-trends endpoint."""

    @pytest.mark.asyncio
    async def test_detection_trends_with_data(self, mock_db_session: AsyncMock) -> None:
        """Test detection trends returns aggregated data when detections exist."""
        start_date = date(2025, 1, 1)
        end_date = date(2025, 1, 3)

        # Mock database query result with detection counts
        mock_row_1 = MagicMock()
        mock_row_1.detection_date = date(2025, 1, 1)
        mock_row_1.detection_count = 10

        mock_row_2 = MagicMock()
        mock_row_2.detection_date = date(2025, 1, 3)
        mock_row_2.detection_count = 5

        mock_result = MagicMock()
        mock_result.all.return_value = [mock_row_1, mock_row_2]
        mock_db_session.execute.return_value = mock_result

        result = await get_detection_trends(
            start_date=start_date, end_date=end_date, db=mock_db_session
        )

        # Verify response structure
        assert isinstance(result, DetectionTrendsResponse)
        assert result.start_date == start_date
        assert result.end_date == end_date
        assert result.total_detections == 15
        assert len(result.data_points) == 3

        # Verify data points (should fill gaps with 0)
        assert result.data_points[0].date == date(2025, 1, 1)
        assert result.data_points[0].count == 10
        assert result.data_points[1].date == date(2025, 1, 2)
        assert result.data_points[1].count == 0  # Gap filled
        assert result.data_points[2].date == date(2025, 1, 3)
        assert result.data_points[2].count == 5

    @pytest.mark.asyncio
    async def test_detection_trends_no_data(self, mock_db_session: AsyncMock) -> None:
        """Test detection trends returns all zeros when no detections exist."""
        start_date = date(2025, 1, 1)
        end_date = date(2025, 1, 2)

        # Mock empty database query result
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        result = await get_detection_trends(
            start_date=start_date, end_date=end_date, db=mock_db_session
        )

        # Verify response has zero counts
        assert result.total_detections == 0
        assert len(result.data_points) == 2
        assert result.data_points[0].count == 0
        assert result.data_points[1].count == 0

    @pytest.mark.asyncio
    async def test_detection_trends_single_day(self, mock_db_session: AsyncMock) -> None:
        """Test detection trends works for single day date range."""
        start_date = date(2025, 1, 1)
        end_date = date(2025, 1, 1)

        # Mock database query result
        mock_row = MagicMock()
        mock_row.detection_date = date(2025, 1, 1)
        mock_row.detection_count = 42

        mock_result = MagicMock()
        mock_result.all.return_value = [mock_row]
        mock_db_session.execute.return_value = mock_result

        result = await get_detection_trends(
            start_date=start_date, end_date=end_date, db=mock_db_session
        )

        # Verify single data point
        assert len(result.data_points) == 1
        assert result.data_points[0].count == 42
        assert result.total_detections == 42

    @pytest.mark.asyncio
    async def test_detection_trends_invalid_date_range(self, mock_db_session: AsyncMock) -> None:
        """Test detection trends raises 400 when start_date is after end_date."""
        start_date = date(2025, 1, 5)
        end_date = date(2025, 1, 1)

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await get_detection_trends(start_date=start_date, end_date=end_date, db=mock_db_session)

        assert exc_info.value.status_code == 400
        assert "start_date must be before or equal to end_date" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_detection_trends_long_range(self, mock_db_session: AsyncMock) -> None:
        """Test detection trends handles long date ranges correctly."""
        start_date = date(2025, 1, 1)
        end_date = date(2025, 1, 31)  # 31 days

        # Mock sparse data (only 3 days with detections)
        mock_row_1 = MagicMock()
        mock_row_1.detection_date = date(2025, 1, 5)
        mock_row_1.detection_count = 10

        mock_row_2 = MagicMock()
        mock_row_2.detection_date = date(2025, 1, 15)
        mock_row_2.detection_count = 20

        mock_row_3 = MagicMock()
        mock_row_3.detection_date = date(2025, 1, 25)
        mock_row_3.detection_count = 30

        mock_result = MagicMock()
        mock_result.all.return_value = [mock_row_1, mock_row_2, mock_row_3]
        mock_db_session.execute.return_value = mock_result

        result = await get_detection_trends(
            start_date=start_date, end_date=end_date, db=mock_db_session
        )

        # Verify all 31 days are present
        assert len(result.data_points) == 31
        assert result.total_detections == 60

        # Verify specific days
        assert result.data_points[4].count == 10  # Jan 5
        assert result.data_points[14].count == 20  # Jan 15
        assert result.data_points[24].count == 30  # Jan 25

        # Verify other days are zero
        assert result.data_points[0].count == 0  # Jan 1
        assert result.data_points[10].count == 0  # Jan 11


class TestRiskHistory:
    """Tests for GET /api/analytics/risk-history endpoint."""

    @pytest.mark.asyncio
    async def test_risk_history_with_data(self, mock_db_session: AsyncMock) -> None:
        """Test risk history returns aggregated risk level data."""
        start_date = date(2025, 1, 1)
        end_date = date(2025, 1, 2)

        # Mock database query result with risk level counts
        mock_row_1 = MagicMock()
        mock_row_1.event_date = date(2025, 1, 1)
        mock_row_1.risk_level = "low"
        mock_row_1.event_count = 10

        mock_row_2 = MagicMock()
        mock_row_2.event_date = date(2025, 1, 1)
        mock_row_2.risk_level = "high"
        mock_row_2.event_count = 2

        mock_row_3 = MagicMock()
        mock_row_3.event_date = date(2025, 1, 2)
        mock_row_3.risk_level = "medium"
        mock_row_3.event_count = 5

        mock_result = MagicMock()
        mock_result.all.return_value = [mock_row_1, mock_row_2, mock_row_3]
        mock_db_session.execute.return_value = mock_result

        result = await get_risk_history(
            start_date=start_date, end_date=end_date, db=mock_db_session
        )

        # Verify response structure
        assert isinstance(result, RiskHistoryResponse)
        assert result.start_date == start_date
        assert result.end_date == end_date
        assert len(result.data_points) == 2

        # Verify day 1 counts
        assert result.data_points[0].date == date(2025, 1, 1)
        assert result.data_points[0].low == 10
        assert result.data_points[0].medium == 0
        assert result.data_points[0].high == 2
        assert result.data_points[0].critical == 0

        # Verify day 2 counts
        assert result.data_points[1].date == date(2025, 1, 2)
        assert result.data_points[1].low == 0
        assert result.data_points[1].medium == 5
        assert result.data_points[1].high == 0
        assert result.data_points[1].critical == 0

    @pytest.mark.asyncio
    async def test_risk_history_no_data(self, mock_db_session: AsyncMock) -> None:
        """Test risk history returns all zeros when no events exist."""
        start_date = date(2025, 1, 1)
        end_date = date(2025, 1, 3)

        # Mock empty database query result
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        result = await get_risk_history(
            start_date=start_date, end_date=end_date, db=mock_db_session
        )

        # Verify all days have zero counts
        assert len(result.data_points) == 3
        for data_point in result.data_points:
            assert data_point.low == 0
            assert data_point.medium == 0
            assert data_point.high == 0
            assert data_point.critical == 0

    @pytest.mark.asyncio
    async def test_risk_history_all_risk_levels(self, mock_db_session: AsyncMock) -> None:
        """Test risk history handles all risk levels correctly."""
        start_date = date(2025, 1, 1)
        end_date = date(2025, 1, 1)

        # Mock all risk levels for a single day
        mock_rows = []
        for risk_level, count in [("low", 10), ("medium", 5), ("high", 3), ("critical", 1)]:
            mock_row = MagicMock()
            mock_row.event_date = date(2025, 1, 1)
            mock_row.risk_level = risk_level
            mock_row.event_count = count
            mock_rows.append(mock_row)

        mock_result = MagicMock()
        mock_result.all.return_value = mock_rows
        mock_db_session.execute.return_value = mock_result

        result = await get_risk_history(
            start_date=start_date, end_date=end_date, db=mock_db_session
        )

        # Verify all risk levels are present
        assert len(result.data_points) == 1
        assert result.data_points[0].low == 10
        assert result.data_points[0].medium == 5
        assert result.data_points[0].high == 3
        assert result.data_points[0].critical == 1

    @pytest.mark.asyncio
    async def test_risk_history_invalid_date_range(self, mock_db_session: AsyncMock) -> None:
        """Test risk history raises 400 when start_date is after end_date."""
        start_date = date(2025, 1, 5)
        end_date = date(2025, 1, 1)

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await get_risk_history(start_date=start_date, end_date=end_date, db=mock_db_session)

        assert exc_info.value.status_code == 400
        assert "start_date must be before or equal to end_date" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_risk_history_fills_gaps(self, mock_db_session: AsyncMock) -> None:
        """Test risk history fills date gaps with zeros."""
        start_date = date(2025, 1, 1)
        end_date = date(2025, 1, 5)

        # Mock data only for day 1 and day 5
        mock_row_1 = MagicMock()
        mock_row_1.event_date = date(2025, 1, 1)
        mock_row_1.risk_level = "high"
        mock_row_1.event_count = 5

        mock_row_2 = MagicMock()
        mock_row_2.event_date = date(2025, 1, 5)
        mock_row_2.risk_level = "low"
        mock_row_2.event_count = 3

        mock_result = MagicMock()
        mock_result.all.return_value = [mock_row_1, mock_row_2]
        mock_db_session.execute.return_value = mock_result

        result = await get_risk_history(
            start_date=start_date, end_date=end_date, db=mock_db_session
        )

        # Verify all 5 days are present
        assert len(result.data_points) == 5

        # Day 1 should have data
        assert result.data_points[0].high == 5

        # Days 2-4 should be all zeros
        for i in range(1, 4):
            assert result.data_points[i].low == 0
            assert result.data_points[i].medium == 0
            assert result.data_points[i].high == 0
            assert result.data_points[i].critical == 0

        # Day 5 should have data
        assert result.data_points[4].low == 3


class TestCameraUptime:
    """Tests for GET /api/analytics/camera-uptime endpoint."""

    @pytest.mark.asyncio
    async def test_camera_uptime_with_data(self, mock_db_session: AsyncMock) -> None:
        """Test camera uptime returns uptime percentage and detection counts."""
        start_date = date(2025, 1, 1)
        end_date = date(2025, 1, 10)  # 10 days

        # Mock database query result with camera data
        mock_row_1 = MagicMock()
        mock_row_1.id = "front_door"
        mock_row_1.name = "Front Door"
        mock_row_1.active_days = 10  # Active all 10 days
        mock_row_1.detection_count = 100

        mock_row_2 = MagicMock()
        mock_row_2.id = "back_door"
        mock_row_2.name = "Back Door"
        mock_row_2.active_days = 5  # Active 5 out of 10 days
        mock_row_2.detection_count = 50

        mock_result = MagicMock()
        mock_result.all.return_value = [mock_row_1, mock_row_2]
        mock_db_session.execute.return_value = mock_result

        result = await get_camera_uptime(
            start_date=start_date, end_date=end_date, db=mock_db_session
        )

        # Verify response structure
        assert isinstance(result, CameraUptimeResponse)
        assert result.start_date == start_date
        assert result.end_date == end_date
        assert len(result.cameras) == 2

        # Verify camera 1 (100% uptime)
        assert result.cameras[0].camera_id == "front_door"
        assert result.cameras[0].camera_name == "Front Door"
        assert result.cameras[0].uptime_percentage == 100.0
        assert result.cameras[0].detection_count == 100

        # Verify camera 2 (50% uptime)
        assert result.cameras[1].camera_id == "back_door"
        assert result.cameras[1].camera_name == "Back Door"
        assert result.cameras[1].uptime_percentage == 50.0
        assert result.cameras[1].detection_count == 50

    @pytest.mark.asyncio
    async def test_camera_uptime_no_detections(self, mock_db_session: AsyncMock) -> None:
        """Test camera uptime handles cameras with no detections (0% uptime)."""
        start_date = date(2025, 1, 1)
        end_date = date(2025, 1, 10)

        # Mock camera with no detections
        mock_row = MagicMock()
        mock_row.id = "garage"
        mock_row.name = "Garage"
        mock_row.active_days = 0
        mock_row.detection_count = 0

        mock_result = MagicMock()
        mock_result.all.return_value = [mock_row]
        mock_db_session.execute.return_value = mock_result

        result = await get_camera_uptime(
            start_date=start_date, end_date=end_date, db=mock_db_session
        )

        # Verify 0% uptime
        assert len(result.cameras) == 1
        assert result.cameras[0].uptime_percentage == 0.0
        assert result.cameras[0].detection_count == 0

    @pytest.mark.asyncio
    async def test_camera_uptime_single_day(self, mock_db_session: AsyncMock) -> None:
        """Test camera uptime works for single day date range."""
        start_date = date(2025, 1, 1)
        end_date = date(2025, 1, 1)

        # Mock camera active on the single day
        mock_row = MagicMock()
        mock_row.id = "front_door"
        mock_row.name = "Front Door"
        mock_row.active_days = 1
        mock_row.detection_count = 25

        mock_result = MagicMock()
        mock_result.all.return_value = [mock_row]
        mock_db_session.execute.return_value = mock_result

        result = await get_camera_uptime(
            start_date=start_date, end_date=end_date, db=mock_db_session
        )

        # Verify 100% uptime for single day
        assert len(result.cameras) == 1
        assert result.cameras[0].uptime_percentage == 100.0
        assert result.cameras[0].detection_count == 25

    @pytest.mark.asyncio
    async def test_camera_uptime_invalid_date_range(self, mock_db_session: AsyncMock) -> None:
        """Test camera uptime raises 400 when start_date is after end_date."""
        start_date = date(2025, 1, 10)
        end_date = date(2025, 1, 1)

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await get_camera_uptime(start_date=start_date, end_date=end_date, db=mock_db_session)

        assert exc_info.value.status_code == 400
        assert "start_date must be before or equal to end_date" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_camera_uptime_partial_uptime_calculation(
        self, mock_db_session: AsyncMock
    ) -> None:
        """Test camera uptime correctly calculates partial uptime percentages."""
        start_date = date(2025, 1, 1)
        end_date = date(2025, 1, 10)  # 10 days

        # Mock camera active 3 out of 10 days
        mock_row = MagicMock()
        mock_row.id = "side_yard"
        mock_row.name = "Side Yard"
        mock_row.active_days = 3
        mock_row.detection_count = 15

        mock_result = MagicMock()
        mock_result.all.return_value = [mock_row]
        mock_db_session.execute.return_value = mock_result

        result = await get_camera_uptime(
            start_date=start_date, end_date=end_date, db=mock_db_session
        )

        # Verify 30% uptime
        assert result.cameras[0].uptime_percentage == 30.0

    @pytest.mark.asyncio
    async def test_camera_uptime_null_detection_count(self, mock_db_session: AsyncMock) -> None:
        """Test camera uptime handles NULL detection counts (converts to 0)."""
        start_date = date(2025, 1, 1)
        end_date = date(2025, 1, 10)

        # Mock camera with NULL detection_count
        mock_row = MagicMock()
        mock_row.id = "test_camera"
        mock_row.name = "Test Camera"
        mock_row.active_days = 0
        mock_row.detection_count = None  # NULL from database

        mock_result = MagicMock()
        mock_result.all.return_value = [mock_row]
        mock_db_session.execute.return_value = mock_result

        result = await get_camera_uptime(
            start_date=start_date, end_date=end_date, db=mock_db_session
        )

        # Verify NULL is converted to 0
        assert result.cameras[0].detection_count == 0


class TestObjectDistribution:
    """Tests for GET /api/analytics/object-distribution endpoint."""

    @pytest.mark.asyncio
    async def test_object_distribution_with_data(self, mock_db_session: AsyncMock) -> None:
        """Test object distribution returns counts and percentages by object type."""
        start_date = date(2025, 1, 1)
        end_date = date(2025, 1, 10)

        # Mock database query result with object type counts
        mock_row_1 = MagicMock()
        mock_row_1.object_type = "person"
        mock_row_1.object_count = 100

        mock_row_2 = MagicMock()
        mock_row_2.object_type = "car"
        mock_row_2.object_count = 50

        mock_row_3 = MagicMock()
        mock_row_3.object_type = "dog"
        mock_row_3.object_count = 25

        mock_result = MagicMock()
        mock_result.all.return_value = [mock_row_1, mock_row_2, mock_row_3]
        mock_db_session.execute.return_value = mock_result

        result = await get_object_distribution(
            start_date=start_date, end_date=end_date, db=mock_db_session
        )

        # Verify response structure
        assert isinstance(result, ObjectDistributionResponse)
        assert result.start_date == start_date
        assert result.end_date == end_date
        assert result.total_detections == 175
        assert len(result.object_types) == 3

        # Verify person (100/175 = 57.14%)
        assert result.object_types[0].object_type == "person"
        assert result.object_types[0].count == 100
        assert result.object_types[0].percentage == 57.14

        # Verify car (50/175 = 28.57%)
        assert result.object_types[1].object_type == "car"
        assert result.object_types[1].count == 50
        assert result.object_types[1].percentage == 28.57

        # Verify dog (25/175 = 14.29%)
        assert result.object_types[2].object_type == "dog"
        assert result.object_types[2].count == 25
        assert result.object_types[2].percentage == 14.29

    @pytest.mark.asyncio
    async def test_object_distribution_no_data(self, mock_db_session: AsyncMock) -> None:
        """Test object distribution returns empty list when no detections exist."""
        start_date = date(2025, 1, 1)
        end_date = date(2025, 1, 10)

        # Mock empty database query result
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        result = await get_object_distribution(
            start_date=start_date, end_date=end_date, db=mock_db_session
        )

        # Verify empty response
        assert result.total_detections == 0
        assert len(result.object_types) == 0

    @pytest.mark.asyncio
    async def test_object_distribution_single_type(self, mock_db_session: AsyncMock) -> None:
        """Test object distribution handles single object type (100% percentage)."""
        start_date = date(2025, 1, 1)
        end_date = date(2025, 1, 10)

        # Mock single object type
        mock_row = MagicMock()
        mock_row.object_type = "person"
        mock_row.object_count = 42

        mock_result = MagicMock()
        mock_result.all.return_value = [mock_row]
        mock_db_session.execute.return_value = mock_result

        result = await get_object_distribution(
            start_date=start_date, end_date=end_date, db=mock_db_session
        )

        # Verify 100% percentage
        assert len(result.object_types) == 1
        assert result.object_types[0].percentage == 100.0

    @pytest.mark.asyncio
    async def test_object_distribution_invalid_date_range(self, mock_db_session: AsyncMock) -> None:
        """Test object distribution raises 400 when start_date is after end_date."""
        start_date = date(2025, 1, 10)
        end_date = date(2025, 1, 1)

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await get_object_distribution(
                start_date=start_date, end_date=end_date, db=mock_db_session
            )

        assert exc_info.value.status_code == 400
        assert "start_date must be before or equal to end_date" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_object_distribution_percentage_rounding(
        self, mock_db_session: AsyncMock
    ) -> None:
        """Test object distribution rounds percentages to 2 decimal places."""
        start_date = date(2025, 1, 1)
        end_date = date(2025, 1, 10)

        # Mock data that produces non-round percentages
        mock_row_1 = MagicMock()
        mock_row_1.object_type = "person"
        mock_row_1.object_count = 10

        mock_row_2 = MagicMock()
        mock_row_2.object_type = "car"
        mock_row_2.object_count = 3

        mock_result = MagicMock()
        mock_result.all.return_value = [mock_row_1, mock_row_2]
        mock_db_session.execute.return_value = mock_result

        result = await get_object_distribution(
            start_date=start_date, end_date=end_date, db=mock_db_session
        )

        # Verify percentages are rounded (10/13 = 76.92%, 3/13 = 23.08%)
        assert result.object_types[0].percentage == 76.92
        assert result.object_types[1].percentage == 23.08

    @pytest.mark.asyncio
    async def test_object_distribution_many_types(self, mock_db_session: AsyncMock) -> None:
        """Test object distribution handles many object types correctly."""
        start_date = date(2025, 1, 1)
        end_date = date(2025, 1, 10)

        # Mock 10 different object types with various counts
        mock_rows = []
        object_types = [
            ("person", 100),
            ("car", 80),
            ("dog", 60),
            ("cat", 40),
            ("truck", 30),
            ("bicycle", 20),
            ("motorcycle", 15),
            ("bird", 10),
            ("deer", 5),
            ("unknown", 2),
        ]

        for obj_type, count in object_types:
            mock_row = MagicMock()
            mock_row.object_type = obj_type
            mock_row.object_count = count
            mock_rows.append(mock_row)

        mock_result = MagicMock()
        mock_result.all.return_value = mock_rows
        mock_db_session.execute.return_value = mock_result

        result = await get_object_distribution(
            start_date=start_date, end_date=end_date, db=mock_db_session
        )

        # Verify all types are present
        assert len(result.object_types) == 10
        assert result.total_detections == 362

        # Verify percentages sum to approximately 100% (allowing for rounding)
        total_percentage = sum(obj.percentage for obj in result.object_types)
        assert 99.9 <= total_percentage <= 100.1
