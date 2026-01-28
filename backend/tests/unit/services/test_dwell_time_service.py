"""Unit tests for DwellTimeService.

Tests cover:
- Loitering detection with Prometheus metrics emission (NEM-4142)
- Record entry and exit operations
- Dwell time calculation
- Alert triggering behavior

Related: NEM-4142 (Loitering Detection Prometheus Metrics)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.models.dwell_time import DwellTimeRecord
from backend.services.dwell_time_service import DwellTimeService

# =============================================================================
# Loitering Metrics Tests (NEM-4142)
# =============================================================================


class TestLoiteringMetricsEmission:
    """Tests for Prometheus metrics emission during loitering detection."""

    @pytest.mark.asyncio
    async def test_check_loitering_emits_metrics_on_first_alert(self) -> None:
        """Verify metrics are emitted when loitering is first detected."""
        # Create a mock database session
        mock_db = AsyncMock()
        mock_db.flush = AsyncMock()

        # Create a mock zone for the record
        mock_zone = MagicMock()
        mock_zone.name = "Test Zone"

        # Create a mock dwell time record that exceeds threshold
        mock_record = MagicMock(spec=DwellTimeRecord)
        mock_record.id = 1
        mock_record.zone_id = 42
        mock_record.track_id = 100
        mock_record.camera_id = "camera-001"
        mock_record.object_class = "person"
        mock_record.entry_time = datetime.now(UTC) - timedelta(minutes=10)
        mock_record.triggered_alert = False  # Not yet triggered
        mock_record.calculate_dwell_time = MagicMock(return_value=600.0)  # 10 minutes
        mock_record.zone = mock_zone

        service = DwellTimeService(mock_db)

        with (
            patch.object(service, "get_active_dwellers", return_value=[mock_record]),
            patch(
                "backend.services.dwell_time_service.record_loitering_alert"
            ) as mock_record_alert,
            patch(
                "backend.services.dwell_time_service.observe_loitering_dwell_time"
            ) as mock_observe_dwell,
            patch(
                "backend.services.dwell_time_service.record_loitering_event"
            ) as mock_record_event,
        ):
            alerts = await service.check_loitering(zone_id=42, threshold_seconds=300.0)

            # Verify alert was generated
            assert len(alerts) == 1
            assert alerts[0].zone_id == 42
            assert alerts[0].camera_id == "camera-001"
            assert alerts[0].dwell_seconds == 600.0

            # Verify Prometheus metrics were emitted
            mock_record_alert.assert_called_once_with("camera-001", "42")
            mock_observe_dwell.assert_called_once_with("camera-001", 600.0)
            mock_record_event.assert_called_once_with("42", "Test Zone", "alert")

            # Verify record was marked as triggered
            assert mock_record.triggered_alert is True
            mock_db.flush.assert_called()

    @pytest.mark.asyncio
    async def test_check_loitering_does_not_emit_metrics_on_subsequent_checks(self) -> None:
        """Verify metrics are NOT emitted again for already-triggered alerts."""
        mock_db = AsyncMock()
        mock_db.flush = AsyncMock()

        # Create a mock zone for the record
        mock_zone = MagicMock()
        mock_zone.name = "Test Zone"

        # Create a record that has ALREADY triggered an alert
        mock_record = MagicMock(spec=DwellTimeRecord)
        mock_record.id = 1
        mock_record.zone_id = 42
        mock_record.track_id = 100
        mock_record.camera_id = "camera-001"
        mock_record.object_class = "person"
        mock_record.entry_time = datetime.now(UTC) - timedelta(minutes=15)
        mock_record.triggered_alert = True  # Already triggered
        mock_record.calculate_dwell_time = MagicMock(return_value=900.0)  # 15 minutes
        mock_record.zone = mock_zone

        service = DwellTimeService(mock_db)

        with (
            patch.object(service, "get_active_dwellers", return_value=[mock_record]),
            patch(
                "backend.services.dwell_time_service.record_loitering_alert"
            ) as mock_record_alert,
            patch(
                "backend.services.dwell_time_service.observe_loitering_dwell_time"
            ) as mock_observe_dwell,
            patch(
                "backend.services.dwell_time_service.record_loitering_event"
            ) as mock_record_event,
        ):
            alerts = await service.check_loitering(zone_id=42, threshold_seconds=300.0)

            # Alert is still returned (for current state tracking)
            assert len(alerts) == 1
            assert alerts[0].dwell_seconds == 900.0

            # But metrics should NOT be emitted again
            mock_record_alert.assert_not_called()
            mock_observe_dwell.assert_not_called()
            mock_record_event.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_loitering_no_metrics_when_below_threshold(self) -> None:
        """Verify no metrics are emitted when dwell time is below threshold."""
        mock_db = AsyncMock()

        # Create a mock zone for the record
        mock_zone = MagicMock()
        mock_zone.name = "Test Zone"

        mock_record = MagicMock(spec=DwellTimeRecord)
        mock_record.id = 1
        mock_record.zone_id = 42
        mock_record.track_id = 100
        mock_record.camera_id = "camera-001"
        mock_record.zone = mock_zone
        mock_record.object_class = "person"
        mock_record.entry_time = datetime.now(UTC) - timedelta(minutes=2)
        mock_record.triggered_alert = False
        mock_record.calculate_dwell_time = MagicMock(return_value=120.0)  # 2 minutes

        service = DwellTimeService(mock_db)

        with (
            patch.object(service, "get_active_dwellers", return_value=[mock_record]),
            patch(
                "backend.services.dwell_time_service.record_loitering_alert"
            ) as mock_record_alert,
            patch(
                "backend.services.dwell_time_service.observe_loitering_dwell_time"
            ) as mock_observe_dwell,
            patch(
                "backend.services.dwell_time_service.record_loitering_event"
            ) as mock_record_event,
        ):
            alerts = await service.check_loitering(zone_id=42, threshold_seconds=300.0)

            # No alert should be generated
            assert len(alerts) == 0

            # No metrics should be emitted
            mock_record_alert.assert_not_called()
            mock_observe_dwell.assert_not_called()
            mock_record_event.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_loitering_emits_metrics_for_multiple_records(self) -> None:
        """Verify metrics are emitted for each newly detected loitering record."""
        mock_db = AsyncMock()
        mock_db.flush = AsyncMock()

        # Create mock zones for the records
        mock_zone1 = MagicMock()
        mock_zone1.name = "Zone A"
        mock_zone2 = MagicMock()
        mock_zone2.name = "Zone B"
        mock_zone3 = MagicMock()
        mock_zone3.name = "Zone C"

        # Create multiple records - one new, one already triggered
        mock_record1 = MagicMock(spec=DwellTimeRecord)
        mock_record1.id = 1
        mock_record1.zone = mock_zone1
        mock_record1.zone_id = 42
        mock_record1.track_id = 100
        mock_record1.camera_id = "camera-001"
        mock_record1.object_class = "person"
        mock_record1.entry_time = datetime.now(UTC) - timedelta(minutes=10)
        mock_record1.triggered_alert = False  # New alert
        mock_record1.calculate_dwell_time = MagicMock(return_value=600.0)

        mock_record2 = MagicMock(spec=DwellTimeRecord)
        mock_record2.id = 2
        mock_record2.zone_id = 42
        mock_record2.track_id = 101
        mock_record2.camera_id = "camera-002"
        mock_record2.object_class = "person"
        mock_record2.entry_time = datetime.now(UTC) - timedelta(minutes=8)
        mock_record2.triggered_alert = True  # Already triggered
        mock_record2.calculate_dwell_time = MagicMock(return_value=480.0)
        mock_record2.zone = mock_zone2

        mock_record3 = MagicMock(spec=DwellTimeRecord)
        mock_record3.id = 3
        mock_record3.zone_id = 42
        mock_record3.track_id = 102
        mock_record3.camera_id = "camera-003"
        mock_record3.object_class = "vehicle"
        mock_record3.entry_time = datetime.now(UTC) - timedelta(minutes=12)
        mock_record3.triggered_alert = False  # New alert
        mock_record3.calculate_dwell_time = MagicMock(return_value=720.0)
        mock_record3.zone = mock_zone3

        service = DwellTimeService(mock_db)

        with (
            patch.object(
                service,
                "get_active_dwellers",
                return_value=[mock_record1, mock_record2, mock_record3],
            ),
            patch(
                "backend.services.dwell_time_service.record_loitering_alert"
            ) as mock_record_alert,
            patch(
                "backend.services.dwell_time_service.observe_loitering_dwell_time"
            ) as mock_observe_dwell,
            patch(
                "backend.services.dwell_time_service.record_loitering_event"
            ) as mock_record_event,
        ):
            alerts = await service.check_loitering(zone_id=42, threshold_seconds=300.0)

            # All three records exceed threshold
            assert len(alerts) == 3

            # Only two should emit metrics (the new ones)
            assert mock_record_alert.call_count == 2
            assert mock_observe_dwell.call_count == 2
            assert mock_record_event.call_count == 2

            # Verify the correct cameras were recorded
            calls = mock_record_alert.call_args_list
            camera_ids = {call[0][0] for call in calls}
            assert camera_ids == {"camera-001", "camera-003"}

            # Verify the correct zone names were recorded for events
            event_calls = mock_record_event.call_args_list
            zone_names = {call[0][1] for call in event_calls}
            assert zone_names == {"Zone A", "Zone C"}

    @pytest.mark.asyncio
    async def test_check_loitering_no_active_dwellers(self) -> None:
        """Verify no metrics when there are no active dwellers in the zone."""
        mock_db = AsyncMock()
        service = DwellTimeService(mock_db)

        with (
            patch.object(service, "get_active_dwellers", return_value=[]),
            patch(
                "backend.services.dwell_time_service.record_loitering_alert"
            ) as mock_record_alert,
            patch(
                "backend.services.dwell_time_service.observe_loitering_dwell_time"
            ) as mock_observe_dwell,
            patch(
                "backend.services.dwell_time_service.record_loitering_event"
            ) as mock_record_event,
        ):
            alerts = await service.check_loitering(zone_id=42, threshold_seconds=300.0)

            assert len(alerts) == 0
            mock_record_alert.assert_not_called()
            mock_observe_dwell.assert_not_called()
            mock_record_event.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_loitering_uses_zone_id_as_string_label(self) -> None:
        """Verify zone_id is converted to string for Prometheus label."""
        mock_db = AsyncMock()
        mock_db.flush = AsyncMock()

        # Create a mock zone for the record
        mock_zone = MagicMock()
        mock_zone.name = "Restricted Area"

        mock_record = MagicMock(spec=DwellTimeRecord)
        mock_record.id = 1
        mock_record.zone_id = 12345
        mock_record.track_id = 100
        mock_record.camera_id = "camera-001"
        mock_record.object_class = "person"
        mock_record.entry_time = datetime.now(UTC) - timedelta(minutes=10)
        mock_record.triggered_alert = False
        mock_record.calculate_dwell_time = MagicMock(return_value=600.0)
        mock_record.zone = mock_zone

        service = DwellTimeService(mock_db)

        with (
            patch.object(service, "get_active_dwellers", return_value=[mock_record]),
            patch(
                "backend.services.dwell_time_service.record_loitering_alert"
            ) as mock_record_alert,
            patch(
                "backend.services.dwell_time_service.observe_loitering_dwell_time"
            ) as mock_observe_dwell,
            patch(
                "backend.services.dwell_time_service.record_loitering_event"
            ) as mock_record_event,
        ):
            await service.check_loitering(zone_id=12345, threshold_seconds=300.0)

            # Verify zone_id is passed as string
            mock_record_alert.assert_called_once_with("camera-001", "12345")
            mock_observe_dwell.assert_called_once_with("camera-001", 600.0)
            mock_record_event.assert_called_once_with("12345", "Restricted Area", "alert")

    @pytest.mark.asyncio
    async def test_check_loitering_handles_missing_zone_relationship(self) -> None:
        """Verify loitering event uses 'unknown' when zone relationship is not loaded."""
        mock_db = AsyncMock()
        mock_db.flush = AsyncMock()

        # Create a record without zone relationship loaded
        mock_record = MagicMock(spec=DwellTimeRecord)
        mock_record.id = 1
        mock_record.zone_id = 99
        mock_record.track_id = 100
        mock_record.camera_id = "camera-001"
        mock_record.object_class = "person"
        mock_record.entry_time = datetime.now(UTC) - timedelta(minutes=10)
        mock_record.triggered_alert = False
        mock_record.calculate_dwell_time = MagicMock(return_value=600.0)
        mock_record.zone = None  # Zone not loaded

        service = DwellTimeService(mock_db)

        with (
            patch.object(service, "get_active_dwellers", return_value=[mock_record]),
            patch(
                "backend.services.dwell_time_service.record_loitering_alert"
            ) as mock_record_alert,
            patch(
                "backend.services.dwell_time_service.observe_loitering_dwell_time"
            ) as mock_observe_dwell,
            patch(
                "backend.services.dwell_time_service.record_loitering_event"
            ) as mock_record_event,
        ):
            await service.check_loitering(zone_id=99, threshold_seconds=300.0)

            # Verify zone_name falls back to "unknown"
            mock_record_alert.assert_called_once_with("camera-001", "99")
            mock_observe_dwell.assert_called_once_with("camera-001", 600.0)
            mock_record_event.assert_called_once_with("99", "unknown", "alert")


# =============================================================================
# Record Entry Tests
# =============================================================================


class TestRecordEntry:
    """Tests for record_entry method."""

    @pytest.mark.asyncio
    async def test_record_entry_creates_new_record(self) -> None:
        """Verify record_entry creates a new DwellTimeRecord."""
        mock_db = AsyncMock()
        mock_db.flush = AsyncMock()
        mock_db.refresh = AsyncMock()
        mock_db.add = MagicMock()

        service = DwellTimeService(mock_db)

        with patch.object(service, "get_active_record", return_value=None):
            record = await service.record_entry(
                zone_id=42,
                track_id=100,
                camera_id="camera-001",
                object_class="person",
            )

            assert record.zone_id == 42
            assert record.track_id == 100
            assert record.camera_id == "camera-001"
            assert record.object_class == "person"
            assert record.triggered_alert is False
            mock_db.add.assert_called_once()
            mock_db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_record_entry_returns_existing_active_record(self) -> None:
        """Verify record_entry returns existing record if already active."""
        mock_db = AsyncMock()

        existing_record = MagicMock(spec=DwellTimeRecord)
        existing_record.id = 5

        service = DwellTimeService(mock_db)

        with patch.object(service, "get_active_record", return_value=existing_record):
            record = await service.record_entry(
                zone_id=42,
                track_id=100,
                camera_id="camera-001",
                object_class="person",
            )

            assert record is existing_record
            mock_db.add.assert_not_called()


# =============================================================================
# Record Exit Tests
# =============================================================================


class TestRecordExit:
    """Tests for record_exit method."""

    @pytest.mark.asyncio
    async def test_record_exit_updates_record_with_dwell_time(self) -> None:
        """Verify record_exit updates exit_time and calculates total_seconds."""
        mock_db = AsyncMock()
        mock_db.flush = AsyncMock()
        mock_db.refresh = AsyncMock()

        entry_time = datetime.now(UTC) - timedelta(minutes=5)
        mock_record = MagicMock(spec=DwellTimeRecord)
        mock_record.entry_time = entry_time
        mock_record.triggered_alert = False

        service = DwellTimeService(mock_db)

        with patch.object(service, "get_active_record", return_value=mock_record):
            result = await service.record_exit(zone_id=42, track_id=100)

            assert result is mock_record
            assert mock_record.exit_time is not None
            # total_seconds should be approximately 300 (5 minutes)
            assert mock_record.total_seconds >= 299  # Allow for small timing differences
            mock_db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_record_exit_returns_none_when_no_active_record(self) -> None:
        """Verify record_exit returns None when no active record exists."""
        mock_db = AsyncMock()
        service = DwellTimeService(mock_db)

        with patch.object(service, "get_active_record", return_value=None):
            result = await service.record_exit(zone_id=42, track_id=100)

            assert result is None


# =============================================================================
# Alert Triggering Edge Cases
# =============================================================================


class TestAlertTriggering:
    """Tests for edge cases in alert triggering logic."""

    @pytest.mark.asyncio
    async def test_alert_only_triggers_once_per_record(self) -> None:
        """Verify that multiple check_loitering calls only trigger alert once."""
        mock_db = AsyncMock()
        mock_db.flush = AsyncMock()

        # Create a mock zone for the record
        mock_zone = MagicMock()
        mock_zone.name = "Test Zone"

        mock_record = MagicMock(spec=DwellTimeRecord)
        mock_record.id = 1
        mock_record.zone_id = 42
        mock_record.track_id = 100
        mock_record.camera_id = "camera-001"
        mock_record.object_class = "person"
        mock_record.entry_time = datetime.now(UTC) - timedelta(minutes=10)
        mock_record.triggered_alert = False
        mock_record.calculate_dwell_time = MagicMock(return_value=600.0)
        mock_record.zone = mock_zone

        service = DwellTimeService(mock_db)

        with (
            patch.object(service, "get_active_dwellers", return_value=[mock_record]),
            patch(
                "backend.services.dwell_time_service.record_loitering_alert"
            ) as mock_record_alert,
            patch(
                "backend.services.dwell_time_service.observe_loitering_dwell_time"
            ) as mock_observe_dwell,
            patch(
                "backend.services.dwell_time_service.record_loitering_event"
            ) as mock_record_event,
        ):
            # First check - should emit metrics
            await service.check_loitering(zone_id=42, threshold_seconds=300.0)
            assert mock_record_alert.call_count == 1
            assert mock_observe_dwell.call_count == 1
            assert mock_record_event.call_count == 1

            # Record is now marked as triggered
            mock_record.triggered_alert = True

            # Second check - should NOT emit metrics again
            await service.check_loitering(zone_id=42, threshold_seconds=300.0)
            assert mock_record_alert.call_count == 1  # Still just 1
            assert mock_observe_dwell.call_count == 1  # Still just 1
            assert mock_record_event.call_count == 1  # Still just 1
