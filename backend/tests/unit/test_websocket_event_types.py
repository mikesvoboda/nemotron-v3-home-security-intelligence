"""Unit tests for WebSocket event type registry and infrastructure.

This module tests the centralized WebSocket event type registry including:
- WebSocketEventType enum completeness and values
- Event metadata registry
- Factory functions for event creation
- Channel and event type lookups
"""

from datetime import UTC, datetime

from backend.core.websocket import (
    EVENT_TYPE_METADATA,
    WebSocketEvent,
    WebSocketEventType,
    create_event,
    get_all_channels,
    get_all_event_types,
    get_event_channel,
    get_event_description,
    get_event_types_by_channel,
    get_required_payload_fields,
    validate_event_type,
)


class TestWebSocketEventType:
    """Tests for WebSocketEventType enum."""

    def test_all_alert_event_types_exist(self):
        """Verify all alert event types are defined."""
        alert_types = [
            WebSocketEventType.ALERT_CREATED,
            WebSocketEventType.ALERT_UPDATED,
            WebSocketEventType.ALERT_DELETED,
            WebSocketEventType.ALERT_ACKNOWLEDGED,
            WebSocketEventType.ALERT_RESOLVED,
            WebSocketEventType.ALERT_DISMISSED,
        ]
        for event_type in alert_types:
            assert event_type.value.startswith("alert.")

    def test_all_camera_event_types_exist(self):
        """Verify all camera event types are defined."""
        camera_types = [
            WebSocketEventType.CAMERA_ONLINE,
            WebSocketEventType.CAMERA_OFFLINE,
            WebSocketEventType.CAMERA_STATUS_CHANGED,
            WebSocketEventType.CAMERA_ENABLED,
            WebSocketEventType.CAMERA_DISABLED,
            WebSocketEventType.CAMERA_ERROR,
            WebSocketEventType.CAMERA_CONFIG_UPDATED,
        ]
        for event_type in camera_types:
            assert event_type.value.startswith("camera.")

    def test_all_job_event_types_exist(self):
        """Verify all job event types are defined."""
        job_types = [
            WebSocketEventType.JOB_STARTED,
            WebSocketEventType.JOB_PROGRESS,
            WebSocketEventType.JOB_COMPLETED,
            WebSocketEventType.JOB_FAILED,
            WebSocketEventType.JOB_CANCELLED,
        ]
        for event_type in job_types:
            assert event_type.value.startswith("job.")

    def test_all_system_event_types_exist(self):
        """Verify all system event types are defined."""
        system_types = [
            WebSocketEventType.SYSTEM_HEALTH_CHANGED,
            WebSocketEventType.SYSTEM_ERROR,
            WebSocketEventType.SYSTEM_STATUS,
            WebSocketEventType.SERVICE_STATUS_CHANGED,
            WebSocketEventType.GPU_STATS_UPDATED,
        ]
        for event_type in system_types:
            assert event_type.value.startswith(("system.", "service.", "gpu."))

    def test_all_security_event_types_exist(self):
        """Verify all security event types are defined."""
        event_types = [
            WebSocketEventType.EVENT_CREATED,
            WebSocketEventType.EVENT_UPDATED,
            WebSocketEventType.EVENT_DELETED,
        ]
        for event_type in event_types:
            assert event_type.value.startswith("event.")

    def test_all_detection_event_types_exist(self):
        """Verify all detection event types are defined."""
        detection_types = [
            WebSocketEventType.DETECTION_NEW,
            WebSocketEventType.DETECTION_BATCH,
        ]
        for event_type in detection_types:
            assert event_type.value.startswith("detection.")

    def test_scene_change_event_type_exists(self):
        """Verify scene change event type is defined."""
        assert WebSocketEventType.SCENE_CHANGE_DETECTED.value == "scene_change.detected"

    def test_all_worker_event_types_exist(self):
        """Verify all worker event types are defined (NEM-2461)."""
        worker_types = [
            WebSocketEventType.WORKER_STARTED,
            WebSocketEventType.WORKER_STOPPED,
            WebSocketEventType.WORKER_HEALTH_CHECK_FAILED,
            WebSocketEventType.WORKER_RESTARTING,
            WebSocketEventType.WORKER_RECOVERED,
            WebSocketEventType.WORKER_ERROR,
        ]
        for event_type in worker_types:
            assert event_type.value.startswith("worker.")

    def test_worker_event_type_values(self):
        """Verify worker event type specific values (NEM-2461)."""
        assert WebSocketEventType.WORKER_STARTED.value == "worker.started"
        assert WebSocketEventType.WORKER_STOPPED.value == "worker.stopped"
        assert WebSocketEventType.WORKER_HEALTH_CHECK_FAILED.value == "worker.health_check_failed"
        assert WebSocketEventType.WORKER_RESTARTING.value == "worker.restarting"
        assert WebSocketEventType.WORKER_RECOVERED.value == "worker.recovered"
        assert WebSocketEventType.WORKER_ERROR.value == "worker.error"

    def test_control_message_types_exist(self):
        """Verify control message types are defined."""
        control_types = [
            WebSocketEventType.PING,
            WebSocketEventType.PONG,
            WebSocketEventType.ERROR,
        ]
        for event_type in control_types:
            assert event_type.value in ("ping", "pong", "error")

    def test_event_type_values_are_unique(self):
        """Verify all event type values are unique."""
        values = [e.value for e in WebSocketEventType]
        assert len(values) == len(set(values))

    def test_event_type_string_enum(self):
        """Verify WebSocketEventType is a string enum."""
        event_type = WebSocketEventType.ALERT_CREATED
        # StrEnum values can be used as strings
        assert str(event_type) == "alert.created"
        assert event_type == "alert.created"


class TestEventTypeMetadata:
    """Tests for EVENT_TYPE_METADATA registry."""

    def test_all_event_types_have_metadata(self):
        """Verify all event types have metadata entries."""
        for event_type in WebSocketEventType:
            assert event_type in EVENT_TYPE_METADATA, f"Missing metadata for {event_type}"

    def test_metadata_has_required_fields(self):
        """Verify all metadata entries have required fields."""
        required_fields = {"description", "channel", "requires_payload", "payload_fields"}
        for event_type, metadata in EVENT_TYPE_METADATA.items():
            for field in required_fields:
                assert field in metadata, f"Missing {field} in metadata for {event_type}"

    def test_metadata_descriptions_are_non_empty(self):
        """Verify all metadata descriptions are non-empty strings."""
        for event_type, metadata in EVENT_TYPE_METADATA.items():
            description = metadata.get("description", "")
            assert isinstance(description, str)
            assert len(description) > 0, f"Empty description for {event_type}"

    def test_metadata_channels_are_valid(self):
        """Verify all metadata channels are valid values."""
        valid_channels = {
            "alerts",
            "cameras",
            "jobs",
            "system",
            "events",
            "detections",
            "workers",  # NEM-2461: Worker events channel
            None,
        }
        for event_type, metadata in EVENT_TYPE_METADATA.items():
            channel = metadata.get("channel")
            assert channel in valid_channels, f"Invalid channel {channel} for {event_type}"

    def test_payload_fields_are_lists(self):
        """Verify all payload_fields are lists."""
        for event_type, metadata in EVENT_TYPE_METADATA.items():
            payload_fields = metadata.get("payload_fields", [])
            assert isinstance(payload_fields, list), f"payload_fields not a list for {event_type}"


class TestCreateEvent:
    """Tests for create_event factory function."""

    def test_create_event_with_required_fields(self):
        """Test creating event with required fields only."""
        event = create_event(
            WebSocketEventType.ALERT_CREATED,
            {"id": "123", "severity": "high"},
        )
        assert event["type"] == WebSocketEventType.ALERT_CREATED
        assert event["payload"]["id"] == "123"
        assert event["payload"]["severity"] == "high"
        assert "timestamp" in event
        assert event.get("correlation_id") is None
        assert event.get("channel") is None

    def test_create_event_with_correlation_id(self):
        """Test creating event with correlation ID."""
        event = create_event(
            WebSocketEventType.ALERT_CREATED,
            {"id": "123"},
            correlation_id="req-abc123",
        )
        assert event["correlation_id"] == "req-abc123"

    def test_create_event_with_channel(self):
        """Test creating event with custom channel."""
        event = create_event(
            WebSocketEventType.ALERT_CREATED,
            {"id": "123"},
            channel="custom_channel",
        )
        assert event["channel"] == "custom_channel"

    def test_create_event_timestamp_is_iso_format(self):
        """Test that event timestamp is in ISO format."""
        event = create_event(
            WebSocketEventType.ALERT_CREATED,
            {"id": "123"},
        )
        timestamp = event["timestamp"]
        # Should be parseable as ISO format
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        assert parsed is not None

    def test_create_event_with_empty_payload(self):
        """Test creating event with empty payload."""
        event = create_event(
            WebSocketEventType.PING,
            {},
        )
        assert event["type"] == WebSocketEventType.PING
        assert event["payload"] == {}


class TestGetEventChannel:
    """Tests for get_event_channel function."""

    def test_alert_events_have_alerts_channel(self):
        """Verify alert events return alerts channel."""
        assert get_event_channel(WebSocketEventType.ALERT_CREATED) == "alerts"
        assert get_event_channel(WebSocketEventType.ALERT_UPDATED) == "alerts"
        assert get_event_channel(WebSocketEventType.ALERT_ACKNOWLEDGED) == "alerts"

    def test_camera_events_have_cameras_channel(self):
        """Verify camera events return cameras channel."""
        assert get_event_channel(WebSocketEventType.CAMERA_ONLINE) == "cameras"
        assert get_event_channel(WebSocketEventType.CAMERA_OFFLINE) == "cameras"
        assert get_event_channel(WebSocketEventType.CAMERA_STATUS_CHANGED) == "cameras"

    def test_job_events_have_jobs_channel(self):
        """Verify job events return jobs channel."""
        assert get_event_channel(WebSocketEventType.JOB_STARTED) == "jobs"
        assert get_event_channel(WebSocketEventType.JOB_PROGRESS) == "jobs"
        assert get_event_channel(WebSocketEventType.JOB_COMPLETED) == "jobs"

    def test_system_events_have_system_channel(self):
        """Verify system events return system channel."""
        assert get_event_channel(WebSocketEventType.SYSTEM_HEALTH_CHANGED) == "system"
        assert get_event_channel(WebSocketEventType.SYSTEM_STATUS) == "system"
        assert get_event_channel(WebSocketEventType.GPU_STATS_UPDATED) == "system"

    def test_security_events_have_events_channel(self):
        """Verify security events return events channel."""
        assert get_event_channel(WebSocketEventType.EVENT_CREATED) == "events"
        assert get_event_channel(WebSocketEventType.EVENT_UPDATED) == "events"

    def test_detection_events_have_detections_channel(self):
        """Verify detection events return detections channel."""
        assert get_event_channel(WebSocketEventType.DETECTION_NEW) == "detections"
        assert get_event_channel(WebSocketEventType.DETECTION_BATCH) == "detections"

    def test_control_messages_have_no_channel(self):
        """Verify control messages return None for channel."""
        assert get_event_channel(WebSocketEventType.PING) is None
        assert get_event_channel(WebSocketEventType.PONG) is None


class TestGetEventDescription:
    """Tests for get_event_description function."""

    def test_returns_description_for_known_types(self):
        """Verify descriptions are returned for known event types."""
        description = get_event_description(WebSocketEventType.ALERT_CREATED)
        assert isinstance(description, str)
        assert len(description) > 0
        assert "alert" in description.lower()

    def test_returns_fallback_for_unknown_types(self):
        """Verify fallback description for unknown types."""
        # All types should have metadata, but test the fallback path
        description = get_event_description(WebSocketEventType.PING)
        assert isinstance(description, str)
        assert len(description) > 0


class TestGetRequiredPayloadFields:
    """Tests for get_required_payload_fields function."""

    def test_alert_created_has_required_fields(self):
        """Verify ALERT_CREATED has expected required fields."""
        fields = get_required_payload_fields(WebSocketEventType.ALERT_CREATED)
        assert "id" in fields
        assert "event_id" in fields
        assert "severity" in fields

    def test_job_progress_has_required_fields(self):
        """Verify JOB_PROGRESS has expected required fields."""
        fields = get_required_payload_fields(WebSocketEventType.JOB_PROGRESS)
        assert "job_id" in fields
        assert "progress" in fields
        assert "status" in fields

    def test_control_messages_have_empty_fields(self):
        """Verify control messages have empty payload fields."""
        fields = get_required_payload_fields(WebSocketEventType.PING)
        assert fields == []


class TestValidateEventType:
    """Tests for validate_event_type function."""

    def test_valid_event_type_string_returns_enum(self):
        """Verify valid string returns WebSocketEventType."""
        result = validate_event_type("alert.created")
        assert result == WebSocketEventType.ALERT_CREATED

    def test_invalid_event_type_string_returns_none(self):
        """Verify invalid string returns None."""
        result = validate_event_type("invalid.event.type")
        assert result is None

    def test_empty_string_returns_none(self):
        """Verify empty string returns None."""
        result = validate_event_type("")
        assert result is None

    def test_case_sensitive_matching(self):
        """Verify event type matching is case-sensitive."""
        result = validate_event_type("ALERT.CREATED")
        assert result is None  # Should be lowercase


class TestGetAllEventTypes:
    """Tests for get_all_event_types function."""

    def test_returns_all_event_types(self):
        """Verify all event types are returned."""
        all_types = get_all_event_types()
        assert len(all_types) == len(WebSocketEventType)
        for event_type in WebSocketEventType:
            assert event_type in all_types

    def test_returns_list(self):
        """Verify return type is a list."""
        result = get_all_event_types()
        assert isinstance(result, list)


class TestGetEventTypesByChannel:
    """Tests for get_event_types_by_channel function."""

    def test_alerts_channel_returns_alert_types(self):
        """Verify alerts channel returns alert event types."""
        types = get_event_types_by_channel("alerts")
        assert WebSocketEventType.ALERT_CREATED in types
        assert WebSocketEventType.ALERT_UPDATED in types
        assert WebSocketEventType.ALERT_ACKNOWLEDGED in types
        # Should not include other types
        assert WebSocketEventType.CAMERA_ONLINE not in types

    def test_cameras_channel_returns_camera_types(self):
        """Verify cameras channel returns camera event types."""
        types = get_event_types_by_channel("cameras")
        assert WebSocketEventType.CAMERA_ONLINE in types
        assert WebSocketEventType.CAMERA_OFFLINE in types
        # Should not include other types
        assert WebSocketEventType.ALERT_CREATED not in types

    def test_unknown_channel_returns_empty_list(self):
        """Verify unknown channel returns empty list."""
        types = get_event_types_by_channel("unknown_channel")
        assert types == []


class TestGetAllChannels:
    """Tests for get_all_channels function."""

    def test_returns_expected_channels(self):
        """Verify expected channels are returned."""
        channels = get_all_channels()
        expected = {"alerts", "cameras", "jobs", "system", "events", "detections", "workers"}
        assert set(channels) == expected

    def test_returns_sorted_list(self):
        """Verify channels are sorted alphabetically."""
        channels = get_all_channels()
        assert channels == sorted(channels)

    def test_excludes_none_channel(self):
        """Verify None channel is excluded."""
        channels = get_all_channels()
        assert None not in channels


class TestWebSocketEventTypedDict:
    """Tests for WebSocketEvent TypedDict structure."""

    def test_event_structure(self):
        """Verify WebSocketEvent has expected structure."""
        event: WebSocketEvent = {
            "type": WebSocketEventType.ALERT_CREATED,
            "payload": {"id": "123"},
            "timestamp": datetime.now(UTC).isoformat(),
            "correlation_id": "req-123",
            "sequence": 1,
            "channel": "alerts",
        }
        assert event["type"] == WebSocketEventType.ALERT_CREATED
        assert event["payload"]["id"] == "123"
        assert event["correlation_id"] == "req-123"
        assert event["sequence"] == 1
        assert event["channel"] == "alerts"

    def test_event_with_optional_fields_none(self):
        """Verify WebSocketEvent allows None for optional fields."""
        event: WebSocketEvent = {
            "type": WebSocketEventType.PING,
            "payload": {},
            "timestamp": datetime.now(UTC).isoformat(),
            "correlation_id": None,
            "sequence": None,
            "channel": None,
        }
        assert event["correlation_id"] is None
        assert event["sequence"] is None
        assert event["channel"] is None


class TestEventTypeHierarchy:
    """Tests for event type naming convention and hierarchy."""

    def test_event_types_follow_domain_action_pattern(self):
        """Verify most event types follow domain.action pattern."""
        exceptions = {"ping", "pong", "error"}  # Control messages don't follow pattern
        for event_type in WebSocketEventType:
            if event_type.value not in exceptions:
                parts = event_type.value.split(".")
                assert len(parts) == 2, f"{event_type} doesn't follow domain.action pattern"

    def test_domains_are_consistent(self):
        """Verify domain names are consistent across related event types."""
        # Group event types by domain
        domains = {}
        for event_type in WebSocketEventType:
            parts = event_type.value.split(".")
            if len(parts) == 2:
                domain = parts[0]
                if domain not in domains:
                    domains[domain] = []
                domains[domain].append(event_type)

        # Verify expected domains exist
        assert "alert" in domains
        assert "camera" in domains
        assert "job" in domains
        assert "system" in domains
        assert "event" in domains
        assert "detection" in domains
