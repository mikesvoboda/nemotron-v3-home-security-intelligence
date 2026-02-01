"""Unit tests for Alert Service API schemas.

Tests the Pydantic schemas for Alert Service CRUD endpoints (NEM-4931).
"""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from backend.api.schemas.alert_service import (
    AcknowledgeRequest,
    AlertServiceCreateRequest,
    AlertServiceDeleteResponse,
    AlertServiceListResponse,
    AlertServiceResponse,
    AlertServiceUpdateRequest,
    DismissRequest,
)
from backend.api.schemas.alerts import AlertSeverity, AlertStatus


class TestAlertServiceCreateRequest:
    """Tests for AlertServiceCreateRequest schema."""

    def test_valid_create_request(self) -> None:
        """Test creating a valid alert request."""
        request = AlertServiceCreateRequest(
            event_id=123,
            severity=AlertSeverity.HIGH,
            dedup_key="front_door:test_alert",
        )
        assert request.event_id == 123
        assert request.severity == AlertSeverity.HIGH
        assert request.dedup_key == "front_door:test_alert"
        assert request.status == AlertStatus.PENDING  # Default
        assert request.channels == []  # Default
        assert request.metadata is None  # Default

    def test_create_request_with_all_fields(self) -> None:
        """Test creating an alert request with all optional fields."""
        request = AlertServiceCreateRequest(
            event_id=456,
            severity=AlertSeverity.CRITICAL,
            dedup_key="back_yard:intrusion",
            rule_id="019477e6-8c5e-7abc-def0-123456789abc",
            status=AlertStatus.DELIVERED,
            channels=["pushover", "webhook"],
            metadata={"source": "external", "priority": "urgent"},
        )
        assert request.event_id == 456
        assert request.rule_id == "019477e6-8c5e-7abc-def0-123456789abc"
        assert request.status == AlertStatus.DELIVERED
        assert request.channels == ["pushover", "webhook"]
        assert request.metadata == {"source": "external", "priority": "urgent"}

    def test_create_request_invalid_dedup_key(self) -> None:
        """Test that invalid dedup_key characters are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            AlertServiceCreateRequest(
                event_id=123,
                severity=AlertSeverity.MEDIUM,
                dedup_key="invalid;key<script>",  # Contains invalid characters
            )
        assert "dedup_key" in str(exc_info.value)

    def test_create_request_missing_required_fields(self) -> None:
        """Test that missing required fields raise validation error."""
        with pytest.raises(ValidationError):
            AlertServiceCreateRequest(event_id=123)  # Missing severity and dedup_key

    def test_create_request_valid_dedup_key_patterns(self) -> None:
        """Test that valid dedup_key patterns are accepted."""
        valid_keys = [
            "camera_1:rule_abc",
            "front-door:person:entry",
            "BACKYARD_CAM:VEHICLE",
            "cam:123:rule:456",
        ]
        for key in valid_keys:
            request = AlertServiceCreateRequest(
                event_id=1,
                severity=AlertSeverity.LOW,
                dedup_key=key,
            )
            assert request.dedup_key == key


class TestAlertServiceUpdateRequest:
    """Tests for AlertServiceUpdateRequest schema."""

    def test_update_request_empty(self) -> None:
        """Test that an empty update request is valid."""
        request = AlertServiceUpdateRequest()
        assert request.status is None
        assert request.severity is None
        assert request.channels is None
        assert request.metadata is None

    def test_update_request_partial_update(self) -> None:
        """Test partial update with only status."""
        request = AlertServiceUpdateRequest(status=AlertStatus.ACKNOWLEDGED)
        assert request.status == AlertStatus.ACKNOWLEDGED
        assert request.severity is None

    def test_update_request_all_fields(self) -> None:
        """Test update with all fields."""
        request = AlertServiceUpdateRequest(
            status=AlertStatus.DISMISSED,
            severity=AlertSeverity.LOW,
            channels=["email"],
            metadata={"dismissed_by": "admin"},
        )
        assert request.status == AlertStatus.DISMISSED
        assert request.severity == AlertSeverity.LOW
        assert request.channels == ["email"]
        assert request.metadata == {"dismissed_by": "admin"}


class TestAlertServiceResponse:
    """Tests for AlertServiceResponse schema."""

    def test_response_from_dict(self) -> None:
        """Test creating response from dictionary."""
        now = datetime.now(UTC)
        data = {
            "id": "019477e6-8c5e-7abc-def0-123456789abc",
            "event_id": 123,
            "rule_id": None,
            "severity": "high",
            "status": "pending",
            "dedup_key": "test:key",
            "channels": ["pushover"],
            "alert_metadata": {"note": "test"},
            "created_at": now,
            "updated_at": now,
            "delivered_at": None,
        }
        response = AlertServiceResponse(**data)
        assert response.id == "019477e6-8c5e-7abc-def0-123456789abc"
        assert response.event_id == 123
        assert response.severity == AlertSeverity.HIGH
        assert response.metadata == {"note": "test"}

    def test_response_enum_serialization(self) -> None:
        """Test that enums are properly serialized."""
        now = datetime.now(UTC)
        response = AlertServiceResponse(
            id="test-id",
            event_id=1,
            rule_id=None,
            severity=AlertSeverity.CRITICAL,
            status=AlertStatus.ACKNOWLEDGED,
            dedup_key="key",
            channels=[],
            metadata=None,
            created_at=now,
            updated_at=now,
            delivered_at=None,
        )
        # Verify enum values
        assert response.severity == AlertSeverity.CRITICAL
        assert response.status == AlertStatus.ACKNOWLEDGED


class TestAlertServiceListResponse:
    """Tests for AlertServiceListResponse schema."""

    def test_list_response_empty(self) -> None:
        """Test empty list response."""
        from backend.api.schemas.pagination import PaginationMeta

        response = AlertServiceListResponse(
            items=[],
            pagination=PaginationMeta(
                total=0,
                limit=50,
                offset=0,
                has_more=False,
            ),
        )
        assert response.items == []
        assert response.pagination.total == 0

    def test_list_response_with_items(self) -> None:
        """Test list response with items."""
        from backend.api.schemas.pagination import PaginationMeta

        now = datetime.now(UTC)
        items = [
            AlertServiceResponse(
                id=f"id-{i}",
                event_id=i,
                rule_id=None,
                severity=AlertSeverity.MEDIUM,
                status=AlertStatus.PENDING,
                dedup_key=f"key-{i}",
                channels=[],
                metadata=None,
                created_at=now,
                updated_at=now,
                delivered_at=None,
            )
            for i in range(3)
        ]
        response = AlertServiceListResponse(
            items=items,
            pagination=PaginationMeta(
                total=3,
                limit=50,
                offset=0,
                has_more=False,
            ),
        )
        assert len(response.items) == 3
        assert response.pagination.total == 3


class TestAlertServiceDeleteResponse:
    """Tests for AlertServiceDeleteResponse schema."""

    def test_delete_response(self) -> None:
        """Test delete response."""
        response = AlertServiceDeleteResponse(
            success=True,
            deleted_id="test-id-123",
            message="Alert deleted successfully",
        )
        assert response.success is True
        assert response.deleted_id == "test-id-123"
        assert response.message == "Alert deleted successfully"

    def test_delete_response_default_message(self) -> None:
        """Test delete response with default message."""
        response = AlertServiceDeleteResponse(
            success=True,
            deleted_id="id",
        )
        assert response.message == "Alert deleted successfully"


class TestAcknowledgeRequest:
    """Tests for AcknowledgeRequest schema."""

    def test_acknowledge_request_empty(self) -> None:
        """Test empty acknowledge request."""
        request = AcknowledgeRequest()
        assert request.correlation_id is None

    def test_acknowledge_request_with_correlation_id(self) -> None:
        """Test acknowledge request with correlation_id."""
        request = AcknowledgeRequest(correlation_id="req-12345")
        assert request.correlation_id == "req-12345"


class TestDismissRequest:
    """Tests for DismissRequest schema."""

    def test_dismiss_request_empty(self) -> None:
        """Test empty dismiss request."""
        request = DismissRequest()
        assert request.reason is None
        assert request.correlation_id is None

    def test_dismiss_request_with_reason(self) -> None:
        """Test dismiss request with reason."""
        request = DismissRequest(
            reason="False positive - neighbor's cat",
            correlation_id="req-67890",
        )
        assert request.reason == "False positive - neighbor's cat"
        assert request.correlation_id == "req-67890"
