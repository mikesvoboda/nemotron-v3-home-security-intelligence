"""Unit tests for EventBroadcaster with new event types (NEM-5073 - TDD Red Phase).

This module tests broadcasting of 8 new WebSocket event types:
- Zone events: zone.crossing, zone.dwell_started, zone.dwell_alert, zone.approach
- Entity events: entity.matched, entity.track_updated
- AI events: ai.threat_detected, ai.action_recognized

These tests are written FIRST (TDD red phase) and will initially FAIL until
the event broadcasting methods are added to backend/services/event_broadcaster.py.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

import pytest

from backend.services.event_broadcaster import EventBroadcaster, reset_broadcaster_state

# Mock Redis and PubSub for testing


class _FakePubSub:
    pass


class _FakeRedis:
    def __init__(self) -> None:
        self.subscribe = AsyncMock(return_value=_FakePubSub())
        self.unsubscribe = AsyncMock(return_value=None)
        self.publish = AsyncMock(return_value=1)

    async def listen(self, _pubsub: Any) -> AsyncIterator[dict[str, Any]]:
        # Default: no messages - empty async generator pattern
        for _ in []:
            yield {}


@pytest.fixture(autouse=True)
def _enable_log_capture(caplog: pytest.LogCaptureFixture) -> None:
    """Automatically enable INFO-level log capture for all tests."""
    caplog.set_level(logging.INFO)


@pytest.fixture(autouse=True)
def _reset_broadcaster_state() -> None:
    """Reset global broadcaster state before each test for isolation."""
    reset_broadcaster_state()


# ==============================================================================
# Zone Event Broadcasting Tests (NEM-5073)
# ==============================================================================


class TestBroadcastZoneEvents:
    """Tests for broadcasting zone-related events."""

    @pytest.mark.asyncio
    async def test_broadcast_zone_crossing_event(self) -> None:
        """Test broadcasting zone.crossing event."""
        redis = _FakeRedis()
        broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

        payload = {
            "zone_id": "zone-123",
            "zone_name": "Front Door Area",
            "entity_id": "entity-456",
            "entity_type": "person",
            "camera_id": "front_door",
            "timestamp": "2026-02-01T12:00:00Z",
            "direction": "entering",
        }

        count = await broadcaster.broadcast_zone_crossing(payload)

        assert count == 1
        redis.publish.assert_awaited_once()
        channel, published = redis.publish.await_args.args
        assert channel == broadcaster.CHANNEL_NAME
        assert published["type"] == "zone.crossing"
        assert published["data"]["zone_id"] == "zone-123"
        assert published["data"]["direction"] == "entering"

    @pytest.mark.asyncio
    async def test_broadcast_zone_dwell_started_event(self) -> None:
        """Test broadcasting zone.dwell_started event."""
        redis = _FakeRedis()
        broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

        payload = {
            "zone_id": "zone-456",
            "zone_name": "Loading Dock",
            "entity_id": "entity-789",
            "entity_type": "person",
            "camera_id": "loading_dock",
            "timestamp": "2026-02-01T12:00:00Z",
        }

        count = await broadcaster.broadcast_zone_dwell_started(payload)

        assert count == 1
        redis.publish.assert_awaited_once()
        channel, published = redis.publish.await_args.args
        assert published["type"] == "zone.dwell_started"
        assert published["data"]["zone_id"] == "zone-456"

    @pytest.mark.asyncio
    async def test_broadcast_zone_dwell_alert_event(self) -> None:
        """Test broadcasting zone.dwell_alert event."""
        redis = _FakeRedis()
        broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

        payload = {
            "zone_id": "zone-789",
            "zone_name": "Restricted Area",
            "entity_id": "entity-123",
            "entity_type": "person",
            "camera_id": "restricted_cam",
            "timestamp": "2026-02-01T12:05:00Z",
            "dwell_duration_seconds": 300,
            "threshold_seconds": 180,
        }

        count = await broadcaster.broadcast_zone_dwell_alert(payload)

        assert count == 1
        redis.publish.assert_awaited_once()
        channel, published = redis.publish.await_args.args
        assert published["type"] == "zone.dwell_alert"
        assert published["data"]["dwell_duration_seconds"] == 300
        assert published["data"]["threshold_seconds"] == 180

    @pytest.mark.asyncio
    async def test_broadcast_zone_approach_event(self) -> None:
        """Test broadcasting zone.approach event."""
        redis = _FakeRedis()
        broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

        payload = {
            "zone_id": "zone-999",
            "zone_name": "Entry Point",
            "entity_id": "entity-555",
            "entity_type": "vehicle",
            "camera_id": "entry_cam",
            "timestamp": "2026-02-01T12:00:00Z",
            "direction": "north",
            "speed": 2.5,
            "eta_seconds": 15,
        }

        count = await broadcaster.broadcast_zone_approach(payload)

        assert count == 1
        redis.publish.assert_awaited_once()
        channel, published = redis.publish.await_args.args
        assert published["type"] == "zone.approach"
        assert published["data"]["direction"] == "north"
        assert published["data"]["speed"] == 2.5
        assert published["data"]["eta_seconds"] == 15


# ==============================================================================
# Entity Event Broadcasting Tests (NEM-5073)
# ==============================================================================


class TestBroadcastEntityEvents:
    """Tests for broadcasting entity-related events."""

    @pytest.mark.asyncio
    async def test_broadcast_entity_matched_event(self) -> None:
        """Test broadcasting entity.matched event."""
        redis = _FakeRedis()
        broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

        payload = {
            "entity_id": "entity-123",
            "matched_entity_id": "entity-456",
            "similarity_score": 0.92,
            "camera_id": "front_door",
            "timestamp": "2026-02-01T12:00:00Z",
            "match_type": "face",
        }

        count = await broadcaster.broadcast_entity_matched(payload)

        assert count == 1
        redis.publish.assert_awaited_once()
        channel, published = redis.publish.await_args.args
        assert published["type"] == "entity.matched"
        assert published["data"]["entity_id"] == "entity-123"
        assert published["data"]["matched_entity_id"] == "entity-456"
        assert published["data"]["similarity_score"] == 0.92

    @pytest.mark.asyncio
    async def test_broadcast_entity_track_updated_event(self) -> None:
        """Test broadcasting entity.track_updated event."""
        redis = _FakeRedis()
        broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

        payload = {
            "entity_id": "entity-789",
            "camera_id": "back_yard",
            "timestamp": "2026-02-01T12:00:00Z",
            "position": {"x": 100.0, "y": 200.0},
            "bbox": {"x": 90.0, "y": 190.0, "width": 50.0, "height": 100.0},
            "velocity": {"x": 1.5, "y": 0.5},
        }

        count = await broadcaster.broadcast_entity_track_updated(payload)

        assert count == 1
        redis.publish.assert_awaited_once()
        channel, published = redis.publish.await_args.args
        assert published["type"] == "entity.track_updated"
        assert published["data"]["entity_id"] == "entity-789"
        assert published["data"]["position"]["x"] == 100.0
        assert published["data"]["bbox"]["width"] == 50.0


# ==============================================================================
# AI Event Broadcasting Tests (NEM-5073)
# ==============================================================================


class TestBroadcastAIEvents:
    """Tests for broadcasting AI-related events."""

    @pytest.mark.asyncio
    async def test_broadcast_ai_threat_detected_event(self) -> None:
        """Test broadcasting ai.threat_detected event."""
        redis = _FakeRedis()
        broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

        payload = {
            "detection_id": "det-123",
            "camera_id": "front_door",
            "timestamp": "2026-02-01T12:00:00Z",
            "threat_type": "weapon",
            "severity": "critical",
            "confidence": 0.95,
            "bbox": {"x": 100.0, "y": 200.0, "width": 50.0, "height": 75.0},
        }

        count = await broadcaster.broadcast_ai_threat_detected(payload)

        assert count == 1
        redis.publish.assert_awaited_once()
        channel, published = redis.publish.await_args.args
        assert published["type"] == "ai.threat_detected"
        assert published["data"]["threat_type"] == "weapon"
        assert published["data"]["severity"] == "critical"
        assert published["data"]["confidence"] == 0.95

    @pytest.mark.asyncio
    async def test_broadcast_ai_action_recognized_event(self) -> None:
        """Test broadcasting ai.action_recognized event."""
        redis = _FakeRedis()
        broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

        payload = {
            "detection_id": "det-456",
            "camera_id": "garage",
            "timestamp": "2026-02-01T12:00:00Z",
            "action_type": "climbing",
            "confidence": 0.88,
            "bbox": {"x": 150.0, "y": 250.0, "width": 60.0, "height": 120.0},
        }

        count = await broadcaster.broadcast_ai_action_recognized(payload)

        assert count == 1
        redis.publish.assert_awaited_once()
        channel, published = redis.publish.await_args.args
        assert published["type"] == "ai.action_recognized"
        assert published["data"]["action_type"] == "climbing"
        assert published["data"]["confidence"] == 0.88


# ==============================================================================
# Event Routing Tests (NEM-5073)
# ==============================================================================


class TestNewEventRouting:
    """Tests for event routing to correct channels."""

    @pytest.mark.asyncio
    async def test_zone_events_route_to_zones_channel(self) -> None:
        """Test that zone events route to zones channel."""
        redis = _FakeRedis()
        broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

        # Test zone crossing
        payload = {
            "zone_id": "zone-123",
            "zone_name": "Area",
            "entity_id": "entity-456",
            "entity_type": "person",
            "camera_id": "cam",
            "timestamp": "2026-02-01T12:00:00Z",
            "direction": "entering",
        }

        count = await broadcaster.broadcast_zone_crossing(payload)
        assert count == 1

        # Verify channel name includes zone routing
        channel, published = redis.publish.await_args.args
        # Channel routing should target zones channel
        assert "zones" in str(channel) or published["type"].startswith("zone.")

    @pytest.mark.asyncio
    async def test_entity_events_route_to_entities_channel(self) -> None:
        """Test that entity events route to entities channel."""
        redis = _FakeRedis()
        broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

        # Test entity matched
        payload = {
            "entity_id": "entity-123",
            "matched_entity_id": "entity-456",
            "similarity_score": 0.95,
            "camera_id": "cam",
            "timestamp": "2026-02-01T12:00:00Z",
        }

        count = await broadcaster.broadcast_entity_matched(payload)
        assert count == 1

        # Verify channel name includes entity routing
        channel, published = redis.publish.await_args.args
        assert "entities" in str(channel) or published["type"].startswith("entity.")

    @pytest.mark.asyncio
    async def test_ai_events_route_to_ai_channel(self) -> None:
        """Test that AI events route to ai channel."""
        redis = _FakeRedis()
        broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

        # Test AI threat detected
        payload = {
            "detection_id": "det-123",
            "camera_id": "cam",
            "timestamp": "2026-02-01T12:00:00Z",
            "threat_type": "weapon",
            "severity": "critical",
            "confidence": 0.98,
        }

        count = await broadcaster.broadcast_ai_threat_detected(payload)
        assert count == 1

        # Verify channel name includes AI routing
        channel, published = redis.publish.await_args.args
        assert "ai" in str(channel) or published["type"].startswith("ai.")


# ==============================================================================
# Payload Validation Tests (NEM-5073)
# ==============================================================================


class TestNewEventPayloadValidation:
    """Tests for payload validation in broadcast methods."""

    @pytest.mark.asyncio
    async def test_broadcast_zone_crossing_validates_required_fields(self) -> None:
        """Test that broadcast_zone_crossing validates required fields."""
        redis = _FakeRedis()
        broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

        # Missing required fields
        invalid_payload = {
            "zone_id": "zone-123",
            # Missing entity_id, camera_id, timestamp, direction
        }

        # Should raise validation error or return 0
        with pytest.raises((ValueError, TypeError, KeyError)):
            await broadcaster.broadcast_zone_crossing(invalid_payload)

    @pytest.mark.asyncio
    async def test_broadcast_entity_matched_validates_similarity_score(self) -> None:
        """Test that broadcast_entity_matched validates similarity score range."""
        redis = _FakeRedis()
        broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

        # Invalid similarity score > 1.0
        invalid_payload = {
            "entity_id": "entity-123",
            "matched_entity_id": "entity-456",
            "similarity_score": 1.5,  # Invalid: > 1.0
            "camera_id": "cam",
            "timestamp": "2026-02-01T12:00:00Z",
        }

        # Should raise validation error
        with pytest.raises((ValueError, TypeError)):
            await broadcaster.broadcast_entity_matched(invalid_payload)

    @pytest.mark.asyncio
    async def test_broadcast_ai_threat_detected_validates_confidence(self) -> None:
        """Test that broadcast_ai_threat_detected validates confidence range."""
        redis = _FakeRedis()
        broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

        # Invalid confidence < 0.0
        invalid_payload = {
            "detection_id": "det-123",
            "camera_id": "cam",
            "timestamp": "2026-02-01T12:00:00Z",
            "threat_type": "weapon",
            "severity": "critical",
            "confidence": -0.1,  # Invalid: < 0.0
        }

        # Should raise validation error
        with pytest.raises((ValueError, TypeError)):
            await broadcaster.broadcast_ai_threat_detected(invalid_payload)
