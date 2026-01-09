"""Unit tests for WebSocket alert message schemas.

Tests cover:
- WebSocketAlertEventType enum values
- WebSocketAlertSeverity enum validation
- WebSocketAlertStatus enum validation
- WebSocketAlertData model validation
- WebSocketAlertCreatedMessage schema
- WebSocketAlertAcknowledgedMessage schema
- WebSocketAlertDismissedMessage schema
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.api.schemas.websocket import (
    WebSocketAlertAcknowledgedMessage,
    WebSocketAlertCreatedMessage,
    WebSocketAlertData,
    WebSocketAlertDismissedMessage,
    WebSocketAlertEventType,
    WebSocketAlertSeverity,
    WebSocketAlertStatus,
)


class TestWebSocketAlertEventType:
    """Tests for WebSocketAlertEventType enum."""

    def test_alert_created_value(self) -> None:
        """Test ALERT_CREATED enum value."""
        assert WebSocketAlertEventType.ALERT_CREATED == "alert_created"

    def test_alert_acknowledged_value(self) -> None:
        """Test ALERT_ACKNOWLEDGED enum value."""
        assert WebSocketAlertEventType.ALERT_ACKNOWLEDGED == "alert_acknowledged"

    def test_alert_dismissed_value(self) -> None:
        """Test ALERT_DISMISSED enum value."""
        assert WebSocketAlertEventType.ALERT_DISMISSED == "alert_dismissed"

    def test_all_event_types_exist(self) -> None:
        """Test that all expected event types exist."""
        expected_types = {"alert_created", "alert_acknowledged", "alert_dismissed"}
        actual_types = {e.value for e in WebSocketAlertEventType}
        assert actual_types == expected_types


class TestWebSocketAlertSeverity:
    """Tests for WebSocketAlertSeverity enum."""

    def test_low_severity_value(self) -> None:
        """Test LOW severity enum value."""
        assert WebSocketAlertSeverity.LOW == "low"

    def test_medium_severity_value(self) -> None:
        """Test MEDIUM severity enum value."""
        assert WebSocketAlertSeverity.MEDIUM == "medium"

    def test_high_severity_value(self) -> None:
        """Test HIGH severity enum value."""
        assert WebSocketAlertSeverity.HIGH == "high"

    def test_critical_severity_value(self) -> None:
        """Test CRITICAL severity enum value."""
        assert WebSocketAlertSeverity.CRITICAL == "critical"

    def test_all_severity_levels_exist(self) -> None:
        """Test that all expected severity levels exist."""
        expected_levels = {"low", "medium", "high", "critical"}
        actual_levels = {s.value for s in WebSocketAlertSeverity}
        assert actual_levels == expected_levels


class TestWebSocketAlertStatus:
    """Tests for WebSocketAlertStatus enum."""

    def test_pending_status_value(self) -> None:
        """Test PENDING status enum value."""
        assert WebSocketAlertStatus.PENDING == "pending"

    def test_delivered_status_value(self) -> None:
        """Test DELIVERED status enum value."""
        assert WebSocketAlertStatus.DELIVERED == "delivered"

    def test_acknowledged_status_value(self) -> None:
        """Test ACKNOWLEDGED status enum value."""
        assert WebSocketAlertStatus.ACKNOWLEDGED == "acknowledged"

    def test_dismissed_status_value(self) -> None:
        """Test DISMISSED status enum value."""
        assert WebSocketAlertStatus.DISMISSED == "dismissed"

    def test_all_status_values_exist(self) -> None:
        """Test that all expected status values exist."""
        expected_statuses = {"pending", "delivered", "acknowledged", "dismissed"}
        actual_statuses = {s.value for s in WebSocketAlertStatus}
        assert actual_statuses == expected_statuses


class TestWebSocketAlertData:
    """Tests for WebSocketAlertData schema validation."""

    @pytest.fixture
    def valid_alert_data(self) -> dict:
        """Create valid alert data for testing."""
        return {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "event_id": 123,
            "rule_id": "550e8400-e29b-41d4-a716-446655440001",
            "severity": "high",
            "status": "pending",
            "dedup_key": "front_door:person:rule1",
            "created_at": "2026-01-09T12:00:00Z",
            "updated_at": "2026-01-09T12:00:00Z",
        }

    def test_valid_alert_data(self, valid_alert_data: dict) -> None:
        """Test that valid alert data passes validation."""
        data = WebSocketAlertData.model_validate(valid_alert_data)
        assert data.id == valid_alert_data["id"]
        assert data.event_id == valid_alert_data["event_id"]
        assert data.rule_id == valid_alert_data["rule_id"]
        assert data.severity == WebSocketAlertSeverity.HIGH
        assert data.status == WebSocketAlertStatus.PENDING
        assert data.dedup_key == valid_alert_data["dedup_key"]

    def test_alert_data_without_rule_id(self, valid_alert_data: dict) -> None:
        """Test that alert data without rule_id passes validation."""
        valid_alert_data["rule_id"] = None
        data = WebSocketAlertData.model_validate(valid_alert_data)
        assert data.rule_id is None

    def test_missing_id_fails(self, valid_alert_data: dict) -> None:
        """Test that missing id field fails validation."""
        del valid_alert_data["id"]
        with pytest.raises(ValidationError) as exc_info:
            WebSocketAlertData.model_validate(valid_alert_data)
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("id",) for e in errors)

    def test_missing_event_id_fails(self, valid_alert_data: dict) -> None:
        """Test that missing event_id field fails validation."""
        del valid_alert_data["event_id"]
        with pytest.raises(ValidationError) as exc_info:
            WebSocketAlertData.model_validate(valid_alert_data)
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("event_id",) for e in errors)

    def test_missing_severity_fails(self, valid_alert_data: dict) -> None:
        """Test that missing severity field fails validation."""
        del valid_alert_data["severity"]
        with pytest.raises(ValidationError) as exc_info:
            WebSocketAlertData.model_validate(valid_alert_data)
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("severity",) for e in errors)

    def test_missing_status_fails(self, valid_alert_data: dict) -> None:
        """Test that missing status field fails validation."""
        del valid_alert_data["status"]
        with pytest.raises(ValidationError) as exc_info:
            WebSocketAlertData.model_validate(valid_alert_data)
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("status",) for e in errors)

    def test_missing_dedup_key_fails(self, valid_alert_data: dict) -> None:
        """Test that missing dedup_key field fails validation."""
        del valid_alert_data["dedup_key"]
        with pytest.raises(ValidationError) as exc_info:
            WebSocketAlertData.model_validate(valid_alert_data)
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("dedup_key",) for e in errors)

    def test_invalid_severity_fails(self, valid_alert_data: dict) -> None:
        """Test that invalid severity value fails validation."""
        valid_alert_data["severity"] = "invalid_severity"
        with pytest.raises(ValidationError) as exc_info:
            WebSocketAlertData.model_validate(valid_alert_data)
        errors = exc_info.value.errors()
        assert any("severity" in str(e["loc"]) for e in errors)

    def test_invalid_status_fails(self, valid_alert_data: dict) -> None:
        """Test that invalid status value fails validation."""
        valid_alert_data["status"] = "invalid_status"
        with pytest.raises(ValidationError) as exc_info:
            WebSocketAlertData.model_validate(valid_alert_data)
        errors = exc_info.value.errors()
        assert any("status" in str(e["loc"]) for e in errors)

    def test_severity_case_insensitive(self, valid_alert_data: dict) -> None:
        """Test that severity validation is case-insensitive."""
        valid_alert_data["severity"] = "HIGH"
        data = WebSocketAlertData.model_validate(valid_alert_data)
        assert data.severity == WebSocketAlertSeverity.HIGH

    def test_status_case_insensitive(self, valid_alert_data: dict) -> None:
        """Test that status validation is case-insensitive."""
        valid_alert_data["status"] = "PENDING"
        data = WebSocketAlertData.model_validate(valid_alert_data)
        assert data.status == WebSocketAlertStatus.PENDING

    def test_all_severity_levels_accepted(self, valid_alert_data: dict) -> None:
        """Test that all severity levels are accepted."""
        for severity in ["low", "medium", "high", "critical"]:
            valid_alert_data["severity"] = severity
            data = WebSocketAlertData.model_validate(valid_alert_data)
            assert data.severity.value == severity

    def test_all_status_values_accepted(self, valid_alert_data: dict) -> None:
        """Test that all status values are accepted."""
        for status in ["pending", "delivered", "acknowledged", "dismissed"]:
            valid_alert_data["status"] = status
            data = WebSocketAlertData.model_validate(valid_alert_data)
            assert data.status.value == status


class TestWebSocketAlertCreatedMessage:
    """Tests for WebSocketAlertCreatedMessage schema."""

    @pytest.fixture
    def valid_alert_data(self) -> dict:
        """Create valid alert data for testing."""
        return {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "event_id": 123,
            "rule_id": None,
            "severity": "high",
            "status": "pending",
            "dedup_key": "front_door:person:rule1",
            "created_at": "2026-01-09T12:00:00Z",
            "updated_at": "2026-01-09T12:00:00Z",
        }

    def test_valid_message(self, valid_alert_data: dict) -> None:
        """Test valid alert created message."""
        data = WebSocketAlertData.model_validate(valid_alert_data)
        message = WebSocketAlertCreatedMessage(data=data)
        assert message.type == "alert_created"
        assert message.data.id == valid_alert_data["id"]

    def test_default_type(self, valid_alert_data: dict) -> None:
        """Test that type defaults to alert_created."""
        data = WebSocketAlertData.model_validate(valid_alert_data)
        message = WebSocketAlertCreatedMessage(data=data)
        assert message.type == "alert_created"

    def test_json_serialization(self, valid_alert_data: dict) -> None:
        """Test JSON serialization of alert created message."""
        data = WebSocketAlertData.model_validate(valid_alert_data)
        message = WebSocketAlertCreatedMessage(data=data)
        json_data = message.model_dump(mode="json")
        assert json_data["type"] == "alert_created"
        assert json_data["data"]["id"] == valid_alert_data["id"]
        assert json_data["data"]["severity"] == "high"


class TestWebSocketAlertAcknowledgedMessage:
    """Tests for WebSocketAlertAcknowledgedMessage schema."""

    @pytest.fixture
    def valid_alert_data(self) -> dict:
        """Create valid alert data for testing."""
        return {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "event_id": 123,
            "rule_id": "550e8400-e29b-41d4-a716-446655440001",
            "severity": "critical",
            "status": "acknowledged",
            "dedup_key": "backyard:vehicle:rule2",
            "created_at": "2026-01-09T12:00:00Z",
            "updated_at": "2026-01-09T12:01:00Z",
        }

    def test_valid_message(self, valid_alert_data: dict) -> None:
        """Test valid alert acknowledged message."""
        data = WebSocketAlertData.model_validate(valid_alert_data)
        message = WebSocketAlertAcknowledgedMessage(data=data)
        assert message.type == "alert_acknowledged"
        assert message.data.status == WebSocketAlertStatus.ACKNOWLEDGED

    def test_default_type(self, valid_alert_data: dict) -> None:
        """Test that type defaults to alert_acknowledged."""
        data = WebSocketAlertData.model_validate(valid_alert_data)
        message = WebSocketAlertAcknowledgedMessage(data=data)
        assert message.type == "alert_acknowledged"

    def test_json_serialization(self, valid_alert_data: dict) -> None:
        """Test JSON serialization of alert acknowledged message."""
        data = WebSocketAlertData.model_validate(valid_alert_data)
        message = WebSocketAlertAcknowledgedMessage(data=data)
        json_data = message.model_dump(mode="json")
        assert json_data["type"] == "alert_acknowledged"
        assert json_data["data"]["status"] == "acknowledged"


class TestWebSocketAlertDismissedMessage:
    """Tests for WebSocketAlertDismissedMessage schema."""

    @pytest.fixture
    def valid_alert_data(self) -> dict:
        """Create valid alert data for testing."""
        return {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "event_id": 456,
            "rule_id": None,
            "severity": "low",
            "status": "dismissed",
            "dedup_key": "garage:animal:rule3",
            "created_at": "2026-01-09T12:00:00Z",
            "updated_at": "2026-01-09T12:02:00Z",
        }

    def test_valid_message(self, valid_alert_data: dict) -> None:
        """Test valid alert dismissed message."""
        data = WebSocketAlertData.model_validate(valid_alert_data)
        message = WebSocketAlertDismissedMessage(data=data)
        assert message.type == "alert_dismissed"
        assert message.data.status == WebSocketAlertStatus.DISMISSED

    def test_default_type(self, valid_alert_data: dict) -> None:
        """Test that type defaults to alert_dismissed."""
        data = WebSocketAlertData.model_validate(valid_alert_data)
        message = WebSocketAlertDismissedMessage(data=data)
        assert message.type == "alert_dismissed"

    def test_json_serialization(self, valid_alert_data: dict) -> None:
        """Test JSON serialization of alert dismissed message."""
        data = WebSocketAlertData.model_validate(valid_alert_data)
        message = WebSocketAlertDismissedMessage(data=data)
        json_data = message.model_dump(mode="json")
        assert json_data["type"] == "alert_dismissed"
        assert json_data["data"]["status"] == "dismissed"
        assert json_data["data"]["severity"] == "low"


class TestWebSocketAlertMessageRoundTrip:
    """Tests for round-trip serialization of alert messages."""

    @pytest.fixture
    def sample_alert_data(self) -> dict:
        """Create sample alert data."""
        return {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "event_id": 789,
            "rule_id": "550e8400-e29b-41d4-a716-446655440002",
            "severity": "medium",
            "status": "delivered",
            "dedup_key": "driveway:person:rule4",
            "created_at": "2026-01-09T10:00:00Z",
            "updated_at": "2026-01-09T10:00:05Z",
        }

    def test_alert_created_round_trip(self, sample_alert_data: dict) -> None:
        """Test that alert created message survives round-trip serialization."""
        data = WebSocketAlertData.model_validate(sample_alert_data)
        original = WebSocketAlertCreatedMessage(data=data)
        json_str = original.model_dump_json()
        restored = WebSocketAlertCreatedMessage.model_validate_json(json_str)
        assert restored.type == original.type
        assert restored.data.id == original.data.id
        assert restored.data.event_id == original.data.event_id

    def test_alert_acknowledged_round_trip(self, sample_alert_data: dict) -> None:
        """Test that alert acknowledged message survives round-trip serialization."""
        sample_alert_data["status"] = "acknowledged"
        data = WebSocketAlertData.model_validate(sample_alert_data)
        original = WebSocketAlertAcknowledgedMessage(data=data)
        json_str = original.model_dump_json()
        restored = WebSocketAlertAcknowledgedMessage.model_validate_json(json_str)
        assert restored.type == original.type
        assert restored.data.status == WebSocketAlertStatus.ACKNOWLEDGED

    def test_alert_dismissed_round_trip(self, sample_alert_data: dict) -> None:
        """Test that alert dismissed message survives round-trip serialization."""
        sample_alert_data["status"] = "dismissed"
        data = WebSocketAlertData.model_validate(sample_alert_data)
        original = WebSocketAlertDismissedMessage(data=data)
        json_str = original.model_dump_json()
        restored = WebSocketAlertDismissedMessage.model_validate_json(json_str)
        assert restored.type == original.type
        assert restored.data.status == WebSocketAlertStatus.DISMISSED
