"""Unit tests for new WebSocket event types (NEM-5073 - TDD Red Phase).

This module tests the 8 new WebSocket event types for Platform Enhancement Strategy:
- Zone events: zone.crossing, zone.dwell_started, zone.dwell_alert, zone.approach
- Entity events: entity.matched, entity.track_updated
- AI events: ai.threat_detected, ai.action_recognized

These tests are written FIRST (TDD red phase) and will initially FAIL until
the event types are added to backend/core/websocket/event_types.py.
"""

from backend.core.websocket import (
    EVENT_TYPE_METADATA,
    WebSocketEventType,
    get_all_channels,
    get_event_channel,
    get_event_description,
    get_event_types_by_channel,
    get_required_payload_fields,
)


class TestNewZoneEventTypes:
    """Tests for new zone-related event types (NEM-5073)."""

    def test_zone_crossing_event_type_exists(self):
        """Verify zone.crossing event type is defined."""
        assert hasattr(WebSocketEventType, "ZONE_CROSSING")
        assert WebSocketEventType.ZONE_CROSSING.value == "zone.crossing"

    def test_zone_dwell_started_event_type_exists(self):
        """Verify zone.dwell_started event type is defined."""
        assert hasattr(WebSocketEventType, "ZONE_DWELL_STARTED")
        assert WebSocketEventType.ZONE_DWELL_STARTED.value == "zone.dwell_started"

    def test_zone_dwell_alert_event_type_exists(self):
        """Verify zone.dwell_alert event type is defined."""
        assert hasattr(WebSocketEventType, "ZONE_DWELL_ALERT")
        assert WebSocketEventType.ZONE_DWELL_ALERT.value == "zone.dwell_alert"

    def test_zone_approach_event_type_exists(self):
        """Verify zone.approach event type is defined."""
        assert hasattr(WebSocketEventType, "ZONE_APPROACH")
        assert WebSocketEventType.ZONE_APPROACH.value == "zone.approach"

    def test_zone_events_follow_naming_convention(self):
        """Verify all zone events follow domain.action pattern."""
        zone_events = [
            WebSocketEventType.ZONE_CROSSING,
            WebSocketEventType.ZONE_DWELL_STARTED,
            WebSocketEventType.ZONE_DWELL_ALERT,
            WebSocketEventType.ZONE_APPROACH,
        ]
        for event_type in zone_events:
            assert event_type.value.startswith("zone.")

    def test_zone_events_have_zones_channel(self):
        """Verify all zone events use the zones channel."""
        assert get_event_channel(WebSocketEventType.ZONE_CROSSING) == "zones"
        assert get_event_channel(WebSocketEventType.ZONE_DWELL_STARTED) == "zones"
        assert get_event_channel(WebSocketEventType.ZONE_DWELL_ALERT) == "zones"
        assert get_event_channel(WebSocketEventType.ZONE_APPROACH) == "zones"

    def test_zones_channel_exists(self):
        """Verify zones channel is in the channel registry."""
        channels = get_all_channels()
        assert "zones" in channels

    def test_zones_channel_returns_zone_event_types(self):
        """Verify zones channel returns all zone event types."""
        zone_types = get_event_types_by_channel("zones")
        assert WebSocketEventType.ZONE_CROSSING in zone_types
        assert WebSocketEventType.ZONE_DWELL_STARTED in zone_types
        assert WebSocketEventType.ZONE_DWELL_ALERT in zone_types
        assert WebSocketEventType.ZONE_APPROACH in zone_types


class TestNewEntityEventTypes:
    """Tests for new entity-related event types (NEM-5073)."""

    def test_entity_matched_event_type_exists(self):
        """Verify entity.matched event type is defined."""
        assert hasattr(WebSocketEventType, "ENTITY_MATCHED")
        assert WebSocketEventType.ENTITY_MATCHED.value == "entity.matched"

    def test_entity_track_updated_event_type_exists(self):
        """Verify entity.track_updated event type is defined."""
        assert hasattr(WebSocketEventType, "ENTITY_TRACK_UPDATED")
        assert WebSocketEventType.ENTITY_TRACK_UPDATED.value == "entity.track_updated"

    def test_entity_events_follow_naming_convention(self):
        """Verify all entity events follow domain.action pattern."""
        entity_events = [
            WebSocketEventType.ENTITY_MATCHED,
            WebSocketEventType.ENTITY_TRACK_UPDATED,
        ]
        for event_type in entity_events:
            assert event_type.value.startswith("entity.")

    def test_entity_events_have_entities_channel(self):
        """Verify all entity events use the entities channel."""
        assert get_event_channel(WebSocketEventType.ENTITY_MATCHED) == "entities"
        assert get_event_channel(WebSocketEventType.ENTITY_TRACK_UPDATED) == "entities"

    def test_entities_channel_exists(self):
        """Verify entities channel is in the channel registry."""
        channels = get_all_channels()
        assert "entities" in channels

    def test_entities_channel_returns_entity_event_types(self):
        """Verify entities channel returns all entity event types."""
        entity_types = get_event_types_by_channel("entities")
        assert WebSocketEventType.ENTITY_MATCHED in entity_types
        assert WebSocketEventType.ENTITY_TRACK_UPDATED in entity_types


class TestNewAIEventTypes:
    """Tests for new AI-related event types (NEM-5073)."""

    def test_ai_threat_detected_event_type_exists(self):
        """Verify ai.threat_detected event type is defined."""
        assert hasattr(WebSocketEventType, "AI_THREAT_DETECTED")
        assert WebSocketEventType.AI_THREAT_DETECTED.value == "ai.threat_detected"

    def test_ai_action_recognized_event_type_exists(self):
        """Verify ai.action_recognized event type is defined."""
        assert hasattr(WebSocketEventType, "AI_ACTION_RECOGNIZED")
        assert WebSocketEventType.AI_ACTION_RECOGNIZED.value == "ai.action_recognized"

    def test_ai_events_follow_naming_convention(self):
        """Verify all AI events follow domain.action pattern."""
        ai_events = [
            WebSocketEventType.AI_THREAT_DETECTED,
            WebSocketEventType.AI_ACTION_RECOGNIZED,
        ]
        for event_type in ai_events:
            assert event_type.value.startswith("ai.")

    def test_ai_events_have_ai_channel(self):
        """Verify all AI events use the ai channel."""
        assert get_event_channel(WebSocketEventType.AI_THREAT_DETECTED) == "ai"
        assert get_event_channel(WebSocketEventType.AI_ACTION_RECOGNIZED) == "ai"

    def test_ai_channel_exists(self):
        """Verify ai channel is in the channel registry."""
        channels = get_all_channels()
        assert "ai" in channels

    def test_ai_channel_returns_ai_event_types(self):
        """Verify ai channel returns all AI event types."""
        ai_types = get_event_types_by_channel("ai")
        assert WebSocketEventType.AI_THREAT_DETECTED in ai_types
        assert WebSocketEventType.AI_ACTION_RECOGNIZED in ai_types


class TestNewEventTypeMetadata:
    """Tests for metadata entries of new event types (NEM-5073)."""

    def test_zone_crossing_has_metadata(self):
        """Verify zone.crossing has complete metadata entry."""
        metadata = EVENT_TYPE_METADATA[WebSocketEventType.ZONE_CROSSING]
        assert metadata["description"]
        assert metadata["channel"] == "zones"
        assert metadata["requires_payload"] is True
        assert "zone_id" in metadata["payload_fields"]
        assert "entity_id" in metadata["payload_fields"]
        assert "camera_id" in metadata["payload_fields"]

    def test_zone_dwell_started_has_metadata(self):
        """Verify zone.dwell_started has complete metadata entry."""
        metadata = EVENT_TYPE_METADATA[WebSocketEventType.ZONE_DWELL_STARTED]
        assert metadata["description"]
        assert metadata["channel"] == "zones"
        assert metadata["requires_payload"] is True
        assert "zone_id" in metadata["payload_fields"]
        assert "entity_id" in metadata["payload_fields"]
        assert "timestamp" in metadata["payload_fields"]

    def test_zone_dwell_alert_has_metadata(self):
        """Verify zone.dwell_alert has complete metadata entry."""
        metadata = EVENT_TYPE_METADATA[WebSocketEventType.ZONE_DWELL_ALERT]
        assert metadata["description"]
        assert metadata["channel"] == "zones"
        assert metadata["requires_payload"] is True
        assert "zone_id" in metadata["payload_fields"]
        assert "entity_id" in metadata["payload_fields"]
        assert "dwell_duration_seconds" in metadata["payload_fields"]
        assert "threshold_seconds" in metadata["payload_fields"]

    def test_zone_approach_has_metadata(self):
        """Verify zone.approach has complete metadata entry."""
        metadata = EVENT_TYPE_METADATA[WebSocketEventType.ZONE_APPROACH]
        assert metadata["description"]
        assert metadata["channel"] == "zones"
        assert metadata["requires_payload"] is True
        assert "zone_id" in metadata["payload_fields"]
        assert "entity_id" in metadata["payload_fields"]
        assert "direction" in metadata["payload_fields"]
        assert "speed" in metadata["payload_fields"]
        assert "eta_seconds" in metadata["payload_fields"]

    def test_entity_matched_has_metadata(self):
        """Verify entity.matched has complete metadata entry."""
        metadata = EVENT_TYPE_METADATA[WebSocketEventType.ENTITY_MATCHED]
        assert metadata["description"]
        assert metadata["channel"] == "entities"
        assert metadata["requires_payload"] is True
        assert "entity_id" in metadata["payload_fields"]
        assert "matched_entity_id" in metadata["payload_fields"]
        assert "similarity_score" in metadata["payload_fields"]
        assert "camera_id" in metadata["payload_fields"]

    def test_entity_track_updated_has_metadata(self):
        """Verify entity.track_updated has complete metadata entry."""
        metadata = EVENT_TYPE_METADATA[WebSocketEventType.ENTITY_TRACK_UPDATED]
        assert metadata["description"]
        assert metadata["channel"] == "entities"
        assert metadata["requires_payload"] is True
        assert "entity_id" in metadata["payload_fields"]
        assert "camera_id" in metadata["payload_fields"]
        assert "position" in metadata["payload_fields"]
        assert "bbox" in metadata["payload_fields"]

    def test_ai_threat_detected_has_metadata(self):
        """Verify ai.threat_detected has complete metadata entry."""
        metadata = EVENT_TYPE_METADATA[WebSocketEventType.AI_THREAT_DETECTED]
        assert metadata["description"]
        assert metadata["channel"] == "ai"
        assert metadata["requires_payload"] is True
        assert "detection_id" in metadata["payload_fields"]
        assert "camera_id" in metadata["payload_fields"]
        assert "threat_type" in metadata["payload_fields"]
        assert "severity" in metadata["payload_fields"]
        assert "confidence" in metadata["payload_fields"]

    def test_ai_action_recognized_has_metadata(self):
        """Verify ai.action_recognized has complete metadata entry."""
        metadata = EVENT_TYPE_METADATA[WebSocketEventType.AI_ACTION_RECOGNIZED]
        assert metadata["description"]
        assert metadata["channel"] == "ai"
        assert metadata["requires_payload"] is True
        assert "detection_id" in metadata["payload_fields"]
        assert "camera_id" in metadata["payload_fields"]
        assert "action_type" in metadata["payload_fields"]
        assert "confidence" in metadata["payload_fields"]

    def test_new_event_types_have_descriptions(self):
        """Verify all new event types have non-empty descriptions."""
        new_event_types = [
            WebSocketEventType.ZONE_CROSSING,
            WebSocketEventType.ZONE_DWELL_STARTED,
            WebSocketEventType.ZONE_DWELL_ALERT,
            WebSocketEventType.ZONE_APPROACH,
            WebSocketEventType.ENTITY_MATCHED,
            WebSocketEventType.ENTITY_TRACK_UPDATED,
            WebSocketEventType.AI_THREAT_DETECTED,
            WebSocketEventType.AI_ACTION_RECOGNIZED,
        ]
        for event_type in new_event_types:
            description = get_event_description(event_type)
            assert isinstance(description, str)
            assert len(description) > 0

    def test_new_event_types_have_required_payload_fields(self):
        """Verify all new event types have required payload fields defined."""
        new_event_types = [
            WebSocketEventType.ZONE_CROSSING,
            WebSocketEventType.ZONE_DWELL_STARTED,
            WebSocketEventType.ZONE_DWELL_ALERT,
            WebSocketEventType.ZONE_APPROACH,
            WebSocketEventType.ENTITY_MATCHED,
            WebSocketEventType.ENTITY_TRACK_UPDATED,
            WebSocketEventType.AI_THREAT_DETECTED,
            WebSocketEventType.AI_ACTION_RECOGNIZED,
        ]
        for event_type in new_event_types:
            fields = get_required_payload_fields(event_type)
            assert isinstance(fields, list)
            assert len(fields) > 0
