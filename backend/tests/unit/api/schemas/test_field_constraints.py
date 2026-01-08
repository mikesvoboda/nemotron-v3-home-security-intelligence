"""Unit tests for schema Field constraints.

Tests for validating that Pydantic schemas have proper Field constraints
including min_length, max_length, ge/le bounds, patterns, and examples.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from backend.api.schemas.audit import AuditLogResponse, AuditLogStats
from backend.api.schemas.logs import FrontendLogCreate, LogEntry, LogStats
from backend.api.schemas.media import MediaErrorResponse


class TestLogEntryConstraints:
    """Tests for LogEntry schema Field constraints."""

    def test_valid_log_entry(self) -> None:
        """Test that a valid log entry passes validation."""
        entry = LogEntry(
            id=1,
            timestamp=datetime.now(),
            level="INFO",
            component="backend.services.detector",
            message="Detection completed",
        )
        assert entry.id == 1
        assert entry.level == "INFO"

    def test_log_entry_id_must_be_positive(self) -> None:
        """Test that log entry ID must be >= 1."""
        with pytest.raises(ValidationError) as exc_info:
            LogEntry(
                id=0,
                timestamp=datetime.now(),
                level="INFO",
                component="test",
                message="test",
            )
        assert "id" in str(exc_info.value)

    def test_log_entry_level_pattern(self) -> None:
        """Test that log level must match expected pattern."""
        with pytest.raises(ValidationError) as exc_info:
            LogEntry(
                id=1,
                timestamp=datetime.now(),
                level="INVALID",
                component="test",
                message="test",
            )
        assert "level" in str(exc_info.value)

    def test_log_entry_valid_levels(self) -> None:
        """Test all valid log levels."""
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            entry = LogEntry(
                id=1,
                timestamp=datetime.now(),
                level=level,
                component="test",
                message="test",
            )
            assert entry.level == level

    def test_log_entry_component_max_length(self) -> None:
        """Test that component has max length constraint."""
        long_component = "a" * 201  # max is 200
        with pytest.raises(ValidationError) as exc_info:
            LogEntry(
                id=1,
                timestamp=datetime.now(),
                level="INFO",
                component=long_component,
                message="test",
            )
        assert "component" in str(exc_info.value)

    def test_log_entry_message_max_length(self) -> None:
        """Test that message has max length constraint."""
        long_message = "a" * 5001  # max is 5000
        with pytest.raises(ValidationError) as exc_info:
            LogEntry(
                id=1,
                timestamp=datetime.now(),
                level="INFO",
                component="test",
                message=long_message,
            )
        assert "message" in str(exc_info.value)

    def test_log_entry_camera_id_pattern(self) -> None:
        """Test that camera_id must match alphanumeric pattern."""
        with pytest.raises(ValidationError) as exc_info:
            LogEntry(
                id=1,
                timestamp=datetime.now(),
                level="INFO",
                component="test",
                message="test",
                camera_id="invalid@id",
            )
        assert "camera_id" in str(exc_info.value)

    def test_log_entry_valid_camera_id(self) -> None:
        """Test valid camera_id formats."""
        valid_camera_ids = ["front_door", "camera-123", "CAM_1"]
        for camera_id in valid_camera_ids:
            entry = LogEntry(
                id=1,
                timestamp=datetime.now(),
                level="INFO",
                component="test",
                message="test",
                camera_id=camera_id,
            )
            assert entry.camera_id == camera_id

    def test_log_entry_duration_ms_non_negative(self) -> None:
        """Test that duration_ms must be >= 0."""
        with pytest.raises(ValidationError) as exc_info:
            LogEntry(
                id=1,
                timestamp=datetime.now(),
                level="INFO",
                component="test",
                message="test",
                duration_ms=-1,
            )
        assert "duration_ms" in str(exc_info.value)

    def test_log_entry_source_pattern(self) -> None:
        """Test that source must be 'backend' or 'frontend'."""
        with pytest.raises(ValidationError) as exc_info:
            LogEntry(
                id=1,
                timestamp=datetime.now(),
                level="INFO",
                component="test",
                message="test",
                source="invalid",
            )
        assert "source" in str(exc_info.value)


class TestFrontendLogCreateConstraints:
    """Tests for FrontendLogCreate schema Field constraints."""

    def test_valid_frontend_log(self) -> None:
        """Test that a valid frontend log passes validation."""
        log = FrontendLogCreate(
            level="ERROR",
            component="RiskGauge",
            message="WebSocket connection lost",
        )
        assert log.level == "ERROR"
        assert log.component == "RiskGauge"

    def test_frontend_log_level_pattern(self) -> None:
        """Test that level must match expected pattern."""
        with pytest.raises(ValidationError) as exc_info:
            FrontendLogCreate(
                level="TRACE",  # Invalid
                component="Test",
                message="test",
            )
        assert "level" in str(exc_info.value)

    def test_frontend_log_component_min_length(self) -> None:
        """Test that component must have at least 1 character."""
        with pytest.raises(ValidationError) as exc_info:
            FrontendLogCreate(
                level="INFO",
                component="",
                message="test",
            )
        assert "component" in str(exc_info.value)

    def test_frontend_log_component_max_length(self) -> None:
        """Test that component has max length constraint."""
        long_component = "a" * 51  # max is 50
        with pytest.raises(ValidationError) as exc_info:
            FrontendLogCreate(
                level="INFO",
                component=long_component,
                message="test",
            )
        assert "component" in str(exc_info.value)

    def test_frontend_log_message_min_length(self) -> None:
        """Test that message must have at least 1 character."""
        with pytest.raises(ValidationError) as exc_info:
            FrontendLogCreate(
                level="INFO",
                component="Test",
                message="",
            )
        assert "message" in str(exc_info.value)

    def test_frontend_log_message_max_length(self) -> None:
        """Test that message has max length constraint."""
        long_message = "a" * 2001  # max is 2000
        with pytest.raises(ValidationError) as exc_info:
            FrontendLogCreate(
                level="INFO",
                component="Test",
                message=long_message,
            )
        assert "message" in str(exc_info.value)


class TestAuditLogResponseConstraints:
    """Tests for AuditLogResponse schema Field constraints."""

    def test_valid_audit_log(self) -> None:
        """Test that a valid audit log passes validation."""
        log = AuditLogResponse(
            id=1,
            timestamp=datetime.now(),
            action="acknowledge",
            resource_type="event",
            actor="admin",
            status="success",
        )
        assert log.id == 1
        assert log.status == "success"

    def test_audit_log_id_must_be_positive(self) -> None:
        """Test that audit log ID must be >= 1."""
        with pytest.raises(ValidationError) as exc_info:
            AuditLogResponse(
                id=0,
                timestamp=datetime.now(),
                action="test",
                resource_type="event",
                actor="admin",
                status="success",
            )
        assert "id" in str(exc_info.value)

    def test_audit_log_action_min_length(self) -> None:
        """Test that action must have at least 1 character."""
        with pytest.raises(ValidationError) as exc_info:
            AuditLogResponse(
                id=1,
                timestamp=datetime.now(),
                action="",
                resource_type="event",
                actor="admin",
                status="success",
            )
        assert "action" in str(exc_info.value)

    def test_audit_log_status_pattern(self) -> None:
        """Test that status must be 'success' or 'failure'."""
        with pytest.raises(ValidationError) as exc_info:
            AuditLogResponse(
                id=1,
                timestamp=datetime.now(),
                action="test",
                resource_type="event",
                actor="admin",
                status="invalid",
            )
        assert "status" in str(exc_info.value)

    def test_audit_log_valid_statuses(self) -> None:
        """Test valid status values."""
        for status in ["success", "failure"]:
            log = AuditLogResponse(
                id=1,
                timestamp=datetime.now(),
                action="test",
                resource_type="event",
                actor="admin",
                status=status,
            )
            assert log.status == status

    def test_audit_log_ip_address_max_length(self) -> None:
        """Test that ip_address has max length constraint."""
        long_ip = "a" * 46  # max is 45 for IPv6
        with pytest.raises(ValidationError) as exc_info:
            AuditLogResponse(
                id=1,
                timestamp=datetime.now(),
                action="test",
                resource_type="event",
                actor="admin",
                status="success",
                ip_address=long_ip,
            )
        assert "ip_address" in str(exc_info.value)


class TestMediaErrorResponseConstraints:
    """Tests for MediaErrorResponse schema Field constraints."""

    def test_valid_media_error(self) -> None:
        """Test that a valid media error passes validation."""
        error = MediaErrorResponse(
            error="File not found",
            path="/export/foscam/front_door/image.jpg",
        )
        assert error.error == "File not found"

    def test_media_error_error_min_length(self) -> None:
        """Test that error must have at least 1 character."""
        with pytest.raises(ValidationError) as exc_info:
            MediaErrorResponse(
                error="",
                path="/path/to/file",
            )
        assert "error" in str(exc_info.value)

    def test_media_error_path_accepts_empty(self) -> None:
        """Test that path can be empty for error reporting of invalid/empty paths."""
        response = MediaErrorResponse(
            error="File not found",
            path="",
        )
        assert response.path == ""

    def test_media_error_path_max_length(self) -> None:
        """Test that path has max length constraint."""
        long_path = "/" + "a" * 4096  # max is 4096
        with pytest.raises(ValidationError) as exc_info:
            MediaErrorResponse(
                error="File not found",
                path=long_path,
            )
        assert "path" in str(exc_info.value)


class TestLogStatsConstraints:
    """Tests for LogStats schema Field constraints."""

    def test_valid_log_stats(self) -> None:
        """Test that valid log stats passes validation."""
        stats = LogStats(
            total_today=100,
            errors_today=5,
            warnings_today=10,
            by_component={"test": 50},
            by_level={"INFO": 85},
        )
        assert stats.total_today == 100

    def test_log_stats_non_negative(self) -> None:
        """Test that count fields must be >= 0."""
        with pytest.raises(ValidationError) as exc_info:
            LogStats(
                total_today=-1,
                errors_today=0,
                warnings_today=0,
                by_component={},
                by_level={},
            )
        assert "total_today" in str(exc_info.value)


class TestAuditLogStatsConstraints:
    """Tests for AuditLogStats schema Field constraints."""

    def test_valid_audit_log_stats(self) -> None:
        """Test that valid audit log stats passes validation."""
        stats = AuditLogStats(
            total_logs=1000,
            logs_today=50,
            by_action={"create": 20},
            by_resource_type={"event": 30},
            by_status={"success": 48},
            recent_actors=["admin"],
        )
        assert stats.total_logs == 1000

    def test_audit_log_stats_non_negative(self) -> None:
        """Test that count fields must be >= 0."""
        with pytest.raises(ValidationError) as exc_info:
            AuditLogStats(
                total_logs=-1,
                logs_today=0,
                by_action={},
                by_resource_type={},
                by_status={},
                recent_actors=[],
            )
        assert "total_logs" in str(exc_info.value)
