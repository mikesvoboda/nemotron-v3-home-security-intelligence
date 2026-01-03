"""Unit tests for camera baseline API routes.

Tests the baseline endpoints:
- GET /api/cameras/{camera_id}/baseline
- GET /api/cameras/{camera_id}/baseline/anomalies

These tests follow TDD methodology - written before implementation.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.api.schemas.baseline import (
    AnomalyListResponse,
    BaselineSummaryResponse,
    CurrentDeviation,
    DailyPattern,
    DeviationInterpretation,
    HourlyPattern,
    ObjectBaseline,
)


class TestGetCameraBaseline:
    """Tests for GET /api/cameras/{camera_id}/baseline endpoint."""

    @pytest.mark.asyncio
    async def test_get_baseline_camera_not_found(self) -> None:
        """Test that baseline endpoint returns 404 for non-existent camera."""
        from backend.api.routes.cameras import get_camera_baseline

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(Exception) as exc_info:
            await get_camera_baseline("nonexistent_camera", db=mock_db)

        assert exc_info.value.status_code == 404
        assert "not found" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_get_baseline_empty_data(self) -> None:
        """Test baseline endpoint returns empty baseline for camera with no data."""
        from backend.api.routes.cameras import get_camera_baseline

        mock_db = AsyncMock()

        # Mock camera query
        mock_camera = MagicMock()
        mock_camera.id = "test_camera"
        mock_camera.name = "Test Camera"
        mock_camera_result = MagicMock()
        mock_camera_result.scalar_one_or_none.return_value = mock_camera
        mock_db.execute.return_value = mock_camera_result

        # Mock baseline service
        mock_baseline_service = MagicMock()
        mock_baseline_service.get_camera_baseline_summary = AsyncMock(
            return_value={
                "camera_id": "test_camera",
                "activity_baseline_count": 0,
                "class_baseline_count": 0,
                "unique_classes": 0,
                "top_classes": [],
                "peak_hours": [],
            }
        )
        mock_baseline_service.get_hourly_patterns = AsyncMock(return_value={})
        mock_baseline_service.get_daily_patterns = AsyncMock(return_value={})
        mock_baseline_service.get_object_baselines = AsyncMock(return_value={})
        mock_baseline_service.get_current_deviation = AsyncMock(return_value=None)
        mock_baseline_service.get_baseline_established_date = AsyncMock(return_value=None)

        with patch(
            "backend.api.routes.cameras.get_baseline_service",
            return_value=mock_baseline_service,
        ):
            result = await get_camera_baseline("test_camera", db=mock_db)

        assert isinstance(result, BaselineSummaryResponse)
        assert result.camera_id == "test_camera"
        assert result.camera_name == "Test Camera"
        assert result.data_points == 0
        assert result.hourly_patterns == {}
        assert result.daily_patterns == {}
        assert result.object_baselines == {}
        assert result.current_deviation is None

    @pytest.mark.asyncio
    async def test_get_baseline_with_data(self) -> None:
        """Test baseline endpoint returns complete data for camera with baselines."""
        from backend.api.routes.cameras import get_camera_baseline

        mock_db = AsyncMock()

        # Mock camera query
        mock_camera = MagicMock()
        mock_camera.id = "front_door"
        mock_camera.name = "Front Door"
        mock_camera_result = MagicMock()
        mock_camera_result.scalar_one_or_none.return_value = mock_camera
        mock_db.execute.return_value = mock_camera_result

        # Mock baseline service with data
        now = datetime.now(UTC)
        mock_baseline_service = MagicMock()
        mock_baseline_service.get_camera_baseline_summary = AsyncMock(
            return_value={
                "camera_id": "front_door",
                "activity_baseline_count": 168,
                "class_baseline_count": 48,
                "unique_classes": 2,
                "top_classes": [
                    {"class": "person", "total_frequency": 100.0},
                    {"class": "vehicle", "total_frequency": 20.0},
                ],
                "peak_hours": [
                    {"hour": 17, "total_activity": 50.0},
                    {"hour": 8, "total_activity": 30.0},
                ],
            }
        )
        mock_baseline_service.get_hourly_patterns = AsyncMock(
            return_value={
                "0": HourlyPattern(avg_detections=0.5, std_dev=0.3, sample_count=30),
                "17": HourlyPattern(avg_detections=5.2, std_dev=1.1, sample_count=30),
            }
        )
        mock_baseline_service.get_daily_patterns = AsyncMock(
            return_value={
                "monday": DailyPattern(avg_detections=45.0, peak_hour=17, total_samples=24),
                "friday": DailyPattern(avg_detections=55.0, peak_hour=18, total_samples=24),
            }
        )
        mock_baseline_service.get_object_baselines = AsyncMock(
            return_value={
                "person": ObjectBaseline(avg_hourly=2.3, peak_hour=17, total_detections=550),
                "vehicle": ObjectBaseline(avg_hourly=0.5, peak_hour=8, total_detections=120),
            }
        )
        mock_baseline_service.get_current_deviation = AsyncMock(
            return_value=CurrentDeviation(
                score=1.8,
                interpretation=DeviationInterpretation.SLIGHTLY_ABOVE_NORMAL,
                contributing_factors=["person_count_elevated"],
            )
        )
        mock_baseline_service.get_baseline_established_date = AsyncMock(
            return_value=now - timedelta(days=30)
        )

        with patch(
            "backend.api.routes.cameras.get_baseline_service",
            return_value=mock_baseline_service,
        ):
            result = await get_camera_baseline("front_door", db=mock_db)

        assert isinstance(result, BaselineSummaryResponse)
        assert result.camera_id == "front_door"
        assert result.camera_name == "Front Door"
        assert result.data_points == 168 + 48  # activity + class baselines
        assert "0" in result.hourly_patterns
        assert "17" in result.hourly_patterns
        assert result.hourly_patterns["17"].avg_detections == 5.2
        assert "monday" in result.daily_patterns
        assert result.daily_patterns["monday"].peak_hour == 17
        assert "person" in result.object_baselines
        assert result.object_baselines["person"].total_detections == 550
        assert result.current_deviation is not None
        assert result.current_deviation.score == 1.8


class TestGetCameraBaselineAnomalies:
    """Tests for GET /api/cameras/{camera_id}/baseline/anomalies endpoint."""

    @pytest.mark.asyncio
    async def test_get_anomalies_camera_not_found(self) -> None:
        """Test that anomalies endpoint returns 404 for non-existent camera."""
        from backend.api.routes.cameras import get_camera_baseline_anomalies

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(Exception) as exc_info:
            await get_camera_baseline_anomalies("nonexistent_camera", days=7, db=mock_db)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_anomalies_no_anomalies(self) -> None:
        """Test anomalies endpoint returns empty list when no anomalies exist."""
        from backend.api.routes.cameras import get_camera_baseline_anomalies

        mock_db = AsyncMock()

        # Mock camera query
        mock_camera = MagicMock()
        mock_camera.id = "test_camera"
        mock_camera_result = MagicMock()
        mock_camera_result.scalar_one_or_none.return_value = mock_camera
        mock_db.execute.return_value = mock_camera_result

        mock_baseline_service = MagicMock()
        mock_baseline_service.get_recent_anomalies = AsyncMock(return_value=[])

        with patch(
            "backend.api.routes.cameras.get_baseline_service",
            return_value=mock_baseline_service,
        ):
            result = await get_camera_baseline_anomalies("test_camera", days=7, db=mock_db)

        assert isinstance(result, AnomalyListResponse)
        assert result.camera_id == "test_camera"
        assert result.anomalies == []
        assert result.count == 0
        assert result.period_days == 7

    @pytest.mark.asyncio
    async def test_get_anomalies_with_data(self) -> None:
        """Test anomalies endpoint returns anomaly events."""
        from backend.api.routes.cameras import get_camera_baseline_anomalies
        from backend.api.schemas.baseline import AnomalyEvent

        mock_db = AsyncMock()

        # Mock camera query
        mock_camera = MagicMock()
        mock_camera.id = "front_door"
        mock_camera_result = MagicMock()
        mock_camera_result.scalar_one_or_none.return_value = mock_camera
        mock_db.execute.return_value = mock_camera_result

        now = datetime.now(UTC)
        mock_anomalies = [
            AnomalyEvent(
                timestamp=now - timedelta(hours=2),
                detection_class="vehicle",
                anomaly_score=0.95,
                expected_frequency=0.1,
                observed_frequency=5.0,
                reason="Vehicle detected at unusual hour",
            ),
            AnomalyEvent(
                timestamp=now - timedelta(hours=5),
                detection_class="person",
                anomaly_score=0.85,
                expected_frequency=0.5,
                observed_frequency=10.0,
                reason="Unusually high person activity",
            ),
        ]

        mock_baseline_service = MagicMock()
        mock_baseline_service.get_recent_anomalies = AsyncMock(return_value=mock_anomalies)

        with patch(
            "backend.api.routes.cameras.get_baseline_service",
            return_value=mock_baseline_service,
        ):
            result = await get_camera_baseline_anomalies("front_door", days=7, db=mock_db)

        assert isinstance(result, AnomalyListResponse)
        assert result.camera_id == "front_door"
        assert result.count == 2
        assert len(result.anomalies) == 2
        assert result.anomalies[0].detection_class == "vehicle"
        assert result.anomalies[0].anomaly_score == 0.95
        assert result.anomalies[1].detection_class == "person"

    @pytest.mark.asyncio
    async def test_get_anomalies_custom_days(self) -> None:
        """Test anomalies endpoint respects days parameter."""
        from backend.api.routes.cameras import get_camera_baseline_anomalies

        mock_db = AsyncMock()

        # Mock camera query
        mock_camera = MagicMock()
        mock_camera.id = "test_camera"
        mock_camera_result = MagicMock()
        mock_camera_result.scalar_one_or_none.return_value = mock_camera
        mock_db.execute.return_value = mock_camera_result

        mock_baseline_service = MagicMock()
        mock_baseline_service.get_recent_anomalies = AsyncMock(return_value=[])

        with patch(
            "backend.api.routes.cameras.get_baseline_service",
            return_value=mock_baseline_service,
        ):
            result = await get_camera_baseline_anomalies("test_camera", days=14, db=mock_db)

        # Verify service was called with correct days parameter
        mock_baseline_service.get_recent_anomalies.assert_called_once()
        call_args = mock_baseline_service.get_recent_anomalies.call_args
        assert call_args.kwargs.get("days") == 14 or call_args.args[1] == 14
        assert result.period_days == 14


class TestBaselineSchemas:
    """Tests for baseline Pydantic schemas."""

    def test_hourly_pattern_validation(self) -> None:
        """Test HourlyPattern schema validation."""
        pattern = HourlyPattern(avg_detections=2.5, std_dev=0.8, sample_count=30)
        assert pattern.avg_detections == 2.5
        assert pattern.std_dev == 0.8
        assert pattern.sample_count == 30

    def test_hourly_pattern_rejects_negative(self) -> None:
        """Test HourlyPattern rejects negative values."""
        with pytest.raises(ValueError):
            HourlyPattern(avg_detections=-1.0, std_dev=0.8, sample_count=30)

    def test_daily_pattern_validation(self) -> None:
        """Test DailyPattern schema validation."""
        pattern = DailyPattern(avg_detections=45.0, peak_hour=17, total_samples=168)
        assert pattern.avg_detections == 45.0
        assert pattern.peak_hour == 17
        assert pattern.total_samples == 168

    def test_daily_pattern_hour_bounds(self) -> None:
        """Test DailyPattern enforces hour bounds (0-23)."""
        # Valid boundary values
        pattern_low = DailyPattern(avg_detections=10.0, peak_hour=0, total_samples=10)
        assert pattern_low.peak_hour == 0

        pattern_high = DailyPattern(avg_detections=10.0, peak_hour=23, total_samples=10)
        assert pattern_high.peak_hour == 23

        # Invalid values
        with pytest.raises(ValueError):
            DailyPattern(avg_detections=10.0, peak_hour=24, total_samples=10)

        with pytest.raises(ValueError):
            DailyPattern(avg_detections=10.0, peak_hour=-1, total_samples=10)

    def test_current_deviation_interpretation_enum(self) -> None:
        """Test CurrentDeviation uses correct interpretation enum values."""
        deviation = CurrentDeviation(
            score=1.8,
            interpretation=DeviationInterpretation.SLIGHTLY_ABOVE_NORMAL,
            contributing_factors=["test_factor"],
        )
        assert deviation.interpretation == DeviationInterpretation.SLIGHTLY_ABOVE_NORMAL
        assert deviation.interpretation.value == "slightly_above_normal"

    def test_baseline_summary_response_optional_fields(self) -> None:
        """Test BaselineSummaryResponse handles optional/empty fields."""
        response = BaselineSummaryResponse(
            camera_id="test",
            camera_name="Test Camera",
            baseline_established=None,
            data_points=0,
            hourly_patterns={},
            daily_patterns={},
            object_baselines={},
            current_deviation=None,
        )
        assert response.baseline_established is None
        assert response.current_deviation is None
        assert response.data_points == 0

    def test_anomaly_event_score_bounds(self) -> None:
        """Test AnomalyEvent anomaly_score is bounded 0.0-1.0."""
        from backend.api.schemas.baseline import AnomalyEvent

        now = datetime.now(UTC)

        # Valid boundary values
        event_low = AnomalyEvent(
            timestamp=now,
            detection_class="person",
            anomaly_score=0.0,
            expected_frequency=1.0,
            observed_frequency=1.0,
            reason="test",
        )
        assert event_low.anomaly_score == 0.0

        event_high = AnomalyEvent(
            timestamp=now,
            detection_class="person",
            anomaly_score=1.0,
            expected_frequency=1.0,
            observed_frequency=1.0,
            reason="test",
        )
        assert event_high.anomaly_score == 1.0

        # Invalid values
        with pytest.raises(ValueError):
            AnomalyEvent(
                timestamp=now,
                detection_class="person",
                anomaly_score=1.5,
                expected_frequency=1.0,
                observed_frequency=1.0,
                reason="test",
            )

        with pytest.raises(ValueError):
            AnomalyEvent(
                timestamp=now,
                detection_class="person",
                anomaly_score=-0.1,
                expected_frequency=1.0,
                observed_frequency=1.0,
                reason="test",
            )

    def test_anomaly_list_response(self) -> None:
        """Test AnomalyListResponse with multiple anomalies."""
        from backend.api.schemas.baseline import AnomalyEvent

        now = datetime.now(UTC)
        anomalies = [
            AnomalyEvent(
                timestamp=now,
                detection_class="vehicle",
                anomaly_score=0.9,
                expected_frequency=0.1,
                observed_frequency=2.0,
                reason="test 1",
            ),
            AnomalyEvent(
                timestamp=now - timedelta(hours=1),
                detection_class="person",
                anomaly_score=0.8,
                expected_frequency=0.5,
                observed_frequency=5.0,
                reason="test 2",
            ),
        ]

        response = AnomalyListResponse(
            camera_id="test",
            anomalies=anomalies,
            count=2,
            period_days=7,
        )

        assert response.count == 2
        assert len(response.anomalies) == 2
        assert response.period_days == 7
