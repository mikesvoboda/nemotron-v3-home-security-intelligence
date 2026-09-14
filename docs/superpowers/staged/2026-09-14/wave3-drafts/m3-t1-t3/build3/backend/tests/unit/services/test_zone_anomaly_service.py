"""Unit tests for zone anomaly detection service.

Tests cover:
- ZoneAnomalyService initialization
- Unusual time detection logic
- Unusual frequency detection logic
- Unusual dwell detection logic
- Severity mapping from deviation
- WebSocket event emission
- Anomaly persistence
- Query methods

Related: NEM-3198 (Backend Anomaly Detection Service)
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.models.zone_anomaly import AnomalySeverity, AnomalyType

# =============================================================================
# Initialization Tests
# =============================================================================


class TestZoneAnomalyServiceInit:
    """Tests for ZoneAnomalyService initialization."""

    def test_init_default_values(self) -> None:
        """Test initialization with default values."""
        from backend.services.zone_anomaly_service import ZoneAnomalyService

        service = ZoneAnomalyService()
        assert service.DEFAULT_THRESHOLD == 2.0
        assert service._redis is None

    def test_init_with_redis_client(self) -> None:
        """Test initialization with Redis client."""
        from backend.services.zone_anomaly_service import ZoneAnomalyService

        mock_redis = MagicMock()
        service = ZoneAnomalyService(redis_client=mock_redis)
        assert service._redis is mock_redis


# =============================================================================
# Severity Mapping Tests
# =============================================================================


class TestDeviationToSeverity:
    """Tests for _deviation_to_severity method."""

    def test_deviation_below_threshold_returns_info(self) -> None:
        """Test that low deviation returns info severity."""
        from backend.services.zone_anomaly_service import ZoneAnomalyService

        service = ZoneAnomalyService()
        assert service._deviation_to_severity(1.0) == AnomalySeverity.INFO
        assert service._deviation_to_severity(2.0) == AnomalySeverity.INFO
        assert service._deviation_to_severity(2.9) == AnomalySeverity.INFO

    def test_deviation_at_warning_threshold(self) -> None:
        """Test that deviation >= 3.0 returns warning."""
        from backend.services.zone_anomaly_service import ZoneAnomalyService

        service = ZoneAnomalyService()
        assert service._deviation_to_severity(3.0) == AnomalySeverity.WARNING
        assert service._deviation_to_severity(3.5) == AnomalySeverity.WARNING
        assert service._deviation_to_severity(3.9) == AnomalySeverity.WARNING

    def test_deviation_at_critical_threshold(self) -> None:
        """Test that deviation >= 4.0 returns critical."""
        from backend.services.zone_anomaly_service import ZoneAnomalyService

        service = ZoneAnomalyService()
        assert service._deviation_to_severity(4.0) == AnomalySeverity.CRITICAL
        assert service._deviation_to_severity(5.0) == AnomalySeverity.CRITICAL
        assert service._deviation_to_severity(10.0) == AnomalySeverity.CRITICAL

    def test_deviation_zero_returns_info(self) -> None:
        """Test that zero deviation returns info."""
        from backend.services.zone_anomaly_service import ZoneAnomalyService

        service = ZoneAnomalyService()
        assert service._deviation_to_severity(0.0) == AnomalySeverity.INFO


# =============================================================================
# Unusual Time Detection Tests
# =============================================================================


class TestCheckUnusualTime:
    """Tests for _check_unusual_time method."""

    def test_detection_at_normal_hour_returns_none(self) -> None:
        """Test that detection at a busy hour returns no anomaly."""
        from backend.services.zone_anomaly_service import ZoneAnomalyService

        service = ZoneAnomalyService()

        detection = MagicMock()
        detection.detected_at = datetime(2026, 1, 21, 14, 30, 0, tzinfo=UTC)
        detection.id = 123
        detection.thumbnail_path = "/thumbnails/det_123.jpg"

        zone = MagicMock()
        zone.id = str(uuid.uuid4())
        zone.camera_id = "front_door"
        zone.name = "Front Yard"

        baseline = MagicMock()
        baseline.hourly_pattern = [0.0] * 24
        baseline.hourly_pattern[14] = 10.0
        baseline.hourly_std = [1.0] * 24

        result = service._check_unusual_time(detection, zone, baseline, threshold=2.0)
        assert result is None

    def test_detection_at_quiet_hour_returns_anomaly(self) -> None:
        """Test that detection at a typically quiet hour returns anomaly."""
        from backend.services.zone_anomaly_service import ZoneAnomalyService

        service = ZoneAnomalyService()

        detection = MagicMock()
        detection.detected_at = datetime(2026, 1, 21, 3, 15, 0, tzinfo=UTC)
        detection.id = 123
        detection.thumbnail_path = "/thumbnails/det_123.jpg"

        zone = MagicMock()
        zone.id = str(uuid.uuid4())
        zone.camera_id = "front_door"
        zone.name = "Front Yard"

        baseline = MagicMock()
        baseline.hourly_pattern = [0.0] * 24
        baseline.hourly_std = [0.0] * 24

        result = service._check_unusual_time(detection, zone, baseline, threshold=2.0)
        assert result is not None
        assert result.anomaly_type == AnomalyType.UNUSUAL_TIME

    def test_detection_without_timestamp_returns_none(self) -> None:
        """Test that detection without timestamp returns None."""
        from backend.services.zone_anomaly_service import ZoneAnomalyService

        service = ZoneAnomalyService()

        detection = MagicMock(spec=[])
        detection.detected_at = None
        detection.timestamp = None

        zone = MagicMock()
        zone.id = str(uuid.uuid4())

        baseline = MagicMock()
        baseline.hourly_pattern = [0.0] * 24
        baseline.hourly_std = [0.0] * 24

        result = service._check_unusual_time(detection, zone, baseline, threshold=2.0)
        assert result is None

    def test_detection_with_insufficient_baseline_returns_none(self) -> None:
        """Test that detection with insufficient baseline data returns None."""
        from backend.services.zone_anomaly_service import ZoneAnomalyService

        service = ZoneAnomalyService()

        detection = MagicMock()
        detection.detected_at = datetime(2026, 1, 21, 14, 30, 0, tzinfo=UTC)
        detection.id = 123

        zone = MagicMock()
        zone.id = str(uuid.uuid4())

        baseline = MagicMock()
        baseline.hourly_pattern = [0.0, 1.0]
        baseline.hourly_std = [0.0, 1.0]

        result = service._check_unusual_time(detection, zone, baseline, threshold=2.0)
        assert result is None


# =============================================================================
# Unusual Frequency Detection Tests
# =============================================================================


class TestCheckUnusualFrequency:
    """Tests for _check_unusual_frequency method."""

    @pytest.mark.asyncio
    async def test_normal_frequency_returns_none(self) -> None:
        """Test that normal activity frequency returns no anomaly."""
        from backend.services.zone_anomaly_service import ZoneAnomalyService

        service = ZoneAnomalyService()

        detection = MagicMock()
        detection.detected_at = datetime(2026, 1, 21, 14, 30, 0, tzinfo=UTC)
        detection.id = 123
        detection.thumbnail_path = "/thumbnails/det_123.jpg"

        zone = MagicMock()
        zone.id = str(uuid.uuid4())
        zone.camera_id = "front_door"
        zone.name = "Front Yard"

        baseline = MagicMock()
        baseline.typical_crossing_rate = 10.0
        baseline.typical_crossing_std = 5.0

        result = await service._check_unusual_frequency(detection, zone, baseline, threshold=2.0)
        assert result is None

    @pytest.mark.asyncio
    async def test_high_frequency_with_low_baseline_returns_anomaly(self) -> None:
        """Test that high activity when baseline is low returns anomaly."""
        from backend.services.zone_anomaly_service import ZoneAnomalyService

        service = ZoneAnomalyService()
        zone_id = uuid.uuid4()

        base_time = datetime(2026, 1, 21, 14, 30, 0, tzinfo=UTC)
        service._frequency_tracker[zone_id] = [
            (base_time - timedelta(minutes=i), i) for i in range(1, 20)
        ]

        detection = MagicMock()
        detection.detected_at = base_time
        detection.id = 999
        detection.thumbnail_path = "/thumbnails/det_999.jpg"

        zone = MagicMock()
        zone.id = str(zone_id)
        zone.camera_id = "front_door"
        zone.name = "Front Yard"

        baseline = MagicMock()
        baseline.typical_crossing_rate = 0.5
        baseline.typical_crossing_std = 0.1

        result = await service._check_unusual_frequency(detection, zone, baseline, threshold=2.0)
        assert result is not None
        assert result.anomaly_type == AnomalyType.UNUSUAL_FREQUENCY

    @pytest.mark.asyncio
    async def test_frequency_tracker_cleanup(self) -> None:
        """Test that frequency tracker removes old entries."""
        from backend.services.zone_anomaly_service import ZoneAnomalyService

        service = ZoneAnomalyService()
        zone_id = uuid.uuid4()

        old_time = datetime(2026, 1, 21, 12, 0, 0, tzinfo=UTC)
        service._frequency_tracker[zone_id] = [
            (old_time, 1),
            (old_time + timedelta(minutes=10), 2),
        ]

        current_time = datetime(2026, 1, 21, 14, 30, 0, tzinfo=UTC)
        detection = MagicMock()
        detection.detected_at = current_time
        detection.id = 999
        detection.thumbnail_path = None

        zone = MagicMock()
        zone.id = str(zone_id)
        zone.camera_id = "front_door"
        zone.name = "Front Yard"

        baseline = MagicMock()
        baseline.typical_crossing_rate = 10.0
        baseline.typical_crossing_std = 5.0

        await service._check_unusual_frequency(detection, zone, baseline, threshold=2.0)
        assert len(service._frequency_tracker[zone_id]) == 1


# =============================================================================
# Unusual Dwell Detection Tests
# =============================================================================


class TestCheckUnusualDwell:
    """Tests for _check_unusual_dwell method."""

    @pytest.mark.asyncio
    async def test_normal_dwell_time_returns_none(self) -> None:
        """Test that normal dwell time returns no anomaly."""
        from backend.services.zone_anomaly_service import ZoneAnomalyService

        service = ZoneAnomalyService()

        detection = MagicMock()
        detection.detected_at = datetime(2026, 1, 21, 14, 30, 0, tzinfo=UTC)
        detection.id = 123
        detection.enrichment_data = {"dwell_time": 30.0}
        detection.thumbnail_path = None

        zone = MagicMock()
        zone.id = str(uuid.uuid4())
        zone.camera_id = "front_door"
        zone.name = "Front Yard"

        baseline = MagicMock()
        baseline.typical_dwell_time = 30.0
        baseline.typical_dwell_std = 10.0

        result = await service._check_unusual_dwell(detection, zone, baseline, threshold=2.0)
        assert result is None

    @pytest.mark.asyncio
    async def test_excessive_dwell_time_returns_anomaly(self) -> None:
        """Test that excessive dwell time returns anomaly."""
        from backend.services.zone_anomaly_service import ZoneAnomalyService

        service = ZoneAnomalyService()

        detection = MagicMock()
        detection.detected_at = datetime(2026, 1, 21, 14, 30, 0, tzinfo=UTC)
        detection.id = 123
        detection.enrichment_data = {"dwell_time": 300.0}
        detection.thumbnail_path = "/thumbnails/det_123.jpg"

        zone = MagicMock()
        zone.id = str(uuid.uuid4())
        zone.camera_id = "front_door"
        zone.name = "Front Yard"

        baseline = MagicMock()
        baseline.typical_dwell_time = 30.0
        baseline.typical_dwell_std = 10.0

        result = await service._check_unusual_dwell(detection, zone, baseline, threshold=2.0)
        assert result is not None
        assert result.anomaly_type == AnomalyType.UNUSUAL_DWELL

    @pytest.mark.asyncio
    async def test_detection_without_dwell_data_returns_none(self) -> None:
        """Test that detection without dwell data returns None."""
        from backend.services.zone_anomaly_service import ZoneAnomalyService

        service = ZoneAnomalyService()

        detection = MagicMock()
        detection.detected_at = datetime(2026, 1, 21, 14, 30, 0, tzinfo=UTC)
        detection.id = 123
        detection.enrichment_data = {}

        zone = MagicMock()
        zone.id = str(uuid.uuid4())
        zone.camera_id = "front_door"
        zone.name = "Front Yard"

        baseline = MagicMock()
        baseline.typical_dwell_time = 30.0
        baseline.typical_dwell_std = 10.0

        result = await service._check_unusual_dwell(detection, zone, baseline, threshold=2.0)
        assert result is None

    @pytest.mark.asyncio
    async def test_detection_without_enrichment_data_returns_none(self) -> None:
        """Test that detection without enrichment_data returns None."""
        from backend.services.zone_anomaly_service import ZoneAnomalyService

        service = ZoneAnomalyService()

        detection = MagicMock()
        detection.detected_at = datetime(2026, 1, 21, 14, 30, 0, tzinfo=UTC)
        detection.id = 123
        detection.enrichment_data = None

        zone = MagicMock()
        zone.id = str(uuid.uuid4())
        zone.camera_id = "front_door"

        baseline = MagicMock()
        baseline.typical_dwell_time = 30.0
        baseline.typical_dwell_std = 10.0

        result = await service._check_unusual_dwell(detection, zone, baseline, threshold=2.0)
        assert result is None


# =============================================================================
# Check Detection Integration Tests
# =============================================================================


class TestCheckDetection:
    """Tests for check_detection main method."""

    @pytest.mark.asyncio
    async def test_no_baseline_returns_none(self) -> None:
        """Test that detection with no baseline returns None."""
        from backend.services.zone_anomaly_service import ZoneAnomalyService

        service = ZoneAnomalyService()

        detection = MagicMock()
        detection.detected_at = datetime(2026, 1, 21, 14, 30, 0, tzinfo=UTC)
        detection.id = 123

        zone = MagicMock()
        zone.id = str(uuid.uuid4())

        mock_session = AsyncMock()

        with patch.object(service._baseline_service, "get_baseline", return_value=None):
            result = await service.check_detection(detection, zone, session=mock_session)
            assert result is None

    @pytest.mark.asyncio
    async def test_baseline_with_no_samples_returns_none(self) -> None:
        """Test that baseline with 0 samples returns None."""
        from backend.services.zone_anomaly_service import ZoneAnomalyService

        service = ZoneAnomalyService()

        detection = MagicMock()
        detection.detected_at = datetime(2026, 1, 21, 14, 30, 0, tzinfo=UTC)
        detection.id = 123

        zone = MagicMock()
        zone.id = str(uuid.uuid4())

        mock_baseline = MagicMock()
        mock_baseline.sample_count = 0

        mock_session = AsyncMock()

        with patch.object(service._baseline_service, "get_baseline", return_value=mock_baseline):
            result = await service.check_detection(detection, zone, session=mock_session)
            assert result is None

    @pytest.mark.asyncio
    async def test_detection_returns_most_severe_anomaly(self) -> None:
        """Test that when multiple anomalies detected, most severe is returned."""
        from backend.services.zone_anomaly_service import ZoneAnomalyService

        service = ZoneAnomalyService()

        detection = MagicMock()
        detection.detected_at = datetime(2026, 1, 21, 3, 15, 0, tzinfo=UTC)
        detection.id = 123
        detection.thumbnail_path = "/thumbnails/det_123.jpg"
        detection.enrichment_data = {"dwell_time": 600.0}

        zone = MagicMock()
        zone.id = str(uuid.uuid4())
        zone.camera_id = "front_door"
        zone.name = "Front Yard"

        mock_baseline = MagicMock()
        mock_baseline.sample_count = 100
        mock_baseline.hourly_pattern = [0.0] * 24
        mock_baseline.hourly_std = [0.0] * 24
        mock_baseline.typical_crossing_rate = 10.0
        mock_baseline.typical_crossing_std = 5.0
        mock_baseline.typical_dwell_time = 30.0
        mock_baseline.typical_dwell_std = 5.0

        mock_session = AsyncMock()

        with patch.object(service._baseline_service, "get_baseline", return_value=mock_baseline):
            with patch.object(service, "_persist_and_emit", new_callable=AsyncMock):
                result = await service.check_detection(detection, zone, session=mock_session)
                assert result is not None
                assert result.severity in [
                    AnomalySeverity.WARNING,
                    AnomalySeverity.CRITICAL,
                ]


# =============================================================================
# WebSocket Emission Tests
# =============================================================================


class TestEmitWebSocketEvent:
    """Tests for _emit_websocket_event method."""

    @pytest.mark.asyncio
    async def test_emit_event_publishes_to_redis(self) -> None:
        """Test that emit publishes correctly formatted message to Redis."""
        from backend.services.zone_anomaly_service import ZoneAnomalyService

        mock_redis = AsyncMock()
        service = ZoneAnomalyService(redis_client=mock_redis)

        anomaly = MagicMock()
        anomaly.id = uuid.uuid4()
        anomaly.zone_id = uuid.uuid4()
        anomaly.camera_id = "front_door"
        anomaly.anomaly_type = AnomalyType.UNUSUAL_TIME
        anomaly.severity = AnomalySeverity.WARNING
        anomaly.title = "Unusual activity at 03:00"
        anomaly.description = "Activity detected at 03:15..."
        anomaly.expected_value = 0.0
        anomaly.actual_value = 1.0
        anomaly.deviation = 3.5
        anomaly.detection_id = 123
        anomaly.thumbnail_url = "/thumbnails/det_123.jpg"
        anomaly.timestamp = datetime(2026, 1, 21, 3, 15, 0, tzinfo=UTC)

        with patch("backend.core.config.get_settings") as mock_settings:
            mock_settings.return_value.redis_event_channel = "security_events"

            await service._emit_websocket_event(anomaly)

            mock_redis.publish.assert_called_once()
            call_args = mock_redis.publish.call_args
            assert call_args[0][0] == "security_events"

            message = call_args[0][1]
            assert message["type"] == "zone.anomaly"
            assert "data" in message
            assert message["data"]["anomaly_type"] == AnomalyType.UNUSUAL_TIME
            assert message["data"]["severity"] == AnomalySeverity.WARNING

    @pytest.mark.asyncio
    async def test_emit_event_without_redis_tries_to_get_redis(self) -> None:
        """Test that emit tries to get Redis if not provided."""
        from backend.services.zone_anomaly_service import ZoneAnomalyService

        service = ZoneAnomalyService()

        anomaly = MagicMock()
        anomaly.id = uuid.uuid4()
        anomaly.zone_id = uuid.uuid4()
        anomaly.camera_id = "front_door"
        anomaly.anomaly_type = AnomalyType.UNUSUAL_TIME
        anomaly.severity = AnomalySeverity.INFO
        anomaly.title = "Test"
        anomaly.description = None
        anomaly.expected_value = 0.0
        anomaly.actual_value = 1.0
        anomaly.deviation = 2.0
        anomaly.detection_id = None
        anomaly.thumbnail_url = None
        anomaly.timestamp = datetime(2026, 1, 21, 3, 15, 0, tzinfo=UTC)

        mock_redis = AsyncMock()

        async def mock_get_redis():
            """Mock async generator that yields the mock redis client."""
            yield mock_redis

        with patch("backend.services.zone_anomaly_service.get_redis", mock_get_redis):
            with patch("backend.core.config.get_settings") as mock_settings:
                mock_settings.return_value.redis_event_channel = "security_events"

                await service._emit_websocket_event(anomaly)

                mock_redis.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_emit_event_handles_redis_error_gracefully(self) -> None:
        """Test that emit handles Redis errors without raising."""
        from backend.services.zone_anomaly_service import ZoneAnomalyService

        mock_redis = AsyncMock()
        mock_redis.publish.side_effect = Exception("Redis connection error")
        service = ZoneAnomalyService(redis_client=mock_redis)

        anomaly = MagicMock()
        anomaly.id = uuid.uuid4()
        anomaly.zone_id = uuid.uuid4()
        anomaly.camera_id = "front_door"
        anomaly.anomaly_type = AnomalyType.UNUSUAL_TIME
        anomaly.severity = AnomalySeverity.INFO
        anomaly.title = "Test"
        anomaly.description = None
        anomaly.expected_value = 0.0
        anomaly.actual_value = 1.0
        anomaly.deviation = 2.0
        anomaly.detection_id = None
        anomaly.thumbnail_url = None
        anomaly.timestamp = datetime(2026, 1, 21, 3, 15, 0, tzinfo=UTC)

        with patch("backend.core.config.get_settings") as mock_settings:
            mock_settings.return_value.redis_event_channel = "security_events"

            await service._emit_websocket_event(anomaly)


# =============================================================================
# Persistence Tests
# =============================================================================


class TestPersistAndEmit:
    """Tests for _persist_and_emit method."""

    @pytest.mark.asyncio
    async def test_persist_adds_anomaly_to_session(self) -> None:
        """Test that persist adds anomaly to provided session."""
        from backend.services.zone_anomaly_service import ZoneAnomalyService

        mock_redis = AsyncMock()
        service = ZoneAnomalyService(redis_client=mock_redis)

        anomaly = MagicMock()
        anomaly.id = uuid.uuid4()
        anomaly.zone_id = uuid.uuid4()
        anomaly.camera_id = "front_door"
        anomaly.anomaly_type = AnomalyType.UNUSUAL_TIME
        anomaly.severity = AnomalySeverity.INFO
        anomaly.title = "Test"
        anomaly.description = None
        anomaly.expected_value = 0.0
        anomaly.actual_value = 1.0
        anomaly.deviation = 2.0
        anomaly.detection_id = None
        anomaly.thumbnail_url = None
        anomaly.timestamp = datetime(2026, 1, 21, 3, 15, 0, tzinfo=UTC)

        mock_session = AsyncMock()

        with patch("backend.core.config.get_settings") as mock_settings:
            mock_settings.return_value.redis_event_channel = "security_events"

            await service._persist_and_emit(anomaly, session=mock_session)

            mock_session.add.assert_called_once_with(anomaly)

    @pytest.mark.asyncio
    async def test_persist_without_session_creates_new_session(self) -> None:
        """Test that persist creates session if not provided."""
        from backend.services.zone_anomaly_service import ZoneAnomalyService

        mock_redis = AsyncMock()
        service = ZoneAnomalyService(redis_client=mock_redis)

        anomaly = MagicMock()
        anomaly.id = uuid.uuid4()
        anomaly.zone_id = uuid.uuid4()
        anomaly.camera_id = "front_door"
        anomaly.anomaly_type = AnomalyType.UNUSUAL_TIME
        anomaly.severity = AnomalySeverity.INFO
        anomaly.title = "Test"
        anomaly.description = None
        anomaly.expected_value = 0.0
        anomaly.actual_value = 1.0
        anomaly.deviation = 2.0
        anomaly.detection_id = None
        anomaly.thumbnail_url = None
        anomaly.timestamp = datetime(2026, 1, 21, 3, 15, 0, tzinfo=UTC)

        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None

        with patch("backend.services.zone_anomaly_service.get_session", return_value=mock_session):
            with patch("backend.core.config.get_settings") as mock_settings:
                mock_settings.return_value.redis_event_channel = "security_events"

                await service._persist_and_emit(anomaly)

                mock_session.add.assert_called_once_with(anomaly)
                mock_session.commit.assert_called_once()


# =============================================================================
# Query Method Tests
# =============================================================================


class TestGetAnomaliesForZone:
    """Tests for get_anomalies_for_zone method."""

    @pytest.mark.asyncio
    async def test_get_anomalies_returns_list(self) -> None:
        """Test that get_anomalies returns a list of anomalies."""
        from backend.services.zone_anomaly_service import ZoneAnomalyService

        service = ZoneAnomalyService()
        zone_id = uuid.uuid4()

        mock_anomaly = MagicMock()
        mock_anomaly.id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_anomaly]

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        result = await service.get_anomalies_for_zone(zone_id, session=mock_session)

        assert len(result) == 1
        assert result[0] == mock_anomaly

    @pytest.mark.asyncio
    async def test_get_anomalies_filters_by_since(self) -> None:
        """Test that get_anomalies filters by since parameter."""
        from backend.services.zone_anomaly_service import ZoneAnomalyService

        service = ZoneAnomalyService()
        zone_id = uuid.uuid4()
        since = datetime(2026, 1, 20, 0, 0, 0, tzinfo=UTC)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        await service.get_anomalies_for_zone(zone_id, since=since, session=mock_session)

        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_anomalies_filters_unacknowledged(self) -> None:
        """Test that get_anomalies can filter to unacknowledged only."""
        from backend.services.zone_anomaly_service import ZoneAnomalyService

        service = ZoneAnomalyService()
        zone_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        await service.get_anomalies_for_zone(
            zone_id, unacknowledged_only=True, session=mock_session
        )

        mock_session.execute.assert_called_once()


class TestAcknowledgeAnomaly:
    """Tests for acknowledge_anomaly method."""

    @pytest.mark.asyncio
    async def test_acknowledge_updates_anomaly(self) -> None:
        """Test that acknowledge updates the anomaly."""
        from backend.services.zone_anomaly_service import ZoneAnomalyService

        service = ZoneAnomalyService()
        anomaly_id = uuid.uuid4()

        mock_anomaly = MagicMock()
        mock_anomaly.id = anomaly_id

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_anomaly

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        result = await service.acknowledge_anomaly(
            anomaly_id, acknowledged_by="user@example.com", session=mock_session
        )

        assert result == mock_anomaly
        mock_anomaly.acknowledge.assert_called_once_with("user@example.com")
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_acknowledge_not_found_returns_none(self) -> None:
        """Test that acknowledge returns None if anomaly not found."""
        from backend.services.zone_anomaly_service import ZoneAnomalyService

        service = ZoneAnomalyService()
        anomaly_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        result = await service.acknowledge_anomaly(anomaly_id, session=mock_session)

        assert result is None
        mock_session.commit.assert_not_called()


class TestGetAnomalyCountsByZone:
    """Tests for get_anomaly_counts_by_zone method."""

    @pytest.mark.asyncio
    async def test_get_counts_returns_dict(self) -> None:
        """Test that get_counts returns dictionary mapping zone_id to count."""
        from backend.services.zone_anomaly_service import ZoneAnomalyService

        service = ZoneAnomalyService()

        zone_id_1 = uuid.uuid4()
        zone_id_2 = uuid.uuid4()

        # SQLAlchemy returns rows that can be accessed both by name and index
        mock_row_1 = (str(zone_id_1), 5)
        mock_row_2 = (str(zone_id_2), 3)

        mock_result = MagicMock()
        mock_result.all.return_value = [mock_row_1, mock_row_2]

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        result = await service.get_anomaly_counts_by_zone(session=mock_session)

        assert result[str(zone_id_1)] == 5
        assert result[str(zone_id_2)] == 3


# =============================================================================
# Singleton Tests
# =============================================================================


class TestZoneAnomalySingleton:
    """Tests for zone anomaly service singleton functions."""

    def test_get_zone_anomaly_service_creates_singleton(self) -> None:
        """Test that get_zone_anomaly_service creates singleton."""
        from backend.services.zone_anomaly_service import (
            get_zone_anomaly_service,
            reset_zone_anomaly_service,
        )

        reset_zone_anomaly_service()
        service1 = get_zone_anomaly_service()
        service2 = get_zone_anomaly_service()

        assert service1 is service2
        reset_zone_anomaly_service()

    def test_reset_zone_anomaly_service(self) -> None:
        """Test that reset_zone_anomaly_service clears singleton."""
        from backend.services.zone_anomaly_service import (
            get_zone_anomaly_service,
            reset_zone_anomaly_service,
        )

        service1 = get_zone_anomaly_service()
        reset_zone_anomaly_service()
        service2 = get_zone_anomaly_service()

        assert service1 is not service2
        reset_zone_anomaly_service()


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_anomaly_type_enum_values(self) -> None:
        """Test that AnomalyType enum has expected values."""
        assert AnomalyType.UNUSUAL_TIME == "unusual_time"
        assert AnomalyType.UNUSUAL_FREQUENCY == "unusual_frequency"
        assert AnomalyType.UNUSUAL_DWELL == "unusual_dwell"
        assert AnomalyType.UNUSUAL_ENTITY == "unusual_entity"

    def test_anomaly_severity_enum_values(self) -> None:
        """Test that AnomalySeverity enum has expected values."""
        assert AnomalySeverity.INFO == "info"
        assert AnomalySeverity.WARNING == "warning"
        assert AnomalySeverity.CRITICAL == "critical"

    def test_deviation_boundary_values(self) -> None:
        """Test severity mapping at exact boundary values."""
        from backend.services.zone_anomaly_service import ZoneAnomalyService

        service = ZoneAnomalyService()

        assert service._deviation_to_severity(3.0) == AnomalySeverity.WARNING
        assert service._deviation_to_severity(2.99999) == AnomalySeverity.INFO
        assert service._deviation_to_severity(4.0) == AnomalySeverity.CRITICAL
        assert service._deviation_to_severity(3.99999) == AnomalySeverity.WARNING

    @pytest.mark.asyncio
    async def test_check_unusual_time_uses_timestamp_fallback(self) -> None:
        """Test that check_unusual_time uses timestamp if detected_at is None."""
        from backend.services.zone_anomaly_service import ZoneAnomalyService

        service = ZoneAnomalyService()

        detection = MagicMock()
        detection.detected_at = None
        detection.timestamp = datetime(2026, 1, 21, 3, 15, 0, tzinfo=UTC)
        detection.id = 123
        detection.thumbnail_path = None

        zone = MagicMock()
        zone.id = str(uuid.uuid4())
        zone.camera_id = "front_door"
        zone.name = "Front Yard"

        baseline = MagicMock()
        baseline.hourly_pattern = [0.0] * 24
        baseline.hourly_std = [0.0] * 24

        result = service._check_unusual_time(detection, zone, baseline, threshold=2.0)
        assert result is not None


# =============================================================================
# Additional Coverage Tests
# =============================================================================


class TestAdditionalCoverage:
    """Additional tests to improve coverage."""

    def test_check_unusual_time_with_zero_std(self) -> None:
        """Test unusual time check when std is 0."""
        from backend.services.zone_anomaly_service import ZoneAnomalyService

        service = ZoneAnomalyService()

        detection = MagicMock()
        detection.detected_at = datetime(2026, 1, 21, 3, 15, 0, tzinfo=UTC)
        detection.id = 123
        detection.thumbnail_path = None

        zone = MagicMock()
        zone.id = str(uuid.uuid4())
        zone.camera_id = "front_door"
        zone.name = "Front Yard"

        # Expected activity is low but non-zero, std is exactly 0
        baseline = MagicMock()
        baseline.hourly_pattern = [0.5] * 24  # Low but above 0.1
        baseline.hourly_std = [0.0] * 24  # All zeros

        result = service._check_unusual_time(detection, zone, baseline, threshold=2.0)
        # With expected=0.5 < 1.0, should calculate deviation
        assert result is not None

    def test_check_unusual_time_with_high_std(self) -> None:
        """Test unusual time check with high std value."""
        from backend.services.zone_anomaly_service import ZoneAnomalyService

        service = ZoneAnomalyService()

        detection = MagicMock()
        detection.detected_at = datetime(2026, 1, 21, 3, 15, 0, tzinfo=UTC)
        detection.id = 123
        detection.thumbnail_path = None

        zone = MagicMock()
        zone.id = str(uuid.uuid4())
        zone.camera_id = "front_door"
        zone.name = "Front Yard"

        # Low expected activity with very high std
        baseline = MagicMock()
        baseline.hourly_pattern = [0.05] * 24  # Very low
        baseline.hourly_std = [10.0] * 24  # High std

        result = service._check_unusual_time(detection, zone, baseline, threshold=2.0)
        # deviation = (1.0 - 0.05) / 10.0 = 0.095, below threshold
        assert result is None

    @pytest.mark.asyncio
    async def test_check_unusual_frequency_without_timestamp(self) -> None:
        """Test frequency check returns None when timestamp is missing."""
        from backend.services.zone_anomaly_service import ZoneAnomalyService

        service = ZoneAnomalyService()

        detection = MagicMock()
        detection.detected_at = None
        detection.timestamp = None

        zone = MagicMock()
        zone.id = str(uuid.uuid4())

        baseline = MagicMock()
        baseline.typical_crossing_rate = 10.0
        baseline.typical_crossing_std = 5.0

        result = await service._check_unusual_frequency(detection, zone, baseline, threshold=2.0)
        assert result is None

    @pytest.mark.asyncio
    async def test_check_unusual_dwell_without_timestamp(self) -> None:
        """Test dwell check handles missing timestamp gracefully."""
        from backend.services.zone_anomaly_service import ZoneAnomalyService

        service = ZoneAnomalyService()

        detection = MagicMock()
        detection.detected_at = None
        detection.timestamp = None
        detection.enrichment_data = {"dwell_time": 600.0}

        zone = MagicMock()
        zone.id = str(uuid.uuid4())
        zone.camera_id = "front_door"
        zone.name = "Front Yard"

        baseline = MagicMock()
        baseline.typical_dwell_time = 30.0
        baseline.typical_dwell_std = 10.0

        result = await service._check_unusual_dwell(detection, zone, baseline, threshold=2.0)
        # Should still work with timestamp=None
        assert result is not None

    @pytest.mark.asyncio
    async def test_check_detection_with_normal_values(self) -> None:
        """Test check_detection when all values are within normal range."""
        from backend.services.zone_anomaly_service import ZoneAnomalyService

        service = ZoneAnomalyService()

        detection = MagicMock()
        detection.detected_at = datetime(2026, 1, 21, 14, 30, 0, tzinfo=UTC)
        detection.id = 123
        detection.thumbnail_path = None
        detection.enrichment_data = {"dwell_time": 25.0}  # Normal dwell

        zone = MagicMock()
        zone.id = str(uuid.uuid4())
        zone.camera_id = "front_door"
        zone.name = "Front Yard"

        mock_baseline = MagicMock()
        mock_baseline.sample_count = 100
        mock_baseline.hourly_pattern = [10.0] * 24  # High activity all day
        mock_baseline.hourly_std = [5.0] * 24
        mock_baseline.typical_crossing_rate = 50.0  # Very high
        mock_baseline.typical_crossing_std = 20.0
        mock_baseline.typical_dwell_time = 30.0
        mock_baseline.typical_dwell_std = 10.0

        mock_session = AsyncMock()

        with patch.object(service._baseline_service, "get_baseline", return_value=mock_baseline):
            result = await service.check_detection(detection, zone, session=mock_session)
            # All values are normal, should return None
            assert result is None

    @pytest.mark.asyncio
    async def test_get_anomalies_for_zone_without_filters(self) -> None:
        """Test get_anomalies with default parameters."""
        from backend.services.zone_anomaly_service import ZoneAnomalyService

        service = ZoneAnomalyService()
        zone_id = uuid.uuid4()

        mock_anomaly = MagicMock()
        mock_anomaly.id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_anomaly]

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        result = await service.get_anomalies_for_zone(
            zone_id,
            since=None,
            unacknowledged_only=False,
            session=mock_session,
        )

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_anomaly_counts_with_filters(self) -> None:
        """Test get_anomaly_counts with since and unacknowledged filters."""
        from backend.services.zone_anomaly_service import ZoneAnomalyService

        service = ZoneAnomalyService()

        since = datetime(2026, 1, 20, 0, 0, 0, tzinfo=UTC)

        mock_row = (str(uuid.uuid4()), 10)
        mock_result = MagicMock()
        mock_result.all.return_value = [mock_row]

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        result = await service.get_anomaly_counts_by_zone(
            since=since,
            unacknowledged_only=True,
            session=mock_session,
        )

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_anomaly_counts_without_session_raises(self) -> None:
        """Test get_anomaly_counts raises when session is None."""
        from backend.services.zone_anomaly_service import ZoneAnomalyService

        service = ZoneAnomalyService()

        with pytest.raises(ValueError, match="session is required"):
            await service.get_anomaly_counts_by_zone(session=None)

    @pytest.mark.asyncio
    async def test_baseline_service_get_baseline_without_session(self) -> None:
        """Test ZoneBaselineService returns None when session is None."""
        from backend.services.zone_anomaly_service import ZoneBaselineService

        service = ZoneBaselineService()
        result = await service.get_baseline("zone-123", session=None)
        assert result is None
