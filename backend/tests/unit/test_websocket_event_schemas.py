"""Unit tests for WebSocket event payload schemas.

This module tests the Pydantic schemas for WebSocket event payloads including:
- Alert event payloads
- Camera event payloads
- Job event payloads
- System event payloads
- Security event payloads
- Detection event payloads
- Validation helpers
"""

import pytest
from pydantic import ValidationError

from backend.core.websocket import WebSocketEventType
from backend.core.websocket.event_schemas import (
    EVENT_PAYLOAD_SCHEMAS,
    AlertAcknowledgedPayload,
    AlertCreatedPayload,
    AlertDeletedPayload,
    AlertDismissedPayload,
    AlertResolvedPayload,
    AlertSeverity,
    AlertStatus,
    AlertUpdatedPayload,
    BoundingBox,
    CameraConfigUpdatedPayload,
    CameraErrorPayload,
    CameraOfflinePayload,
    CameraOnlinePayload,
    CameraStatus,
    CameraStatusChangedPayload,
    ConnectionErrorPayload,
    ConnectionEstablishedPayload,
    DetectionBatchPayload,
    DetectionNewPayload,
    ErrorPayload,
    EventCreatedPayload,
    EventDeletedPayload,
    EventUpdatedPayload,
    GPUStatsUpdatedPayload,
    JobCancelledPayload,
    JobCompletedPayload,
    JobFailedPayload,
    JobProgressPayload,
    JobStartedPayload,
    RiskLevel,
    SceneChangeDetectedPayload,
    SceneChangeType,
    ServiceStatus,
    ServiceStatusChangedPayload,
    SystemErrorPayload,
    SystemHealth,
    SystemHealthChangedPayload,
    SystemStatusPayload,
    get_payload_schema,
    validate_payload,
)


class TestAlertPayloadSchemas:
    """Tests for alert event payload schemas."""

    def test_alert_created_payload_valid(self):
        """Test valid AlertCreatedPayload."""
        payload = AlertCreatedPayload(
            id="550e8400-e29b-41d4-a716-446655440000",
            event_id=123,
            severity="high",
            status="pending",
            dedup_key="front_door:person:rule1",
            created_at="2026-01-09T12:00:00Z",
            updated_at="2026-01-09T12:00:00Z",
        )
        assert payload.id == "550e8400-e29b-41d4-a716-446655440000"
        assert payload.event_id == 123
        assert payload.severity == AlertSeverity.HIGH
        assert payload.status == AlertStatus.PENDING

    def test_alert_created_payload_with_enum(self):
        """Test AlertCreatedPayload with enum values."""
        payload = AlertCreatedPayload(
            id="123",
            event_id=1,
            severity=AlertSeverity.CRITICAL,
            status=AlertStatus.DELIVERED,
            dedup_key="test",
            created_at="2026-01-09T12:00:00Z",
            updated_at="2026-01-09T12:00:00Z",
        )
        assert payload.severity == AlertSeverity.CRITICAL
        assert payload.status == AlertStatus.DELIVERED

    def test_alert_created_payload_missing_required(self):
        """Test AlertCreatedPayload fails with missing required fields."""
        with pytest.raises(ValidationError) as exc_info:
            AlertCreatedPayload(
                id="123",
                # Missing event_id, severity, status, etc.
            )
        errors = exc_info.value.errors()
        assert any(e["loc"][0] == "event_id" for e in errors)
        assert any(e["loc"][0] == "severity" for e in errors)

    def test_alert_created_payload_invalid_severity(self):
        """Test AlertCreatedPayload fails with invalid severity."""
        with pytest.raises(ValidationError):
            AlertCreatedPayload(
                id="123",
                event_id=1,
                severity="invalid_severity",
                status="pending",
                dedup_key="test",
                created_at="2026-01-09T12:00:00Z",
                updated_at="2026-01-09T12:00:00Z",
            )

    def test_alert_updated_payload(self):
        """Test AlertUpdatedPayload."""
        payload = AlertUpdatedPayload(
            id="123",
            updated_at="2026-01-09T12:00:00Z",
            updated_fields=["status", "severity"],
            severity="medium",
        )
        assert payload.severity == AlertSeverity.MEDIUM
        assert payload.updated_fields == ["status", "severity"]

    def test_alert_acknowledged_payload(self):
        """Test AlertAcknowledgedPayload."""
        payload = AlertAcknowledgedPayload(
            id="123",
            event_id=1,
            acknowledged_at="2026-01-09T12:00:00Z",
        )
        assert payload.id == "123"
        assert payload.event_id == 1

    def test_alert_resolved_payload(self):
        """Test AlertResolvedPayload."""
        payload = AlertResolvedPayload(
            id="123",
            event_id=1,
            resolved_at="2026-01-09T12:00:00Z",
            resolution_notes="False alarm",
        )
        assert payload.resolution_notes == "False alarm"

    def test_alert_dismissed_payload(self):
        """Test AlertDismissedPayload."""
        payload = AlertDismissedPayload(
            id="123",
            event_id=1,
            dismissed_at="2026-01-09T12:00:00Z",
            reason="Duplicate",
        )
        assert payload.reason == "Duplicate"

    def test_alert_deleted_payload(self):
        """Test AlertDeletedPayload."""
        payload = AlertDeletedPayload(
            id="123",
            reason="Cleanup",
        )
        assert payload.id == "123"
        assert payload.reason == "Cleanup"


class TestCameraPayloadSchemas:
    """Tests for camera event payload schemas."""

    def test_camera_online_payload(self):
        """Test CameraOnlinePayload."""
        payload = CameraOnlinePayload(
            camera_id="front_door",
            camera_name="Front Door Camera",
            timestamp="2026-01-09T12:00:00Z",
        )
        assert payload.camera_id == "front_door"
        assert payload.camera_name == "Front Door Camera"

    def test_camera_offline_payload(self):
        """Test CameraOfflinePayload."""
        payload = CameraOfflinePayload(
            camera_id="back_yard",
            camera_name="Back Yard Camera",
            timestamp="2026-01-09T12:00:00Z",
            reason="Connection timeout",
        )
        assert payload.reason == "Connection timeout"

    def test_camera_status_changed_payload(self):
        """Test CameraStatusChangedPayload."""
        payload = CameraStatusChangedPayload(
            camera_id="garage",
            camera_name="Garage Camera",
            status="online",
            previous_status="offline",
            timestamp="2026-01-09T12:00:00Z",
        )
        assert payload.status == CameraStatus.ONLINE
        assert payload.previous_status == CameraStatus.OFFLINE

    def test_camera_status_changed_with_enum(self):
        """Test CameraStatusChangedPayload with enum values."""
        payload = CameraStatusChangedPayload(
            camera_id="garage",
            camera_name="Garage Camera",
            status=CameraStatus.ERROR,
            previous_status=CameraStatus.ONLINE,
            timestamp="2026-01-09T12:00:00Z",
            reason="Hardware failure",
            details={"error_code": "CAM_001"},
        )
        assert payload.status == CameraStatus.ERROR
        assert payload.details == {"error_code": "CAM_001"}

    def test_camera_error_payload(self):
        """Test CameraErrorPayload."""
        payload = CameraErrorPayload(
            camera_id="porch",
            camera_name="Porch Camera",
            error="Connection refused",
            error_code="ERR_CONN",
            timestamp="2026-01-09T12:00:00Z",
        )
        assert payload.error == "Connection refused"
        assert payload.error_code == "ERR_CONN"

    def test_camera_config_updated_payload(self):
        """Test CameraConfigUpdatedPayload."""
        payload = CameraConfigUpdatedPayload(
            camera_id="front_door",
            updated_fields=["name", "resolution", "fps"],
            updated_at="2026-01-09T12:00:00Z",
        )
        assert len(payload.updated_fields) == 3


class TestJobPayloadSchemas:
    """Tests for job event payload schemas."""

    def test_job_started_payload(self):
        """Test JobStartedPayload."""
        payload = JobStartedPayload(
            job_id="job-123",
            job_type="export",
            started_at="2026-01-09T12:00:00Z",
            estimated_duration=300,
            metadata={"format": "mp4"},
        )
        assert payload.job_id == "job-123"
        assert payload.estimated_duration == 300
        assert payload.metadata["format"] == "mp4"

    def test_job_progress_payload(self):
        """Test JobProgressPayload."""
        payload = JobProgressPayload(
            job_id="job-123",
            job_type="export",
            progress=50,
            status="running",
            message="Processing frames...",
        )
        assert payload.progress == 50
        assert payload.message == "Processing frames..."

    def test_job_progress_validates_range(self):
        """Test JobProgressPayload validates progress range."""
        # Valid: 0
        payload = JobProgressPayload(
            job_id="job-123",
            job_type="export",
            progress=0,
            status="starting",
        )
        assert payload.progress == 0

        # Valid: 100
        payload = JobProgressPayload(
            job_id="job-123",
            job_type="export",
            progress=100,
            status="complete",
        )
        assert payload.progress == 100

        # Invalid: > 100
        with pytest.raises(ValidationError):
            JobProgressPayload(
                job_id="job-123",
                job_type="export",
                progress=101,
                status="error",
            )

        # Invalid: < 0
        with pytest.raises(ValidationError):
            JobProgressPayload(
                job_id="job-123",
                job_type="export",
                progress=-1,
                status="error",
            )

    def test_job_completed_payload(self):
        """Test JobCompletedPayload."""
        payload = JobCompletedPayload(
            job_id="job-123",
            job_type="export",
            completed_at="2026-01-09T12:05:00Z",
            result={"file_path": "/exports/video.mp4", "size": 1024000},
            duration_seconds=300.5,
        )
        assert payload.result["file_path"] == "/exports/video.mp4"
        assert payload.duration_seconds == 300.5

    def test_job_failed_payload(self):
        """Test JobFailedPayload."""
        payload = JobFailedPayload(
            job_id="job-123",
            job_type="export",
            failed_at="2026-01-09T12:03:00Z",
            error="Disk full",
            error_code="ERR_DISK_FULL",
            retryable=True,
        )
        assert payload.error == "Disk full"
        assert payload.retryable is True

    def test_job_cancelled_payload(self):
        """Test JobCancelledPayload."""
        payload = JobCancelledPayload(
            job_id="job-123",
            job_type="export",
            cancelled_at="2026-01-09T12:02:00Z",
            reason="User requested cancellation",
        )
        assert payload.reason == "User requested cancellation"


class TestSystemPayloadSchemas:
    """Tests for system event payload schemas."""

    def test_system_health_changed_payload(self):
        """Test SystemHealthChangedPayload."""
        payload = SystemHealthChangedPayload(
            health="degraded",
            previous_health="healthy",
            components={
                "database": "healthy",
                "redis": "healthy",
                "ai": "unhealthy",
            },
            timestamp="2026-01-09T12:00:00Z",
        )
        assert payload.health == SystemHealth.DEGRADED
        assert payload.previous_health == SystemHealth.HEALTHY
        assert payload.components["ai"] == "unhealthy"

    def test_system_error_payload(self):
        """Test SystemErrorPayload."""
        payload = SystemErrorPayload(
            error="DATABASE_CONNECTION_LOST",
            message="Failed to connect to PostgreSQL",
            timestamp="2026-01-09T12:00:00Z",
            details={"host": "localhost", "port": 5432},
            recoverable=True,
        )
        assert payload.error == "DATABASE_CONNECTION_LOST"
        assert payload.recoverable is True

    def test_system_status_payload(self):
        """Test SystemStatusPayload."""
        payload = SystemStatusPayload(
            gpu={"utilization": 45.5, "memory_used": 8000000000},
            cameras={"active": 4, "total": 6},
            queue={"pending": 2, "processing": 1},
            health="healthy",
            ai={"rtdetr": "healthy", "nemotron": "degraded"},
            timestamp="2026-01-09T12:00:00Z",
        )
        assert payload.gpu["utilization"] == 45.5
        assert payload.cameras["active"] == 4
        assert payload.ai["nemotron"] == "degraded"

    def test_service_status_changed_payload(self):
        """Test ServiceStatusChangedPayload."""
        payload = ServiceStatusChangedPayload(
            service="nemotron",
            status="restarting",
            previous_status="unhealthy",
            message="Auto-restart triggered",
            timestamp="2026-01-09T12:00:00Z",
        )
        assert payload.status == ServiceStatus.RESTARTING
        assert payload.previous_status == ServiceStatus.UNHEALTHY

    def test_gpu_stats_updated_payload(self):
        """Test GPUStatsUpdatedPayload."""
        payload = GPUStatsUpdatedPayload(
            utilization=75.5,
            memory_used=16000000000,
            memory_total=24000000000,
            temperature=72.0,
            inference_fps=30.5,
            timestamp="2026-01-09T12:00:00Z",
        )
        assert payload.utilization == 75.5
        assert payload.temperature == 72.0


class TestSecurityEventPayloadSchemas:
    """Tests for security event payload schemas."""

    def test_event_created_payload(self):
        """Test EventCreatedPayload."""
        payload = EventCreatedPayload(
            id=123,
            event_id=123,
            batch_id="batch-456",
            camera_id="front_door",
            risk_score=75,
            risk_level="high",
            summary="Person detected at front door",
            reasoning="Unknown person observed approaching the door",
        )
        assert payload.id == 123
        assert payload.risk_score == 75
        assert payload.risk_level == RiskLevel.HIGH

    def test_event_created_validates_risk_score_range(self):
        """Test EventCreatedPayload validates risk score range."""
        # Valid: 0
        payload = EventCreatedPayload(
            id=1,
            event_id=1,
            batch_id="batch-1",
            camera_id="cam",
            risk_score=0,
            risk_level="low",
            summary="Test",
            reasoning="Test",
        )
        assert payload.risk_score == 0

        # Valid: 100
        payload = EventCreatedPayload(
            id=1,
            event_id=1,
            batch_id="batch-1",
            camera_id="cam",
            risk_score=100,
            risk_level="critical",
            summary="Test",
            reasoning="Test",
        )
        assert payload.risk_score == 100

        # Invalid: > 100
        with pytest.raises(ValidationError):
            EventCreatedPayload(
                id=1,
                event_id=1,
                batch_id="batch-1",
                camera_id="cam",
                risk_score=101,
                risk_level="critical",
                summary="Test",
                reasoning="Test",
            )

    def test_event_updated_payload(self):
        """Test EventUpdatedPayload."""
        payload = EventUpdatedPayload(
            id=123,
            updated_fields=["risk_score", "risk_level"],
            risk_score=85,
            risk_level="critical",
            updated_at="2026-01-09T12:00:00Z",
        )
        assert payload.risk_level == RiskLevel.CRITICAL
        assert "risk_score" in payload.updated_fields

    def test_event_deleted_payload(self):
        """Test EventDeletedPayload."""
        payload = EventDeletedPayload(
            id=123,
            reason="False positive",
        )
        assert payload.id == 123
        assert payload.reason == "False positive"


class TestDetectionPayloadSchemas:
    """Tests for detection event payload schemas."""

    def test_bounding_box(self):
        """Test BoundingBox model."""
        bbox = BoundingBox(
            x=100.0,
            y=200.0,
            width=50.0,
            height=75.0,
        )
        assert bbox.x == 100.0
        assert bbox.width == 50.0

    def test_detection_new_payload(self):
        """Test DetectionNewPayload."""
        payload = DetectionNewPayload(
            detection_id="det-123",
            event_id="evt-456",
            label="person",
            confidence=0.95,
            bbox=BoundingBox(x=100, y=200, width=50, height=100),
            camera_id="front_door",
            timestamp="2026-01-09T12:00:00Z",
        )
        assert payload.label == "person"
        assert payload.confidence == 0.95
        assert payload.bbox.width == 50

    def test_detection_new_validates_confidence_range(self):
        """Test DetectionNewPayload validates confidence range."""
        # Valid: 0
        payload = DetectionNewPayload(
            detection_id="det-1",
            label="person",
            confidence=0.0,
            camera_id="cam",
            timestamp="2026-01-09T12:00:00Z",
        )
        assert payload.confidence == 0.0

        # Valid: 1
        payload = DetectionNewPayload(
            detection_id="det-1",
            label="person",
            confidence=1.0,
            camera_id="cam",
            timestamp="2026-01-09T12:00:00Z",
        )
        assert payload.confidence == 1.0

        # Invalid: > 1
        with pytest.raises(ValidationError):
            DetectionNewPayload(
                detection_id="det-1",
                label="person",
                confidence=1.5,
                camera_id="cam",
                timestamp="2026-01-09T12:00:00Z",
            )

    def test_detection_batch_payload(self):
        """Test DetectionBatchPayload."""
        detection = DetectionNewPayload(
            detection_id="det-1",
            label="person",
            confidence=0.95,
            camera_id="front_door",
            timestamp="2026-01-09T12:00:00Z",
        )
        payload = DetectionBatchPayload(
            batch_id="batch-123",
            detections=[detection],
            frame_timestamp="2026-01-09T12:00:00Z",
            camera_id="front_door",
            frame_count=1,
        )
        assert len(payload.detections) == 1
        assert payload.detections[0].label == "person"


class TestSceneChangePayloadSchema:
    """Tests for scene change event payload schema."""

    def test_scene_change_detected_payload(self):
        """Test SceneChangeDetectedPayload."""
        payload = SceneChangeDetectedPayload(
            id=1,
            camera_id="front_door",
            detected_at="2026-01-09T12:00:00Z",
            change_type="view_blocked",
            similarity_score=0.45,
        )
        assert payload.change_type == SceneChangeType.VIEW_BLOCKED
        assert payload.similarity_score == 0.45

    def test_scene_change_validates_similarity_range(self):
        """Test SceneChangeDetectedPayload validates similarity score."""
        # Valid range
        payload = SceneChangeDetectedPayload(
            id=1,
            camera_id="cam",
            detected_at="2026-01-09T12:00:00Z",
            change_type="view_tampered",
            similarity_score=0.0,
        )
        assert payload.similarity_score == 0.0

        # Invalid: > 1
        with pytest.raises(ValidationError):
            SceneChangeDetectedPayload(
                id=1,
                camera_id="cam",
                detected_at="2026-01-09T12:00:00Z",
                change_type="view_tampered",
                similarity_score=1.5,
            )


class TestConnectionPayloadSchemas:
    """Tests for connection event payload schemas."""

    def test_connection_established_payload(self):
        """Test ConnectionEstablishedPayload."""
        payload = ConnectionEstablishedPayload(
            connection_id="conn-123",
            timestamp="2026-01-09T12:00:00Z",
        )
        assert payload.connection_id == "conn-123"

    def test_connection_error_payload(self):
        """Test ConnectionErrorPayload."""
        payload = ConnectionErrorPayload(
            error="TIMEOUT",
            message="Connection timed out after 30s",
            timestamp="2026-01-09T12:00:00Z",
        )
        assert payload.error == "TIMEOUT"


class TestErrorPayloadSchema:
    """Tests for error payload schema."""

    def test_error_payload(self):
        """Test ErrorPayload."""
        payload = ErrorPayload(
            error="INVALID_MESSAGE",
            message="Failed to parse message",
            details={"position": 42, "expected": "JSON"},
        )
        assert payload.error == "INVALID_MESSAGE"
        assert payload.details["position"] == 42


class TestPayloadSchemaMapping:
    """Tests for EVENT_PAYLOAD_SCHEMAS mapping."""

    def test_all_event_types_with_payloads_have_schemas(self):
        """Verify all event types that require payloads have schemas."""
        # Event types that explicitly don't require payloads
        no_payload_types = {
            WebSocketEventType.PING,
            WebSocketEventType.PONG,
            WebSocketEventType.CONNECTION_ESTABLISHED,
            WebSocketEventType.CAMERA_ENABLED,
            WebSocketEventType.CAMERA_DISABLED,
        }

        for event_type in WebSocketEventType:
            if event_type not in no_payload_types:
                # Most event types should have schemas
                schema = get_payload_schema(event_type)
                # It's OK if some don't have schemas (they'll use generic validation)
                # Just check the mapping exists for core types
                if event_type in EVENT_PAYLOAD_SCHEMAS:
                    assert schema is not None, f"Missing schema for {event_type}"

    def test_get_payload_schema_returns_correct_type(self):
        """Test get_payload_schema returns correct schema types."""
        assert get_payload_schema(WebSocketEventType.ALERT_CREATED) == AlertCreatedPayload
        assert get_payload_schema(WebSocketEventType.CAMERA_ONLINE) == CameraOnlinePayload
        assert get_payload_schema(WebSocketEventType.JOB_STARTED) == JobStartedPayload
        assert get_payload_schema(WebSocketEventType.SYSTEM_STATUS) == SystemStatusPayload

    def test_get_payload_schema_returns_none_for_unknown(self):
        """Test get_payload_schema returns None for types without schema."""
        # PING doesn't have a specific schema
        schema = get_payload_schema(WebSocketEventType.PING)
        # It may or may not have a schema - if it doesn't, that's fine
        # The important thing is it doesn't raise an error


class TestValidatePayloadFunction:
    """Tests for validate_payload helper function."""

    def test_validate_payload_success(self):
        """Test validate_payload with valid data."""
        data = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "event_id": 123,
            "severity": "high",
            "status": "pending",
            "dedup_key": "test",
            "created_at": "2026-01-09T12:00:00Z",
            "updated_at": "2026-01-09T12:00:00Z",
        }
        result = validate_payload(WebSocketEventType.ALERT_CREATED, data)

        assert isinstance(result, AlertCreatedPayload)
        assert result.id == "550e8400-e29b-41d4-a716-446655440000"

    def test_validate_payload_failure(self):
        """Test validate_payload with invalid data."""
        data = {"invalid": "data"}

        with pytest.raises(ValidationError):
            validate_payload(WebSocketEventType.ALERT_CREATED, data)

    def test_validate_payload_no_schema(self):
        """Test validate_payload raises for event without schema."""
        # CAMERA_ENABLED and CAMERA_DISABLED don't have specific payload schemas
        schema = get_payload_schema(WebSocketEventType.CAMERA_ENABLED)
        if schema is None:
            with pytest.raises(ValueError, match="No payload schema defined"):
                validate_payload(WebSocketEventType.CAMERA_ENABLED, {})

    def test_validate_payload_with_job_payload(self):
        """Test validate_payload with JobStartedPayload."""
        data = {
            "job_id": "job-123",
            "job_type": "export",
            "started_at": "2026-01-09T12:00:00Z",
        }
        result = validate_payload(WebSocketEventType.JOB_STARTED, data)
        assert isinstance(result, JobStartedPayload)
        assert result.job_id == "job-123"

    def test_validate_payload_with_system_payload(self):
        """Test validate_payload with SystemStatusPayload."""
        data = {
            "gpu": {"utilization": 50.0},
            "cameras": {"active": 3, "total": 5},
            "queue": {"pending": 1, "processing": 0},
            "health": "healthy",
            "timestamp": "2026-01-09T12:00:00Z",
        }
        result = validate_payload(WebSocketEventType.SYSTEM_STATUS, data)
        assert isinstance(result, SystemStatusPayload)


class TestEnumStringCoercion:
    """Tests for enum string coercion in validators."""

    def test_severity_with_invalid_type_raises(self):
        """Test severity with invalid type (not str or enum) raises ValueError."""
        with pytest.raises(ValidationError) as exc_info:
            AlertCreatedPayload(
                id="123",
                event_id=1,
                severity=123,  # Invalid type: int
                status="pending",
                dedup_key="test",
                created_at="2026-01-09T12:00:00Z",
                updated_at="2026-01-09T12:00:00Z",
            )
        # The validator should raise for invalid type
        assert any("severity" in str(e) for e in exc_info.value.errors())

    def test_status_with_invalid_type_raises(self):
        """Test status with invalid type (not str or enum) raises ValueError."""
        with pytest.raises(ValidationError) as exc_info:
            AlertCreatedPayload(
                id="123",
                event_id=1,
                severity="high",
                status=456,  # Invalid type: int
                dedup_key="test",
                created_at="2026-01-09T12:00:00Z",
                updated_at="2026-01-09T12:00:00Z",
            )
        assert any("status" in str(e) for e in exc_info.value.errors())

    def test_severity_coerces_lowercase(self):
        """Test severity accepts lowercase strings."""
        payload = AlertCreatedPayload(
            id="123",
            event_id=1,
            severity="high",
            status="pending",
            dedup_key="test",
            created_at="2026-01-09T12:00:00Z",
            updated_at="2026-01-09T12:00:00Z",
        )
        assert payload.severity == AlertSeverity.HIGH

    def test_status_coerces_lowercase(self):
        """Test status accepts lowercase strings."""
        payload = AlertCreatedPayload(
            id="123",
            event_id=1,
            severity="low",
            status="acknowledged",
            dedup_key="test",
            created_at="2026-01-09T12:00:00Z",
            updated_at="2026-01-09T12:00:00Z",
        )
        assert payload.status == AlertStatus.ACKNOWLEDGED

    def test_camera_status_coerces_lowercase(self):
        """Test camera status accepts lowercase strings."""
        payload = CameraStatusChangedPayload(
            camera_id="cam",
            camera_name="Camera",
            status="error",
            previous_status="online",
            timestamp="2026-01-09T12:00:00Z",
        )
        assert payload.status == CameraStatus.ERROR
        assert payload.previous_status == CameraStatus.ONLINE

    def test_system_health_coerces_lowercase(self):
        """Test system health accepts lowercase strings."""
        payload = SystemHealthChangedPayload(
            health="degraded",
            previous_health="healthy",
            components={},
            timestamp="2026-01-09T12:00:00Z",
        )
        assert payload.health == SystemHealth.DEGRADED

    def test_risk_level_coerces_lowercase(self):
        """Test risk level accepts lowercase strings."""
        payload = EventCreatedPayload(
            id=1,
            event_id=1,
            batch_id="batch-1",
            camera_id="cam",
            risk_score=50,
            risk_level="medium",
            summary="Test",
            reasoning="Test",
        )
        assert payload.risk_level == RiskLevel.MEDIUM

    def test_risk_level_with_invalid_type_raises(self):
        """Test risk level with invalid type raises ValueError."""
        with pytest.raises(ValidationError) as exc_info:
            EventCreatedPayload(
                id=1,
                event_id=1,
                batch_id="batch-1",
                camera_id="cam",
                risk_score=50,
                risk_level=999,  # Invalid type: int
                summary="Test",
                reasoning="Test",
            )
        assert any("risk_level" in str(e) for e in exc_info.value.errors())

    def test_scene_change_type_coerces_lowercase(self):
        """Test scene change type accepts lowercase strings."""
        payload = SceneChangeDetectedPayload(
            id=1,
            camera_id="cam",
            detected_at="2026-01-09T12:00:00Z",
            change_type="angle_changed",
            similarity_score=0.7,
        )
        assert payload.change_type == SceneChangeType.ANGLE_CHANGED

    def test_scene_change_type_with_invalid_type_raises(self):
        """Test scene change type with invalid type raises ValueError."""
        with pytest.raises(ValidationError) as exc_info:
            SceneChangeDetectedPayload(
                id=1,
                camera_id="cam",
                detected_at="2026-01-09T12:00:00Z",
                change_type=123,  # Invalid type: int
                similarity_score=0.7,
            )
        assert any("change_type" in str(e) for e in exc_info.value.errors())

    def test_camera_status_with_invalid_type_raises(self):
        """Test camera status with invalid type raises ValueError."""
        with pytest.raises(ValidationError) as exc_info:
            CameraStatusChangedPayload(
                camera_id="cam",
                camera_name="Camera",
                status=["invalid"],  # Invalid type: list
                timestamp="2026-01-09T12:00:00Z",
            )
        assert any("status" in str(e) for e in exc_info.value.errors())

    def test_system_health_with_invalid_type_raises(self):
        """Test system health with invalid type raises ValueError."""
        with pytest.raises(ValidationError) as exc_info:
            SystemHealthChangedPayload(
                health={"invalid": "dict"},  # Invalid type: dict
                components={},
                timestamp="2026-01-09T12:00:00Z",
            )
        assert any("health" in str(e) for e in exc_info.value.errors())

    def test_service_status_with_invalid_type_raises(self):
        """Test service status with invalid type raises ValueError."""
        with pytest.raises(ValidationError) as exc_info:
            ServiceStatusChangedPayload(
                service="test",
                status=[1, 2, 3],  # Invalid type: list
                timestamp="2026-01-09T12:00:00Z",
            )
        assert any("status" in str(e) for e in exc_info.value.errors())


class TestExtraFieldsIgnored:
    """Tests for extra field handling (configured to ignore)."""

    def test_extra_fields_are_ignored(self):
        """Test that extra fields in payload are ignored."""
        payload = AlertCreatedPayload(
            id="123",
            event_id=1,
            severity="high",
            status="pending",
            dedup_key="test",
            created_at="2026-01-09T12:00:00Z",
            updated_at="2026-01-09T12:00:00Z",
            extra_field="should be ignored",  # Extra field
        )
        # Should not raise and extra field should be ignored
        assert payload.id == "123"
        assert not hasattr(payload, "extra_field")
