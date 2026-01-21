"""Unit tests for schema Field constraints.

Tests for validating that Pydantic schemas have proper Field constraints
including min_length, max_length, ge/le bounds, patterns, and examples.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from backend.api.schemas.audit import AuditLogResponse, AuditLogStats
from backend.api.schemas.media import MediaErrorResponse


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

    @pytest.mark.parametrize("status", ["success", "failure"])
    def test_audit_log_valid_statuses(self, status: str) -> None:
        """Test valid status values."""
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
