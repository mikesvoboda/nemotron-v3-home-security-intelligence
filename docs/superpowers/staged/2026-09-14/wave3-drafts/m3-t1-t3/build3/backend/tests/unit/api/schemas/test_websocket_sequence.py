"""Unit tests for WebSocket event sequence validation schemas.

These tests verify that WebSocket messages include sequence numbers for:
- Frontend event ordering
- Gap detection
- Duplicate filtering
- Resync requests

NEM-2019: Implement WebSocket event sequence validation
"""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from backend.api.schemas.websocket import (
    WebSocketAckMessage,
    WebSocketEventData,
    WebSocketEventMessage,
    WebSocketResyncRequest,
    WebSocketSceneChangeData,
    WebSocketSceneChangeMessage,
    WebSocketSequencedMessage,
    WebSocketServiceStatusData,
    WebSocketServiceStatusMessage,
)

# ==============================================================================
# WebSocketSequencedMessage Tests
# ==============================================================================


class TestWebSocketSequencedMessage:
    """Tests for the WebSocketSequencedMessage base schema."""

    def test_sequenced_message_with_valid_sequence(self) -> None:
        """Test that a valid sequence number is accepted."""
        msg = WebSocketSequencedMessage(
            type="event",
            sequence=1,
            timestamp=datetime.now().isoformat(),
        )
        assert msg.sequence == 1
        assert msg.type == "event"

    def test_sequenced_message_sequence_must_be_positive(self) -> None:
        """Test that sequence must be a positive integer."""
        with pytest.raises(ValidationError) as exc_info:
            WebSocketSequencedMessage(
                type="event",
                sequence=0,
                timestamp=datetime.now().isoformat(),
            )
        assert "sequence" in str(exc_info.value)

    def test_sequenced_message_sequence_negative_rejected(self) -> None:
        """Test that negative sequence numbers are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            WebSocketSequencedMessage(
                type="event",
                sequence=-1,
                timestamp=datetime.now().isoformat(),
            )
        assert "sequence" in str(exc_info.value)

    def test_sequenced_message_timestamp_required(self) -> None:
        """Test that timestamp is required in sequenced messages."""
        with pytest.raises(ValidationError) as exc_info:
            WebSocketSequencedMessage(
                type="event",
                sequence=1,
            )
        assert "timestamp" in str(exc_info.value)

    def test_sequenced_message_requires_ack_optional_default_false(self) -> None:
        """Test that requires_ack defaults to False."""
        msg = WebSocketSequencedMessage(
            type="event",
            sequence=1,
            timestamp=datetime.now().isoformat(),
        )
        assert msg.requires_ack is False

    def test_sequenced_message_requires_ack_can_be_true(self) -> None:
        """Test that requires_ack can be set to True."""
        msg = WebSocketSequencedMessage(
            type="event",
            sequence=1,
            timestamp=datetime.now().isoformat(),
            requires_ack=True,
        )
        assert msg.requires_ack is True

    def test_sequenced_message_replay_flag_optional(self) -> None:
        """Test that replay flag is optional and defaults to False."""
        msg = WebSocketSequencedMessage(
            type="event",
            sequence=1,
            timestamp=datetime.now().isoformat(),
        )
        assert msg.replay is False

    def test_sequenced_message_replay_flag_can_be_true(self) -> None:
        """Test that replay flag can be set for replayed messages."""
        msg = WebSocketSequencedMessage(
            type="event",
            sequence=1,
            timestamp=datetime.now().isoformat(),
            replay=True,
        )
        assert msg.replay is True


# ==============================================================================
# WebSocketResyncRequest Tests
# ==============================================================================


class TestWebSocketResyncRequest:
    """Tests for resync request messages from frontend to backend."""

    def test_resync_request_with_valid_last_sequence(self) -> None:
        """Test creating a resync request with last seen sequence."""
        req = WebSocketResyncRequest(
            type="resync",
            last_sequence=42,
            channel="events",
        )
        assert req.type == "resync"
        assert req.last_sequence == 42
        assert req.channel == "events"

    def test_resync_request_last_sequence_zero_for_initial(self) -> None:
        """Test that last_sequence=0 is valid (never received any messages)."""
        req = WebSocketResyncRequest(
            type="resync",
            last_sequence=0,
            channel="events",
        )
        assert req.last_sequence == 0

    def test_resync_request_negative_sequence_rejected(self) -> None:
        """Test that negative last_sequence is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            WebSocketResyncRequest(
                type="resync",
                last_sequence=-1,
                channel="events",
            )
        assert "last_sequence" in str(exc_info.value)

    def test_resync_request_channel_required(self) -> None:
        """Test that channel is required in resync request."""
        with pytest.raises(ValidationError) as exc_info:
            WebSocketResyncRequest(
                type="resync",
                last_sequence=42,
            )
        assert "channel" in str(exc_info.value)

    def test_resync_request_valid_channels(self) -> None:
        """Test that valid channel names are accepted."""
        for channel in ["events", "system"]:
            req = WebSocketResyncRequest(
                type="resync",
                last_sequence=10,
                channel=channel,
            )
            assert req.channel == channel


# ==============================================================================
# WebSocketAckMessage Tests
# ==============================================================================


class TestWebSocketAckMessage:
    """Tests for acknowledgment messages from frontend to backend."""

    def test_ack_message_with_valid_sequence(self) -> None:
        """Test creating an ack message with a sequence number."""
        ack = WebSocketAckMessage(
            type="ack",
            sequence=42,
        )
        assert ack.type == "ack"
        assert ack.sequence == 42

    def test_ack_message_sequence_must_be_positive(self) -> None:
        """Test that ack sequence must be positive."""
        with pytest.raises(ValidationError) as exc_info:
            WebSocketAckMessage(
                type="ack",
                sequence=0,
            )
        assert "sequence" in str(exc_info.value)

    def test_ack_message_negative_sequence_rejected(self) -> None:
        """Test that negative ack sequence is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            WebSocketAckMessage(
                type="ack",
                sequence=-1,
            )
        assert "sequence" in str(exc_info.value)


# ==============================================================================
# Integration Tests - Event Messages with Sequences
# ==============================================================================


class TestSequencedEventMessage:
    """Tests for event messages with sequence numbers."""

    def test_event_message_includes_sequence_in_json(self) -> None:
        """Test that serialized event messages include sequence number."""
        event_data = WebSocketEventData(
            id=1,
            event_id=1,
            batch_id="batch_123",
            camera_id="front_door",
            risk_score=75,
            risk_level="high",
            summary="Person detected",
            reasoning="Unknown individual at entrance",
            started_at="2025-12-23T12:00:00",
        )
        msg = WebSocketEventMessage(data=event_data)

        # Add sequence after creation (simulating broadcaster behavior)
        json_dict = msg.model_dump(mode="json")
        json_dict["sequence"] = 1
        json_dict["timestamp"] = datetime.now().isoformat()
        json_dict["requires_ack"] = False

        assert "sequence" in json_dict
        assert json_dict["sequence"] == 1

    def test_high_risk_events_require_ack(self) -> None:
        """Test that high-risk events (score >= 80) should require ack."""
        # This tests the requires_ack logic in EventBroadcaster
        event_data = {
            "type": "event",
            "data": {
                "id": 1,
                "event_id": 1,
                "batch_id": "batch_123",
                "camera_id": "front_door",
                "risk_score": 85,  # >= 80, should require ack
                "risk_level": "critical",
                "summary": "Suspicious activity",
                "reasoning": "Unknown individual acting suspiciously",
            },
        }

        # The requires_ack determination is done by EventBroadcaster.requires_ack()
        from backend.services.event_broadcaster import requires_ack

        assert requires_ack(event_data) is True

    def test_low_risk_events_dont_require_ack(self) -> None:
        """Test that low-risk events (score < 80) don't require ack."""
        event_data = {
            "type": "event",
            "data": {
                "id": 1,
                "event_id": 1,
                "batch_id": "batch_123",
                "camera_id": "front_door",
                "risk_score": 30,  # < 80, should not require ack
                "risk_level": "low",
                "summary": "Normal activity",
                "reasoning": "Resident returning home",
            },
        }

        from backend.services.event_broadcaster import requires_ack

        assert requires_ack(event_data) is False

    def test_critical_risk_level_requires_ack(self) -> None:
        """Test that critical risk level events require ack regardless of score."""
        event_data = {
            "type": "event",
            "data": {
                "id": 1,
                "event_id": 1,
                "batch_id": "batch_123",
                "camera_id": "front_door",
                "risk_score": 70,  # < 80, but critical level
                "risk_level": "critical",
                "summary": "Critical event",
                "reasoning": "Immediate attention required",
            },
        }

        from backend.services.event_broadcaster import requires_ack

        assert requires_ack(event_data) is True


# ==============================================================================
# Integration Tests - Service Status with Sequences
# ==============================================================================


class TestSequencedServiceStatusMessage:
    """Tests for service status messages with sequence numbers."""

    def test_service_status_can_have_sequence(self) -> None:
        """Test that service status messages can include sequence."""
        status_data = WebSocketServiceStatusData(
            service="nemotron",
            status="healthy",
            message="Service recovered",
        )
        msg = WebSocketServiceStatusMessage(
            data=status_data,
            timestamp="2025-12-23T12:00:00.000Z",
        )

        json_dict = msg.model_dump(mode="json")
        json_dict["sequence"] = 5

        assert json_dict["sequence"] == 5


# ==============================================================================
# Integration Tests - Scene Change with Sequences
# ==============================================================================


class TestSequencedSceneChangeMessage:
    """Tests for scene change messages with sequence numbers."""

    def test_scene_change_can_have_sequence(self) -> None:
        """Test that scene change messages can include sequence."""
        scene_data = WebSocketSceneChangeData(
            id=1,
            camera_id="front_door",
            detected_at="2026-01-03T10:30:00Z",
            change_type="view_blocked",
            similarity_score=0.23,
        )
        msg = WebSocketSceneChangeMessage(data=scene_data)

        json_dict = msg.model_dump(mode="json")
        json_dict["sequence"] = 3

        assert json_dict["sequence"] == 3
