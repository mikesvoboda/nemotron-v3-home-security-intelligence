"""Unit tests for new WebSocket event payload schemas (NEM-5073 - TDD Red Phase).

This module tests the Pydantic payload schemas for 8 new WebSocket event types:
- Zone events: zone.crossing, zone.dwell_started, zone.dwell_alert, zone.approach
- Entity events: entity.matched, entity.track_updated
- AI events: ai.threat_detected, ai.action_recognized

These tests are written FIRST (TDD red phase) and will initially FAIL until
the payload schemas are added to backend/core/websocket/event_schemas.py.
"""

import pytest
from backend.core.websocket import WebSocketEventType
from backend.core.websocket.event_schemas import (
    EVENT_PAYLOAD_SCHEMAS,
    get_payload_schema,
    validate_payload,
)
from pydantic import ValidationError

# Import new payload schemas (will fail until schemas are implemented)
try:
    from backend.core.websocket.event_schemas import (
        AIActionRecognizedPayload,
        AIThreatDetectedPayload,
        EntityMatchedPayload,
        EntityTrackUpdatedPayload,
        ZoneApproachPayload,
        ZoneCrossingPayload,
        ZoneDwellAlertPayload,
        ZoneDwellStartedPayload,
    )
except ImportError:
    # Tests will fail appropriately if schemas don't exist yet
    pass


class TestZoneCrossingPayloadSchema:
    """Tests for zone.crossing event payload schema."""

    def test_zone_crossing_payload_validation_success(self):
        """Test valid ZoneCrossingPayload."""
        payload = ZoneCrossingPayload(
            zone_id="zone-123",
            zone_name="Front Door Area",
            entity_id="entity-456",
            entity_type="person",
            camera_id="front_door",
            timestamp="2026-02-01T12:00:00Z",
            direction="entering",
        )
        assert payload.zone_id == "zone-123"
        assert payload.entity_id == "entity-456"
        assert payload.direction == "entering"

    def test_zone_crossing_payload_missing_required_fields(self):
        """Test ZoneCrossingPayload fails with missing required fields."""
        with pytest.raises(ValidationError) as exc_info:
            ZoneCrossingPayload(
                zone_id="zone-123",
                # Missing entity_id, camera_id, timestamp, direction
            )
        errors = exc_info.value.errors()
        assert any(e["loc"][0] == "entity_id" for e in errors)
        assert any(e["loc"][0] == "camera_id" for e in errors)
        assert any(e["loc"][0] == "timestamp" for e in errors)
        assert any(e["loc"][0] == "direction" for e in errors)

    def test_zone_crossing_payload_optional_fields(self):
        """Test ZoneCrossingPayload with optional fields."""
        payload = ZoneCrossingPayload(
            zone_id="zone-123",
            zone_name="Side Gate",
            entity_id="entity-789",
            entity_type="vehicle",
            camera_id="side_yard",
            timestamp="2026-02-01T12:00:00Z",
            direction="exiting",
            bbox={"x": 100.0, "y": 200.0, "width": 50.0, "height": 100.0},
        )
        assert payload.bbox is not None
        assert payload.bbox["x"] == 100.0


class TestZoneDwellStartedPayloadSchema:
    """Tests for zone.dwell_started event payload schema."""

    def test_zone_dwell_started_payload_validation_success(self):
        """Test valid ZoneDwellStartedPayload."""
        payload = ZoneDwellStartedPayload(
            zone_id="zone-123",
            zone_name="Loading Dock",
            entity_id="entity-456",
            entity_type="person",
            camera_id="loading_dock",
            timestamp="2026-02-01T12:00:00Z",
        )
        assert payload.zone_id == "zone-123"
        assert payload.entity_id == "entity-456"
        assert payload.timestamp == "2026-02-01T12:00:00Z"

    def test_zone_dwell_started_payload_missing_required_fields(self):
        """Test ZoneDwellStartedPayload fails with missing required fields."""
        with pytest.raises(ValidationError) as exc_info:
            ZoneDwellStartedPayload(
                zone_id="zone-123",
                # Missing entity_id, camera_id, timestamp
            )
        errors = exc_info.value.errors()
        assert any(e["loc"][0] == "entity_id" for e in errors)
        assert any(e["loc"][0] == "camera_id" for e in errors)
        assert any(e["loc"][0] == "timestamp" for e in errors)


class TestZoneDwellAlertPayloadSchema:
    """Tests for zone.dwell_alert event payload schema."""

    def test_zone_dwell_alert_payload_validation_success(self):
        """Test valid ZoneDwellAlertPayload."""
        payload = ZoneDwellAlertPayload(
            zone_id="zone-123",
            zone_name="Restricted Area",
            entity_id="entity-456",
            entity_type="person",
            camera_id="restricted_cam",
            timestamp="2026-02-01T12:05:00Z",
            dwell_duration_seconds=300,
            threshold_seconds=180,
        )
        assert payload.dwell_duration_seconds == 300
        assert payload.threshold_seconds == 180

    def test_zone_dwell_alert_payload_validates_duration(self):
        """Test ZoneDwellAlertPayload validates duration is non-negative."""
        # Valid: 0 seconds
        payload = ZoneDwellAlertPayload(
            zone_id="zone-123",
            zone_name="Area",
            entity_id="entity-456",
            entity_type="person",
            camera_id="cam",
            timestamp="2026-02-01T12:00:00Z",
            dwell_duration_seconds=0,
            threshold_seconds=60,
        )
        assert payload.dwell_duration_seconds == 0

        # Invalid: negative duration
        with pytest.raises(ValidationError):
            ZoneDwellAlertPayload(
                zone_id="zone-123",
                zone_name="Area",
                entity_id="entity-456",
                entity_type="person",
                camera_id="cam",
                timestamp="2026-02-01T12:00:00Z",
                dwell_duration_seconds=-10,
                threshold_seconds=60,
            )

    def test_zone_dwell_alert_payload_validates_threshold(self):
        """Test ZoneDwellAlertPayload validates threshold is positive."""
        # Valid: positive threshold
        payload = ZoneDwellAlertPayload(
            zone_id="zone-123",
            zone_name="Area",
            entity_id="entity-456",
            entity_type="person",
            camera_id="cam",
            timestamp="2026-02-01T12:00:00Z",
            dwell_duration_seconds=100,
            threshold_seconds=60,
        )
        assert payload.threshold_seconds == 60

        # Invalid: zero or negative threshold
        with pytest.raises(ValidationError):
            ZoneDwellAlertPayload(
                zone_id="zone-123",
                zone_name="Area",
                entity_id="entity-456",
                entity_type="person",
                camera_id="cam",
                timestamp="2026-02-01T12:00:00Z",
                dwell_duration_seconds=100,
                threshold_seconds=0,
            )


class TestZoneApproachPayloadSchema:
    """Tests for zone.approach event payload schema."""

    def test_zone_approach_payload_validation_success(self):
        """Test valid ZoneApproachPayload."""
        payload = ZoneApproachPayload(
            zone_id="zone-123",
            zone_name="Entry Point",
            entity_id="entity-456",
            entity_type="person",
            camera_id="entry_cam",
            timestamp="2026-02-01T12:00:00Z",
            direction="north",
            speed=1.5,
            eta_seconds=10,
        )
        assert payload.direction == "north"
        assert payload.speed == 1.5
        assert payload.eta_seconds == 10

    def test_zone_approach_payload_validates_speed(self):
        """Test ZoneApproachPayload validates speed is non-negative."""
        # Valid: 0 speed
        payload = ZoneApproachPayload(
            zone_id="zone-123",
            zone_name="Area",
            entity_id="entity-456",
            entity_type="person",
            camera_id="cam",
            timestamp="2026-02-01T12:00:00Z",
            direction="east",
            speed=0.0,
            eta_seconds=30,
        )
        assert payload.speed == 0.0

        # Invalid: negative speed
        with pytest.raises(ValidationError):
            ZoneApproachPayload(
                zone_id="zone-123",
                zone_name="Area",
                entity_id="entity-456",
                entity_type="person",
                camera_id="cam",
                timestamp="2026-02-01T12:00:00Z",
                direction="west",
                speed=-1.0,
                eta_seconds=30,
            )

    def test_zone_approach_payload_validates_eta(self):
        """Test ZoneApproachPayload validates ETA is non-negative."""
        # Valid: 0 ETA
        payload = ZoneApproachPayload(
            zone_id="zone-123",
            zone_name="Area",
            entity_id="entity-456",
            entity_type="person",
            camera_id="cam",
            timestamp="2026-02-01T12:00:00Z",
            direction="south",
            speed=2.0,
            eta_seconds=0,
        )
        assert payload.eta_seconds == 0

        # Invalid: negative ETA
        with pytest.raises(ValidationError):
            ZoneApproachPayload(
                zone_id="zone-123",
                zone_name="Area",
                entity_id="entity-456",
                entity_type="person",
                camera_id="cam",
                timestamp="2026-02-01T12:00:00Z",
                direction="north",
                speed=2.0,
                eta_seconds=-5,
            )


class TestEntityMatchedPayloadSchema:
    """Tests for entity.matched event payload schema."""

    def test_entity_matched_payload_validation_success(self):
        """Test valid EntityMatchedPayload."""
        payload = EntityMatchedPayload(
            entity_id="entity-123",
            matched_entity_id="entity-456",
            similarity_score=0.92,
            camera_id="front_door",
            timestamp="2026-02-01T12:00:00Z",
            match_type="face",
        )
        assert payload.entity_id == "entity-123"
        assert payload.matched_entity_id == "entity-456"
        assert payload.similarity_score == 0.92
        assert payload.match_type == "face"

    def test_entity_matched_payload_validates_similarity_score_range(self):
        """Test EntityMatchedPayload validates similarity score range (0-1)."""
        # Valid: 0.0
        payload = EntityMatchedPayload(
            entity_id="entity-123",
            matched_entity_id="entity-456",
            similarity_score=0.0,
            camera_id="cam",
            timestamp="2026-02-01T12:00:00Z",
        )
        assert payload.similarity_score == 0.0

        # Valid: 1.0
        payload = EntityMatchedPayload(
            entity_id="entity-123",
            matched_entity_id="entity-456",
            similarity_score=1.0,
            camera_id="cam",
            timestamp="2026-02-01T12:00:00Z",
        )
        assert payload.similarity_score == 1.0

        # Invalid: > 1.0
        with pytest.raises(ValidationError):
            EntityMatchedPayload(
                entity_id="entity-123",
                matched_entity_id="entity-456",
                similarity_score=1.5,
                camera_id="cam",
                timestamp="2026-02-01T12:00:00Z",
            )

        # Invalid: < 0.0
        with pytest.raises(ValidationError):
            EntityMatchedPayload(
                entity_id="entity-123",
                matched_entity_id="entity-456",
                similarity_score=-0.1,
                camera_id="cam",
                timestamp="2026-02-01T12:00:00Z",
            )

    def test_entity_matched_payload_missing_required_fields(self):
        """Test EntityMatchedPayload fails with missing required fields."""
        with pytest.raises(ValidationError) as exc_info:
            EntityMatchedPayload(
                entity_id="entity-123",
                # Missing matched_entity_id, similarity_score, camera_id, timestamp
            )
        errors = exc_info.value.errors()
        assert any(e["loc"][0] == "matched_entity_id" for e in errors)
        assert any(e["loc"][0] == "similarity_score" for e in errors)
        assert any(e["loc"][0] == "camera_id" for e in errors)
        assert any(e["loc"][0] == "timestamp" for e in errors)


class TestEntityTrackUpdatedPayloadSchema:
    """Tests for entity.track_updated event payload schema."""

    def test_entity_track_updated_payload_validation_success(self):
        """Test valid EntityTrackUpdatedPayload."""
        payload = EntityTrackUpdatedPayload(
            entity_id="entity-123",
            camera_id="back_yard",
            timestamp="2026-02-01T12:00:00Z",
            position={"x": 100.0, "y": 200.0},
            bbox={"x": 90.0, "y": 190.0, "width": 50.0, "height": 100.0},
            velocity={"x": 1.5, "y": 0.5},
        )
        assert payload.entity_id == "entity-123"
        assert payload.position["x"] == 100.0
        assert payload.bbox["width"] == 50.0
        assert payload.velocity is not None

    def test_entity_track_updated_payload_missing_required_fields(self):
        """Test EntityTrackUpdatedPayload fails with missing required fields."""
        with pytest.raises(ValidationError) as exc_info:
            EntityTrackUpdatedPayload(
                entity_id="entity-123",
                # Missing camera_id, timestamp, position, bbox
            )
        errors = exc_info.value.errors()
        assert any(e["loc"][0] == "camera_id" for e in errors)
        assert any(e["loc"][0] == "timestamp" for e in errors)
        assert any(e["loc"][0] == "position" for e in errors)
        assert any(e["loc"][0] == "bbox" for e in errors)

    def test_entity_track_updated_payload_optional_velocity(self):
        """Test EntityTrackUpdatedPayload with optional velocity field."""
        payload = EntityTrackUpdatedPayload(
            entity_id="entity-123",
            camera_id="cam",
            timestamp="2026-02-01T12:00:00Z",
            position={"x": 100.0, "y": 200.0},
            bbox={"x": 90.0, "y": 190.0, "width": 50.0, "height": 100.0},
        )
        # Velocity is optional
        assert payload.velocity is None


class TestAIThreatDetectedPayloadSchema:
    """Tests for ai.threat_detected event payload schema."""

    def test_ai_threat_detected_payload_validation_success(self):
        """Test valid AIThreatDetectedPayload."""
        payload = AIThreatDetectedPayload(
            detection_id="det-123",
            camera_id="front_door",
            timestamp="2026-02-01T12:00:00Z",
            threat_type="weapon",
            severity="critical",
            confidence=0.95,
            bbox={"x": 100.0, "y": 200.0, "width": 50.0, "height": 75.0},
        )
        assert payload.threat_type == "weapon"
        assert payload.severity == "critical"
        assert payload.confidence == 0.95

    def test_ai_threat_detected_payload_validates_confidence_range(self):
        """Test AIThreatDetectedPayload validates confidence range (0-1)."""
        # Valid: 0.0
        payload = AIThreatDetectedPayload(
            detection_id="det-123",
            camera_id="cam",
            timestamp="2026-02-01T12:00:00Z",
            threat_type="weapon",
            severity="low",
            confidence=0.0,
        )
        assert payload.confidence == 0.0

        # Valid: 1.0
        payload = AIThreatDetectedPayload(
            detection_id="det-123",
            camera_id="cam",
            timestamp="2026-02-01T12:00:00Z",
            threat_type="weapon",
            severity="high",
            confidence=1.0,
        )
        assert payload.confidence == 1.0

        # Invalid: > 1.0
        with pytest.raises(ValidationError):
            AIThreatDetectedPayload(
                detection_id="det-123",
                camera_id="cam",
                timestamp="2026-02-01T12:00:00Z",
                threat_type="weapon",
                severity="high",
                confidence=1.5,
            )

    def test_ai_threat_detected_payload_missing_required_fields(self):
        """Test AIThreatDetectedPayload fails with missing required fields."""
        with pytest.raises(ValidationError) as exc_info:
            AIThreatDetectedPayload(
                detection_id="det-123",
                # Missing camera_id, timestamp, threat_type, severity, confidence
            )
        errors = exc_info.value.errors()
        assert any(e["loc"][0] == "camera_id" for e in errors)
        assert any(e["loc"][0] == "threat_type" for e in errors)
        assert any(e["loc"][0] == "severity" for e in errors)
        assert any(e["loc"][0] == "confidence" for e in errors)


class TestAIActionRecognizedPayloadSchema:
    """Tests for ai.action_recognized event payload schema."""

    def test_ai_action_recognized_payload_validation_success(self):
        """Test valid AIActionRecognizedPayload."""
        payload = AIActionRecognizedPayload(
            detection_id="det-123",
            camera_id="garage",
            timestamp="2026-02-01T12:00:00Z",
            action_type="climbing",
            confidence=0.88,
            bbox={"x": 150.0, "y": 250.0, "width": 60.0, "height": 120.0},
        )
        assert payload.action_type == "climbing"
        assert payload.confidence == 0.88

    def test_ai_action_recognized_payload_validates_confidence_range(self):
        """Test AIActionRecognizedPayload validates confidence range (0-1)."""
        # Valid: 0.0
        payload = AIActionRecognizedPayload(
            detection_id="det-123",
            camera_id="cam",
            timestamp="2026-02-01T12:00:00Z",
            action_type="walking",
            confidence=0.0,
        )
        assert payload.confidence == 0.0

        # Valid: 1.0
        payload = AIActionRecognizedPayload(
            detection_id="det-123",
            camera_id="cam",
            timestamp="2026-02-01T12:00:00Z",
            action_type="running",
            confidence=1.0,
        )
        assert payload.confidence == 1.0

        # Invalid: < 0.0
        with pytest.raises(ValidationError):
            AIActionRecognizedPayload(
                detection_id="det-123",
                camera_id="cam",
                timestamp="2026-02-01T12:00:00Z",
                action_type="jumping",
                confidence=-0.1,
            )

    def test_ai_action_recognized_payload_missing_required_fields(self):
        """Test AIActionRecognizedPayload fails with missing required fields."""
        with pytest.raises(ValidationError) as exc_info:
            AIActionRecognizedPayload(
                detection_id="det-123",
                # Missing camera_id, timestamp, action_type, confidence
            )
        errors = exc_info.value.errors()
        assert any(e["loc"][0] == "camera_id" for e in errors)
        assert any(e["loc"][0] == "action_type" for e in errors)
        assert any(e["loc"][0] == "confidence" for e in errors)


class TestNewEventPayloadSchemaMapping:
    """Tests for new event type payload schema mapping."""

    def test_all_new_event_types_have_schemas(self):
        """Verify all new event types have payload schemas registered."""
        new_event_types = {
            WebSocketEventType.ZONE_CROSSING: ZoneCrossingPayload,
            WebSocketEventType.ZONE_DWELL_STARTED: ZoneDwellStartedPayload,
            WebSocketEventType.ZONE_DWELL_ALERT: ZoneDwellAlertPayload,
            WebSocketEventType.ZONE_APPROACH: ZoneApproachPayload,
            WebSocketEventType.ENTITY_MATCHED: EntityMatchedPayload,
            WebSocketEventType.ENTITY_TRACK_UPDATED: EntityTrackUpdatedPayload,
            WebSocketEventType.AI_THREAT_DETECTED: AIThreatDetectedPayload,
            WebSocketEventType.AI_ACTION_RECOGNIZED: AIActionRecognizedPayload,
        }

        for event_type, expected_schema in new_event_types.items():
            schema = get_payload_schema(event_type)
            assert schema is not None, f"Missing schema for {event_type}"
            assert schema == expected_schema

    def test_new_event_types_in_payload_schema_registry(self):
        """Verify all new event types are in EVENT_PAYLOAD_SCHEMAS."""
        assert WebSocketEventType.ZONE_CROSSING in EVENT_PAYLOAD_SCHEMAS
        assert WebSocketEventType.ZONE_DWELL_STARTED in EVENT_PAYLOAD_SCHEMAS
        assert WebSocketEventType.ZONE_DWELL_ALERT in EVENT_PAYLOAD_SCHEMAS
        assert WebSocketEventType.ZONE_APPROACH in EVENT_PAYLOAD_SCHEMAS
        assert WebSocketEventType.ENTITY_MATCHED in EVENT_PAYLOAD_SCHEMAS
        assert WebSocketEventType.ENTITY_TRACK_UPDATED in EVENT_PAYLOAD_SCHEMAS
        assert WebSocketEventType.AI_THREAT_DETECTED in EVENT_PAYLOAD_SCHEMAS
        assert WebSocketEventType.AI_ACTION_RECOGNIZED in EVENT_PAYLOAD_SCHEMAS

    def test_validate_payload_function_works_for_new_event_types(self):
        """Test validate_payload helper function works for new event types."""
        # Zone crossing example
        data = {
            "zone_id": "zone-123",
            "zone_name": "Front Door",
            "entity_id": "entity-456",
            "entity_type": "person",
            "camera_id": "front_door",
            "timestamp": "2026-02-01T12:00:00Z",
            "direction": "entering",
        }
        result = validate_payload(WebSocketEventType.ZONE_CROSSING, data)
        assert isinstance(result, ZoneCrossingPayload)
        assert result.zone_id == "zone-123"

        # Entity matched example
        data = {
            "entity_id": "entity-123",
            "matched_entity_id": "entity-456",
            "similarity_score": 0.95,
            "camera_id": "cam",
            "timestamp": "2026-02-01T12:00:00Z",
        }
        result = validate_payload(WebSocketEventType.ENTITY_MATCHED, data)
        assert isinstance(result, EntityMatchedPayload)
        assert result.similarity_score == 0.95

        # AI threat detected example
        data = {
            "detection_id": "det-123",
            "camera_id": "cam",
            "timestamp": "2026-02-01T12:00:00Z",
            "threat_type": "weapon",
            "severity": "critical",
            "confidence": 0.98,
        }
        result = validate_payload(WebSocketEventType.AI_THREAT_DETECTED, data)
        assert isinstance(result, AIThreatDetectedPayload)
        assert result.threat_type == "weapon"
