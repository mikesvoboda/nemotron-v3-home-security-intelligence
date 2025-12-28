"""Unit tests for audit logging functionality."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from backend.models.audit import AuditAction, AuditLog, AuditStatus
from backend.services.audit import AuditService


class TestAuditLogModel:
    """Tests for the AuditLog model."""

    def test_audit_log_creation(self):
        """Test creating an AuditLog instance."""
        log = AuditLog(
            timestamp=datetime.now(UTC),
            action=AuditAction.EVENT_REVIEWED.value,
            resource_type="event",
            resource_id="123",
            actor="test_user",
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
            details={"key": "value"},
            status=AuditStatus.SUCCESS.value,
        )

        assert log.action == "event_reviewed"
        assert log.resource_type == "event"
        assert log.resource_id == "123"
        assert log.actor == "test_user"
        assert log.ip_address == "192.168.1.1"
        assert log.status == "success"

    def test_audit_log_repr(self):
        """Test the string representation of AuditLog."""
        log = AuditLog(
            id=1,
            timestamp=datetime.now(UTC),
            action="event_reviewed",
            resource_type="event",
            resource_id="123",
            actor="test_user",
            status="success",
        )

        repr_str = repr(log)
        assert "AuditLog" in repr_str
        assert "event_reviewed" in repr_str
        assert "event" in repr_str
        assert "test_user" in repr_str

    def test_audit_action_enum(self):
        """Test the AuditAction enum values."""
        assert AuditAction.EVENT_REVIEWED.value == "event_reviewed"
        assert AuditAction.EVENT_DISMISSED.value == "event_dismissed"
        assert AuditAction.SETTINGS_CHANGED.value == "settings_changed"
        assert AuditAction.MEDIA_EXPORTED.value == "media_exported"
        assert AuditAction.RULE_CREATED.value == "rule_created"
        assert AuditAction.CAMERA_CREATED.value == "camera_created"
        assert AuditAction.CAMERA_UPDATED.value == "camera_updated"
        assert AuditAction.CAMERA_DELETED.value == "camera_deleted"
        assert AuditAction.LOGIN.value == "login"
        assert AuditAction.LOGOUT.value == "logout"

    def test_audit_status_enum(self):
        """Test the AuditStatus enum values."""
        assert AuditStatus.SUCCESS.value == "success"
        assert AuditStatus.FAILURE.value == "failure"


class TestAuditService:
    """Tests for the AuditService."""

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session."""
        mock_session = MagicMock()
        mock_session.add = MagicMock()
        mock_session.flush = MagicMock()
        return mock_session

    @pytest.fixture
    def mock_request(self):
        """Create a mock FastAPI request."""
        mock_req = MagicMock()
        mock_req.client = MagicMock()
        mock_req.client.host = "127.0.0.1"
        # Use MagicMock for headers to allow setting .get
        mock_headers = MagicMock()
        mock_headers.get = lambda key, default=None: {
            "user-agent": "TestBrowser/1.0",
            "x-forwarded-for": None,
        }.get(key, default)
        mock_req.headers = mock_headers
        return mock_req

    @pytest.mark.asyncio
    async def test_log_action_with_enum(self, mock_db_session, mock_request):
        """Test logging an audit action with enum values."""
        # Make flush async
        mock_db_session.flush = MagicMock()

        async def async_flush():
            mock_db_session.flush()

        mock_db_session.flush = async_flush

        result = await AuditService.log_action(
            db=mock_db_session,
            action=AuditAction.EVENT_REVIEWED,
            resource_type="event",
            resource_id="123",
            actor="test_user",
            details={"test": "data"},
            request=mock_request,
            status=AuditStatus.SUCCESS,
        )

        assert result.action == "event_reviewed"
        assert result.resource_type == "event"
        assert result.resource_id == "123"
        assert result.actor == "test_user"
        assert result.status == "success"
        assert result.ip_address == "127.0.0.1"
        assert result.user_agent == "TestBrowser/1.0"

    @pytest.mark.asyncio
    async def test_log_action_with_string(self, mock_db_session, mock_request):
        """Test logging an audit action with string values."""

        async def async_flush():
            pass

        mock_db_session.flush = async_flush

        result = await AuditService.log_action(
            db=mock_db_session,
            action="custom_action",
            resource_type="custom_resource",
            actor="system",
            status="success",
        )

        assert result.action == "custom_action"
        assert result.resource_type == "custom_resource"
        assert result.actor == "system"

    @pytest.mark.asyncio
    async def test_log_action_extracts_forwarded_ip(self, mock_db_session):
        """Test that X-Forwarded-For header is used for IP extraction."""

        async def async_flush():
            pass

        mock_db_session.flush = async_flush

        mock_req = MagicMock()
        mock_req.client = MagicMock()
        mock_req.client.host = "10.0.0.1"
        mock_req.headers = MagicMock()
        mock_req.headers.get = lambda key, default=None: {
            "x-forwarded-for": "203.0.113.50, 10.0.0.1",
            "user-agent": "TestBrowser/1.0",
        }.get(key, default)

        result = await AuditService.log_action(
            db=mock_db_session,
            action=AuditAction.CAMERA_CREATED,
            resource_type="camera",
            actor="anonymous",
            request=mock_req,
        )

        # Should use first IP from X-Forwarded-For
        assert result.ip_address == "203.0.113.50"

    @pytest.mark.asyncio
    async def test_log_action_without_request(self, mock_db_session):
        """Test logging without a request object."""

        async def async_flush():
            pass

        mock_db_session.flush = async_flush

        result = await AuditService.log_action(
            db=mock_db_session,
            action=AuditAction.SETTINGS_CHANGED,
            resource_type="settings",
            actor="system",
        )

        assert result.ip_address is None
        assert result.user_agent is None


@pytest.mark.skipif(
    "CI" not in __import__("os").environ,
    reason="Database tests require PostgreSQL - run in CI or with TEST_DATABASE_URL set",
)
class TestAuditServiceDatabase:
    """Integration tests for AuditService with real database."""

    @pytest.mark.asyncio
    async def test_log_and_retrieve_audit(self, test_db):
        """Test logging and retrieving audit entries from database."""
        async with test_db() as session:
            # Log an action
            await AuditService.log_action(
                db=session,
                action=AuditAction.CAMERA_CREATED,
                resource_type="camera",
                resource_id="test-camera-1",
                actor="test_user",
                details={"name": "Test Camera"},
            )
            await session.commit()

            # Retrieve the logs
            logs, count = await AuditService.get_audit_logs(
                db=session,
                action="camera_created",
            )

            assert count >= 1
            assert any(log.resource_id == "test-camera-1" for log in logs)

    @pytest.mark.asyncio
    async def test_get_audit_logs_with_filters(self, test_db):
        """Test filtering audit logs."""
        async with test_db() as session:
            # Create multiple audit logs
            for i in range(5):
                await AuditService.log_action(
                    db=session,
                    action=AuditAction.EVENT_REVIEWED
                    if i % 2 == 0
                    else AuditAction.EVENT_DISMISSED,
                    resource_type="event",
                    resource_id=f"event-{i}",
                    actor="test_user" if i < 3 else "other_user",
                )
            await session.commit()

            # Filter by action
            logs, _count = await AuditService.get_audit_logs(
                db=session,
                action="event_reviewed",
            )
            assert all(log.action == "event_reviewed" for log in logs)

            # Filter by actor
            logs, _count = await AuditService.get_audit_logs(
                db=session,
                actor="test_user",
            )
            assert all(log.actor == "test_user" for log in logs)

    @pytest.mark.asyncio
    async def test_get_audit_logs_pagination(self, test_db):
        """Test pagination of audit logs."""
        async with test_db() as session:
            # Create 10 audit logs
            for i in range(10):
                await AuditService.log_action(
                    db=session,
                    action=AuditAction.CAMERA_UPDATED,
                    resource_type="camera",
                    resource_id=f"camera-{i}",
                    actor="system",
                )
            await session.commit()

            # Test pagination
            logs_page1, total = await AuditService.get_audit_logs(
                db=session,
                action="camera_updated",
                limit=5,
                offset=0,
            )
            assert len(logs_page1) == 5 or len(logs_page1) == total

            if total > 5:
                logs_page2, _ = await AuditService.get_audit_logs(
                    db=session,
                    action="camera_updated",
                    limit=5,
                    offset=5,
                )
                # Ensure no overlap
                page1_ids = {log.id for log in logs_page1}
                page2_ids = {log.id for log in logs_page2}
                assert page1_ids.isdisjoint(page2_ids)

    @pytest.mark.asyncio
    async def test_get_audit_log_by_id(self, test_db):
        """Test retrieving a specific audit log by ID."""
        async with test_db() as session:
            # Create an audit log
            log = await AuditService.log_action(
                db=session,
                action=AuditAction.MEDIA_EXPORTED,
                resource_type="event",
                actor="test_user",
                details={"filename": "export.csv"},
            )
            await session.commit()

            # Retrieve by ID
            retrieved = await AuditService.get_audit_log_by_id(db=session, audit_id=log.id)

            assert retrieved is not None
            assert retrieved.id == log.id
            assert retrieved.action == "media_exported"

    @pytest.mark.asyncio
    async def test_get_audit_log_by_id_not_found(self, test_db):
        """Test retrieving a non-existent audit log."""
        async with test_db() as session:
            result = await AuditService.get_audit_log_by_id(db=session, audit_id=99999)
            assert result is None
