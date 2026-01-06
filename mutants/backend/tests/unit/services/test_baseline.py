"""Unit tests for baseline activity service.

Tests cover:
- BaselineService initialization with validation
- Time decay calculations
- Anomaly detection logic
- Async database methods
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.baseline import BaselineService

# =============================================================================
# Initialization Tests
# =============================================================================


class TestBaselineServiceInit:
    """Tests for BaselineService initialization."""

    def test_init_default_values(self) -> None:
        """Test initialization with default values."""
        service = BaselineService()
        assert service.decay_factor == 0.1
        assert service.window_days == 30
        assert service.anomaly_threshold_std == 2.0
        assert service.min_samples == 10

    def test_init_custom_values(self) -> None:
        """Test initialization with custom values."""
        service = BaselineService(
            decay_factor=0.2,
            window_days=14,
            anomaly_threshold_std=3.0,
            min_samples=5,
        )
        assert service.decay_factor == 0.2
        assert service.window_days == 14
        assert service.anomaly_threshold_std == 3.0
        assert service.min_samples == 5

    def test_init_invalid_decay_factor_zero(self) -> None:
        """Test that decay_factor cannot be zero."""
        with pytest.raises(ValueError) as exc_info:
            BaselineService(decay_factor=0)
        assert "decay_factor" in str(exc_info.value)

    def test_init_invalid_decay_factor_negative(self) -> None:
        """Test that decay_factor cannot be negative."""
        with pytest.raises(ValueError) as exc_info:
            BaselineService(decay_factor=-0.1)
        assert "decay_factor" in str(exc_info.value)

    def test_init_invalid_decay_factor_too_high(self) -> None:
        """Test that decay_factor cannot exceed 1."""
        with pytest.raises(ValueError) as exc_info:
            BaselineService(decay_factor=1.1)
        assert "decay_factor" in str(exc_info.value)

    def test_init_decay_factor_exactly_one(self) -> None:
        """Test that decay_factor can be exactly 1."""
        service = BaselineService(decay_factor=1.0)
        assert service.decay_factor == 1.0

    def test_init_invalid_window_days_zero(self) -> None:
        """Test that window_days cannot be zero."""
        with pytest.raises(ValueError) as exc_info:
            BaselineService(window_days=0)
        assert "window_days" in str(exc_info.value)

    def test_init_invalid_window_days_negative(self) -> None:
        """Test that window_days cannot be negative."""
        with pytest.raises(ValueError) as exc_info:
            BaselineService(window_days=-1)
        assert "window_days" in str(exc_info.value)

    def test_init_invalid_anomaly_threshold_negative(self) -> None:
        """Test that anomaly_threshold_std cannot be negative."""
        with pytest.raises(ValueError) as exc_info:
            BaselineService(anomaly_threshold_std=-1.0)
        assert "anomaly_threshold_std" in str(exc_info.value)

    def test_init_anomaly_threshold_zero(self) -> None:
        """Test that anomaly_threshold_std can be zero."""
        service = BaselineService(anomaly_threshold_std=0)
        assert service.anomaly_threshold_std == 0

    def test_init_invalid_min_samples_zero(self) -> None:
        """Test that min_samples cannot be zero."""
        with pytest.raises(ValueError) as exc_info:
            BaselineService(min_samples=0)
        assert "min_samples" in str(exc_info.value)

    def test_init_invalid_min_samples_negative(self) -> None:
        """Test that min_samples cannot be negative."""
        with pytest.raises(ValueError) as exc_info:
            BaselineService(min_samples=-1)
        assert "min_samples" in str(exc_info.value)


# =============================================================================
# Time Decay Tests
# =============================================================================


class TestCalculateTimeDecay:
    """Tests for _calculate_time_decay method."""

    def test_decay_same_time(self) -> None:
        """Test decay when timestamps are the same."""
        service = BaselineService(decay_factor=0.1)
        now = datetime.now(UTC)
        decay = service._calculate_time_decay(now, now)
        # At time 0, decay should be 1.0
        assert abs(decay - 1.0) < 0.001

    def test_decay_one_day(self) -> None:
        """Test decay after one day."""
        service = BaselineService(decay_factor=0.1)
        now = datetime.now(UTC)
        yesterday = now - timedelta(days=1)
        decay = service._calculate_time_decay(yesterday, now)
        # After 1 day with decay_factor=0.1, decay should be e^(-ln(10))
        # which is approximately 0.1
        assert 0 < decay < 1

    def test_decay_outside_window(self) -> None:
        """Test decay when outside window returns zero."""
        service = BaselineService(decay_factor=0.1, window_days=30)
        now = datetime.now(UTC)
        old_date = now - timedelta(days=35)
        decay = service._calculate_time_decay(old_date, now)
        assert decay == 0.0

    def test_decay_at_window_boundary(self) -> None:
        """Test decay at exactly the window boundary."""
        service = BaselineService(decay_factor=0.1, window_days=30)
        now = datetime.now(UTC)
        boundary = now - timedelta(days=30)
        decay = service._calculate_time_decay(boundary, now)
        # At exactly 30 days, it should still have a small non-zero decay
        assert decay > 0

    def test_decay_handles_naive_timestamps(self) -> None:
        """Test that decay handles naive timestamps."""
        service = BaselineService(decay_factor=0.1)
        now = datetime.now()  # naive datetime
        yesterday = now - timedelta(days=1)
        # Should not raise
        decay = service._calculate_time_decay(yesterday, now)
        assert 0 < decay < 1

    def test_decay_higher_factor_slower_decay(self) -> None:
        """Test that higher decay factor means slower decay."""
        service_fast = BaselineService(decay_factor=0.1)
        service_slow = BaselineService(decay_factor=0.9)
        now = datetime.now(UTC)
        yesterday = now - timedelta(days=1)

        decay_fast = service_fast._calculate_time_decay(yesterday, now)
        decay_slow = service_slow._calculate_time_decay(yesterday, now)

        # Higher decay factor means less decay (higher remaining value)
        assert decay_slow > decay_fast


# =============================================================================
# Edge Cases and Calculation Tests
# =============================================================================


class TestBaselineCalculations:
    """Tests for baseline-related calculations."""

    def test_exponential_decay_formula(self) -> None:
        """Test the exponential decay formula."""
        service = BaselineService(decay_factor=0.5)
        now = datetime.now(UTC)

        # After 1 day, decay should be 0.5^1 = 0.5
        one_day_ago = now - timedelta(days=1)
        decay = service._calculate_time_decay(one_day_ago, now)
        # The formula is e^(-days * ln(1/decay_factor))
        # = e^(-1 * ln(2)) = e^(-ln(2)) = 0.5
        assert abs(decay - 0.5) < 0.01

    def test_window_days_minimum(self) -> None:
        """Test minimum window_days value."""
        service = BaselineService(window_days=1)
        now = datetime.now(UTC)

        # 23 hours ago should still be within window
        hours_23_ago = now - timedelta(hours=23)
        decay = service._calculate_time_decay(hours_23_ago, now)
        assert decay > 0

        # 25 hours ago should be outside window
        hours_25_ago = now - timedelta(hours=25)
        decay = service._calculate_time_decay(hours_25_ago, now)
        assert decay == 0


# =============================================================================
# Async Method Tests
# =============================================================================


class TestUpdateBaseline:
    """Tests for update_baseline async method."""

    @pytest.mark.asyncio
    async def test_update_baseline_with_session(self) -> None:
        """Test update_baseline with provided session."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        mock_session.add = MagicMock()

        service = BaselineService()
        timestamp = datetime(2025, 12, 23, 14, 30, 0, tzinfo=UTC)

        await service.update_baseline("camera-1", "person", timestamp, session=mock_session)

        # Should have called execute for select operations
        assert mock_session.execute.called

    @pytest.mark.asyncio
    async def test_update_baseline_creates_new_records(self) -> None:
        """Test that update_baseline creates new baseline records."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        service = BaselineService()
        timestamp = datetime(2025, 12, 23, 14, 30, 0, tzinfo=UTC)

        await service.update_baseline("camera-1", "person", timestamp, session=mock_session)

        # Should have added new baseline records
        assert mock_session.add.call_count >= 1


class TestUpdateActivityBaseline:
    """Tests for _update_activity_baseline method."""

    @pytest.mark.asyncio
    async def test_update_existing_baseline(self) -> None:
        """Test updating an existing activity baseline."""
        mock_session = AsyncMock()
        now = datetime.now(UTC)

        # Create mock existing baseline
        mock_existing = MagicMock()
        mock_existing.id = 1
        mock_existing.avg_count = 5.0
        mock_existing.sample_count = 10
        mock_existing.last_updated = now - timedelta(hours=1)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_existing
        mock_session.execute.return_value = mock_result

        service = BaselineService()
        await service._update_activity_baseline(mock_session, "camera-1", 14, 0, now)

        # Should have executed update statement
        assert mock_session.execute.call_count >= 1

    @pytest.mark.asyncio
    async def test_update_stale_baseline_resets(self) -> None:
        """Test that stale baseline gets reset."""
        mock_session = AsyncMock()
        now = datetime.now(UTC)

        # Create mock stale baseline (outside window)
        mock_existing = MagicMock()
        mock_existing.id = 1
        mock_existing.avg_count = 5.0
        mock_existing.sample_count = 10
        mock_existing.last_updated = now - timedelta(days=35)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_existing
        mock_session.execute.return_value = mock_result

        service = BaselineService(window_days=30)
        await service._update_activity_baseline(mock_session, "camera-1", 14, 0, now)

        # Should have executed update statement
        assert mock_session.execute.call_count >= 1


class TestUpdateClassBaseline:
    """Tests for _update_class_baseline method."""

    @pytest.mark.asyncio
    async def test_create_new_class_baseline(self) -> None:
        """Test creating a new class baseline."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        service = BaselineService()
        now = datetime.now(UTC)
        await service._update_class_baseline(mock_session, "camera-1", "person", 14, now)

        # Should have added new baseline
        assert mock_session.add.called

    @pytest.mark.asyncio
    async def test_update_existing_class_baseline(self) -> None:
        """Test updating an existing class baseline."""
        mock_session = AsyncMock()
        now = datetime.now(UTC)

        mock_existing = MagicMock()
        mock_existing.id = 1
        mock_existing.frequency = 0.5
        mock_existing.sample_count = 5
        mock_existing.last_updated = now - timedelta(hours=2)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_existing
        mock_session.execute.return_value = mock_result

        service = BaselineService()
        await service._update_class_baseline(mock_session, "camera-1", "person", 14, now)

        # Should have executed update statement
        assert mock_session.execute.call_count >= 1


class TestGetActivityRate:
    """Tests for get_activity_rate method."""

    @pytest.mark.asyncio
    async def test_get_activity_rate_no_baseline(self) -> None:
        """Test get_activity_rate returns 0 when no baseline exists."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        service = BaselineService()
        rate = await service.get_activity_rate("camera-1", 14, 0, session=mock_session)

        assert rate == 0.0

    @pytest.mark.asyncio
    async def test_get_activity_rate_with_baseline(self) -> None:
        """Test get_activity_rate returns decayed rate."""
        mock_session = AsyncMock()
        now = datetime.now(UTC)

        mock_baseline = MagicMock()
        mock_baseline.avg_count = 10.0
        mock_baseline.last_updated = now - timedelta(hours=1)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_baseline
        mock_session.execute.return_value = mock_result

        service = BaselineService(decay_factor=0.9)
        rate = await service.get_activity_rate("camera-1", 14, 0, session=mock_session)

        # Rate should be decayed from 10.0
        assert 0 < rate <= 10.0


class TestGetClassFrequency:
    """Tests for get_class_frequency method."""

    @pytest.mark.asyncio
    async def test_get_class_frequency_no_baseline(self) -> None:
        """Test get_class_frequency returns 0 when no baseline exists."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        service = BaselineService()
        freq = await service.get_class_frequency("camera-1", "person", 14, session=mock_session)

        assert freq == 0.0

    @pytest.mark.asyncio
    async def test_get_class_frequency_with_baseline(self) -> None:
        """Test get_class_frequency returns decayed frequency."""
        mock_session = AsyncMock()
        now = datetime.now(UTC)

        mock_baseline = MagicMock()
        mock_baseline.frequency = 0.8
        mock_baseline.last_updated = now - timedelta(hours=1)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_baseline
        mock_session.execute.return_value = mock_result

        service = BaselineService(decay_factor=0.9)
        freq = await service.get_class_frequency("camera-1", "person", 14, session=mock_session)

        # Frequency should be decayed from 0.8
        assert 0 < freq <= 0.8


class TestIsAnomalous:
    """Tests for is_anomalous method."""

    @pytest.mark.asyncio
    async def test_is_anomalous_no_baselines(self) -> None:
        """Test is_anomalous returns neutral when no baselines exist."""
        mock_session = AsyncMock()

        # Class baseline
        mock_class_result = MagicMock()
        mock_class_result.scalar_one_or_none.return_value = None

        # All baselines for this hour
        mock_all_result = MagicMock()
        mock_all_scalars = MagicMock()
        mock_all_scalars.all.return_value = []
        mock_all_result.scalars.return_value = mock_all_scalars

        mock_session.execute.side_effect = [mock_class_result, mock_all_result]

        service = BaselineService()
        timestamp = datetime(2025, 12, 23, 14, 30, 0, tzinfo=UTC)
        is_anomaly, score = await service.is_anomalous(
            "camera-1", "person", timestamp, session=mock_session
        )

        # Should return neutral score
        assert is_anomaly is False
        assert score == 0.5

    @pytest.mark.asyncio
    async def test_is_anomalous_insufficient_samples(self) -> None:
        """Test is_anomalous returns neutral when insufficient samples."""
        mock_session = AsyncMock()
        now = datetime.now(UTC)

        # Class baseline
        mock_class_baseline = MagicMock()
        mock_class_baseline.detection_class = "person"
        mock_class_baseline.frequency = 1.0
        mock_class_baseline.sample_count = 2  # Below min_samples
        mock_class_baseline.last_updated = now - timedelta(hours=1)

        mock_class_result = MagicMock()
        mock_class_result.scalar_one_or_none.return_value = mock_class_baseline

        # All baselines for this hour
        mock_all_result = MagicMock()
        mock_all_scalars = MagicMock()
        mock_all_scalars.all.return_value = [mock_class_baseline]
        mock_all_result.scalars.return_value = mock_all_scalars

        mock_session.execute.side_effect = [mock_class_result, mock_all_result]

        service = BaselineService(min_samples=10)
        timestamp = datetime(2025, 12, 23, 14, 30, 0, tzinfo=UTC)
        is_anomaly, score = await service.is_anomalous(
            "camera-1", "person", timestamp, session=mock_session
        )

        # Should return neutral score
        assert is_anomaly is False
        assert score == 0.5

    @pytest.mark.asyncio
    async def test_is_anomalous_class_never_seen(self) -> None:
        """Test is_anomalous returns high score for never-seen class."""
        mock_session = AsyncMock()
        now = datetime.now(UTC)

        # Class baseline (not found for requested class)
        mock_class_result = MagicMock()
        mock_class_result.scalar_one_or_none.return_value = None

        # All baselines - only other classes exist
        mock_other_baseline = MagicMock()
        mock_other_baseline.detection_class = "vehicle"
        mock_other_baseline.frequency = 1.0
        mock_other_baseline.sample_count = 100
        mock_other_baseline.last_updated = now - timedelta(hours=1)

        mock_all_result = MagicMock()
        mock_all_scalars = MagicMock()
        mock_all_scalars.all.return_value = [mock_other_baseline]
        mock_all_result.scalars.return_value = mock_all_scalars

        mock_session.execute.side_effect = [mock_class_result, mock_all_result]

        service = BaselineService(min_samples=10)
        timestamp = datetime(2025, 12, 23, 14, 30, 0, tzinfo=UTC)
        _is_anomaly, score = await service.is_anomalous(
            "camera-1", "person", timestamp, session=mock_session
        )

        # Should return highly anomalous
        assert score == 1.0

    @pytest.mark.asyncio
    async def test_is_anomalous_common_class(self) -> None:
        """Test is_anomalous returns low score for common class."""
        mock_session = AsyncMock()
        now = datetime.now(UTC)

        # Class baseline (found)
        mock_class_baseline = MagicMock()
        mock_class_baseline.detection_class = "person"
        mock_class_baseline.frequency = 10.0
        mock_class_baseline.sample_count = 50
        mock_class_baseline.last_updated = now - timedelta(hours=1)

        mock_class_result = MagicMock()
        mock_class_result.scalar_one_or_none.return_value = mock_class_baseline

        # All baselines
        mock_all_result = MagicMock()
        mock_all_scalars = MagicMock()
        mock_all_scalars.all.return_value = [mock_class_baseline]
        mock_all_result.scalars.return_value = mock_all_scalars

        mock_session.execute.side_effect = [mock_class_result, mock_all_result]

        service = BaselineService(min_samples=10, decay_factor=0.9)
        timestamp = datetime(2025, 12, 23, 14, 30, 0, tzinfo=UTC)
        _is_anomaly, score = await service.is_anomalous(
            "camera-1", "person", timestamp, session=mock_session
        )

        # Should return low anomaly score (common class)
        assert score < 0.5

    @pytest.mark.asyncio
    async def test_is_anomalous_decayed_to_zero(self) -> None:
        """Test is_anomalous handles class baseline decayed to zero."""
        mock_session = AsyncMock()
        now = datetime.now(UTC)

        # Class baseline exists but is very old (decayed)
        mock_class_baseline = MagicMock()
        mock_class_baseline.detection_class = "person"
        mock_class_baseline.frequency = 1.0
        mock_class_baseline.sample_count = 50
        mock_class_baseline.last_updated = now - timedelta(days=29)  # Near window edge

        mock_class_result = MagicMock()
        mock_class_result.scalar_one_or_none.return_value = mock_class_baseline

        # Other class with recent updates
        mock_other_baseline = MagicMock()
        mock_other_baseline.detection_class = "vehicle"
        mock_other_baseline.frequency = 10.0
        mock_other_baseline.sample_count = 100
        mock_other_baseline.last_updated = now - timedelta(hours=1)

        mock_all_result = MagicMock()
        mock_all_scalars = MagicMock()
        mock_all_scalars.all.return_value = [mock_class_baseline, mock_other_baseline]
        mock_all_result.scalars.return_value = mock_all_scalars

        mock_session.execute.side_effect = [mock_class_result, mock_all_result]

        service = BaselineService(min_samples=10, decay_factor=0.1, window_days=30)
        timestamp = datetime(2025, 12, 23, 14, 30, 0, tzinfo=UTC)
        _is_anomaly, score = await service.is_anomalous(
            "camera-1", "person", timestamp, session=mock_session
        )

        # Score should be high (class is rare now)
        assert score > 0.5


class TestGetCameraBaselineSummary:
    """Tests for get_camera_baseline_summary method."""

    @pytest.mark.asyncio
    async def test_get_summary_empty(self) -> None:
        """Test get_camera_baseline_summary with no baselines."""
        mock_session = AsyncMock()

        # Activity baselines
        mock_activity_result = MagicMock()
        mock_activity_scalars = MagicMock()
        mock_activity_scalars.all.return_value = []
        mock_activity_result.scalars.return_value = mock_activity_scalars

        # Class baselines
        mock_class_result = MagicMock()
        mock_class_scalars = MagicMock()
        mock_class_scalars.all.return_value = []
        mock_class_result.scalars.return_value = mock_class_scalars

        mock_session.execute.side_effect = [mock_activity_result, mock_class_result]

        service = BaselineService()
        summary = await service.get_camera_baseline_summary("camera-1", session=mock_session)

        assert summary["camera_id"] == "camera-1"
        assert summary["activity_baseline_count"] == 0
        assert summary["class_baseline_count"] == 0
        assert summary["unique_classes"] == 0
        assert summary["top_classes"] == []
        assert summary["peak_hours"] == []

    @pytest.mark.asyncio
    async def test_get_summary_with_data(self) -> None:
        """Test get_camera_baseline_summary with existing baselines."""
        mock_session = AsyncMock()

        # Activity baselines
        mock_activity1 = MagicMock()
        mock_activity1.hour = 14
        mock_activity1.avg_count = 10.0

        mock_activity2 = MagicMock()
        mock_activity2.hour = 15
        mock_activity2.avg_count = 5.0

        mock_activity_result = MagicMock()
        mock_activity_scalars = MagicMock()
        mock_activity_scalars.all.return_value = [mock_activity1, mock_activity2]
        mock_activity_result.scalars.return_value = mock_activity_scalars

        # Class baselines
        mock_class1 = MagicMock()
        mock_class1.detection_class = "person"
        mock_class1.frequency = 8.0

        mock_class2 = MagicMock()
        mock_class2.detection_class = "vehicle"
        mock_class2.frequency = 3.0

        mock_class_result = MagicMock()
        mock_class_scalars = MagicMock()
        mock_class_scalars.all.return_value = [mock_class1, mock_class2]
        mock_class_result.scalars.return_value = mock_class_scalars

        mock_session.execute.side_effect = [mock_activity_result, mock_class_result]

        service = BaselineService()
        summary = await service.get_camera_baseline_summary("camera-1", session=mock_session)

        assert summary["camera_id"] == "camera-1"
        assert summary["activity_baseline_count"] == 2
        assert summary["class_baseline_count"] == 2
        assert summary["unique_classes"] == 2
        assert len(summary["top_classes"]) == 2
        assert summary["top_classes"][0]["class"] == "person"
        assert len(summary["peak_hours"]) == 2
        assert summary["peak_hours"][0]["hour"] == 14


# =============================================================================
# Singleton Tests
# =============================================================================


class TestBaselineSingleton:
    """Tests for baseline service singleton functions."""

    def test_get_baseline_service_creates_singleton(self) -> None:
        """Test that get_baseline_service creates singleton."""
        from backend.services.baseline import get_baseline_service, reset_baseline_service

        reset_baseline_service()
        service1 = get_baseline_service()
        service2 = get_baseline_service()

        assert service1 is service2
        reset_baseline_service()

    def test_reset_baseline_service(self) -> None:
        """Test that reset_baseline_service clears singleton."""
        from backend.services.baseline import get_baseline_service, reset_baseline_service

        service1 = get_baseline_service()
        reset_baseline_service()
        service2 = get_baseline_service()

        assert service1 is not service2
        reset_baseline_service()
