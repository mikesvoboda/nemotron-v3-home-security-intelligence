"""Unit tests for SecurityAuditLogger service (NEM-1616).

This module provides comprehensive tests for:
- SecurityAuditLogger: High-level audit logging service
- Rate limit violation logging
- Content-Type rejection logging
- File magic number rejection logging
- Configuration change logging
- Bulk export logging
- Cleanup operation logging
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.models.audit import AuditAction, AuditStatus
from backend.services.audit_logger import (
    SecurityAuditLogger,
    _serialize_value,
    audit_logger,
    get_audit_logger,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    return db


@pytest.fixture
def mock_request():
    """Create a mock FastAPI request."""
    # Create a simple mock without spec to allow attribute assignment
    request = MagicMock()
    request.client.host = "192.168.1.100"
    request.url.path = "/api/test"
    request.method = "POST"
    request.headers.get.return_value = None
    request.query_params.get.return_value = None
    return request


@pytest.fixture
def audit_logger_instance():
    """Get a fresh audit logger instance."""
    return SecurityAuditLogger()


# =============================================================================
# SecurityAuditLogger Tests
# =============================================================================


class TestSecurityAuditLogger:
    """Tests for SecurityAuditLogger class."""

    def test_initialization(self, audit_logger_instance):
        """Test audit logger initializes correctly."""
        assert audit_logger_instance._audit_service is not None

    @pytest.mark.asyncio
    async def test_log_rate_limit_exceeded(self, audit_logger_instance, mock_db, mock_request):
        """Test logging rate limit exceeded event."""
        with patch.object(
            audit_logger_instance._audit_service,
            "log_action",
            new_callable=AsyncMock,
        ) as mock_log:
            mock_log.return_value = MagicMock(id=1)

            await audit_logger_instance.log_rate_limit_exceeded(
                db=mock_db,
                request=mock_request,
                tier="default",
                current_count=65,
                limit=60,
            )

            mock_log.assert_called_once()
            call_kwargs = mock_log.call_args[1]

            assert call_kwargs["action"] == AuditAction.RATE_LIMIT_EXCEEDED
            assert call_kwargs["resource_type"] == "api"
            assert call_kwargs["status"] == AuditStatus.FAILURE
            assert call_kwargs["details"]["tier"] == "default"
            assert call_kwargs["details"]["current_count"] == 65
            assert call_kwargs["details"]["limit"] == 60
            assert call_kwargs["details"]["path"] == "/api/test"
            assert call_kwargs["details"]["method"] == "POST"

    @pytest.mark.asyncio
    async def test_log_rate_limit_exceeded_without_request(self, audit_logger_instance, mock_db):
        """Test logging rate limit exceeded without request context."""
        with patch.object(
            audit_logger_instance._audit_service,
            "log_action",
            new_callable=AsyncMock,
        ) as mock_log:
            mock_log.return_value = MagicMock(id=1)

            await audit_logger_instance.log_rate_limit_exceeded(
                db=mock_db,
                request=None,
                tier="media",
                current_count=130,
                limit=120,
                client_ip="10.0.0.1",
            )

            mock_log.assert_called_once()
            call_kwargs = mock_log.call_args[1]

            assert call_kwargs["action"] == AuditAction.RATE_LIMIT_EXCEEDED
            assert "10.xxx.xxx.xxx" in call_kwargs["actor"]  # IP should be masked

    @pytest.mark.asyncio
    async def test_log_content_type_rejected(self, audit_logger_instance, mock_db, mock_request):
        """Test logging Content-Type rejection event."""
        with patch.object(
            audit_logger_instance._audit_service,
            "log_action",
            new_callable=AsyncMock,
        ) as mock_log:
            mock_log.return_value = MagicMock(id=1)

            await audit_logger_instance.log_content_type_rejected(
                db=mock_db,
                request=mock_request,
                content_type="text/plain",
            )

            mock_log.assert_called_once()
            call_kwargs = mock_log.call_args[1]

            assert call_kwargs["action"] == AuditAction.CONTENT_TYPE_REJECTED
            assert call_kwargs["resource_type"] == "api"
            assert call_kwargs["status"] == AuditStatus.FAILURE
            assert call_kwargs["details"]["content_type"] == "text/plain"
            assert call_kwargs["details"]["path"] == "/api/test"

    @pytest.mark.asyncio
    async def test_log_content_type_rejected_without_request(self, audit_logger_instance, mock_db):
        """Test logging Content-Type rejection without request context."""
        with patch.object(
            audit_logger_instance._audit_service,
            "log_action",
            new_callable=AsyncMock,
        ) as mock_log:
            mock_log.return_value = MagicMock(id=1)

            await audit_logger_instance.log_content_type_rejected(
                db=mock_db,
                request=None,
                content_type="application/xml",
                path="/api/create",
                method="PUT",
            )

            mock_log.assert_called_once()
            call_kwargs = mock_log.call_args[1]

            assert call_kwargs["details"]["content_type"] == "application/xml"
            assert call_kwargs["details"]["path"] == "/api/create"
            assert call_kwargs["details"]["method"] == "PUT"

    @pytest.mark.asyncio
    async def test_log_file_magic_rejected(self, audit_logger_instance, mock_db, mock_request):
        """Test logging file magic rejection event."""
        with patch.object(
            audit_logger_instance._audit_service,
            "log_action",
            new_callable=AsyncMock,
        ) as mock_log:
            mock_log.return_value = MagicMock(id=1)

            await audit_logger_instance.log_file_magic_rejected(
                db=mock_db,
                request=mock_request,
                claimed_type="image/png",
                detected_type="image/jpeg",
                filename="malicious.png",
            )

            mock_log.assert_called_once()
            call_kwargs = mock_log.call_args[1]

            assert call_kwargs["action"] == AuditAction.FILE_MAGIC_REJECTED
            assert call_kwargs["resource_type"] == "upload"
            assert call_kwargs["resource_id"] == "malicious.png"
            assert call_kwargs["status"] == AuditStatus.FAILURE
            assert call_kwargs["details"]["claimed_type"] == "image/png"
            assert call_kwargs["details"]["detected_type"] == "image/jpeg"

    @pytest.mark.asyncio
    async def test_log_file_magic_rejected_unknown_type(
        self, audit_logger_instance, mock_db, mock_request
    ):
        """Test logging file magic rejection with unknown detected type."""
        with patch.object(
            audit_logger_instance._audit_service,
            "log_action",
            new_callable=AsyncMock,
        ) as mock_log:
            mock_log.return_value = MagicMock(id=1)

            await audit_logger_instance.log_file_magic_rejected(
                db=mock_db,
                request=mock_request,
                claimed_type="image/png",
                detected_type=None,
                filename="unknown.exe",
            )

            mock_log.assert_called_once()
            call_kwargs = mock_log.call_args[1]

            assert call_kwargs["details"]["detected_type"] is None

    @pytest.mark.asyncio
    async def test_log_config_change(self, audit_logger_instance, mock_db, mock_request):
        """Test logging configuration change event."""
        with patch.object(
            audit_logger_instance._audit_service,
            "log_action",
            new_callable=AsyncMock,
        ) as mock_log:
            mock_log.return_value = MagicMock(id=1)

            await audit_logger_instance.log_config_change(
                db=mock_db,
                request=mock_request,
                setting_name="batch_window_seconds",
                old_value=90,
                new_value=120,
            )

            mock_log.assert_called_once()
            call_kwargs = mock_log.call_args[1]

            assert call_kwargs["action"] == AuditAction.CONFIG_UPDATED
            assert call_kwargs["resource_type"] == "settings"
            assert call_kwargs["status"] == AuditStatus.SUCCESS
            assert call_kwargs["details"]["setting"] == "batch_window_seconds"
            assert call_kwargs["details"]["old_value"] == 90
            assert call_kwargs["details"]["new_value"] == 120
            assert "timestamp" in call_kwargs["details"]

    @pytest.mark.asyncio
    async def test_log_config_change_with_resource_id(
        self, audit_logger_instance, mock_db, mock_request
    ):
        """Test logging configuration change with resource ID."""
        with patch.object(
            audit_logger_instance._audit_service,
            "log_action",
            new_callable=AsyncMock,
        ) as mock_log:
            mock_log.return_value = MagicMock(id=1)

            await audit_logger_instance.log_config_change(
                db=mock_db,
                request=mock_request,
                setting_name="sensitivity",
                old_value="medium",
                new_value="high",
                resource_id="camera_front_door",
            )

            mock_log.assert_called_once()
            call_kwargs = mock_log.call_args[1]

            assert call_kwargs["resource_id"] == "camera_front_door"

    @pytest.mark.asyncio
    async def test_log_security_alert(self, audit_logger_instance, mock_db, mock_request):
        """Test logging general security alert."""
        with patch.object(
            audit_logger_instance._audit_service,
            "log_action",
            new_callable=AsyncMock,
        ) as mock_log:
            mock_log.return_value = MagicMock(id=1)

            await audit_logger_instance.log_security_alert(
                db=mock_db,
                request=mock_request,
                alert_type="suspicious_activity",
                details={"ip_count": 100, "duration_seconds": 60},
                severity="high",
            )

            mock_log.assert_called_once()
            call_kwargs = mock_log.call_args[1]

            assert call_kwargs["action"] == AuditAction.SECURITY_ALERT
            assert call_kwargs["resource_type"] == "security"
            assert call_kwargs["status"] == AuditStatus.FAILURE
            assert call_kwargs["details"]["alert_type"] == "suspicious_activity"
            assert call_kwargs["details"]["severity"] == "high"
            assert call_kwargs["details"]["ip_count"] == 100

    @pytest.mark.asyncio
    async def test_log_bulk_export(self, audit_logger_instance, mock_db, mock_request):
        """Test logging bulk export operation."""
        with patch.object(
            audit_logger_instance._audit_service,
            "log_action",
            new_callable=AsyncMock,
        ) as mock_log:
            mock_log.return_value = MagicMock(id=1)

            await audit_logger_instance.log_bulk_export(
                db=mock_db,
                request=mock_request,
                export_type="events",
                record_count=1500,
                filters={"camera_id": "front_door", "date_range": "2024-01-01 to 2024-01-31"},
            )

            mock_log.assert_called_once()
            call_kwargs = mock_log.call_args[1]

            assert call_kwargs["action"] == AuditAction.BULK_EXPORT_COMPLETED
            assert call_kwargs["resource_type"] == "events"
            assert call_kwargs["status"] == AuditStatus.SUCCESS
            assert call_kwargs["details"]["record_count"] == 1500
            assert call_kwargs["details"]["filters"]["camera_id"] == "front_door"

    @pytest.mark.asyncio
    async def test_log_bulk_export_no_filters(self, audit_logger_instance, mock_db, mock_request):
        """Test logging bulk export without filters."""
        with patch.object(
            audit_logger_instance._audit_service,
            "log_action",
            new_callable=AsyncMock,
        ) as mock_log:
            mock_log.return_value = MagicMock(id=1)

            await audit_logger_instance.log_bulk_export(
                db=mock_db,
                request=mock_request,
                export_type="detections",
                record_count=500,
            )

            mock_log.assert_called_once()
            call_kwargs = mock_log.call_args[1]

            assert call_kwargs["details"]["filters"] == {}

    @pytest.mark.asyncio
    async def test_log_cleanup_executed(self, audit_logger_instance, mock_db, mock_request):
        """Test logging cleanup operation."""
        with patch.object(
            audit_logger_instance._audit_service,
            "log_action",
            new_callable=AsyncMock,
        ) as mock_log:
            mock_log.return_value = MagicMock(id=1)

            await audit_logger_instance.log_cleanup_executed(
                db=mock_db,
                request=mock_request,
                dry_run=False,
                deleted_counts={"events": 100, "detections": 500, "logs": 1000},
                freed_bytes=1024 * 1024 * 50,  # 50MB
            )

            mock_log.assert_called_once()
            call_kwargs = mock_log.call_args[1]

            assert call_kwargs["action"] == AuditAction.CLEANUP_EXECUTED
            assert call_kwargs["resource_type"] == "system"
            assert call_kwargs["status"] == AuditStatus.SUCCESS
            assert call_kwargs["details"]["dry_run"] is False
            assert call_kwargs["details"]["deleted_counts"]["events"] == 100
            assert call_kwargs["details"]["freed_bytes"] == 52428800

    @pytest.mark.asyncio
    async def test_log_cleanup_executed_dry_run(self, audit_logger_instance, mock_db, mock_request):
        """Test logging cleanup dry run."""
        with patch.object(
            audit_logger_instance._audit_service,
            "log_action",
            new_callable=AsyncMock,
        ) as mock_log:
            mock_log.return_value = MagicMock(id=1)

            await audit_logger_instance.log_cleanup_executed(
                db=mock_db,
                request=mock_request,
                dry_run=True,
                deleted_counts={"events": 50},
            )

            mock_log.assert_called_once()
            call_kwargs = mock_log.call_args[1]

            assert call_kwargs["details"]["dry_run"] is True


# =============================================================================
# _serialize_value Tests
# =============================================================================


class TestSerializeValue:
    """Tests for _serialize_value helper function."""

    def test_serialize_none(self):
        """Test serializing None."""
        assert _serialize_value(None) is None

    def test_serialize_string(self):
        """Test serializing string."""
        assert _serialize_value("test") == "test"

    def test_serialize_int(self):
        """Test serializing integer."""
        assert _serialize_value(42) == 42

    def test_serialize_float(self):
        """Test serializing float."""
        assert _serialize_value(3.14) == 3.14

    def test_serialize_bool(self):
        """Test serializing boolean."""
        assert _serialize_value(True) is True
        assert _serialize_value(False) is False

    def test_serialize_list(self):
        """Test serializing list."""
        assert _serialize_value([1, 2, "three"]) == [1, 2, "three"]

    def test_serialize_nested_list(self):
        """Test serializing nested list."""
        assert _serialize_value([1, [2, 3]]) == [1, [2, 3]]

    def test_serialize_dict(self):
        """Test serializing dict."""
        assert _serialize_value({"key": "value", "num": 42}) == {"key": "value", "num": 42}

    def test_serialize_nested_dict(self):
        """Test serializing nested dict."""
        result = _serialize_value({"outer": {"inner": "value"}})
        assert result == {"outer": {"inner": "value"}}

    def test_serialize_datetime(self):
        """Test serializing datetime converts to string."""
        dt = datetime(2024, 1, 15, 12, 30, 0, tzinfo=UTC)
        result = _serialize_value(dt)
        assert isinstance(result, str)
        assert "2024" in result

    def test_serialize_custom_object(self):
        """Test serializing custom object converts to string."""

        class CustomObject:
            def __str__(self):
                return "custom_value"

        result = _serialize_value(CustomObject())
        assert result == "custom_value"


# =============================================================================
# Singleton and Factory Tests
# =============================================================================


class TestAuditLoggerSingleton:
    """Tests for audit logger singleton pattern."""

    def test_singleton_instance(self):
        """Test that audit_logger is a singleton."""
        assert audit_logger is not None
        assert isinstance(audit_logger, SecurityAuditLogger)

    def test_get_audit_logger_returns_singleton(self):
        """Test get_audit_logger returns the singleton."""
        logger = get_audit_logger()
        assert logger is audit_logger

    def test_get_audit_logger_multiple_calls(self):
        """Test multiple calls return same instance."""
        logger1 = get_audit_logger()
        logger2 = get_audit_logger()
        assert logger1 is logger2


# =============================================================================
# AuditAction Enum Tests (NEM-1616 additions)
# =============================================================================


class TestAuditActionEnum:
    """Tests for new AuditAction enum values."""

    def test_rate_limit_exceeded_action(self):
        """Test RATE_LIMIT_EXCEEDED action exists."""
        assert AuditAction.RATE_LIMIT_EXCEEDED.value == "rate_limit_exceeded"

    def test_security_alert_action(self):
        """Test SECURITY_ALERT action exists."""
        assert AuditAction.SECURITY_ALERT.value == "security_alert"

    def test_content_type_rejected_action(self):
        """Test CONTENT_TYPE_REJECTED action exists."""
        assert AuditAction.CONTENT_TYPE_REJECTED.value == "content_type_rejected"

    def test_file_magic_rejected_action(self):
        """Test FILE_MAGIC_REJECTED action exists."""
        assert AuditAction.FILE_MAGIC_REJECTED.value == "file_magic_rejected"

    def test_bulk_export_completed_action(self):
        """Test BULK_EXPORT_COMPLETED action exists."""
        assert AuditAction.BULK_EXPORT_COMPLETED.value == "bulk_export_completed"

    def test_cleanup_executed_action(self):
        """Test CLEANUP_EXECUTED action exists."""
        assert AuditAction.CLEANUP_EXECUTED.value == "cleanup_executed"

    def test_zone_actions(self):
        """Test zone-related actions exist."""
        assert AuditAction.ZONE_CREATED.value == "zone_created"
        assert AuditAction.ZONE_UPDATED.value == "zone_updated"
        assert AuditAction.ZONE_DELETED.value == "zone_deleted"


# =============================================================================
# Audit Failure Doesn't Block Operation Tests (NEM-2541)
# =============================================================================


class TestAuditFailureDoesNotBlockOperations:
    """Tests verifying audit log failures don't block main operations (NEM-2541).

    These tests ensure that when an audit log write fails:
    1. The failure is logged at WARNING level with full context
    2. The main operation continues to completion
    3. No exception is raised to the caller
    """

    @pytest.mark.asyncio
    async def test_log_rate_limit_continues_on_audit_failure(
        self, audit_logger_instance, mock_db, mock_request
    ):
        """Test log_rate_limit_exceeded completes even when audit fails."""
        with patch.object(
            audit_logger_instance._audit_service,
            "log_action",
            new_callable=AsyncMock,
        ) as mock_log:
            mock_log.side_effect = Exception("Database connection lost")

            # Should NOT raise an exception
            await audit_logger_instance.log_rate_limit_exceeded(
                db=mock_db,
                request=mock_request,
                tier="default",
                current_count=65,
                limit=60,
            )

            # log_action was called and raised, but method completed
            mock_log.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_content_type_continues_on_audit_failure(
        self, audit_logger_instance, mock_db, mock_request
    ):
        """Test log_content_type_rejected completes even when audit fails."""
        with patch.object(
            audit_logger_instance._audit_service,
            "log_action",
            new_callable=AsyncMock,
        ) as mock_log:
            mock_log.side_effect = RuntimeError("Connection timeout")

            # Should NOT raise an exception
            await audit_logger_instance.log_content_type_rejected(
                db=mock_db,
                request=mock_request,
                content_type="text/plain",
            )

            mock_log.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_file_magic_continues_on_audit_failure(
        self, audit_logger_instance, mock_db, mock_request
    ):
        """Test log_file_magic_rejected completes even when audit fails."""
        with patch.object(
            audit_logger_instance._audit_service,
            "log_action",
            new_callable=AsyncMock,
        ) as mock_log:
            mock_log.side_effect = OSError("Disk full")

            # Should NOT raise an exception
            await audit_logger_instance.log_file_magic_rejected(
                db=mock_db,
                request=mock_request,
                claimed_type="image/png",
                detected_type="application/pdf",
                filename="malicious.png",
            )

            mock_log.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_config_change_continues_on_audit_failure(
        self, audit_logger_instance, mock_db, mock_request
    ):
        """Test log_config_change completes even when audit fails."""
        with patch.object(
            audit_logger_instance._audit_service,
            "log_action",
            new_callable=AsyncMock,
        ) as mock_log:
            mock_log.side_effect = ValueError("Invalid data")

            # Should NOT raise an exception
            await audit_logger_instance.log_config_change(
                db=mock_db,
                request=mock_request,
                setting_name="batch_window_seconds",
                old_value=90,
                new_value=120,
            )

            mock_log.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_security_alert_continues_on_audit_failure(
        self, audit_logger_instance, mock_db, mock_request
    ):
        """Test log_security_alert completes even when audit fails."""
        with patch.object(
            audit_logger_instance._audit_service,
            "log_action",
            new_callable=AsyncMock,
        ) as mock_log:
            mock_log.side_effect = ConnectionError("Network unreachable")

            # Should NOT raise an exception
            await audit_logger_instance.log_security_alert(
                db=mock_db,
                request=mock_request,
                alert_type="brute_force_attempt",
                details={"attempts": 100},
                severity="high",
            )

            mock_log.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_bulk_export_continues_on_audit_failure(
        self, audit_logger_instance, mock_db, mock_request
    ):
        """Test log_bulk_export completes even when audit fails."""
        with patch.object(
            audit_logger_instance._audit_service,
            "log_action",
            new_callable=AsyncMock,
        ) as mock_log:
            mock_log.side_effect = TimeoutError("Query timed out")

            # Should NOT raise an exception
            await audit_logger_instance.log_bulk_export(
                db=mock_db,
                request=mock_request,
                export_type="events",
                record_count=1000,
                filters={"camera_id": "front_door"},
            )

            mock_log.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_cleanup_executed_continues_on_audit_failure(
        self, audit_logger_instance, mock_db, mock_request
    ):
        """Test log_cleanup_executed completes even when audit fails."""
        with patch.object(
            audit_logger_instance._audit_service,
            "log_action",
            new_callable=AsyncMock,
        ) as mock_log:
            mock_log.side_effect = PermissionError("Access denied")

            # Should NOT raise an exception
            await audit_logger_instance.log_cleanup_executed(
                db=mock_db,
                request=mock_request,
                dry_run=False,
                deleted_counts={"events": 50, "detections": 200},
                freed_bytes=1024 * 1024 * 10,
            )

            mock_log.assert_called_once()

    @pytest.mark.asyncio
    async def test_audit_failure_logs_warning_with_full_context(
        self, audit_logger_instance, mock_db, mock_request
    ):
        """Test that audit failures are logged with full context (NEM-2541)."""
        with (
            patch.object(
                audit_logger_instance._audit_service,
                "log_action",
                new_callable=AsyncMock,
            ) as mock_log,
            patch("backend.services.audit_logger.logger.warning") as mock_warning,
        ):
            mock_log.side_effect = Exception("Database error")

            await audit_logger_instance.log_rate_limit_exceeded(
                db=mock_db,
                request=mock_request,
                tier="default",
                current_count=65,
                limit=60,
            )

            # Verify warning was called with full context
            mock_warning.assert_called()
            call_args = mock_warning.call_args
            assert call_args[0][0] == "Audit log write failed"
            extra = call_args[1]["extra"]
            assert "action" in extra
            assert "resource_type" in extra
            assert "error_type" in extra
            assert "error_message" in extra
            assert extra["error_type"] == "Exception"
            assert extra["error_message"] == "Database error"
