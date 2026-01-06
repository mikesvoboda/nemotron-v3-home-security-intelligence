"""Unit tests for camera baseline API routes.

Tests the baseline endpoints:
- GET /api/cameras/{camera_id}/baseline
- GET /api/cameras/{camera_id}/baseline/anomalies
- GET /api/cameras/{camera_id}/baseline/activity
- GET /api/cameras/{camera_id}/baseline/classes

These tests follow TDD methodology - written before implementation.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.api.schemas.baseline import (
    ActivityBaselineEntry,
    ActivityBaselineResponse,
    AnomalyListResponse,
    BaselineSummaryResponse,
    ClassBaselineEntry,
    ClassBaselineResponse,
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


class TestGetCameraActivityBaseline:
    """Tests for GET /api/cameras/{camera_id}/baseline/activity endpoint."""

    @pytest.mark.asyncio
    async def test_get_activity_baseline_camera_not_found(self) -> None:
        """Test that activity baseline endpoint returns 404 for non-existent camera."""
        from backend.api.routes.cameras import get_camera_activity_baseline

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(Exception) as exc_info:
            await get_camera_activity_baseline("nonexistent_camera", db=mock_db)

        assert exc_info.value.status_code == 404
        assert "not found" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_get_activity_baseline_empty_data(self) -> None:
        """Test activity baseline endpoint returns empty response for camera with no data."""
        from backend.api.routes.cameras import get_camera_activity_baseline

        mock_db = AsyncMock()

        # Mock camera query
        mock_camera = MagicMock()
        mock_camera.id = "test_camera"
        mock_camera.name = "Test Camera"
        mock_camera_result = MagicMock()
        mock_camera_result.scalar_one_or_none.return_value = mock_camera
        mock_db.execute.return_value = mock_camera_result

        # Mock baseline service returning empty list
        mock_baseline_service = MagicMock()
        mock_baseline_service.get_activity_baselines_raw = AsyncMock(return_value=[])
        mock_baseline_service.min_samples = 10

        with patch(
            "backend.api.routes.cameras.get_baseline_service",
            return_value=mock_baseline_service,
        ):
            result = await get_camera_activity_baseline("test_camera", db=mock_db)

        assert isinstance(result, ActivityBaselineResponse)
        assert result.camera_id == "test_camera"
        assert result.entries == []
        assert result.total_samples == 0
        assert result.peak_hour is None
        assert result.peak_day is None
        assert result.learning_complete is False

    @pytest.mark.asyncio
    async def test_get_activity_baseline_with_data(self) -> None:
        """Test activity baseline endpoint returns entries for camera with baselines."""
        from backend.api.routes.cameras import get_camera_activity_baseline

        mock_db = AsyncMock()

        # Mock camera query
        mock_camera = MagicMock()
        mock_camera.id = "front_door"
        mock_camera.name = "Front Door"
        mock_camera_result = MagicMock()
        mock_camera_result.scalar_one_or_none.return_value = mock_camera
        mock_db.execute.return_value = mock_camera_result

        # Create mock baseline records
        mock_baselines = []
        for day in range(7):
            for hour in range(24):
                mock_baseline = MagicMock()
                mock_baseline.hour = hour
                mock_baseline.day_of_week = day
                mock_baseline.avg_count = 1.0 + (hour / 24.0) * 3.0  # Higher later in day
                mock_baseline.sample_count = 15
                mock_baselines.append(mock_baseline)

        mock_baseline_service = MagicMock()
        mock_baseline_service.get_activity_baselines_raw = AsyncMock(return_value=mock_baselines)
        mock_baseline_service.min_samples = 10

        with patch(
            "backend.api.routes.cameras.get_baseline_service",
            return_value=mock_baseline_service,
        ):
            result = await get_camera_activity_baseline("front_door", db=mock_db)

        assert isinstance(result, ActivityBaselineResponse)
        assert result.camera_id == "front_door"
        assert len(result.entries) == 168  # 24 hours * 7 days
        assert result.total_samples == 168 * 15  # 15 samples per entry
        assert result.peak_hour == 23  # Highest hour due to formula
        assert result.learning_complete is True
        assert result.min_samples_required == 10


class TestGetCameraClassBaseline:
    """Tests for GET /api/cameras/{camera_id}/baseline/classes endpoint."""

    @pytest.mark.asyncio
    async def test_get_class_baseline_camera_not_found(self) -> None:
        """Test that class baseline endpoint returns 404 for non-existent camera."""
        from backend.api.routes.cameras import get_camera_class_baseline

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(Exception) as exc_info:
            await get_camera_class_baseline("nonexistent_camera", db=mock_db)

        assert exc_info.value.status_code == 404
        assert "not found" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_get_class_baseline_empty_data(self) -> None:
        """Test class baseline endpoint returns empty response for camera with no data."""
        from backend.api.routes.cameras import get_camera_class_baseline

        mock_db = AsyncMock()

        # Mock camera query
        mock_camera = MagicMock()
        mock_camera.id = "test_camera"
        mock_camera.name = "Test Camera"
        mock_camera_result = MagicMock()
        mock_camera_result.scalar_one_or_none.return_value = mock_camera
        mock_db.execute.return_value = mock_camera_result

        # Mock baseline service returning empty list
        mock_baseline_service = MagicMock()
        mock_baseline_service.get_class_baselines_raw = AsyncMock(return_value=[])

        with patch(
            "backend.api.routes.cameras.get_baseline_service",
            return_value=mock_baseline_service,
        ):
            result = await get_camera_class_baseline("test_camera", db=mock_db)

        assert isinstance(result, ClassBaselineResponse)
        assert result.camera_id == "test_camera"
        assert result.entries == []
        assert result.unique_classes == []
        assert result.total_samples == 0
        assert result.most_common_class is None

    @pytest.mark.asyncio
    async def test_get_class_baseline_with_data(self) -> None:
        """Test class baseline endpoint returns entries for camera with baselines."""
        from backend.api.routes.cameras import get_camera_class_baseline

        mock_db = AsyncMock()

        # Mock camera query
        mock_camera = MagicMock()
        mock_camera.id = "front_door"
        mock_camera.name = "Front Door"
        mock_camera_result = MagicMock()
        mock_camera_result.scalar_one_or_none.return_value = mock_camera
        mock_db.execute.return_value = mock_camera_result

        # Create mock class baseline records
        mock_baselines = []
        for detection_class in ["person", "vehicle", "animal"]:
            for hour in range(24):
                mock_baseline = MagicMock()
                mock_baseline.detection_class = detection_class
                mock_baseline.hour = hour
                mock_baseline.frequency = 2.0 if detection_class == "person" else 1.0
                mock_baseline.sample_count = 100 if detection_class == "person" else 50
                mock_baselines.append(mock_baseline)

        mock_baseline_service = MagicMock()
        mock_baseline_service.get_class_baselines_raw = AsyncMock(return_value=mock_baselines)

        with patch(
            "backend.api.routes.cameras.get_baseline_service",
            return_value=mock_baseline_service,
        ):
            result = await get_camera_class_baseline("front_door", db=mock_db)

        assert isinstance(result, ClassBaselineResponse)
        assert result.camera_id == "front_door"
        assert len(result.entries) == 72  # 3 classes * 24 hours
        assert set(result.unique_classes) == {"person", "vehicle", "animal"}
        assert result.most_common_class == "person"  # Most sample_count
        assert result.total_samples == (100 * 24) + (50 * 24) + (50 * 24)


class TestActivityBaselineSchemas:
    """Tests for activity baseline Pydantic schemas."""

    def test_activity_baseline_entry_validation(self) -> None:
        """Test ActivityBaselineEntry schema validation."""
        entry = ActivityBaselineEntry(
            hour=17,
            day_of_week=4,
            avg_count=5.2,
            sample_count=30,
            is_peak=True,
        )
        assert entry.hour == 17
        assert entry.day_of_week == 4
        assert entry.avg_count == 5.2
        assert entry.sample_count == 30
        assert entry.is_peak is True

    def test_activity_baseline_entry_hour_bounds(self) -> None:
        """Test ActivityBaselineEntry enforces hour bounds (0-23)."""
        # Valid boundary values
        entry_low = ActivityBaselineEntry(
            hour=0, day_of_week=0, avg_count=1.0, sample_count=1, is_peak=False
        )
        assert entry_low.hour == 0

        entry_high = ActivityBaselineEntry(
            hour=23, day_of_week=0, avg_count=1.0, sample_count=1, is_peak=False
        )
        assert entry_high.hour == 23

        # Invalid values
        with pytest.raises(ValueError):
            ActivityBaselineEntry(
                hour=24, day_of_week=0, avg_count=1.0, sample_count=1, is_peak=False
            )

        with pytest.raises(ValueError):
            ActivityBaselineEntry(
                hour=-1, day_of_week=0, avg_count=1.0, sample_count=1, is_peak=False
            )

    def test_activity_baseline_entry_day_bounds(self) -> None:
        """Test ActivityBaselineEntry enforces day_of_week bounds (0-6)."""
        # Valid boundary values
        entry_low = ActivityBaselineEntry(
            hour=0, day_of_week=0, avg_count=1.0, sample_count=1, is_peak=False
        )
        assert entry_low.day_of_week == 0

        entry_high = ActivityBaselineEntry(
            hour=0, day_of_week=6, avg_count=1.0, sample_count=1, is_peak=False
        )
        assert entry_high.day_of_week == 6

        # Invalid values
        with pytest.raises(ValueError):
            ActivityBaselineEntry(
                hour=0, day_of_week=7, avg_count=1.0, sample_count=1, is_peak=False
            )

        with pytest.raises(ValueError):
            ActivityBaselineEntry(
                hour=0, day_of_week=-1, avg_count=1.0, sample_count=1, is_peak=False
            )

    def test_activity_baseline_response_validation(self) -> None:
        """Test ActivityBaselineResponse schema validation."""
        entries = [
            ActivityBaselineEntry(
                hour=0, day_of_week=0, avg_count=1.0, sample_count=10, is_peak=False
            ),
            ActivityBaselineEntry(
                hour=17, day_of_week=4, avg_count=5.0, sample_count=15, is_peak=True
            ),
        ]
        response = ActivityBaselineResponse(
            camera_id="test",
            entries=entries,
            total_samples=25,
            peak_hour=17,
            peak_day=4,
            learning_complete=True,
            min_samples_required=10,
        )
        assert response.camera_id == "test"
        assert len(response.entries) == 2
        assert response.peak_hour == 17
        assert response.peak_day == 4
        assert response.learning_complete is True


class TestClassBaselineSchemas:
    """Tests for class baseline Pydantic schemas."""

    def test_class_baseline_entry_validation(self) -> None:
        """Test ClassBaselineEntry schema validation."""
        entry = ClassBaselineEntry(
            object_class="person",
            hour=17,
            frequency=3.5,
            sample_count=45,
        )
        assert entry.object_class == "person"
        assert entry.hour == 17
        assert entry.frequency == 3.5
        assert entry.sample_count == 45

    def test_class_baseline_entry_hour_bounds(self) -> None:
        """Test ClassBaselineEntry enforces hour bounds (0-23)."""
        # Valid boundary values
        entry_low = ClassBaselineEntry(object_class="test", hour=0, frequency=1.0, sample_count=1)
        assert entry_low.hour == 0

        entry_high = ClassBaselineEntry(object_class="test", hour=23, frequency=1.0, sample_count=1)
        assert entry_high.hour == 23

        # Invalid values
        with pytest.raises(ValueError):
            ClassBaselineEntry(object_class="test", hour=24, frequency=1.0, sample_count=1)

    def test_class_baseline_response_validation(self) -> None:
        """Test ClassBaselineResponse schema validation."""
        entries = [
            ClassBaselineEntry(object_class="person", hour=17, frequency=3.5, sample_count=45),
            ClassBaselineEntry(object_class="vehicle", hour=8, frequency=2.1, sample_count=30),
        ]
        response = ClassBaselineResponse(
            camera_id="test",
            entries=entries,
            unique_classes=["person", "vehicle"],
            total_samples=75,
            most_common_class="person",
        )
        assert response.camera_id == "test"
        assert len(response.entries) == 2
        assert "person" in response.unique_classes
        assert response.most_common_class == "person"


class TestAnomalyConfigEndpoints:
    """Tests for /api/system/anomaly-config endpoints."""

    @pytest.mark.asyncio
    async def test_get_anomaly_config(self) -> None:
        """Test GET /api/system/anomaly-config returns current configuration."""
        from backend.api.routes.system import get_anomaly_config
        from backend.api.schemas.baseline import AnomalyConfig

        mock_service = MagicMock()
        mock_service.anomaly_threshold_std = 2.0
        mock_service.min_samples = 10
        mock_service.decay_factor = 0.1
        mock_service.window_days = 30

        # Import is inside function, so patch at source
        with patch("backend.services.baseline.get_baseline_service", return_value=mock_service):
            result = await get_anomaly_config()

        assert isinstance(result, AnomalyConfig)
        assert result.threshold_stdev == 2.0
        assert result.min_samples == 10
        assert result.decay_factor == 0.1
        assert result.window_days == 30

    @pytest.mark.asyncio
    async def test_update_anomaly_config_threshold(self) -> None:
        """Test PATCH /api/system/anomaly-config updates threshold."""
        from backend.api.routes.system import update_anomaly_config
        from backend.api.schemas.baseline import AnomalyConfig, AnomalyConfigUpdate

        mock_service = MagicMock()
        mock_service.anomaly_threshold_std = 2.0
        mock_service.min_samples = 10
        mock_service.decay_factor = 0.1
        mock_service.window_days = 30

        def update_side_effect(*, threshold_stdev=None, min_samples=None):
            if threshold_stdev is not None:
                mock_service.anomaly_threshold_std = threshold_stdev
            if min_samples is not None:
                mock_service.min_samples = min_samples

        mock_service.update_config = MagicMock(side_effect=update_side_effect)

        mock_request = MagicMock()
        mock_db = AsyncMock()

        update = AnomalyConfigUpdate(threshold_stdev=2.5)

        with (
            patch("backend.services.baseline.get_baseline_service", return_value=mock_service),
            patch("backend.services.audit.AuditService.log_action", new_callable=AsyncMock),
        ):
            result = await update_anomaly_config(update, mock_request, mock_db)

        assert isinstance(result, AnomalyConfig)
        assert result.threshold_stdev == 2.5
        mock_service.update_config.assert_called_once_with(
            threshold_stdev=2.5,
            min_samples=None,
        )

    @pytest.mark.asyncio
    async def test_update_anomaly_config_min_samples(self) -> None:
        """Test PATCH /api/system/anomaly-config updates min_samples."""
        from backend.api.routes.system import update_anomaly_config
        from backend.api.schemas.baseline import AnomalyConfig, AnomalyConfigUpdate

        mock_service = MagicMock()
        mock_service.anomaly_threshold_std = 2.0
        mock_service.min_samples = 10
        mock_service.decay_factor = 0.1
        mock_service.window_days = 30

        def update_side_effect(*, threshold_stdev=None, min_samples=None):
            if threshold_stdev is not None:
                mock_service.anomaly_threshold_std = threshold_stdev
            if min_samples is not None:
                mock_service.min_samples = min_samples

        mock_service.update_config = MagicMock(side_effect=update_side_effect)

        mock_request = MagicMock()
        mock_db = AsyncMock()

        update = AnomalyConfigUpdate(min_samples=15)

        with (
            patch("backend.services.baseline.get_baseline_service", return_value=mock_service),
            patch("backend.services.audit.AuditService.log_action", new_callable=AsyncMock),
        ):
            result = await update_anomaly_config(update, mock_request, mock_db)

        assert isinstance(result, AnomalyConfig)
        assert result.min_samples == 15

    @pytest.mark.asyncio
    async def test_update_anomaly_config_invalid_threshold(self) -> None:
        """Test PATCH /api/system/anomaly-config rejects invalid threshold via service."""
        from backend.api.routes.system import update_anomaly_config
        from backend.api.schemas.baseline import AnomalyConfigUpdate

        mock_service = MagicMock()
        mock_service.anomaly_threshold_std = 2.0
        mock_service.min_samples = 10
        mock_service.decay_factor = 0.1
        mock_service.window_days = 30

        # Service raises ValueError when invalid config is attempted
        mock_service.update_config = MagicMock(
            side_effect=ValueError("threshold_stdev must be positive")
        )

        mock_request = MagicMock()
        mock_db = AsyncMock()

        # Use a valid Pydantic value but one that triggers service validation error
        update = AnomalyConfigUpdate(threshold_stdev=0.001)

        with patch("backend.services.baseline.get_baseline_service", return_value=mock_service):
            with pytest.raises(Exception) as exc_info:
                await update_anomaly_config(update, mock_request, mock_db)

            assert exc_info.value.status_code == 400


class TestAnomalyConfigSchemas:
    """Tests for anomaly config Pydantic schemas."""

    def test_anomaly_config_validation(self) -> None:
        """Test AnomalyConfig schema validation."""
        from backend.api.schemas.baseline import AnomalyConfig

        config = AnomalyConfig(
            threshold_stdev=2.0,
            min_samples=10,
            decay_factor=0.1,
            window_days=30,
        )
        assert config.threshold_stdev == 2.0
        assert config.min_samples == 10
        assert config.decay_factor == 0.1
        assert config.window_days == 30

    def test_anomaly_config_threshold_bounds(self) -> None:
        """Test AnomalyConfig enforces threshold bounds."""
        from backend.api.schemas.baseline import AnomalyConfig

        # threshold_stdev must be > 0
        with pytest.raises(ValueError):
            AnomalyConfig(threshold_stdev=0, min_samples=10, decay_factor=0.1, window_days=30)

        with pytest.raises(ValueError):
            AnomalyConfig(threshold_stdev=-1, min_samples=10, decay_factor=0.1, window_days=30)

    def test_anomaly_config_decay_factor_bounds(self) -> None:
        """Test AnomalyConfig enforces decay_factor bounds (0 < factor <= 1)."""
        from backend.api.schemas.baseline import AnomalyConfig

        # Valid boundaries
        config_high = AnomalyConfig(
            threshold_stdev=2.0, min_samples=10, decay_factor=1.0, window_days=30
        )
        assert config_high.decay_factor == 1.0

        config_low = AnomalyConfig(
            threshold_stdev=2.0, min_samples=10, decay_factor=0.01, window_days=30
        )
        assert config_low.decay_factor == 0.01

        # Invalid values
        with pytest.raises(ValueError):
            AnomalyConfig(threshold_stdev=2.0, min_samples=10, decay_factor=0, window_days=30)

        with pytest.raises(ValueError):
            AnomalyConfig(threshold_stdev=2.0, min_samples=10, decay_factor=1.5, window_days=30)

    def test_anomaly_config_update_validation(self) -> None:
        """Test AnomalyConfigUpdate schema allows partial updates."""
        from backend.api.schemas.baseline import AnomalyConfigUpdate

        # Only threshold_stdev
        update1 = AnomalyConfigUpdate(threshold_stdev=2.5)
        assert update1.threshold_stdev == 2.5
        assert update1.min_samples is None

        # Only min_samples
        update2 = AnomalyConfigUpdate(min_samples=15)
        assert update2.threshold_stdev is None
        assert update2.min_samples == 15

        # Both values
        update3 = AnomalyConfigUpdate(threshold_stdev=3.0, min_samples=20)
        assert update3.threshold_stdev == 3.0
        assert update3.min_samples == 20

        # Empty update (no values)
        update4 = AnomalyConfigUpdate()
        assert update4.threshold_stdev is None
        assert update4.min_samples is None
