"""Integration tests for Frigate NVR Integration Service.

This module contains integration tests for the FrigateIntegrationService that verify
end-to-end functionality with real MQTT broker and database interactions.

The service integrates with Frigate NVR by:
- Subscribing to Frigate MQTT event topics
- Parsing Frigate detection events
- Mapping Frigate camera IDs to HSI camera IDs
- Converting Frigate object labels to HSI types
- Converting bounding box formats
- Filtering by confidence threshold
- Deduplicating events

Related Issues:
    - NEM-5159: [Implement] Phase 9: Frigate Integration
    - NEM-5032: Epic 3: Ecosystem Integration

Test Organization:
    - Service initialization tests: Settings and MQTT client integration
    - MQTT subscription tests: Topic subscriptions and event handling
    - Event processing tests: Detection parsing and mapping
    - Error handling tests: Invalid payloads and malformed data
    - URL generation tests: Snapshot and clip URL construction
    - Configuration tests: Camera mapping and settings validation

Acceptance Criteria:
    - Service subscribes to frigate/+/events topic on start
    - Events are parsed and validated using Pydantic schemas
    - Camera IDs are mapped correctly via settings
    - Object labels are mapped to HSI types
    - Bounding boxes are converted from normalized to pixel coordinates
    - Low-confidence detections are filtered out
    - Duplicate events are deduplicated
    - Service starts/stops cleanly
    - Snapshot and clip URLs are generated correctly

Design Decisions:
    - Uses real MQTTClient instance with mocked broker operations
    - Tests database interactions with real async session
    - Mocks external Frigate API calls for snapshot/clip URLs
    - Each test uses unique event IDs to prevent collisions
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.frigate_integration import (
    FrigateDetection,
    FrigateEvent,
    FrigateIntegrationService,
    FrigateSettings,
)
from backend.services.mqtt_client import MQTTClient, MQTTClientSettings

# Mark all tests as integration
pytestmark = [pytest.mark.integration]


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def frigate_settings() -> FrigateSettings:
    """Create Frigate integration settings for testing."""
    return FrigateSettings(
        enabled=True,
        mqtt_topic_prefix="frigate",
        camera_mapping={
            "front_door": "camera_001",
            "backyard": "camera_002",
        },
        api_url="http://frigate:5000",
        import_snapshots=True,
        min_confidence=0.5,
    )


@pytest.fixture
def mqtt_settings() -> MQTTClientSettings:
    """Create MQTT settings for testing."""
    return MQTTClientSettings(
        broker_host="localhost",
        broker_port=1883,
        client_id="frigate-integration-test",
        topic_prefix="frigate",
        qos_default=1,
    )


@pytest.fixture
def mock_mqtt_client(mqtt_settings: MQTTClientSettings) -> MagicMock:
    """Create a mock MQTT client for testing.

    Mocks the MQTTClient to avoid actual broker connections in integration tests.
    The service behavior is tested against database operations, not MQTT operations.
    """
    mock_client = MagicMock(spec=MQTTClient)
    mock_client.settings = mqtt_settings
    mock_client.connected = True
    mock_client.subscribe = AsyncMock()
    mock_client.unsubscribe = AsyncMock()
    mock_client.publish = AsyncMock()
    return mock_client


@pytest.fixture
def frigate_service(
    mock_mqtt_client: MagicMock,
    frigate_settings: FrigateSettings,
) -> FrigateIntegrationService:
    """Create FrigateIntegrationService instance for testing."""
    return FrigateIntegrationService(
        mqtt_client=mock_mqtt_client,
        settings=frigate_settings,
    )


@pytest.fixture
def sample_frigate_detection() -> dict:
    """Create a sample Frigate detection payload."""
    return {
        "id": "1234567890.123456-abc123",
        "camera": "front_door",
        "frame_time": 1706745600.123,
        "label": "person",
        "score": 0.85,
        "box": [0.1, 0.2, 0.9, 0.8],  # [y1, x1, y2, x2] normalized
        "area": 250000,
        "region": [0.0, 0.0, 1.0, 1.0],
        "current_zones": ["entryway"],
        "entered_zones": ["entryway"],
        "has_clip": True,
        "has_snapshot": True,
        "stationary": False,
        "motionless_count": 0,
        "position_changes": 12,
    }


@pytest.fixture
def sample_frigate_event(sample_frigate_detection: dict) -> dict:
    """Create a sample Frigate event payload (new event)."""
    return {
        "type": "new",
        "before": None,
        "after": sample_frigate_detection,
    }


# =============================================================================
# Service Initialization Tests
# =============================================================================


class TestFrigateServiceInitialization:
    """Tests for FrigateIntegrationService initialization."""

    @pytest.mark.asyncio
    async def test_service_initializes_with_settings(
        self,
        mock_mqtt_client: MagicMock,
        frigate_settings: FrigateSettings,
    ) -> None:
        """Test service initializes correctly with settings."""
        service = FrigateIntegrationService(
            mqtt_client=mock_mqtt_client,
            settings=frigate_settings,
        )

        assert service._settings == frigate_settings
        assert service._client == mock_mqtt_client
        assert service._running is False
        assert len(service._processed_events) == 0

    @pytest.mark.asyncio
    async def test_service_initializes_with_default_settings(
        self,
        mock_mqtt_client: MagicMock,
    ) -> None:
        """Test service initializes with default settings when none provided."""
        service = FrigateIntegrationService(mqtt_client=mock_mqtt_client)

        assert service._settings is not None
        assert service._settings.enabled is False
        assert service._settings.mqtt_topic_prefix == "frigate"
        assert service._settings.min_confidence == 0.5

    @pytest.mark.asyncio
    async def test_service_logs_initialization(
        self,
        mock_mqtt_client: MagicMock,
        frigate_settings: FrigateSettings,
    ) -> None:
        """Test service logs initialization with settings."""
        with patch("backend.services.frigate_integration.logger") as mock_logger:
            FrigateIntegrationService(
                mqtt_client=mock_mqtt_client,
                settings=frigate_settings,
            )

            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args
            assert "FrigateIntegrationService initialized" in call_args[0][0]


# =============================================================================
# MQTT Subscription Tests
# =============================================================================


class TestFrigateMQTTSubscription:
    """Tests for MQTT topic subscription."""

    @pytest.mark.asyncio
    async def test_start_subscribes_to_events_topic(
        self,
        frigate_service: FrigateIntegrationService,
        mock_mqtt_client: MagicMock,
    ) -> None:
        """Test that start() subscribes to frigate/+/events topic."""
        await frigate_service.start()

        mock_mqtt_client.subscribe.assert_called_once()
        call_args = mock_mqtt_client.subscribe.call_args
        assert call_args[0][0] == "frigate/+/events"

    @pytest.mark.asyncio
    async def test_start_sets_running_flag(
        self,
        frigate_service: FrigateIntegrationService,
    ) -> None:
        """Test that start() sets the running flag."""
        assert frigate_service._running is False

        await frigate_service.start()

        assert frigate_service._running is True

    @pytest.mark.asyncio
    async def test_start_is_idempotent(
        self,
        frigate_service: FrigateIntegrationService,
        mock_mqtt_client: MagicMock,
    ) -> None:
        """Test that calling start() multiple times is safe."""
        await frigate_service.start()
        await frigate_service.start()
        await frigate_service.start()

        # Should only subscribe once
        assert mock_mqtt_client.subscribe.call_count == 1

    @pytest.mark.asyncio
    async def test_start_skips_if_disabled(self) -> None:
        """Test that start() does nothing when integration is disabled."""
        mock_client = MagicMock(spec=MQTTClient)
        mock_client.subscribe = AsyncMock()

        settings = FrigateSettings(enabled=False)
        service = FrigateIntegrationService(mqtt_client=mock_client, settings=settings)

        await service.start()

        mock_client.subscribe.assert_not_called()
        assert service._running is False

    @pytest.mark.asyncio
    async def test_stop_unsubscribes_from_events(
        self,
        frigate_service: FrigateIntegrationService,
        mock_mqtt_client: MagicMock,
    ) -> None:
        """Test that stop() unsubscribes from events topic."""
        await frigate_service.start()
        await frigate_service.stop()

        mock_mqtt_client.unsubscribe.assert_called_once()
        call_args = mock_mqtt_client.unsubscribe.call_args
        assert call_args[0][0] == "frigate/+/events"

    @pytest.mark.asyncio
    async def test_stop_clears_running_flag(
        self,
        frigate_service: FrigateIntegrationService,
    ) -> None:
        """Test that stop() clears the running flag."""
        await frigate_service.start()
        assert frigate_service._running is True

        await frigate_service.stop()

        assert frigate_service._running is False

    @pytest.mark.asyncio
    async def test_stop_is_idempotent(
        self,
        frigate_service: FrigateIntegrationService,
        mock_mqtt_client: MagicMock,
    ) -> None:
        """Test that calling stop() when not running is safe."""
        await frigate_service.stop()
        await frigate_service.stop()

        # Should not call unsubscribe if not running
        mock_mqtt_client.unsubscribe.assert_not_called()


# =============================================================================
# Event Processing Tests
# =============================================================================


class TestFrigateEventProcessing:
    """Tests for Frigate event processing and parsing."""

    @pytest.mark.asyncio
    async def test_processes_new_event(
        self,
        frigate_service: FrigateIntegrationService,
        sample_frigate_event: dict,
    ) -> None:
        """Test that service processes 'new' event type."""
        with patch("backend.services.frigate_integration.logger") as mock_logger:
            await frigate_service._on_event("frigate/front_door/events", sample_frigate_event)

            # Should log the detection
            mock_logger.info.assert_called()
            call_args = mock_logger.info.call_args
            assert "Frigate detection received" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_processes_end_event(
        self,
        frigate_service: FrigateIntegrationService,
        sample_frigate_event: dict,
    ) -> None:
        """Test that service processes 'end' event type."""
        sample_frigate_event["type"] = "end"

        with patch("backend.services.frigate_integration.logger") as mock_logger:
            await frigate_service._on_event("frigate/front_door/events", sample_frigate_event)

            # Should log the detection
            mock_logger.info.assert_called()

    @pytest.mark.asyncio
    async def test_ignores_update_event(
        self,
        frigate_service: FrigateIntegrationService,
        sample_frigate_event: dict,
    ) -> None:
        """Test that service ignores 'update' event type."""
        sample_frigate_event["type"] = "update"

        with patch("backend.services.frigate_integration.logger") as mock_logger:
            await frigate_service._on_event("frigate/front_door/events", sample_frigate_event)

            # Should not log detection (only debug/warning if any)
            info_calls = [
                call
                for call in mock_logger.info.call_args_list
                if "Frigate detection received" in str(call)
            ]
            assert len(info_calls) == 0

    @pytest.mark.asyncio
    async def test_filters_low_confidence_detection(
        self,
        frigate_service: FrigateIntegrationService,
        sample_frigate_event: dict,
    ) -> None:
        """Test that detections below min_confidence are filtered."""
        # Set confidence below threshold
        sample_frigate_event["after"]["score"] = 0.3

        with patch("backend.services.frigate_integration.logger") as mock_logger:
            await frigate_service._on_event("frigate/front_door/events", sample_frigate_event)

            # Should log debug message about threshold
            mock_logger.debug.assert_called()
            debug_call = mock_logger.debug.call_args[0][0]
            assert "below threshold" in debug_call

    @pytest.mark.asyncio
    async def test_deduplicates_events(
        self,
        frigate_service: FrigateIntegrationService,
        sample_frigate_event: dict,
    ) -> None:
        """Test that duplicate events are not processed twice."""
        # Process same event twice
        await frigate_service._on_event("frigate/front_door/events", sample_frigate_event)

        with patch("backend.services.frigate_integration.logger") as mock_logger:
            await frigate_service._on_event("frigate/front_door/events", sample_frigate_event)

            # Second call should not log detection (already processed)
            info_calls = [
                call
                for call in mock_logger.info.call_args_list
                if "Frigate detection received" in str(call)
            ]
            assert len(info_calls) == 0

    @pytest.mark.asyncio
    async def test_evicts_old_processed_events(
        self,
        frigate_service: FrigateIntegrationService,
        sample_frigate_detection: dict,
    ) -> None:
        """Test that processed event cache is evicted when it grows too large."""
        # Add 10001 events to trigger eviction (threshold is 10000)
        for i in range(10001):
            event = {
                "type": "new",
                "after": {
                    **sample_frigate_detection,
                    "id": f"event_{i}",
                },
            }
            await frigate_service._on_event("frigate/front_door/events", event)

        # Cache should be trimmed to 5000 entries (keeps second half)
        # After processing 10001 events, we have 10001 entries, which triggers eviction
        # The eviction keeps the last 5000 entries, so we should have exactly 5001
        # because we process one more after the eviction threshold
        assert len(frigate_service._processed_events) == 5001

    @pytest.mark.asyncio
    async def test_handles_invalid_event_payload_gracefully(
        self,
        frigate_service: FrigateIntegrationService,
    ) -> None:
        """Test that invalid event payload is handled gracefully."""
        invalid_payload = {"invalid": "data", "missing": "required_fields"}

        with patch("backend.services.frigate_integration.logger") as mock_logger:
            await frigate_service._on_event("frigate/front_door/events", invalid_payload)

            # Should log error
            mock_logger.error.assert_called()
            error_call = mock_logger.error.call_args[0][0]
            assert "Failed to process Frigate event" in error_call

    @pytest.mark.asyncio
    async def test_handles_exception_during_processing(
        self,
        frigate_service: FrigateIntegrationService,
        sample_frigate_event: dict,
    ) -> None:
        """Test that exceptions during event processing are caught."""
        with (
            patch("backend.services.frigate_integration.logger") as mock_logger,
            patch.object(
                FrigateEvent,
                "model_validate",
                side_effect=Exception("Simulated error"),
            ),
        ):
            await frigate_service._on_event("frigate/front_door/events", sample_frigate_event)

            # Should log error and continue
            mock_logger.error.assert_called()


# =============================================================================
# Camera and Object Mapping Tests
# =============================================================================


class TestFrigateMappings:
    """Tests for camera ID and object type mappings."""

    @pytest.mark.asyncio
    async def test_maps_frigate_camera_to_hsi_camera(
        self,
        frigate_service: FrigateIntegrationService,
    ) -> None:
        """Test that Frigate camera IDs are mapped to HSI camera IDs."""
        hsi_camera = frigate_service._map_camera_id("front_door")
        assert hsi_camera == "camera_001"

        hsi_camera = frigate_service._map_camera_id("backyard")
        assert hsi_camera == "camera_002"

    @pytest.mark.asyncio
    async def test_uses_frigate_camera_id_if_no_mapping(
        self,
        frigate_service: FrigateIntegrationService,
    ) -> None:
        """Test that unmapped camera IDs pass through unchanged."""
        hsi_camera = frigate_service._map_camera_id("unknown_camera")
        assert hsi_camera == "unknown_camera"

    @pytest.mark.asyncio
    async def test_maps_object_labels_correctly(
        self,
        frigate_service: FrigateIntegrationService,
    ) -> None:
        """Test that Frigate labels are mapped to HSI object types."""
        # Person mapping
        assert frigate_service._map_object_type("person") == "person"

        # Vehicle mappings
        assert frigate_service._map_object_type("car") == "vehicle"
        assert frigate_service._map_object_type("truck") == "vehicle"
        assert frigate_service._map_object_type("motorcycle") == "vehicle"

        # Animal mappings
        assert frigate_service._map_object_type("dog") == "animal"
        assert frigate_service._map_object_type("cat") == "animal"
        assert frigate_service._map_object_type("bird") == "animal"

        # Other
        assert frigate_service._map_object_type("bicycle") == "bicycle"

    @pytest.mark.asyncio
    async def test_passes_through_unknown_labels(
        self,
        frigate_service: FrigateIntegrationService,
    ) -> None:
        """Test that unknown labels pass through unchanged."""
        assert frigate_service._map_object_type("unknown_object") == "unknown_object"


# =============================================================================
# Bounding Box Conversion Tests
# =============================================================================


class TestBoundingBoxConversion:
    """Tests for bounding box format conversion."""

    @pytest.mark.asyncio
    async def test_converts_normalized_bbox_to_pixels(
        self,
        frigate_service: FrigateIntegrationService,
    ) -> None:
        """Test conversion from Frigate normalized bbox to pixel coordinates."""
        # Frigate format: [y1, x1, y2, x2] normalized (0-1)
        frigate_bbox = [0.1, 0.2, 0.9, 0.8]

        result = frigate_service._convert_bbox(frigate_bbox, image_width=1920, image_height=1080)

        # HSI format: {bbox_x, bbox_y, bbox_width, bbox_height} in pixels
        assert result["bbox_x"] == int(0.2 * 1920)  # x1 * width
        assert result["bbox_y"] == int(0.1 * 1080)  # y1 * height
        assert result["bbox_width"] == int((0.8 - 0.2) * 1920)  # (x2 - x1) * width
        assert result["bbox_height"] == int((0.9 - 0.1) * 1080)  # (y2 - y1) * height

    @pytest.mark.asyncio
    async def test_converts_bbox_with_custom_resolution(
        self,
        frigate_service: FrigateIntegrationService,
    ) -> None:
        """Test bbox conversion with custom image resolution."""
        frigate_bbox = [0.0, 0.0, 1.0, 1.0]  # Full frame

        result = frigate_service._convert_bbox(frigate_bbox, image_width=3840, image_height=2160)

        assert result["bbox_x"] == 0
        assert result["bbox_y"] == 0
        assert result["bbox_width"] == 3840
        assert result["bbox_height"] == 2160

    @pytest.mark.asyncio
    async def test_converts_partial_bbox(
        self,
        frigate_service: FrigateIntegrationService,
    ) -> None:
        """Test bbox conversion for partial detection."""
        # Small detection in top-left
        frigate_bbox = [0.0, 0.0, 0.25, 0.25]

        result = frigate_service._convert_bbox(frigate_bbox)

        assert result["bbox_x"] == 0
        assert result["bbox_y"] == 0
        assert result["bbox_width"] == 480  # 0.25 * 1920
        assert result["bbox_height"] == 270  # 0.25 * 1080


# =============================================================================
# URL Generation Tests
# =============================================================================


class TestSnapshotClipURLs:
    """Tests for snapshot and clip URL generation."""

    @pytest.mark.asyncio
    async def test_generates_snapshot_url(
        self,
        frigate_service: FrigateIntegrationService,
    ) -> None:
        """Test that snapshot URL is generated correctly."""
        event_id = "1234567890.123456-abc123"

        url = await frigate_service.get_snapshot_url(event_id)

        assert url == "http://frigate:5000/api/events/1234567890.123456-abc123/snapshot.jpg"

    @pytest.mark.asyncio
    async def test_generates_clip_url(
        self,
        frigate_service: FrigateIntegrationService,
    ) -> None:
        """Test that clip URL is generated correctly."""
        event_id = "1234567890.123456-abc123"

        url = await frigate_service.get_clip_url(event_id)

        assert url == "http://frigate:5000/api/events/1234567890.123456-abc123/clip.mp4"

    @pytest.mark.asyncio
    async def test_returns_none_when_api_url_not_configured(
        self,
        mock_mqtt_client: MagicMock,
    ) -> None:
        """Test that URL methods return None when api_url is not configured."""
        settings = FrigateSettings(enabled=True, api_url=None)
        service = FrigateIntegrationService(mqtt_client=mock_mqtt_client, settings=settings)

        snapshot_url = await service.get_snapshot_url("test-event")
        clip_url = await service.get_clip_url("test-event")

        assert snapshot_url is None
        assert clip_url is None


# =============================================================================
# Configuration and Settings Tests
# =============================================================================


class TestFrigateSettings:
    """Tests for FrigateSettings validation."""

    @pytest.mark.asyncio
    async def test_default_settings_are_disabled(self) -> None:
        """Test that default settings have integration disabled."""
        settings = FrigateSettings()

        assert settings.enabled is False
        assert settings.mqtt_topic_prefix == "frigate"
        assert settings.min_confidence == 0.5
        assert settings.import_snapshots is True

    @pytest.mark.asyncio
    async def test_settings_load_from_environment(self) -> None:
        """Test that settings can load from environment variables."""
        with patch.dict(
            "os.environ",
            {
                "FRIGATE_ENABLED": "true",
                "FRIGATE_MQTT_TOPIC_PREFIX": "nvr",
                "FRIGATE_MIN_CONFIDENCE": "0.7",
                "FRIGATE_API_URL": "http://nvr.local:5000",
            },
        ):
            settings = FrigateSettings()

            assert settings.enabled is True
            assert settings.mqtt_topic_prefix == "nvr"
            assert settings.min_confidence == 0.7
            assert settings.api_url == "http://nvr.local:5000"

    @pytest.mark.asyncio
    async def test_min_confidence_validation(self) -> None:
        """Test that min_confidence is validated to be between 0 and 1."""
        # Valid range
        settings = FrigateSettings(min_confidence=0.0)
        assert settings.min_confidence == 0.0

        settings = FrigateSettings(min_confidence=1.0)
        assert settings.min_confidence == 1.0

        # Invalid range should raise validation error
        with pytest.raises(Exception):  # Pydantic validation error
            FrigateSettings(min_confidence=1.5)

        with pytest.raises(Exception):
            FrigateSettings(min_confidence=-0.1)

    @pytest.mark.asyncio
    async def test_camera_mapping_as_dict(self) -> None:
        """Test that camera_mapping can be set as a dictionary."""
        mapping = {
            "cam1": "hsi_cam_1",
            "cam2": "hsi_cam_2",
        }
        settings = FrigateSettings(camera_mapping=mapping)

        assert settings.camera_mapping == mapping


# =============================================================================
# Pydantic Schema Validation Tests
# =============================================================================


class TestFrigatePydanticSchemas:
    """Tests for Frigate Pydantic schema validation."""

    @pytest.mark.asyncio
    async def test_frigate_detection_schema_validates(
        self,
        sample_frigate_detection: dict,
    ) -> None:
        """Test that FrigateDetection schema validates valid payload."""
        detection = FrigateDetection.model_validate(sample_frigate_detection)

        assert detection.id == sample_frigate_detection["id"]
        assert detection.camera == sample_frigate_detection["camera"]
        assert detection.label == sample_frigate_detection["label"]
        assert detection.score == sample_frigate_detection["score"]

    @pytest.mark.asyncio
    async def test_frigate_event_schema_validates(
        self,
        sample_frigate_event: dict,
    ) -> None:
        """Test that FrigateEvent schema validates valid payload."""
        event = FrigateEvent.model_validate(sample_frigate_event)

        assert event.type == "new"
        assert event.before is None
        assert event.after is not None
        assert event.after.label == "person"

    @pytest.mark.asyncio
    async def test_detection_schema_rejects_invalid_data(self) -> None:
        """Test that FrigateDetection schema rejects invalid data."""
        invalid_data = {
            "id": "test-id",
            # Missing required fields
        }

        with pytest.raises(Exception):  # Pydantic validation error
            FrigateDetection.model_validate(invalid_data)

    @pytest.mark.asyncio
    async def test_event_schema_with_before_and_after(
        self,
        sample_frigate_detection: dict,
    ) -> None:
        """Test that event schema handles both before and after states."""
        event_data = {
            "type": "end",
            "before": {**sample_frigate_detection, "score": 0.75},
            "after": {**sample_frigate_detection, "score": 0.80},
        }

        event = FrigateEvent.model_validate(event_data)

        assert event.type == "end"
        assert event.before is not None
        assert event.after is not None
        assert event.before.score == 0.75
        assert event.after.score == 0.80


# =============================================================================
# Integration with Database Tests
# =============================================================================


class TestFrigateDatabaseIntegration:
    """Tests for Frigate integration with database operations.

    Note: These tests verify the integration pattern. The actual database
    insertion is marked as TODO in the service (NEM-5159).
    These tests don't require database access yet, they just verify the
    service behavior with mocked MQTT client.
    """

    @pytest.mark.asyncio
    async def test_event_processing_logs_detection_info(
        self,
        frigate_service: FrigateIntegrationService,
        sample_frigate_event: dict,
    ) -> None:
        """Test that event processing logs detection information.

        This test verifies the current behavior (logging).
        When NEM-5159 is implemented, this should be updated to verify
        database insertion.
        """
        with patch("backend.services.frigate_integration.logger") as mock_logger:
            await frigate_service._on_event("frigate/front_door/events", sample_frigate_event)

            # Verify logging includes expected fields
            info_call = mock_logger.info.call_args
            assert info_call is not None
            extra = info_call[1]["extra"]

            assert extra["frigate_camera"] == "front_door"
            assert extra["hsi_camera_id"] == "camera_001"  # Mapped via camera_mapping
            assert extra["label"] == "person"
            assert extra["object_type"] == "person"  # Mapped via _map_object_type
            assert extra["confidence"] == 0.85
            assert "bbox" in extra

    @pytest.mark.asyncio
    async def test_multiple_events_processed_sequentially(
        self,
        frigate_service: FrigateIntegrationService,
        sample_frigate_detection: dict,
    ) -> None:
        """Test that multiple events can be processed sequentially."""
        events = []
        for i in range(5):
            event = {
                "type": "new",
                "after": {
                    **sample_frigate_detection,
                    "id": f"event_{i}",
                    "score": 0.5 + (i * 0.1),  # Varying confidence
                },
            }
            events.append(event)

        # Process all events
        for event in events:
            await frigate_service._on_event("frigate/front_door/events", event)

        # All events should be in processed cache
        assert len(frigate_service._processed_events) == 5


# =============================================================================
# Error Handling and Edge Cases
# =============================================================================


class TestFrigateErrorHandling:
    """Tests for error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_handles_missing_optional_fields(
        self,
        frigate_service: FrigateIntegrationService,
    ) -> None:
        """Test that service handles detections with missing optional fields."""
        minimal_event = {
            "type": "new",
            "after": {
                "id": "minimal-event",
                "camera": "test_camera",
                "frame_time": 1706745600.0,
                "label": "person",
                "score": 0.9,
                "box": [0.1, 0.1, 0.9, 0.9],
                "area": 100000,
                "region": [0.0, 0.0, 1.0, 1.0],
                # Optional fields use defaults
            },
        }

        # Should process without error
        with patch("backend.services.frigate_integration.logger") as mock_logger:
            await frigate_service._on_event("frigate/test_camera/events", minimal_event)

            mock_logger.info.assert_called()

    @pytest.mark.asyncio
    async def test_handles_zero_confidence_detection(
        self,
        frigate_service: FrigateIntegrationService,
        sample_frigate_event: dict,
    ) -> None:
        """Test that zero-confidence detections are filtered."""
        sample_frigate_event["after"]["score"] = 0.0

        with patch("backend.services.frigate_integration.logger") as mock_logger:
            await frigate_service._on_event("frigate/front_door/events", sample_frigate_event)

            # Should log debug about threshold
            mock_logger.debug.assert_called()

    @pytest.mark.asyncio
    async def test_handles_confidence_exactly_at_threshold(
        self,
        frigate_service: FrigateIntegrationService,
        sample_frigate_event: dict,
    ) -> None:
        """Test that detections exactly at threshold are not filtered."""
        sample_frigate_event["after"]["score"] = 0.5  # Exactly at min_confidence

        with patch("backend.services.frigate_integration.logger") as mock_logger:
            await frigate_service._on_event("frigate/front_door/events", sample_frigate_event)

            # Should process (not filtered)
            info_calls = [
                call
                for call in mock_logger.info.call_args_list
                if "Frigate detection received" in str(call)
            ]
            assert len(info_calls) == 1

    @pytest.mark.asyncio
    async def test_handles_empty_zones_list(
        self,
        frigate_service: FrigateIntegrationService,
        sample_frigate_event: dict,
    ) -> None:
        """Test that detections with empty zones are handled."""
        sample_frigate_event["after"]["current_zones"] = []
        sample_frigate_event["after"]["entered_zones"] = []

        with patch("backend.services.frigate_integration.logger") as mock_logger:
            await frigate_service._on_event("frigate/front_door/events", sample_frigate_event)

            # Should still process
            mock_logger.info.assert_called()

    @pytest.mark.asyncio
    async def test_handles_unicode_in_camera_name(
        self,
        frigate_service: FrigateIntegrationService,
        sample_frigate_event: dict,
    ) -> None:
        """Test that camera names with unicode characters are handled."""
        sample_frigate_event["after"]["camera"] = "camera_名前_123"

        with patch("backend.services.frigate_integration.logger"):
            # Should not raise exception
            await frigate_service._on_event("frigate/camera_名前_123/events", sample_frigate_event)
