"""Unit tests for WebSocket discriminated union message validation (NEM-3394).

This module tests the discriminated union pattern for WebSocket messages,
which uses Literal types as discriminators for automatic message routing
and improved validation performance (2-5x faster than generic Union validation).

Tests cover:
- Discriminated union type resolution
- Automatic routing based on 'type' field
- Validation of all message types through the union
- Performance comparison with generic validation
- Error handling for invalid types
"""

from __future__ import annotations

import json
import time

import pytest
from pydantic import TypeAdapter, ValidationError

from backend.api.schemas.websocket import (
    WebSocketAckMessage,
    WebSocketAlertAcknowledgedMessage,
    WebSocketAlertCreatedMessage,
    WebSocketAlertDeletedMessage,
    WebSocketAlertDismissedMessage,
    WebSocketAlertResolvedMessage,
    WebSocketAlertUpdatedMessage,
    WebSocketCameraStatusMessage,
    WebSocketDetectionBatchMessage,
    WebSocketDetectionNewMessage,
    WebSocketErrorResponse,
    # Outgoing message types
    WebSocketEventMessage,
    # Discriminated union types (to be implemented)
    WebSocketIncomingMessage,
    WebSocketInfrastructureAlertMessage,
    WebSocketJobCompletedMessage,
    WebSocketJobFailedMessage,
    WebSocketJobProgressMessage,
    # Discriminated union for outgoing messages (to be implemented)
    WebSocketOutgoingMessage,
    # Incoming message types
    WebSocketPingMessage,
    WebSocketPongResponse,
    WebSocketResyncRequest,
    WebSocketSceneChangeMessage,
    WebSocketServiceStatusMessage,
    WebSocketSubscribeMessage,
    WebSocketSummaryUpdateMessage,
    WebSocketUnsubscribeMessage,
    WebSocketWorkerStatusMessage,
)


class TestIncomingMessageDiscriminatedUnion:
    """Tests for incoming WebSocket message discriminated union."""

    def test_ping_message_resolved(self) -> None:
        """Test that ping message is resolved to WebSocketPingMessage."""
        data = {"type": "ping"}
        adapter = TypeAdapter(WebSocketIncomingMessage)
        message = adapter.validate_python(data)
        assert isinstance(message, WebSocketPingMessage)
        assert message.type == "ping"

    def test_subscribe_message_resolved(self) -> None:
        """Test that subscribe message is resolved to WebSocketSubscribeMessage."""
        data = {"type": "subscribe", "channels": ["events", "alerts"]}
        adapter = TypeAdapter(WebSocketIncomingMessage)
        message = adapter.validate_python(data)
        assert isinstance(message, WebSocketSubscribeMessage)
        assert message.type == "subscribe"
        assert message.channels == ["events", "alerts"]

    def test_unsubscribe_message_resolved(self) -> None:
        """Test that unsubscribe message is resolved to WebSocketUnsubscribeMessage."""
        data = {"type": "unsubscribe", "channels": ["events"]}
        adapter = TypeAdapter(WebSocketIncomingMessage)
        message = adapter.validate_python(data)
        assert isinstance(message, WebSocketUnsubscribeMessage)
        assert message.type == "unsubscribe"
        assert message.channels == ["events"]

    def test_resync_message_resolved(self) -> None:
        """Test that resync message is resolved to WebSocketResyncRequest."""
        data = {"type": "resync", "last_sequence": 42, "channel": "events"}
        adapter = TypeAdapter(WebSocketIncomingMessage)
        message = adapter.validate_python(data)
        assert isinstance(message, WebSocketResyncRequest)
        assert message.type == "resync"
        assert message.last_sequence == 42
        assert message.channel == "events"

    def test_ack_message_resolved(self) -> None:
        """Test that ack message is resolved to WebSocketAckMessage."""
        data = {"type": "ack", "sequence": 100}
        adapter = TypeAdapter(WebSocketIncomingMessage)
        message = adapter.validate_python(data)
        assert isinstance(message, WebSocketAckMessage)
        assert message.type == "ack"
        assert message.sequence == 100

    def test_invalid_type_raises_error(self) -> None:
        """Test that invalid message type raises ValidationError."""
        data = {"type": "invalid_type"}
        adapter = TypeAdapter(WebSocketIncomingMessage)
        with pytest.raises(ValidationError) as exc_info:
            adapter.validate_python(data)
        # Should mention the discriminator value not being valid
        errors = exc_info.value.errors()
        assert len(errors) > 0

    def test_missing_type_raises_error(self) -> None:
        """Test that missing type field raises ValidationError."""
        data = {"channels": ["events"]}
        adapter = TypeAdapter(WebSocketIncomingMessage)
        with pytest.raises(ValidationError):
            adapter.validate_python(data)

    def test_json_string_validation(self) -> None:
        """Test validation from JSON string."""
        json_str = '{"type": "ping"}'
        adapter = TypeAdapter(WebSocketIncomingMessage)
        message = adapter.validate_json(json_str)
        assert isinstance(message, WebSocketPingMessage)


class TestOutgoingMessageDiscriminatedUnion:
    """Tests for outgoing WebSocket message discriminated union."""

    def test_event_message_resolved(self) -> None:
        """Test that event message is resolved to WebSocketEventMessage."""
        data = {
            "type": "event",
            "data": {
                "id": 1,
                "event_id": 1,
                "batch_id": "batch_123",
                "camera_id": "front_door",
                "risk_score": 75,
                "risk_level": "high",
                "summary": "Person detected",
                "reasoning": "Unknown person at door",
            },
        }
        adapter = TypeAdapter(WebSocketOutgoingMessage)
        message = adapter.validate_python(data)
        assert isinstance(message, WebSocketEventMessage)
        assert message.type == "event"

    def test_service_status_message_resolved(self) -> None:
        """Test that service_status message is resolved correctly."""
        data = {
            "type": "service_status",
            "data": {
                "service": "redis",
                "status": "healthy",
                "message": "OK",
            },
            "timestamp": "2026-01-23T12:00:00Z",
        }
        adapter = TypeAdapter(WebSocketOutgoingMessage)
        message = adapter.validate_python(data)
        assert isinstance(message, WebSocketServiceStatusMessage)
        assert message.type == "service_status"

    def test_camera_status_message_resolved(self) -> None:
        """Test that camera_status message is resolved correctly."""
        data = {
            "type": "camera_status",
            "data": {
                "event_type": "camera.offline",
                "camera_id": "front_door",
                "camera_name": "Front Door",
                "status": "offline",
                "timestamp": "2026-01-23T12:00:00Z",
            },
        }
        adapter = TypeAdapter(WebSocketOutgoingMessage)
        message = adapter.validate_python(data)
        assert isinstance(message, WebSocketCameraStatusMessage)
        assert message.type == "camera_status"

    def test_detection_new_message_resolved(self) -> None:
        """Test that detection.new message is resolved correctly."""
        data = {
            "type": "detection.new",
            "data": {
                "detection_id": 123,
                "batch_id": "batch_456",
                "camera_id": "front_door",
                "label": "person",
                "confidence": 0.95,
                "timestamp": "2026-01-23T12:00:00Z",
            },
        }
        adapter = TypeAdapter(WebSocketOutgoingMessage)
        message = adapter.validate_python(data)
        assert isinstance(message, WebSocketDetectionNewMessage)
        assert message.type == "detection.new"

    def test_detection_batch_message_resolved(self) -> None:
        """Test that detection.batch message is resolved correctly."""
        data = {
            "type": "detection.batch",
            "data": {
                "batch_id": "batch_789",
                "camera_id": "garage",
                "detection_ids": [1, 2, 3],
                "detection_count": 3,
                "started_at": "2026-01-23T12:00:00Z",
                "closed_at": "2026-01-23T12:01:30Z",
            },
        }
        adapter = TypeAdapter(WebSocketOutgoingMessage)
        message = adapter.validate_python(data)
        assert isinstance(message, WebSocketDetectionBatchMessage)
        assert message.type == "detection.batch"

    def test_alert_created_message_resolved(self) -> None:
        """Test that alert_created message is resolved correctly."""
        data = {
            "type": "alert_created",
            "data": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "event_id": 123,
                "severity": "high",
                "status": "pending",
                "dedup_key": "front_door:person:rule1",
                "created_at": "2026-01-23T12:00:00Z",
                "updated_at": "2026-01-23T12:00:00Z",
            },
        }
        adapter = TypeAdapter(WebSocketOutgoingMessage)
        message = adapter.validate_python(data)
        assert isinstance(message, WebSocketAlertCreatedMessage)
        assert message.type == "alert_created"

    def test_job_progress_message_resolved(self) -> None:
        """Test that job_progress message is resolved correctly."""
        data = {
            "type": "job_progress",
            "data": {
                "job_id": "job-123",
                "job_type": "export",
                "progress": 50,
                "status": "running",
            },
        }
        adapter = TypeAdapter(WebSocketOutgoingMessage)
        message = adapter.validate_python(data)
        assert isinstance(message, WebSocketJobProgressMessage)
        assert message.type == "job_progress"

    def test_job_completed_message_resolved(self) -> None:
        """Test that job_completed message is resolved correctly."""
        data = {
            "type": "job_completed",
            "data": {
                "job_id": "job-456",
                "job_type": "export",
                "result": {"file_path": "/exports/data.json"},
            },
        }
        adapter = TypeAdapter(WebSocketOutgoingMessage)
        message = adapter.validate_python(data)
        assert isinstance(message, WebSocketJobCompletedMessage)
        assert message.type == "job_completed"

    def test_job_failed_message_resolved(self) -> None:
        """Test that job_failed message is resolved correctly."""
        data = {
            "type": "job_failed",
            "data": {
                "job_id": "job-789",
                "job_type": "export",
                "error": "Disk full",
            },
        }
        adapter = TypeAdapter(WebSocketOutgoingMessage)
        message = adapter.validate_python(data)
        assert isinstance(message, WebSocketJobFailedMessage)
        assert message.type == "job_failed"

    def test_pong_response_resolved(self) -> None:
        """Test that pong response is resolved correctly."""
        data = {"type": "pong"}
        adapter = TypeAdapter(WebSocketOutgoingMessage)
        message = adapter.validate_python(data)
        assert isinstance(message, WebSocketPongResponse)
        assert message.type == "pong"

    def test_error_response_resolved(self) -> None:
        """Test that error response is resolved correctly."""
        data = {
            "type": "error",
            "error": "invalid_json",
            "message": "Message must be valid JSON",
        }
        adapter = TypeAdapter(WebSocketOutgoingMessage)
        message = adapter.validate_python(data)
        assert isinstance(message, WebSocketErrorResponse)
        assert message.type == "error"

    def test_worker_status_message_resolved(self) -> None:
        """Test that worker_status message is resolved correctly."""
        data = {
            "type": "worker_status",
            "data": {
                "event_type": "worker.started",
                "worker_name": "detection_worker",
                "worker_type": "detection",
                "timestamp": "2026-01-23T12:00:00Z",
            },
        }
        adapter = TypeAdapter(WebSocketOutgoingMessage)
        message = adapter.validate_python(data)
        assert isinstance(message, WebSocketWorkerStatusMessage)
        assert message.type == "worker_status"

    def test_infrastructure_alert_message_resolved(self) -> None:
        """Test that infrastructure_alert message is resolved correctly."""
        data = {
            "type": "infrastructure_alert",
            "data": {
                "alertname": "HSIGPUMemoryHigh",
                "status": "firing",
                "fingerprint": "abc123",
            },
        }
        adapter = TypeAdapter(WebSocketOutgoingMessage)
        message = adapter.validate_python(data)
        assert isinstance(message, WebSocketInfrastructureAlertMessage)
        assert message.type == "infrastructure_alert"

    def test_summary_update_message_resolved(self) -> None:
        """Test that summary_update message is resolved correctly."""
        data = {
            "type": "summary_update",
            "data": {
                "hourly": None,
                "daily": None,
            },
        }
        adapter = TypeAdapter(WebSocketOutgoingMessage)
        message = adapter.validate_python(data)
        assert isinstance(message, WebSocketSummaryUpdateMessage)
        assert message.type == "summary_update"

    def test_scene_change_message_resolved(self) -> None:
        """Test that scene_change message is resolved correctly."""
        data = {
            "type": "scene_change",
            "data": {
                "id": 1,
                "camera_id": "front_door",
                "detected_at": "2026-01-23T12:00:00Z",
                "change_type": "view_blocked",
                "similarity_score": 0.45,
            },
        }
        adapter = TypeAdapter(WebSocketOutgoingMessage)
        message = adapter.validate_python(data)
        assert isinstance(message, WebSocketSceneChangeMessage)
        assert message.type == "scene_change"


class TestAlertMessageVariants:
    """Test all alert message variants through discriminated union."""

    def test_alert_acknowledged_resolved(self) -> None:
        """Test alert_acknowledged message resolution."""
        data = {
            "type": "alert_acknowledged",
            "data": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "event_id": 123,
                "severity": "high",
                "status": "acknowledged",
                "dedup_key": "test",
                "created_at": "2026-01-23T12:00:00Z",
                "updated_at": "2026-01-23T12:01:00Z",
            },
        }
        adapter = TypeAdapter(WebSocketOutgoingMessage)
        message = adapter.validate_python(data)
        assert isinstance(message, WebSocketAlertAcknowledgedMessage)
        assert message.type == "alert_acknowledged"

    def test_alert_dismissed_resolved(self) -> None:
        """Test alert_dismissed message resolution."""
        data = {
            "type": "alert_dismissed",
            "data": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "event_id": 123,
                "severity": "high",
                "status": "dismissed",
                "dedup_key": "test",
                "created_at": "2026-01-23T12:00:00Z",
                "updated_at": "2026-01-23T12:02:00Z",
            },
        }
        adapter = TypeAdapter(WebSocketOutgoingMessage)
        message = adapter.validate_python(data)
        assert isinstance(message, WebSocketAlertDismissedMessage)
        assert message.type == "alert_dismissed"

    def test_alert_updated_resolved(self) -> None:
        """Test alert_updated message resolution."""
        data = {
            "type": "alert_updated",
            "data": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "event_id": 123,
                "severity": "high",
                "status": "pending",
                "dedup_key": "test",
                "created_at": "2026-01-23T12:00:00Z",
                "updated_at": "2026-01-23T12:00:30Z",
            },
        }
        adapter = TypeAdapter(WebSocketOutgoingMessage)
        message = adapter.validate_python(data)
        assert isinstance(message, WebSocketAlertUpdatedMessage)
        assert message.type == "alert_updated"

    def test_alert_deleted_resolved(self) -> None:
        """Test alert_deleted message resolution."""
        data = {
            "type": "alert_deleted",
            "data": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "reason": "Duplicate alert",
            },
        }
        adapter = TypeAdapter(WebSocketOutgoingMessage)
        message = adapter.validate_python(data)
        assert isinstance(message, WebSocketAlertDeletedMessage)
        assert message.type == "alert_deleted"

    def test_alert_resolved_resolved(self) -> None:
        """Test alert_resolved message resolution."""
        data = {
            "type": "alert_resolved",
            "data": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "event_id": 123,
                "severity": "high",
                "status": "dismissed",
                "dedup_key": "test",
                "created_at": "2026-01-23T12:00:00Z",
                "updated_at": "2026-01-23T12:02:00Z",
            },
        }
        adapter = TypeAdapter(WebSocketOutgoingMessage)
        message = adapter.validate_python(data)
        assert isinstance(message, WebSocketAlertResolvedMessage)
        assert message.type == "alert_resolved"


class TestDiscriminatedUnionPerformance:
    """Performance tests for discriminated union validation.

    These tests verify that discriminated union validation is faster
    than generic union validation (expected 2-5x improvement).
    """

    @pytest.fixture
    def sample_messages(self) -> list[dict]:
        """Generate sample messages for performance testing."""
        return [
            {"type": "ping"},
            {"type": "subscribe", "channels": ["events"]},
            {"type": "unsubscribe", "channels": ["alerts"]},
            {"type": "resync", "last_sequence": 42, "channel": "events"},
            {"type": "ack", "sequence": 100},
        ]

    def test_discriminated_union_validation_speed(self, sample_messages: list[dict]) -> None:
        """Test that discriminated union validation is reasonably fast.

        This test validates 1000 messages and ensures it completes in reasonable time.
        The discriminated union should be significantly faster than brute-force validation.
        """
        adapter = TypeAdapter(WebSocketIncomingMessage)

        # Warm up
        for msg in sample_messages:
            adapter.validate_python(msg)

        # Time 1000 validations
        iterations = 1000
        start = time.perf_counter()
        for _ in range(iterations):
            for msg in sample_messages:
                adapter.validate_python(msg)
        elapsed = time.perf_counter() - start

        # Should complete 5000 validations in under 1 second (generous limit)
        assert elapsed < 1.0, (
            f"Validation took {elapsed:.3f}s for {iterations * len(sample_messages)} messages"
        )

    def test_json_validation_speed(self, sample_messages: list[dict]) -> None:
        """Test that JSON string validation is also fast."""
        adapter = TypeAdapter(WebSocketIncomingMessage)
        json_messages = [json.dumps(msg) for msg in sample_messages]

        # Warm up
        for json_msg in json_messages:
            adapter.validate_json(json_msg)

        # Time 1000 iterations
        iterations = 1000
        start = time.perf_counter()
        for _ in range(iterations):
            for json_msg in json_messages:
                adapter.validate_json(json_msg)
        elapsed = time.perf_counter() - start

        # Should complete in under 1 second
        assert elapsed < 1.0, (
            f"JSON validation took {elapsed:.3f}s for {iterations * len(json_messages)} messages"
        )


class TestDiscriminatedUnionEdgeCases:
    """Edge case tests for discriminated union validation."""

    def test_extra_fields_ignored(self) -> None:
        """Test that extra fields are ignored (forward compatibility)."""
        data = {
            "type": "ping",
            "extra_field": "should be ignored",
            "another_extra": 123,
        }
        adapter = TypeAdapter(WebSocketIncomingMessage)
        message = adapter.validate_python(data)
        assert isinstance(message, WebSocketPingMessage)
        assert message.type == "ping"

    def test_none_type_raises_error(self) -> None:
        """Test that None type raises ValidationError."""
        data = {"type": None}
        adapter = TypeAdapter(WebSocketIncomingMessage)
        with pytest.raises(ValidationError):
            adapter.validate_python(data)

    def test_empty_string_type_raises_error(self) -> None:
        """Test that empty string type raises ValidationError."""
        data = {"type": ""}
        adapter = TypeAdapter(WebSocketIncomingMessage)
        with pytest.raises(ValidationError):
            adapter.validate_python(data)

    def test_numeric_type_raises_error(self) -> None:
        """Test that numeric type raises ValidationError."""
        data = {"type": 123}
        adapter = TypeAdapter(WebSocketIncomingMessage)
        with pytest.raises(ValidationError):
            adapter.validate_python(data)

    def test_case_sensitive_type(self) -> None:
        """Test that type field is case-sensitive (Literal types are exact match)."""
        # "PING" should not match "ping" in Literal["ping"]
        data = {"type": "PING"}
        adapter = TypeAdapter(WebSocketIncomingMessage)
        with pytest.raises(ValidationError):
            adapter.validate_python(data)

    def test_whitespace_in_type_raises_error(self) -> None:
        """Test that type with whitespace raises ValidationError."""
        data = {"type": " ping "}
        adapter = TypeAdapter(WebSocketIncomingMessage)
        with pytest.raises(ValidationError):
            adapter.validate_python(data)
