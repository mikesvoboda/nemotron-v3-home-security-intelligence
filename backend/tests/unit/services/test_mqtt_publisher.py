"""Unit tests for MQTT Publisher Service.

Tests the MQTTPublisher service that publishes security events to MQTT topics
for Home Assistant and other MQTT-compatible systems.

Related Issues:
    - NEM-5134: [TDD] Write tests for Phase 1: MQTT Event Publishing
    - NEM-5032: Epic 3: Ecosystem Integration
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.mqtt_publisher import (
    MQTTPublisher,
    MQTTPublisherSettings,
    get_topic_for_event,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_mqtt_client() -> AsyncMock:
    """Create a mock MQTT client."""
    client = AsyncMock()
    client.connected = True
    client.publish = AsyncMock()
    client.connect = AsyncMock()
    client.disconnect = AsyncMock()
    return client


@pytest.fixture
def publisher_settings() -> MQTTPublisherSettings:
    """Create test publisher settings."""
    return MQTTPublisherSettings(
        enabled=True,
        events_qos=1,
        status_qos=0,
        retain_status=True,
        retain_events=False,
    )


@pytest.fixture
def publisher(
    mock_mqtt_client: AsyncMock, publisher_settings: MQTTPublisherSettings
) -> MQTTPublisher:
    """Create a publisher instance with mocked MQTT client."""
    return MQTTPublisher(
        mqtt_client=mock_mqtt_client,
        settings=publisher_settings,
    )


# =============================================================================
# Settings Tests
# =============================================================================


class TestMQTTPublisherSettings:
    """Tests for MQTTPublisherSettings configuration."""

    def test_default_settings(self) -> None:
        """Test default settings values."""
        settings = MQTTPublisherSettings()
        assert settings.enabled is True
        assert settings.events_qos == 1
        assert settings.status_qos == 0
        assert settings.retain_status is True
        assert settings.retain_events is False

    def test_custom_settings(self) -> None:
        """Test custom settings override defaults."""
        settings = MQTTPublisherSettings(
            enabled=False,
            events_qos=2,
            status_qos=1,
            retain_status=False,
            retain_events=True,
        )
        assert settings.enabled is False
        assert settings.events_qos == 2
        assert settings.status_qos == 1
        assert settings.retain_status is False
        assert settings.retain_events is True

    def test_qos_validation_range(self) -> None:
        """Test QoS values are validated to 0-2 range."""
        with pytest.raises(ValueError):
            MQTTPublisherSettings(events_qos=3)
        with pytest.raises(ValueError):
            MQTTPublisherSettings(status_qos=-1)


# =============================================================================
# Topic Mapping Tests
# =============================================================================


class TestTopicMapping:
    """Tests for event type to MQTT topic mapping.

    M3 T8 (audit Part 4): the class's 18 per-event tests were parametrize
    duplicates differing only in (event, payload, expected topic) — the
    guard tool bucketed them as three AST-shape variants (single-line vs
    multi-line call formatting) that are semantically one table; the table
    is now the single source, every pair preserved as a param.
    """

    @pytest.mark.parametrize(
        ("event_type", "payload", "expected_topic"),
        [
            ("alert.created", {"severity": "high"}, "alerts/high"),
            ("alert.updated", {"severity": "medium"}, "alerts/medium"),
            ("camera.online", {"camera_id": "front_door"}, "health/cameras/front_door"),
            ("camera.offline", {"camera_id": "backyard"}, "health/cameras/backyard"),
            (
                "detection.new",
                {"camera_id": "garage", "object_type": "person"},
                "detections/garage/person",
            ),
            ("detection.batch", {"camera_id": "driveway"}, "detections/driveway/batch"),
            ("zone.crossing", {"zone_id": "perimeter_1"}, "zones/perimeter_1/crossing"),
            ("zone.dwell_started", {"zone_id": "entrance"}, "zones/entrance/dwell"),
            ("zone.dwell_alert", {"zone_id": "lobby"}, "zones/lobby/dwell"),
            ("entity.matched", {"entity_type": "person"}, "entities/person"),
            ("entity.track_updated", {"entity_type": "vehicle"}, "entities/vehicle"),
            ("system.health_changed", {}, "health/system"),
            ("ai.threat_detected", {"camera_id": "entrance"}, "ai/threats/entrance"),
            (
                "ai.action_recognized",
                {"camera_id": "parking", "action": "loitering"},
                "ai/actions/parking",
            ),
            ("event.created", {"camera_id": "unknown"}, "events/unknown"),
            ("unknown.event.type", {"camera_id": "test"}, "events/test"),
            ("detection.new", {"object_type": "car"}, "detections/unknown/car"),
            ("zone.crossing", {}, "zones/unknown/crossing"),
        ],
        ids=[
            "alert_created",
            "alert_updated",
            "camera_online",
            "camera_offline",
            "detection_new",
            "detection_batch",
            "zone_crossing",
            "zone_dwell_started",
            "zone_dwell_alert",
            "entity_matched",
            "entity_track_updated",
            "system_health",
            "ai_threat_detected",
            "ai_action_recognized",
            "generic_event",
            "unknown_event_type_fallback",
            "missing_camera_id_uses_default",
            "missing_zone_id_uses_default",
        ],
    )
    def test_event_type_maps_to_topic(
        self, event_type: str, payload: dict, expected_topic: str
    ) -> None:
        """Each event type maps to its documented MQTT topic."""
        topic = get_topic_for_event(event_type, payload)
        assert topic == expected_topic


# =============================================================================
# Publisher Core Tests
# =============================================================================


class TestMQTTPublisher:
    """Tests for MQTTPublisher core functionality."""

    @pytest.mark.asyncio
    async def test_publish_event_calls_mqtt_client(
        self, publisher: MQTTPublisher, mock_mqtt_client: AsyncMock
    ) -> None:
        """Test publishing event calls MQTT client publish."""
        event_data = {
            "type": "alert.created",
            "data": {"severity": "high", "message": "Motion detected"},
        }

        await publisher.publish_event("alert.created", event_data)

        mock_mqtt_client.publish.assert_called_once()
        call_args = mock_mqtt_client.publish.call_args
        assert call_args.kwargs["topic"] == "alerts/high"
        assert call_args.kwargs["qos"] == 1  # events_qos

    @pytest.mark.asyncio
    async def test_publish_event_includes_full_payload(
        self, publisher: MQTTPublisher, mock_mqtt_client: AsyncMock
    ) -> None:
        """Test published event includes full event data."""
        event_data = {
            "type": "detection.new",
            "data": {
                "camera_id": "front",
                "object_type": "person",
                "confidence": 0.95,
                "bbox": [100, 200, 300, 400],
            },
        }

        await publisher.publish_event("detection.new", event_data)

        call_args = mock_mqtt_client.publish.call_args
        payload = call_args.kwargs["payload"]
        assert payload["type"] == "detection.new"
        assert payload["data"]["confidence"] == 0.95

    @pytest.mark.asyncio
    async def test_publish_status_uses_qos_0(
        self, publisher: MQTTPublisher, mock_mqtt_client: AsyncMock
    ) -> None:
        """Test status events use QoS 0."""
        event_data = {
            "type": "camera.online",
            "data": {"camera_id": "garage", "status": "online"},
        }

        await publisher.publish_event("camera.online", event_data)

        call_args = mock_mqtt_client.publish.call_args
        assert call_args.kwargs["qos"] == 0  # status_qos

    @pytest.mark.asyncio
    async def test_publish_status_uses_retain_flag(
        self, publisher: MQTTPublisher, mock_mqtt_client: AsyncMock
    ) -> None:
        """Test status events use retain flag."""
        event_data = {
            "type": "camera.offline",
            "data": {"camera_id": "backyard"},
        }

        await publisher.publish_event("camera.offline", event_data)

        call_args = mock_mqtt_client.publish.call_args
        assert call_args.kwargs["retain"] is True

    @pytest.mark.asyncio
    async def test_publish_event_no_retain_for_events(
        self, publisher: MQTTPublisher, mock_mqtt_client: AsyncMock
    ) -> None:
        """Test regular events do not use retain flag."""
        event_data = {
            "type": "alert.created",
            "data": {"severity": "low"},
        }

        await publisher.publish_event("alert.created", event_data)

        call_args = mock_mqtt_client.publish.call_args
        assert call_args.kwargs["retain"] is False

    @pytest.mark.asyncio
    async def test_publish_skipped_when_disabled(self, mock_mqtt_client: AsyncMock) -> None:
        """Test publishing is skipped when publisher is disabled."""
        settings = MQTTPublisherSettings(enabled=False)
        publisher = MQTTPublisher(mqtt_client=mock_mqtt_client, settings=settings)

        await publisher.publish_event("alert.created", {"type": "alert.created"})

        mock_mqtt_client.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_publish_skipped_when_not_connected(
        self, publisher: MQTTPublisher, mock_mqtt_client: AsyncMock
    ) -> None:
        """Test publishing is skipped when MQTT client is not connected."""
        mock_mqtt_client.connected = False

        await publisher.publish_event("alert.created", {"type": "alert.created"})

        mock_mqtt_client.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_publish_error_logged_not_raised(
        self, publisher: MQTTPublisher, mock_mqtt_client: AsyncMock
    ) -> None:
        """Test publish errors are logged but not raised."""
        mock_mqtt_client.publish.side_effect = Exception("Connection lost")

        # Should not raise
        await publisher.publish_event("alert.created", {"type": "alert.created"})

    @pytest.mark.asyncio
    async def test_publish_adds_timestamp_if_missing(
        self, publisher: MQTTPublisher, mock_mqtt_client: AsyncMock
    ) -> None:
        """Test timestamp is added to payload if not present."""
        event_data = {
            "type": "alert.created",
            "data": {"severity": "high"},
        }

        await publisher.publish_event("alert.created", event_data)

        call_args = mock_mqtt_client.publish.call_args
        payload = call_args.kwargs["payload"]
        assert "timestamp" in payload


# =============================================================================
# Batch Publishing Tests
# =============================================================================


class TestMQTTPublisherBatch:
    """Tests for batch publishing functionality."""

    @pytest.mark.asyncio
    async def test_publish_multiple_events(
        self, publisher: MQTTPublisher, mock_mqtt_client: AsyncMock
    ) -> None:
        """Test publishing multiple events in sequence."""
        events = [
            {"type": "detection.new", "data": {"camera_id": "cam1", "object_type": "person"}},
            {"type": "detection.new", "data": {"camera_id": "cam2", "object_type": "vehicle"}},
            {"type": "alert.created", "data": {"severity": "high"}},
        ]

        for event in events:
            await publisher.publish_event(event["type"], event)

        assert mock_mqtt_client.publish.call_count == 3

    @pytest.mark.asyncio
    async def test_publish_batch_detections(
        self, publisher: MQTTPublisher, mock_mqtt_client: AsyncMock
    ) -> None:
        """Test publishing a batch of detections."""
        batch_data = {
            "type": "detection.batch",
            "data": {
                "camera_id": "front_door",
                "batch_id": "batch_123",
                "detection_count": 5,
                "detections": [
                    {"object_type": "person", "confidence": 0.9},
                    {"object_type": "person", "confidence": 0.85},
                ],
            },
        }

        await publisher.publish_event("detection.batch", batch_data)

        call_args = mock_mqtt_client.publish.call_args
        assert call_args.kwargs["topic"] == "detections/front_door/batch"


# =============================================================================
# Zone Event Tests
# =============================================================================


class TestMQTTPublisherZoneEvents:
    """Tests for zone-related event publishing."""

    @pytest.mark.asyncio
    async def test_publish_zone_crossing(
        self, publisher: MQTTPublisher, mock_mqtt_client: AsyncMock
    ) -> None:
        """Test publishing zone crossing event."""
        event_data = {
            "type": "zone.crossing",
            "data": {
                "zone_id": "perimeter_north",
                "zone_name": "North Perimeter",
                "entity_id": "entity_456",
                "entity_type": "person",
                "direction": "entering",
                "timestamp": "2026-02-01T10:00:00Z",
            },
        }

        await publisher.publish_event("zone.crossing", event_data)

        call_args = mock_mqtt_client.publish.call_args
        assert call_args.kwargs["topic"] == "zones/perimeter_north/crossing"
        assert call_args.kwargs["qos"] == 1

    @pytest.mark.asyncio
    async def test_publish_zone_dwell_alert(
        self, publisher: MQTTPublisher, mock_mqtt_client: AsyncMock
    ) -> None:
        """Test publishing zone dwell alert."""
        event_data = {
            "type": "zone.dwell_alert",
            "data": {
                "zone_id": "entrance_lobby",
                "zone_name": "Entrance Lobby",
                "entity_id": "entity_789",
                "dwell_time": 45.5,
                "threshold": 30.0,
            },
        }

        await publisher.publish_event("zone.dwell_alert", event_data)

        call_args = mock_mqtt_client.publish.call_args
        assert call_args.kwargs["topic"] == "zones/entrance_lobby/dwell"


# =============================================================================
# Health/Status Event Tests
# =============================================================================


class TestMQTTPublisherHealthEvents:
    """Tests for health and status event publishing."""

    @pytest.mark.asyncio
    async def test_publish_camera_health(
        self, publisher: MQTTPublisher, mock_mqtt_client: AsyncMock
    ) -> None:
        """Test publishing camera health status."""
        event_data = {
            "type": "camera.online",
            "data": {
                "camera_id": "garage_cam",
                "status": "online",
                "previous_status": "offline",
            },
        }

        await publisher.publish_event("camera.online", event_data)

        call_args = mock_mqtt_client.publish.call_args
        assert call_args.kwargs["topic"] == "health/cameras/garage_cam"
        assert call_args.kwargs["qos"] == 0
        assert call_args.kwargs["retain"] is True

    @pytest.mark.asyncio
    async def test_publish_system_health(
        self, publisher: MQTTPublisher, mock_mqtt_client: AsyncMock
    ) -> None:
        """Test publishing system health status."""
        event_data = {
            "type": "system.health_changed",
            "data": {
                "health": "healthy",
                "components": {
                    "database": "healthy",
                    "redis": "healthy",
                    "ai_service": "healthy",
                },
            },
        }

        await publisher.publish_event("system.health_changed", event_data)

        call_args = mock_mqtt_client.publish.call_args
        assert call_args.kwargs["topic"] == "health/system"
        assert call_args.kwargs["qos"] == 0
        assert call_args.kwargs["retain"] is True


# =============================================================================
# Event Broadcaster Integration Tests
# =============================================================================


class TestMQTTPublisherBroadcasterIntegration:
    """Tests for integration with EventBroadcaster."""

    @pytest.mark.asyncio
    async def test_register_with_broadcaster(self, publisher: MQTTPublisher) -> None:
        """Test publisher can register as broadcaster callback."""
        mock_broadcaster = MagicMock()
        mock_broadcaster.register_mqtt_callback = MagicMock()

        publisher.register_with_broadcaster(mock_broadcaster)

        mock_broadcaster.register_mqtt_callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_callback_publishes_event(
        self, publisher: MQTTPublisher, mock_mqtt_client: AsyncMock
    ) -> None:
        """Test callback from broadcaster triggers publish."""
        # Get the callback function
        callback = publisher.get_broadcast_callback()

        # Simulate broadcaster calling the callback
        await callback("alert.created", {"type": "alert.created", "data": {"severity": "high"}})

        mock_mqtt_client.publish.assert_called_once()


# =============================================================================
# Metrics Tests
# =============================================================================


class TestMQTTPublisherMetrics:
    """Tests for Prometheus metrics integration."""

    @pytest.mark.asyncio
    async def test_publish_increments_counter(
        self, publisher: MQTTPublisher, mock_mqtt_client: AsyncMock
    ) -> None:
        """Test successful publish increments counter."""
        with patch.object(publisher, "_increment_publish_counter") as mock_counter:
            await publisher.publish_event(
                "alert.created", {"type": "alert.created", "data": {"severity": "high"}}
            )
            mock_counter.assert_called_once_with("alerts", success=True)

    @pytest.mark.asyncio
    async def test_publish_error_increments_error_counter(
        self, publisher: MQTTPublisher, mock_mqtt_client: AsyncMock
    ) -> None:
        """Test publish error increments error counter."""
        mock_mqtt_client.publish.side_effect = Exception("Publish failed")

        with patch.object(publisher, "_increment_publish_counter") as mock_counter:
            await publisher.publish_event(
                "alert.created", {"type": "alert.created", "data": {"severity": "high"}}
            )
            mock_counter.assert_called_once_with("alerts", success=False)


# =============================================================================
# Event Type Classification Tests
# =============================================================================


class TestEventTypeClassification:
    """Tests for event type classification (status vs regular events)."""

    def test_camera_events_are_status(self, publisher: MQTTPublisher) -> None:
        """Test camera events are classified as status events."""
        assert publisher.is_status_event("camera.online") is True
        assert publisher.is_status_event("camera.offline") is True
        assert publisher.is_status_event("camera.error") is True

    def test_system_events_are_status(self, publisher: MQTTPublisher) -> None:
        """Test system health events are classified as status events."""
        assert publisher.is_status_event("system.health_changed") is True
        assert publisher.is_status_event("system.status") is True

    def test_alert_events_are_not_status(self, publisher: MQTTPublisher) -> None:
        """Test alert events are not classified as status events."""
        assert publisher.is_status_event("alert.created") is False
        assert publisher.is_status_event("alert.updated") is False

    def test_detection_events_are_not_status(self, publisher: MQTTPublisher) -> None:
        """Test detection events are not classified as status events."""
        assert publisher.is_status_event("detection.new") is False
        assert publisher.is_status_event("detection.batch") is False

    def test_zone_events_are_not_status(self, publisher: MQTTPublisher) -> None:
        """Test zone events are not classified as status events."""
        assert publisher.is_status_event("zone.crossing") is False
        assert publisher.is_status_event("zone.dwell_alert") is False


# =============================================================================
# Concurrent Publishing Tests
# =============================================================================


class TestMQTTPublisherConcurrency:
    """Tests for concurrent publishing scenarios."""

    @pytest.mark.asyncio
    async def test_concurrent_publishes(
        self, publisher: MQTTPublisher, mock_mqtt_client: AsyncMock
    ) -> None:
        """Test concurrent publishes are handled correctly."""
        events = [
            {"type": "alert.created", "data": {"severity": "high", "id": i}} for i in range(10)
        ]

        # Publish all events concurrently
        await asyncio.gather(*[publisher.publish_event("alert.created", event) for event in events])

        assert mock_mqtt_client.publish.call_count == 10

    @pytest.mark.asyncio
    async def test_publish_does_not_block_on_slow_client(
        self, publisher: MQTTPublisher, mock_mqtt_client: AsyncMock
    ) -> None:
        """Test publishing doesn't block when client is slow."""

        # Simulate slow publish
        async def slow_publish(*args, **kwargs):
            await asyncio.sleep(0.1)

        mock_mqtt_client.publish = slow_publish

        # Should complete without blocking main thread significantly
        start = asyncio.get_event_loop().time()
        await publisher.publish_event(
            "alert.created", {"type": "alert.created", "data": {"severity": "high"}}
        )
        elapsed = asyncio.get_event_loop().time() - start

        # Allow some tolerance but should be reasonably quick
        assert elapsed < 0.5
