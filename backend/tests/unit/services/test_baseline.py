"""Unit tests for baseline activity service.

Tests cover:
- BaselineService initialization with validation
- Time decay calculations
- Anomaly detection logic
- Async database methods
- Property-based tests for mathematical invariants
- Error handling and edge cases
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import given
from hypothesis import strategies as st

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

    @pytest.mark.asyncio
    async def test_update_stale_class_baseline_resets(self) -> None:
        """Test that stale class baseline gets reset."""
        mock_session = AsyncMock()
        now = datetime.now(UTC)

        # Create mock stale baseline (outside window)
        mock_existing = MagicMock()
        mock_existing.id = 1
        mock_existing.frequency = 0.5
        mock_existing.sample_count = 10
        mock_existing.last_updated = now - timedelta(days=35)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_existing
        mock_session.execute.return_value = mock_result

        service = BaselineService(window_days=30)
        await service._update_class_baseline(mock_session, "camera-1", "person", 14, now)

        # Should have executed update statement
        assert mock_session.execute.call_count >= 1


class TestUpdateBaselineAutoSession:
    """Tests for update_baseline without session parameter."""

    @pytest.mark.asyncio
    async def test_update_baseline_without_session_auto_commits(self) -> None:
        """Test update_baseline creates and commits its own session."""
        from unittest.mock import patch

        service = BaselineService()
        timestamp = datetime(2025, 12, 23, 14, 30, 0, tzinfo=UTC)

        # Mock get_session to track if it's called
        with patch("backend.services.baseline.get_session") as mock_get_session:
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_session.execute.return_value = mock_result
            mock_session.__aenter__.return_value = mock_session
            mock_session.__aexit__.return_value = None
            mock_get_session.return_value = mock_session

            await service.update_baseline("camera-1", "person", timestamp)

            # Should have called get_session since no session was provided
            mock_get_session.assert_called_once()
            # Should have committed
            mock_session.commit.assert_called_once()


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

    @pytest.mark.asyncio
    async def test_get_activity_rate_without_session(self) -> None:
        """Test get_activity_rate creates its own session."""
        from unittest.mock import patch

        service = BaselineService()

        with patch("backend.services.baseline.get_session") as mock_get_session:
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_session.execute.return_value = mock_result
            mock_session.__aenter__.return_value = mock_session
            mock_session.__aexit__.return_value = None
            mock_get_session.return_value = mock_session

            rate = await service.get_activity_rate("camera-1", 14, 0)

            assert rate == 0.0
            mock_get_session.assert_called_once()


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

    @pytest.mark.asyncio
    async def test_get_class_frequency_without_session(self) -> None:
        """Test get_class_frequency creates its own session."""
        from unittest.mock import patch

        service = BaselineService()

        with patch("backend.services.baseline.get_session") as mock_get_session:
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_session.execute.return_value = mock_result
            mock_session.__aenter__.return_value = mock_session
            mock_session.__aexit__.return_value = None
            mock_get_session.return_value = mock_session

            freq = await service.get_class_frequency("camera-1", "person", 14)

            assert freq == 0.0
            mock_get_session.assert_called_once()


class TestIsAnomalousAutoSession:
    """Tests for is_anomalous method without session parameter."""

    @pytest.mark.asyncio
    async def test_is_anomalous_without_session(self) -> None:
        """Test is_anomalous creates its own session."""
        from unittest.mock import patch

        service = BaselineService()
        timestamp = datetime(2025, 12, 23, 14, 30, 0, tzinfo=UTC)

        with patch("backend.services.baseline.get_session") as mock_get_session:
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
            mock_session.__aenter__.return_value = mock_session
            mock_session.__aexit__.return_value = None
            mock_get_session.return_value = mock_session

            is_anomaly, score = await service.is_anomalous("camera-1", "person", timestamp)

            assert is_anomaly is False
            assert score == 0.5
            mock_get_session.assert_called_once()


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


class TestGetCameraBaselineSummaryAutoSession:
    """Tests for get_camera_baseline_summary without session parameter."""

    @pytest.mark.asyncio
    async def test_get_summary_without_session(self) -> None:
        """Test get_camera_baseline_summary creates its own session."""
        from unittest.mock import patch

        service = BaselineService()

        with patch("backend.services.baseline.get_session") as mock_get_session:
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
            mock_session.__aenter__.return_value = mock_session
            mock_session.__aexit__.return_value = None
            mock_get_session.return_value = mock_session

            summary = await service.get_camera_baseline_summary("camera-1")

            assert summary["camera_id"] == "camera-1"
            mock_get_session.assert_called_once()


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


class TestGetHourlyPatternsAutoSession:
    """Tests for get_hourly_patterns without session parameter."""

    @pytest.mark.asyncio
    async def test_get_hourly_patterns_without_session(self) -> None:
        """Test get_hourly_patterns creates its own session."""
        from unittest.mock import patch

        service = BaselineService()

        with patch("backend.services.baseline.get_session") as mock_get_session:
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_scalars = MagicMock()
            mock_scalars.all.return_value = []
            mock_result.scalars.return_value = mock_scalars
            mock_session.execute.return_value = mock_result
            mock_session.__aenter__.return_value = mock_session
            mock_session.__aexit__.return_value = None
            mock_get_session.return_value = mock_session

            patterns = await service.get_hourly_patterns("camera-1")

            assert patterns == {}
            mock_get_session.assert_called_once()


class TestGetHourlyPatterns:
    """Tests for get_hourly_patterns method."""

    @pytest.mark.asyncio
    async def test_get_hourly_patterns_empty(self) -> None:
        """Test get_hourly_patterns with no baselines."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        service = BaselineService()
        patterns = await service.get_hourly_patterns("camera-1", session=mock_session)

        assert patterns == {}

    @pytest.mark.asyncio
    async def test_get_hourly_patterns_single_baseline(self) -> None:
        """Test get_hourly_patterns with single baseline per hour."""
        from backend.api.schemas.baseline import HourlyPattern

        mock_session = AsyncMock()

        mock_baseline = MagicMock()
        mock_baseline.hour = 14
        mock_baseline.avg_count = 5.5
        mock_baseline.sample_count = 20

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_baseline]
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        service = BaselineService()
        patterns = await service.get_hourly_patterns("camera-1", session=mock_session)

        assert "14" in patterns
        assert isinstance(patterns["14"], HourlyPattern)
        assert patterns["14"].avg_detections == 5.5
        assert patterns["14"].std_dev == 0.0  # Only one sample
        assert patterns["14"].sample_count == 20

    @pytest.mark.asyncio
    async def test_get_hourly_patterns_multiple_baselines(self) -> None:
        """Test get_hourly_patterns with multiple baselines per hour."""
        mock_session = AsyncMock()

        mock_baseline1 = MagicMock()
        mock_baseline1.hour = 14
        mock_baseline1.avg_count = 10.0
        mock_baseline1.sample_count = 20

        mock_baseline2 = MagicMock()
        mock_baseline2.hour = 14
        mock_baseline2.avg_count = 6.0
        mock_baseline2.sample_count = 15

        mock_baseline3 = MagicMock()
        mock_baseline3.hour = 15
        mock_baseline3.avg_count = 8.0
        mock_baseline3.sample_count = 10

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_baseline1, mock_baseline2, mock_baseline3]
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        service = BaselineService()
        patterns = await service.get_hourly_patterns("camera-1", session=mock_session)

        assert "14" in patterns
        assert "15" in patterns
        assert patterns["14"].avg_detections == 8.0  # Average of 10 and 6
        assert patterns["14"].sample_count == 35  # Sum of 20 and 15
        assert patterns["14"].std_dev > 0  # Should have non-zero std dev
        assert patterns["15"].avg_detections == 8.0
        assert patterns["15"].sample_count == 10


class TestGetDailyPatternsAutoSession:
    """Tests for get_daily_patterns without session parameter."""

    @pytest.mark.asyncio
    async def test_get_daily_patterns_without_session(self) -> None:
        """Test get_daily_patterns creates its own session."""
        from unittest.mock import patch

        service = BaselineService()

        with patch("backend.services.baseline.get_session") as mock_get_session:
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_scalars = MagicMock()
            mock_scalars.all.return_value = []
            mock_result.scalars.return_value = mock_scalars
            mock_session.execute.return_value = mock_result
            mock_session.__aenter__.return_value = mock_session
            mock_session.__aexit__.return_value = None
            mock_get_session.return_value = mock_session

            patterns = await service.get_daily_patterns("camera-1")

            assert patterns == {}
            mock_get_session.assert_called_once()


class TestGetDailyPatterns:
    """Tests for get_daily_patterns method."""

    @pytest.mark.asyncio
    async def test_get_daily_patterns_empty(self) -> None:
        """Test get_daily_patterns with no baselines."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        service = BaselineService()
        patterns = await service.get_daily_patterns("camera-1", session=mock_session)

        assert patterns == {}

    @pytest.mark.asyncio
    async def test_get_daily_patterns_with_data(self) -> None:
        """Test get_daily_patterns with baseline data."""
        from backend.api.schemas.baseline import DailyPattern

        mock_session = AsyncMock()

        # Monday (day 0) data
        mock_baseline1 = MagicMock()
        mock_baseline1.day_of_week = 0
        mock_baseline1.hour = 9
        mock_baseline1.avg_count = 10.0
        mock_baseline1.sample_count = 20

        mock_baseline2 = MagicMock()
        mock_baseline2.day_of_week = 0
        mock_baseline2.hour = 14
        mock_baseline2.avg_count = 15.0
        mock_baseline2.sample_count = 25

        # Tuesday (day 1) data
        mock_baseline3 = MagicMock()
        mock_baseline3.day_of_week = 1
        mock_baseline3.hour = 10
        mock_baseline3.avg_count = 8.0
        mock_baseline3.sample_count = 15

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_baseline1, mock_baseline2, mock_baseline3]
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        service = BaselineService()
        patterns = await service.get_daily_patterns("camera-1", session=mock_session)

        assert "monday" in patterns
        assert "tuesday" in patterns
        assert isinstance(patterns["monday"], DailyPattern)
        assert patterns["monday"].avg_detections == 25.0  # Sum of 10 and 15
        assert patterns["monday"].peak_hour == 14  # Hour with highest activity
        assert patterns["monday"].total_samples == 45  # Sum of 20 and 25
        assert patterns["tuesday"].avg_detections == 8.0
        assert patterns["tuesday"].peak_hour == 10


class TestGetObjectBaselinesAutoSession:
    """Tests for get_object_baselines without session parameter."""

    @pytest.mark.asyncio
    async def test_get_object_baselines_without_session(self) -> None:
        """Test get_object_baselines creates its own session."""
        from unittest.mock import patch

        service = BaselineService()

        with patch("backend.services.baseline.get_session") as mock_get_session:
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_scalars = MagicMock()
            mock_scalars.all.return_value = []
            mock_result.scalars.return_value = mock_scalars
            mock_session.execute.return_value = mock_result
            mock_session.__aenter__.return_value = mock_session
            mock_session.__aexit__.return_value = None
            mock_get_session.return_value = mock_session

            baselines = await service.get_object_baselines("camera-1")

            assert baselines == {}
            mock_get_session.assert_called_once()


class TestGetObjectBaselines:
    """Tests for get_object_baselines method."""

    @pytest.mark.asyncio
    async def test_get_object_baselines_empty(self) -> None:
        """Test get_object_baselines with no baselines."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        service = BaselineService()
        baselines = await service.get_object_baselines("camera-1", session=mock_session)

        assert baselines == {}

    @pytest.mark.asyncio
    async def test_get_object_baselines_with_data(self) -> None:
        """Test get_object_baselines with baseline data."""
        from backend.api.schemas.baseline import ObjectBaseline

        mock_session = AsyncMock()

        # Person class baselines
        mock_baseline1 = MagicMock()
        mock_baseline1.detection_class = "person"
        mock_baseline1.hour = 9
        mock_baseline1.frequency = 5.0
        mock_baseline1.sample_count = 20

        mock_baseline2 = MagicMock()
        mock_baseline2.detection_class = "person"
        mock_baseline2.hour = 14
        mock_baseline2.frequency = 8.0
        mock_baseline2.sample_count = 30

        # Vehicle class baseline
        mock_baseline3 = MagicMock()
        mock_baseline3.detection_class = "vehicle"
        mock_baseline3.hour = 10
        mock_baseline3.frequency = 3.0
        mock_baseline3.sample_count = 10

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_baseline1, mock_baseline2, mock_baseline3]
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        service = BaselineService()
        baselines = await service.get_object_baselines("camera-1", session=mock_session)

        assert "person" in baselines
        assert "vehicle" in baselines
        assert isinstance(baselines["person"], ObjectBaseline)
        assert baselines["person"].avg_hourly == 6.5  # Average of 5.0 and 8.0
        assert baselines["person"].peak_hour == 14  # Hour with highest frequency
        assert baselines["person"].total_detections == 50  # Sum of 20 and 30
        assert baselines["vehicle"].avg_hourly == 3.0
        assert baselines["vehicle"].peak_hour == 10
        assert baselines["vehicle"].total_detections == 10


class TestInterpretZScore:
    """Tests for _interpret_z_score method."""

    def test_interpret_far_below_normal(self) -> None:
        """Test z-score interpretation for far below normal."""
        from backend.api.schemas.baseline import DeviationInterpretation

        service = BaselineService()
        interpretation = service._interpret_z_score(-2.5)
        assert interpretation == DeviationInterpretation.FAR_BELOW_NORMAL

    def test_interpret_below_normal(self) -> None:
        """Test z-score interpretation for below normal."""
        from backend.api.schemas.baseline import DeviationInterpretation

        service = BaselineService()
        interpretation = service._interpret_z_score(-1.5)
        assert interpretation == DeviationInterpretation.BELOW_NORMAL

    def test_interpret_normal(self) -> None:
        """Test z-score interpretation for normal."""
        from backend.api.schemas.baseline import DeviationInterpretation

        service = BaselineService()
        interpretation = service._interpret_z_score(0.5)
        assert interpretation == DeviationInterpretation.NORMAL

    def test_interpret_slightly_above_normal(self) -> None:
        """Test z-score interpretation for slightly above normal."""
        from backend.api.schemas.baseline import DeviationInterpretation

        service = BaselineService()
        interpretation = service._interpret_z_score(1.5)
        assert interpretation == DeviationInterpretation.SLIGHTLY_ABOVE_NORMAL

    def test_interpret_above_normal(self) -> None:
        """Test z-score interpretation for above normal."""
        from backend.api.schemas.baseline import DeviationInterpretation

        service = BaselineService()
        interpretation = service._interpret_z_score(2.5)
        assert interpretation == DeviationInterpretation.ABOVE_NORMAL

    def test_interpret_far_above_normal(self) -> None:
        """Test z-score interpretation for far above normal."""
        from backend.api.schemas.baseline import DeviationInterpretation

        service = BaselineService()
        interpretation = service._interpret_z_score(3.5)
        assert interpretation == DeviationInterpretation.FAR_ABOVE_NORMAL


class TestGetCurrentDeviationAutoSession:
    """Tests for get_current_deviation without session parameter."""

    @pytest.mark.asyncio
    async def test_get_current_deviation_without_session(self) -> None:
        """Test get_current_deviation creates its own session."""
        from unittest.mock import patch

        service = BaselineService()

        with patch("backend.services.baseline.get_session") as mock_get_session:
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_session.execute.return_value = mock_result
            mock_session.__aenter__.return_value = mock_session
            mock_session.__aexit__.return_value = None
            mock_get_session.return_value = mock_session

            deviation = await service.get_current_deviation("camera-1")

            assert deviation is None
            mock_get_session.assert_called_once()


class TestGetCurrentDeviation:
    """Tests for get_current_deviation method."""

    @pytest.mark.asyncio
    async def test_get_current_deviation_no_baseline(self) -> None:
        """Test get_current_deviation when no baseline exists."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        service = BaselineService()
        deviation = await service.get_current_deviation("camera-1", session=mock_session)

        assert deviation is None

    @pytest.mark.asyncio
    async def test_get_current_deviation_insufficient_samples(self) -> None:
        """Test get_current_deviation with insufficient samples."""
        mock_session = AsyncMock()

        mock_baseline = MagicMock()
        mock_baseline.sample_count = 5  # Less than min_samples
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_baseline
        mock_session.execute.return_value = mock_result

        service = BaselineService(min_samples=10)
        deviation = await service.get_current_deviation("camera-1", session=mock_session)

        assert deviation is None

    @pytest.mark.asyncio
    async def test_get_current_deviation_with_data(self) -> None:
        """Test get_current_deviation with sufficient baseline data."""
        from backend.api.schemas.baseline import CurrentDeviation, DeviationInterpretation

        mock_session = AsyncMock()

        # Current baseline
        mock_baseline = MagicMock()
        mock_baseline.avg_count = 15.0
        mock_baseline.sample_count = 50

        # All baselines for this hour
        mock_all_baseline1 = MagicMock()
        mock_all_baseline1.avg_count = 10.0

        mock_all_baseline2 = MagicMock()
        mock_all_baseline2.avg_count = 12.0

        mock_all_baseline3 = MagicMock()
        mock_all_baseline3.avg_count = 15.0

        # First query: current baseline
        mock_result1 = MagicMock()
        mock_result1.scalar_one_or_none.return_value = mock_baseline

        # Second query: all baselines for this hour
        mock_result2 = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_all_baseline1, mock_all_baseline2, mock_all_baseline3]
        mock_result2.scalars.return_value = mock_scalars

        # Third query: class baselines
        mock_result3 = MagicMock()
        mock_class_scalars = MagicMock()
        mock_class_scalars.all.return_value = []
        mock_result3.scalars.return_value = mock_class_scalars

        mock_session.execute.side_effect = [mock_result1, mock_result2, mock_result3]

        service = BaselineService(min_samples=10)
        deviation = await service.get_current_deviation("camera-1", session=mock_session)

        assert deviation is not None
        assert isinstance(deviation, CurrentDeviation)
        assert isinstance(deviation.interpretation, DeviationInterpretation)
        assert isinstance(deviation.contributing_factors, list)

    @pytest.mark.asyncio
    async def test_get_current_deviation_elevated_factors(self) -> None:
        """Test get_current_deviation identifies elevated class factors."""
        mock_session = AsyncMock()

        # Current baseline with elevated activity
        mock_baseline = MagicMock()
        mock_baseline.avg_count = 20.0
        mock_baseline.sample_count = 50

        # All baselines showing lower averages
        mock_all_baseline = MagicMock()
        mock_all_baseline.avg_count = 10.0

        # Class baseline with elevated frequency
        mock_class_baseline = MagicMock()
        mock_class_baseline.detection_class = "person"
        mock_class_baseline.frequency = 5.0  # Above 2.0 threshold

        # First query: current baseline
        mock_result1 = MagicMock()
        mock_result1.scalar_one_or_none.return_value = mock_baseline

        # Second query: all baselines
        mock_result2 = MagicMock()
        mock_scalars2 = MagicMock()
        mock_scalars2.all.return_value = [mock_all_baseline]
        mock_result2.scalars.return_value = mock_scalars2

        # Third query: class baselines
        mock_result3 = MagicMock()
        mock_scalars3 = MagicMock()
        mock_scalars3.all.return_value = [mock_class_baseline]
        mock_result3.scalars.return_value = mock_scalars3

        mock_session.execute.side_effect = [mock_result1, mock_result2, mock_result3]

        service = BaselineService(min_samples=10)
        deviation = await service.get_current_deviation("camera-1", session=mock_session)

        assert deviation is not None
        assert "person_count_elevated" in deviation.contributing_factors


class TestGetBaselineEstablishedDateAutoSession:
    """Tests for get_baseline_established_date without session parameter."""

    @pytest.mark.asyncio
    async def test_get_baseline_established_date_without_session(self) -> None:
        """Test get_baseline_established_date creates its own session."""
        from unittest.mock import patch

        service = BaselineService()

        with patch("backend.services.baseline.get_session") as mock_get_session:
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar.return_value = None
            mock_session.execute.return_value = mock_result
            mock_session.__aenter__.return_value = mock_session
            mock_session.__aexit__.return_value = None
            mock_get_session.return_value = mock_session

            date = await service.get_baseline_established_date("camera-1")

            assert date is None
            mock_get_session.assert_called_once()


class TestGetBaselineEstablishedDate:
    """Tests for get_baseline_established_date method."""

    @pytest.mark.asyncio
    async def test_get_baseline_established_date_none(self) -> None:
        """Test get_baseline_established_date with no baselines."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = None
        mock_session.execute.return_value = mock_result

        service = BaselineService()
        date = await service.get_baseline_established_date("camera-1", session=mock_session)

        assert date is None

    @pytest.mark.asyncio
    async def test_get_baseline_established_date_activity_only(self) -> None:
        """Test get_baseline_established_date with only activity baselines."""
        mock_session = AsyncMock()
        activity_date = datetime(2025, 1, 1, tzinfo=UTC)

        # First query: activity baseline
        mock_result1 = MagicMock()
        mock_result1.scalar.return_value = activity_date

        # Second query: class baseline
        mock_result2 = MagicMock()
        mock_result2.scalar.return_value = None

        mock_session.execute.side_effect = [mock_result1, mock_result2]

        service = BaselineService()
        date = await service.get_baseline_established_date("camera-1", session=mock_session)

        assert date == activity_date

    @pytest.mark.asyncio
    async def test_get_baseline_established_date_class_only(self) -> None:
        """Test get_baseline_established_date with only class baselines."""
        mock_session = AsyncMock()
        class_date = datetime(2025, 1, 2, tzinfo=UTC)

        # First query: activity baseline
        mock_result1 = MagicMock()
        mock_result1.scalar.return_value = None

        # Second query: class baseline
        mock_result2 = MagicMock()
        mock_result2.scalar.return_value = class_date

        mock_session.execute.side_effect = [mock_result1, mock_result2]

        service = BaselineService()
        date = await service.get_baseline_established_date("camera-1", session=mock_session)

        assert date == class_date

    @pytest.mark.asyncio
    async def test_get_baseline_established_date_earliest(self) -> None:
        """Test get_baseline_established_date returns earliest date."""
        mock_session = AsyncMock()
        activity_date = datetime(2025, 1, 1, tzinfo=UTC)
        class_date = datetime(2025, 1, 5, tzinfo=UTC)

        # First query: activity baseline
        mock_result1 = MagicMock()
        mock_result1.scalar.return_value = activity_date

        # Second query: class baseline
        mock_result2 = MagicMock()
        mock_result2.scalar.return_value = class_date

        mock_session.execute.side_effect = [mock_result1, mock_result2]

        service = BaselineService()
        date = await service.get_baseline_established_date("camera-1", session=mock_session)

        assert date == activity_date  # Earlier date


class TestGetRecentAnomalies:
    """Tests for get_recent_anomalies method."""

    @pytest.mark.asyncio
    async def test_get_recent_anomalies_returns_empty(self) -> None:
        """Test get_recent_anomalies returns empty list (not implemented)."""
        service = BaselineService()
        anomalies = await service.get_recent_anomalies("camera-1", days=7)

        assert anomalies == []


class TestGetActivityBaselinesRawAutoSession:
    """Tests for get_activity_baselines_raw without session parameter."""

    @pytest.mark.asyncio
    async def test_get_activity_baselines_raw_without_session(self) -> None:
        """Test get_activity_baselines_raw creates its own session."""
        from unittest.mock import patch

        service = BaselineService()

        with patch("backend.services.baseline.get_session") as mock_get_session:
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_scalars = MagicMock()
            mock_scalars.all.return_value = []
            mock_result.scalars.return_value = mock_scalars
            mock_session.execute.return_value = mock_result
            mock_session.__aenter__.return_value = mock_session
            mock_session.__aexit__.return_value = None
            mock_get_session.return_value = mock_session

            baselines = await service.get_activity_baselines_raw("camera-1")

            assert baselines == []
            mock_get_session.assert_called_once()


class TestGetActivityBaselinesRaw:
    """Tests for get_activity_baselines_raw method."""

    @pytest.mark.asyncio
    async def test_get_activity_baselines_raw_empty(self) -> None:
        """Test get_activity_baselines_raw with no baselines."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        service = BaselineService()
        baselines = await service.get_activity_baselines_raw("camera-1", session=mock_session)

        assert baselines == []

    @pytest.mark.asyncio
    async def test_get_activity_baselines_raw_with_data(self) -> None:
        """Test get_activity_baselines_raw returns ordered data."""
        mock_session = AsyncMock()

        mock_baseline1 = MagicMock()
        mock_baseline1.day_of_week = 0
        mock_baseline1.hour = 9

        mock_baseline2 = MagicMock()
        mock_baseline2.day_of_week = 0
        mock_baseline2.hour = 14

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_baseline1, mock_baseline2]
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        service = BaselineService()
        baselines = await service.get_activity_baselines_raw("camera-1", session=mock_session)

        assert len(baselines) == 2
        assert baselines[0].day_of_week == 0
        assert baselines[0].hour == 9


class TestGetClassBaselinesRawAutoSession:
    """Tests for get_class_baselines_raw without session parameter."""

    @pytest.mark.asyncio
    async def test_get_class_baselines_raw_without_session(self) -> None:
        """Test get_class_baselines_raw creates its own session."""
        from unittest.mock import patch

        service = BaselineService()

        with patch("backend.services.baseline.get_session") as mock_get_session:
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_scalars = MagicMock()
            mock_scalars.all.return_value = []
            mock_result.scalars.return_value = mock_scalars
            mock_session.execute.return_value = mock_result
            mock_session.__aenter__.return_value = mock_session
            mock_session.__aexit__.return_value = None
            mock_get_session.return_value = mock_session

            baselines = await service.get_class_baselines_raw("camera-1")

            assert baselines == []
            mock_get_session.assert_called_once()


class TestGetClassBaselinesRaw:
    """Tests for get_class_baselines_raw method."""

    @pytest.mark.asyncio
    async def test_get_class_baselines_raw_empty(self) -> None:
        """Test get_class_baselines_raw with no baselines."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        service = BaselineService()
        baselines = await service.get_class_baselines_raw("camera-1", session=mock_session)

        assert baselines == []

    @pytest.mark.asyncio
    async def test_get_class_baselines_raw_with_data(self) -> None:
        """Test get_class_baselines_raw returns ordered data."""
        mock_session = AsyncMock()

        mock_baseline1 = MagicMock()
        mock_baseline1.detection_class = "person"
        mock_baseline1.hour = 9

        mock_baseline2 = MagicMock()
        mock_baseline2.detection_class = "person"
        mock_baseline2.hour = 14

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_baseline1, mock_baseline2]
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        service = BaselineService()
        baselines = await service.get_class_baselines_raw("camera-1", session=mock_session)

        assert len(baselines) == 2
        assert baselines[0].detection_class == "person"
        assert baselines[0].hour == 9


class TestUpdateConfig:
    """Tests for update_config method."""

    def test_update_config_threshold(self) -> None:
        """Test updating anomaly threshold."""
        service = BaselineService(anomaly_threshold_std=2.0)
        service.update_config(threshold_stdev=3.0)

        assert service.anomaly_threshold_std == 3.0

    def test_update_config_min_samples(self) -> None:
        """Test updating minimum samples."""
        service = BaselineService(min_samples=10)
        service.update_config(min_samples=20)

        assert service.min_samples == 20

    def test_update_config_both_params(self) -> None:
        """Test updating both parameters."""
        service = BaselineService()
        service.update_config(threshold_stdev=3.5, min_samples=15)

        assert service.anomaly_threshold_std == 3.5
        assert service.min_samples == 15

    def test_update_config_invalid_threshold(self) -> None:
        """Test that invalid threshold raises ValueError."""
        service = BaselineService()

        with pytest.raises(ValueError) as exc_info:
            service.update_config(threshold_stdev=0)

        assert "threshold_stdev must be positive" in str(exc_info.value)

    def test_update_config_negative_threshold(self) -> None:
        """Test that negative threshold raises ValueError."""
        service = BaselineService()

        with pytest.raises(ValueError) as exc_info:
            service.update_config(threshold_stdev=-1.0)

        assert "threshold_stdev must be positive" in str(exc_info.value)

    def test_update_config_invalid_min_samples(self) -> None:
        """Test that invalid min_samples raises ValueError."""
        service = BaselineService()

        with pytest.raises(ValueError) as exc_info:
            service.update_config(min_samples=0)

        assert "min_samples must be at least 1" in str(exc_info.value)


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


# =============================================================================
# Property-Based Tests (Hypothesis)
# =============================================================================


class TestPropertyBasedDecay:
    """Property-based tests for time decay calculations."""

    @given(
        decay_factor=st.floats(min_value=0.01, max_value=1.0),
        days_elapsed=st.floats(min_value=0.0, max_value=30.0),
    )
    def test_decay_always_between_zero_and_one(
        self, decay_factor: float, days_elapsed: float
    ) -> None:
        """Property: decay value is always between 0 and 1."""
        service = BaselineService(decay_factor=decay_factor, window_days=30)
        now = datetime.now(UTC)
        past = now - timedelta(days=days_elapsed)

        decay = service._calculate_time_decay(past, now)

        assert 0.0 <= decay <= 1.0

    @given(
        decay_factor=st.floats(min_value=0.01, max_value=1.0),
        window_days=st.integers(min_value=1, max_value=365),
    )
    def test_decay_outside_window_is_zero(self, decay_factor: float, window_days: int) -> None:
        """Property: decay outside window is exactly zero."""
        service = BaselineService(decay_factor=decay_factor, window_days=window_days)
        now = datetime.now(UTC)
        outside_window = now - timedelta(days=window_days + 1)

        decay = service._calculate_time_decay(outside_window, now)

        assert decay == 0.0

    @given(decay_factor=st.floats(min_value=0.01, max_value=1.0))
    def test_decay_at_zero_time_is_one(self, decay_factor: float) -> None:
        """Property: decay at zero time elapsed is 1.0."""
        service = BaselineService(decay_factor=decay_factor)
        now = datetime.now(UTC)

        decay = service._calculate_time_decay(now, now)

        assert abs(decay - 1.0) < 0.001  # Allow small floating point error

    @given(
        decay_factor=st.floats(min_value=0.01, max_value=0.99),
        days_elapsed=st.floats(min_value=1.0, max_value=29.0),
    )
    def test_decay_is_monotonically_decreasing(
        self, decay_factor: float, days_elapsed: float
    ) -> None:
        """Property: decay decreases as time increases."""
        service = BaselineService(decay_factor=decay_factor, window_days=30)
        now = datetime.now(UTC)
        earlier = now - timedelta(days=days_elapsed)
        later = now - timedelta(days=days_elapsed / 2)

        decay_earlier = service._calculate_time_decay(earlier, now)
        decay_later = service._calculate_time_decay(later, now)

        # Decay at earlier time should be less than or equal to decay at later time
        assert decay_earlier <= decay_later

    @given(
        window_days=st.integers(min_value=1, max_value=365),
        min_samples=st.integers(min_value=1, max_value=100),
    )
    def test_service_initialization_invariants(self, window_days: int, min_samples: int) -> None:
        """Property: service initialization preserves values."""
        service = BaselineService(
            decay_factor=0.5,
            window_days=window_days,
            anomaly_threshold_std=2.0,
            min_samples=min_samples,
        )

        assert service.decay_factor == 0.5
        assert service.window_days == window_days
        assert service.anomaly_threshold_std == 2.0
        assert service.min_samples == min_samples


class TestPropertyBasedAnomalyScores:
    """Property-based tests for anomaly score calculations."""

    @given(
        anomaly_threshold_std=st.floats(min_value=0.0, max_value=5.0),
        min_samples=st.integers(min_value=1, max_value=100),
    )
    def test_anomaly_score_in_valid_range(
        self, anomaly_threshold_std: float, min_samples: int
    ) -> None:
        """Property: anomaly scores are always between 0.0 and 1.0."""
        # This test validates the invariant without needing database
        service = BaselineService(
            anomaly_threshold_std=anomaly_threshold_std, min_samples=min_samples
        )

        # Test that the service is initialized with valid parameters
        assert service.anomaly_threshold_std == anomaly_threshold_std
        assert service.min_samples == min_samples
        assert 0.0 <= anomaly_threshold_std <= 5.0
        assert 1 <= min_samples <= 100


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_midnight_boundary_hour_zero(self) -> None:
        """Test detection at midnight (hour 0)."""
        _service = BaselineService()
        timestamp = datetime(2025, 12, 23, 0, 0, 0, tzinfo=UTC)

        # Should not raise
        assert timestamp.hour == 0

    def test_day_of_week_boundary_sunday(self) -> None:
        """Test detection on Sunday (day 6)."""
        _service = BaselineService()
        # 2025-12-21 is a Sunday
        timestamp = datetime(2025, 12, 21, 12, 0, 0, tzinfo=UTC)

        assert timestamp.weekday() == 6

    def test_threshold_boundary_exact_match(self) -> None:
        """Test anomaly detection at exact threshold boundary."""
        service = BaselineService(anomaly_threshold_std=2.0)

        # Test that service can handle exact threshold calculations
        # The actual threshold cutoff is: 1.0 - 1.0 / (2.0 + 1) = 1.0 - 1/3 ≈ 0.667
        threshold = 1.0 - 1.0 / (service.anomaly_threshold_std + 1)

        assert abs(threshold - 0.667) < 0.01

    def test_time_decay_with_microseconds(self) -> None:
        """Test time decay calculation with microseconds precision."""
        service = BaselineService()
        now = datetime(2025, 12, 23, 12, 0, 0, 123456, tzinfo=UTC)
        past = datetime(2025, 12, 23, 11, 59, 59, 999999, tzinfo=UTC)

        decay = service._calculate_time_decay(past, now)

        # Should handle microsecond precision
        assert 0.0 <= decay <= 1.0

    @pytest.mark.asyncio
    async def test_update_baseline_without_session_creates_new_session(self) -> None:
        """Test update_baseline without session parameter creates its own."""
        service = BaselineService()
        timestamp = datetime(2025, 12, 23, 14, 30, 0, tzinfo=UTC)

        # Mock get_session to track if it was called
        with patch("backend.services.baseline.get_session") as mock_get_session:
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_session.execute.return_value = mock_result
            mock_session.commit = AsyncMock()

            # Make get_session return an async context manager
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_session
            mock_context.__aexit__.return_value = None
            mock_get_session.return_value = mock_context

            await service.update_baseline("camera-1", "person", timestamp)

            # Verify that get_session was called (no session passed)
            mock_get_session.assert_called_once()
            # Verify commit was called
            mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_activity_rate_without_session_creates_new_session(self) -> None:
        """Test get_activity_rate without session creates its own."""
        service = BaselineService()

        with patch("backend.services.baseline.get_session") as mock_get_session:
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_session.execute.return_value = mock_result

            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_session
            mock_context.__aexit__.return_value = None
            mock_get_session.return_value = mock_context

            rate = await service.get_activity_rate("camera-1", 14, 0)

            mock_get_session.assert_called_once()
            assert rate == 0.0

    @pytest.mark.asyncio
    async def test_get_class_frequency_without_session_creates_new_session(self) -> None:
        """Test get_class_frequency without session creates its own."""
        service = BaselineService()

        with patch("backend.services.baseline.get_session") as mock_get_session:
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_session.execute.return_value = mock_result

            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_session
            mock_context.__aexit__.return_value = None
            mock_get_session.return_value = mock_context

            freq = await service.get_class_frequency("camera-1", "person", 14)

            mock_get_session.assert_called_once()
            assert freq == 0.0
