"""Integration tests for baseline activity modeling service.

Tests cover:
- Update baseline operations (with mocked database)
- Activity rate and class frequency queries (with mocked database)
- Anomaly detection (with mocked database)
- Camera baseline summary (with mocked database)
- Full integration tests (with real test database)

Unit tests (initialization, singleton, time decay, model attributes)
have been moved to backend/tests/unit/test_baseline.py
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.baseline import (
    BaselineService,
    reset_baseline_service,
)

# Mark as integration since tests require mocked or real PostgreSQL database
pytestmark = pytest.mark.integration


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def baseline_service():
    """Create baseline service instance with default configuration."""
    return BaselineService()


@pytest.fixture(autouse=True)
def reset_service_singleton():
    """Reset the baseline service singleton before and after each test."""
    reset_baseline_service()
    yield
    reset_baseline_service()


# ============================================================================
# Update Baseline Tests (with mocked database)
# ============================================================================


class TestUpdateBaseline:
    """Tests for update_baseline method."""

    @pytest.mark.asyncio
    async def test_update_baseline_creates_new_records(self, baseline_service):
        """Test that update_baseline creates new baseline records."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        timestamp = datetime(2025, 1, 15, 10, 30, 0, tzinfo=UTC)

        await baseline_service.update_baseline(
            camera_id="camera_1",
            detection_class="person",
            timestamp=timestamp,
            session=mock_session,
        )

        # Should have made 2 select queries (activity + class baseline)
        # and added 2 new objects
        assert mock_session.add.call_count == 2

    @pytest.mark.asyncio
    async def test_update_baseline_updates_existing(self, baseline_service):
        """Test that update_baseline updates existing baseline records."""
        mock_session = AsyncMock()

        # Mock existing activity baseline
        existing_activity = MagicMock()
        existing_activity.id = 1
        existing_activity.avg_count = 5.0
        existing_activity.sample_count = 10
        existing_activity.last_updated = datetime(2025, 1, 14, 10, 0, 0, tzinfo=UTC)

        # Mock existing class baseline
        existing_class = MagicMock()
        existing_class.id = 2
        existing_class.frequency = 0.5
        existing_class.sample_count = 8
        existing_class.last_updated = datetime(2025, 1, 14, 10, 0, 0, tzinfo=UTC)

        mock_result1 = MagicMock()
        mock_result1.scalar_one_or_none.return_value = existing_activity
        mock_result2 = MagicMock()
        mock_result2.scalar_one_or_none.return_value = existing_class

        mock_session.execute.side_effect = [mock_result1, MagicMock(), mock_result2, MagicMock()]

        timestamp = datetime(2025, 1, 15, 10, 30, 0, tzinfo=UTC)

        await baseline_service.update_baseline(
            camera_id="camera_1",
            detection_class="person",
            timestamp=timestamp,
            session=mock_session,
        )

        # Should have updated existing records (execute called for updates)
        # 2 selects + 2 updates = 4 executes
        assert mock_session.execute.call_count == 4


# ============================================================================
# Get Activity Rate Tests (with mocked database)
# ============================================================================


class TestGetActivityRate:
    """Tests for get_activity_rate method."""

    @pytest.mark.asyncio
    async def test_get_activity_rate_no_baseline(self, baseline_service):
        """Test get_activity_rate returns 0 when no baseline exists."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        rate = await baseline_service.get_activity_rate(
            camera_id="camera_1",
            hour=10,
            day_of_week=2,
            session=mock_session,
        )

        assert rate == 0.0

    @pytest.mark.asyncio
    async def test_get_activity_rate_with_baseline(self, baseline_service):
        """Test get_activity_rate returns decayed average."""
        mock_session = AsyncMock()

        existing_baseline = MagicMock()
        existing_baseline.avg_count = 10.0
        existing_baseline.last_updated = datetime.now(UTC) - timedelta(hours=12)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_baseline
        mock_session.execute.return_value = mock_result

        rate = await baseline_service.get_activity_rate(
            camera_id="camera_1",
            hour=10,
            day_of_week=2,
            session=mock_session,
        )

        # Rate should be positive but less than 10 due to decay
        assert 0 < rate < 10.0

    @pytest.mark.asyncio
    async def test_get_activity_rate_stale_baseline(self, baseline_service):
        """Test get_activity_rate with stale baseline returns 0."""
        mock_session = AsyncMock()

        # Baseline older than window
        existing_baseline = MagicMock()
        existing_baseline.avg_count = 10.0
        existing_baseline.last_updated = datetime.now(UTC) - timedelta(days=45)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_baseline
        mock_session.execute.return_value = mock_result

        rate = await baseline_service.get_activity_rate(
            camera_id="camera_1",
            hour=10,
            day_of_week=2,
            session=mock_session,
        )

        # Decay is 0 for stale baselines
        assert rate == 0.0


# ============================================================================
# Get Class Frequency Tests (with mocked database)
# ============================================================================


class TestGetClassFrequency:
    """Tests for get_class_frequency method."""

    @pytest.mark.asyncio
    async def test_get_class_frequency_no_baseline(self, baseline_service):
        """Test get_class_frequency returns 0 when no baseline exists."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        freq = await baseline_service.get_class_frequency(
            camera_id="camera_1",
            detection_class="vehicle",
            hour=3,
            session=mock_session,
        )

        assert freq == 0.0

    @pytest.mark.asyncio
    async def test_get_class_frequency_with_baseline(self, baseline_service):
        """Test get_class_frequency returns decayed frequency."""
        mock_session = AsyncMock()

        existing_baseline = MagicMock()
        existing_baseline.frequency = 0.8
        existing_baseline.last_updated = datetime.now(UTC) - timedelta(hours=6)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_baseline
        mock_session.execute.return_value = mock_result

        freq = await baseline_service.get_class_frequency(
            camera_id="camera_1",
            detection_class="person",
            hour=10,
            session=mock_session,
        )

        # Frequency should be positive but less than 0.8 due to decay
        assert 0 < freq < 0.8


# ============================================================================
# Anomaly Detection Tests (with mocked database)
# ============================================================================


class TestIsAnomalous:
    """Tests for is_anomalous method."""

    @pytest.mark.asyncio
    async def test_is_anomalous_no_baselines(self, baseline_service):
        """Test is_anomalous returns neutral when no baselines exist."""
        mock_session = AsyncMock()

        mock_class_result = MagicMock()
        mock_class_result.scalar_one_or_none.return_value = None

        mock_all_result = MagicMock()
        mock_all_result.scalars.return_value.all.return_value = []

        mock_session.execute.side_effect = [mock_class_result, mock_all_result]

        timestamp = datetime(2025, 1, 15, 10, 30, 0, tzinfo=UTC)

        is_anomaly, score = await baseline_service.is_anomalous(
            camera_id="camera_1",
            detection_class="vehicle",
            timestamp=timestamp,
            session=mock_session,
        )

        # No data means uncertain, returns neutral
        assert is_anomaly is False
        assert score == 0.5

    @pytest.mark.asyncio
    async def test_is_anomalous_insufficient_samples(self, baseline_service):
        """Test is_anomalous returns neutral with insufficient samples."""
        mock_session = AsyncMock()

        # Create baseline with low sample count
        existing_baseline = MagicMock()
        existing_baseline.detection_class = "person"
        existing_baseline.frequency = 0.5
        existing_baseline.sample_count = 3  # Below min_samples (10)
        existing_baseline.last_updated = datetime.now(UTC)

        mock_class_result = MagicMock()
        mock_class_result.scalar_one_or_none.return_value = existing_baseline

        mock_all_result = MagicMock()
        mock_all_result.scalars.return_value.all.return_value = [existing_baseline]

        mock_session.execute.side_effect = [mock_class_result, mock_all_result]

        timestamp = datetime(2025, 1, 15, 10, 30, 0, tzinfo=UTC)

        is_anomaly, score = await baseline_service.is_anomalous(
            camera_id="camera_1",
            detection_class="person",
            timestamp=timestamp,
            session=mock_session,
        )

        # Insufficient samples means uncertain
        assert is_anomaly is False
        assert score == 0.5

    @pytest.mark.asyncio
    async def test_is_anomalous_class_never_seen(self, baseline_service):
        """Test is_anomalous for class never seen at this hour."""
        mock_session = AsyncMock()

        # Other class exists but not the one we're checking
        other_baseline = MagicMock()
        other_baseline.detection_class = "person"
        other_baseline.frequency = 1.0
        other_baseline.sample_count = 50
        other_baseline.last_updated = datetime.now(UTC)

        mock_class_result = MagicMock()
        mock_class_result.scalar_one_or_none.return_value = None  # vehicle never seen

        mock_all_result = MagicMock()
        mock_all_result.scalars.return_value.all.return_value = [other_baseline]

        mock_session.execute.side_effect = [mock_class_result, mock_all_result]

        timestamp = datetime(2025, 1, 15, 3, 0, 0, tzinfo=UTC)  # 3 AM

        is_anomaly, score = await baseline_service.is_anomalous(
            camera_id="camera_1",
            detection_class="vehicle",
            timestamp=timestamp,
            session=mock_session,
        )

        # Vehicle never seen at 3 AM = highly anomalous
        assert is_anomaly is True
        assert score == 1.0

    @pytest.mark.asyncio
    async def test_is_anomalous_common_class(self, baseline_service):
        """Test is_anomalous for commonly seen class."""
        mock_session = AsyncMock()

        # Person is frequently seen at this hour
        person_baseline = MagicMock()
        person_baseline.detection_class = "person"
        person_baseline.frequency = 0.9
        person_baseline.sample_count = 100
        person_baseline.last_updated = datetime.now(UTC)

        mock_class_result = MagicMock()
        mock_class_result.scalar_one_or_none.return_value = person_baseline

        mock_all_result = MagicMock()
        mock_all_result.scalars.return_value.all.return_value = [person_baseline]

        mock_session.execute.side_effect = [mock_class_result, mock_all_result]

        timestamp = datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC)

        is_anomaly, score = await baseline_service.is_anomalous(
            camera_id="camera_1",
            detection_class="person",
            timestamp=timestamp,
            session=mock_session,
        )

        # Person commonly seen = not anomalous
        assert is_anomaly is False
        assert score < 0.5  # Low anomaly score

    @pytest.mark.asyncio
    async def test_is_anomalous_rare_class(self, baseline_service):
        """Test is_anomalous for rarely seen class."""
        mock_session = AsyncMock()

        # Person is common, vehicle is rare
        person_baseline = MagicMock()
        person_baseline.detection_class = "person"
        person_baseline.frequency = 0.9
        person_baseline.sample_count = 100
        person_baseline.last_updated = datetime.now(UTC)

        vehicle_baseline = MagicMock()
        vehicle_baseline.detection_class = "vehicle"
        vehicle_baseline.frequency = 0.1
        vehicle_baseline.sample_count = 10
        vehicle_baseline.last_updated = datetime.now(UTC)

        mock_class_result = MagicMock()
        mock_class_result.scalar_one_or_none.return_value = vehicle_baseline

        mock_all_result = MagicMock()
        mock_all_result.scalars.return_value.all.return_value = [
            person_baseline,
            vehicle_baseline,
        ]

        mock_session.execute.side_effect = [mock_class_result, mock_all_result]

        timestamp = datetime(2025, 1, 15, 3, 0, 0, tzinfo=UTC)

        _is_anomaly, score = await baseline_service.is_anomalous(
            camera_id="camera_1",
            detection_class="vehicle",
            timestamp=timestamp,
            session=mock_session,
        )

        # Vehicle rarely seen = higher anomaly score
        assert score > 0.5


# ============================================================================
# Camera Baseline Summary Tests
# ============================================================================


class TestCameraBaselineSummary:
    """Tests for get_camera_baseline_summary method."""

    @pytest.mark.asyncio
    async def test_summary_no_baselines(self, baseline_service):
        """Test summary when camera has no baselines."""
        mock_session = AsyncMock()

        mock_activity_result = MagicMock()
        mock_activity_result.scalars.return_value.all.return_value = []

        mock_class_result = MagicMock()
        mock_class_result.scalars.return_value.all.return_value = []

        mock_session.execute.side_effect = [mock_activity_result, mock_class_result]

        summary = await baseline_service.get_camera_baseline_summary(
            camera_id="new_camera",
            session=mock_session,
        )

        assert summary["camera_id"] == "new_camera"
        assert summary["activity_baseline_count"] == 0
        assert summary["class_baseline_count"] == 0
        assert summary["unique_classes"] == 0
        assert summary["top_classes"] == []
        assert summary["peak_hours"] == []

    @pytest.mark.asyncio
    async def test_summary_with_baselines(self, baseline_service):
        """Test summary with existing baselines."""
        mock_session = AsyncMock()

        # Activity baselines
        activity1 = MagicMock()
        activity1.hour = 10
        activity1.avg_count = 5.0

        activity2 = MagicMock()
        activity2.hour = 14
        activity2.avg_count = 8.0

        mock_activity_result = MagicMock()
        mock_activity_result.scalars.return_value.all.return_value = [activity1, activity2]

        # Class baselines
        class1 = MagicMock()
        class1.detection_class = "person"
        class1.frequency = 0.8

        class2 = MagicMock()
        class2.detection_class = "vehicle"
        class2.frequency = 0.3

        mock_class_result = MagicMock()
        mock_class_result.scalars.return_value.all.return_value = [class1, class2]

        mock_session.execute.side_effect = [mock_activity_result, mock_class_result]

        summary = await baseline_service.get_camera_baseline_summary(
            camera_id="camera_1",
            session=mock_session,
        )

        assert summary["camera_id"] == "camera_1"
        assert summary["activity_baseline_count"] == 2
        assert summary["class_baseline_count"] == 2
        assert summary["unique_classes"] == 2
        assert len(summary["top_classes"]) == 2
        assert summary["top_classes"][0]["class"] == "person"  # Highest frequency
        assert len(summary["peak_hours"]) == 2
        assert summary["peak_hours"][0]["hour"] == 14  # Highest activity


# ============================================================================
# Integration Tests (with test database)
# ============================================================================


@pytest.mark.slow
@pytest.mark.asyncio
async def test_baseline_service_with_database(test_db):
    """Integration test: update and query baselines with real database."""
    from backend.models.camera import Camera

    service = BaselineService()

    async with test_db() as session:
        # Create a test camera
        camera = Camera(
            id="test_camera_1",
            name="Test Camera",
            folder_path="/test/path",
            status="online",
        )
        session.add(camera)
        await session.commit()

        # Update baselines
        timestamp = datetime.now(UTC)
        await service.update_baseline(
            camera_id="test_camera_1",
            detection_class="person",
            timestamp=timestamp,
            session=session,
        )
        await session.commit()

        # Query activity rate
        hour = timestamp.hour
        day_of_week = timestamp.weekday()
        rate = await service.get_activity_rate(
            camera_id="test_camera_1",
            hour=hour,
            day_of_week=day_of_week,
            session=session,
        )

        assert rate > 0

        # Query class frequency
        freq = await service.get_class_frequency(
            camera_id="test_camera_1",
            detection_class="person",
            hour=hour,
            session=session,
        )

        assert freq > 0


@pytest.mark.slow
@pytest.mark.asyncio
async def test_baseline_multiple_updates(test_db):
    """Integration test: multiple updates to the same baseline."""
    from backend.models.camera import Camera

    service = BaselineService(decay_factor=0.5)  # Higher decay for visible changes

    async with test_db() as session:
        # Create a test camera
        camera = Camera(
            id="test_camera_2",
            name="Test Camera 2",
            folder_path="/test/path2",
            status="online",
        )
        session.add(camera)
        await session.commit()

        # First update
        timestamp = datetime.now(UTC)
        await service.update_baseline(
            camera_id="test_camera_2",
            detection_class="person",
            timestamp=timestamp,
            session=session,
        )
        await session.commit()

        rate1 = await service.get_activity_rate(
            camera_id="test_camera_2",
            hour=timestamp.hour,
            day_of_week=timestamp.weekday(),
            session=session,
        )

        # Second update (same time slot)
        await service.update_baseline(
            camera_id="test_camera_2",
            detection_class="person",
            timestamp=timestamp,
            session=session,
        )
        await session.commit()

        rate2 = await service.get_activity_rate(
            camera_id="test_camera_2",
            hour=timestamp.hour,
            day_of_week=timestamp.weekday(),
            session=session,
        )

        # Rate should have increased with more observations
        # (EWMA should blend the values)
        assert rate2 >= rate1 * 0.9  # Allow for decay effects


@pytest.mark.slow
@pytest.mark.asyncio
async def test_baseline_different_classes(test_db):
    """Integration test: track different classes at the same hour."""
    from backend.models.camera import Camera

    service = BaselineService()

    async with test_db() as session:
        # Create a test camera
        camera = Camera(
            id="test_camera_3",
            name="Test Camera 3",
            folder_path="/test/path3",
            status="online",
        )
        session.add(camera)
        await session.commit()

        timestamp = datetime.now(UTC)

        # Update person baseline
        await service.update_baseline(
            camera_id="test_camera_3",
            detection_class="person",
            timestamp=timestamp,
            session=session,
        )
        await session.commit()

        # Update vehicle baseline
        await service.update_baseline(
            camera_id="test_camera_3",
            detection_class="vehicle",
            timestamp=timestamp,
            session=session,
        )
        await session.commit()

        # Check frequencies
        person_freq = await service.get_class_frequency(
            camera_id="test_camera_3",
            detection_class="person",
            hour=timestamp.hour,
            session=session,
        )

        vehicle_freq = await service.get_class_frequency(
            camera_id="test_camera_3",
            detection_class="vehicle",
            hour=timestamp.hour,
            session=session,
        )

        # Both should be tracked
        assert person_freq > 0
        assert vehicle_freq > 0

        # Get summary
        summary = await service.get_camera_baseline_summary(
            camera_id="test_camera_3",
            session=session,
        )

        assert summary["unique_classes"] == 2
