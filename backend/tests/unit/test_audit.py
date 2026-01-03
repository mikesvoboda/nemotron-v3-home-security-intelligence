"""Unit tests for audit logging functionality.

These tests use mocked database sessions and do not require a real database.
For integration tests with a real database, see backend/tests/integration/test_audit.py
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
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


class TestAuditAction:
    """Tests for the AuditAction enum."""

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


class TestAuditStatus:
    """Tests for the AuditStatus enum."""

    def test_audit_status_enum(self):
        """Test the AuditStatus enum values."""
        assert AuditStatus.SUCCESS.value == "success"
        assert AuditStatus.FAILURE.value == "failure"


class TestAuditService:
    """Tests for the AuditService using mocked database sessions."""

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session with spec to prevent mocking non-existent attributes."""
        from sqlalchemy.ext.asyncio import AsyncSession

        mock_session = MagicMock(spec=AsyncSession)
        mock_session.add = MagicMock()
        mock_session.flush = MagicMock()
        return mock_session

    @pytest.fixture
    def mock_request(self):
        """Create a mock FastAPI request.

        Note: We don't use spec=Request here because Request has complex nested
        attributes (client.host, headers.get) that are difficult to mock with spec.
        The test focuses on the AuditService behavior, not Request validation.
        """
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

    @pytest.mark.asyncio
    async def test_get_audit_logs_no_filters(self, mock_db_session):
        """Test get_audit_logs with no filters returns all logs."""
        # Create mock audit logs
        mock_logs = [
            AuditLog(
                id=1,
                timestamp=datetime.now(UTC),
                action="event_reviewed",
                resource_type="event",
                resource_id="123",
                actor="test_user",
                status="success",
            ),
            AuditLog(
                id=2,
                timestamp=datetime.now(UTC),
                action="camera_created",
                resource_type="camera",
                resource_id="456",
                actor="admin",
                status="success",
            ),
        ]

        # Mock the count query result
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 2

        # Mock the logs query result
        mock_logs_result = MagicMock()
        mock_logs_scalars = MagicMock()
        mock_logs_scalars.all.return_value = mock_logs
        mock_logs_result.scalars.return_value = mock_logs_scalars

        # Setup execute to return different results for count and main query
        call_count = [0]

        async def mock_execute(query):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_count_result
            return mock_logs_result

        mock_db_session.execute = mock_execute

        logs, total = await AuditService.get_audit_logs(db=mock_db_session)

        assert total == 2
        assert len(logs) == 2
        assert logs[0].action == "event_reviewed"
        assert logs[1].action == "camera_created"

    @pytest.mark.asyncio
    async def test_get_audit_logs_with_action_filter(self, mock_db_session):
        """Test get_audit_logs filtered by action."""
        mock_logs = [
            AuditLog(
                id=1,
                timestamp=datetime.now(UTC),
                action="event_reviewed",
                resource_type="event",
                resource_id="123",
                actor="test_user",
                status="success",
            ),
        ]

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1

        mock_logs_result = MagicMock()
        mock_logs_scalars = MagicMock()
        mock_logs_scalars.all.return_value = mock_logs
        mock_logs_result.scalars.return_value = mock_logs_scalars

        call_count = [0]

        async def mock_execute(query):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_count_result
            return mock_logs_result

        mock_db_session.execute = mock_execute

        logs, total = await AuditService.get_audit_logs(db=mock_db_session, action="event_reviewed")

        assert total == 1
        assert len(logs) == 1
        assert logs[0].action == "event_reviewed"

    @pytest.mark.asyncio
    async def test_get_audit_logs_with_resource_type_filter(self, mock_db_session):
        """Test get_audit_logs filtered by resource_type."""
        mock_logs = [
            AuditLog(
                id=1,
                timestamp=datetime.now(UTC),
                action="camera_created",
                resource_type="camera",
                resource_id="cam-1",
                actor="admin",
                status="success",
            ),
        ]

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1

        mock_logs_result = MagicMock()
        mock_logs_scalars = MagicMock()
        mock_logs_scalars.all.return_value = mock_logs
        mock_logs_result.scalars.return_value = mock_logs_scalars

        call_count = [0]

        async def mock_execute(query):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_count_result
            return mock_logs_result

        mock_db_session.execute = mock_execute

        logs, total = await AuditService.get_audit_logs(db=mock_db_session, resource_type="camera")

        assert total == 1
        assert logs[0].resource_type == "camera"

    @pytest.mark.asyncio
    async def test_get_audit_logs_with_resource_id_filter(self, mock_db_session):
        """Test get_audit_logs filtered by resource_id."""
        mock_logs = [
            AuditLog(
                id=1,
                timestamp=datetime.now(UTC),
                action="event_reviewed",
                resource_type="event",
                resource_id="specific-event-123",
                actor="test_user",
                status="success",
            ),
        ]

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1

        mock_logs_result = MagicMock()
        mock_logs_scalars = MagicMock()
        mock_logs_scalars.all.return_value = mock_logs
        mock_logs_result.scalars.return_value = mock_logs_scalars

        call_count = [0]

        async def mock_execute(query):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_count_result
            return mock_logs_result

        mock_db_session.execute = mock_execute

        logs, total = await AuditService.get_audit_logs(
            db=mock_db_session, resource_id="specific-event-123"
        )

        assert total == 1
        assert logs[0].resource_id == "specific-event-123"

    @pytest.mark.asyncio
    async def test_get_audit_logs_with_actor_filter(self, mock_db_session):
        """Test get_audit_logs filtered by actor."""
        mock_logs = [
            AuditLog(
                id=1,
                timestamp=datetime.now(UTC),
                action="settings_changed",
                resource_type="settings",
                resource_id=None,
                actor="admin_user",
                status="success",
            ),
        ]

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1

        mock_logs_result = MagicMock()
        mock_logs_scalars = MagicMock()
        mock_logs_scalars.all.return_value = mock_logs
        mock_logs_result.scalars.return_value = mock_logs_scalars

        call_count = [0]

        async def mock_execute(query):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_count_result
            return mock_logs_result

        mock_db_session.execute = mock_execute

        logs, total = await AuditService.get_audit_logs(db=mock_db_session, actor="admin_user")

        assert total == 1
        assert logs[0].actor == "admin_user"

    @pytest.mark.asyncio
    async def test_get_audit_logs_with_status_filter(self, mock_db_session):
        """Test get_audit_logs filtered by status."""
        mock_logs = [
            AuditLog(
                id=1,
                timestamp=datetime.now(UTC),
                action="login",
                resource_type="auth",
                resource_id=None,
                actor="test_user",
                status="failure",
            ),
        ]

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1

        mock_logs_result = MagicMock()
        mock_logs_scalars = MagicMock()
        mock_logs_scalars.all.return_value = mock_logs
        mock_logs_result.scalars.return_value = mock_logs_scalars

        call_count = [0]

        async def mock_execute(query):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_count_result
            return mock_logs_result

        mock_db_session.execute = mock_execute

        logs, total = await AuditService.get_audit_logs(db=mock_db_session, status="failure")

        assert total == 1
        assert logs[0].status == "failure"

    @pytest.mark.asyncio
    async def test_get_audit_logs_with_date_range_filter(self, mock_db_session):
        """Test get_audit_logs filtered by date range."""
        now = datetime.now(UTC)
        mock_logs = [
            AuditLog(
                id=1,
                timestamp=now - timedelta(hours=1),
                action="event_reviewed",
                resource_type="event",
                resource_id="123",
                actor="test_user",
                status="success",
            ),
        ]

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1

        mock_logs_result = MagicMock()
        mock_logs_scalars = MagicMock()
        mock_logs_scalars.all.return_value = mock_logs
        mock_logs_result.scalars.return_value = mock_logs_scalars

        call_count = [0]

        async def mock_execute(query):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_count_result
            return mock_logs_result

        mock_db_session.execute = mock_execute

        start_date = now - timedelta(days=1)
        end_date = now + timedelta(days=1)

        logs, total = await AuditService.get_audit_logs(
            db=mock_db_session, start_date=start_date, end_date=end_date
        )

        assert total == 1
        assert len(logs) == 1

    @pytest.mark.asyncio
    async def test_get_audit_logs_with_pagination(self, mock_db_session):
        """Test get_audit_logs with pagination (limit and offset)."""
        mock_logs = [
            AuditLog(
                id=6,
                timestamp=datetime.now(UTC),
                action="event_reviewed",
                resource_type="event",
                resource_id="6",
                actor="test_user",
                status="success",
            ),
        ]

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 10  # Total of 10 records

        mock_logs_result = MagicMock()
        mock_logs_scalars = MagicMock()
        mock_logs_scalars.all.return_value = mock_logs
        mock_logs_result.scalars.return_value = mock_logs_scalars

        call_count = [0]

        async def mock_execute(query):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_count_result
            return mock_logs_result

        mock_db_session.execute = mock_execute

        logs, total = await AuditService.get_audit_logs(db=mock_db_session, limit=5, offset=5)

        assert total == 10
        assert len(logs) == 1  # Only 1 mock log returned

    @pytest.mark.asyncio
    async def test_get_audit_logs_empty_result(self, mock_db_session):
        """Test get_audit_logs when no logs match."""
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0

        mock_logs_result = MagicMock()
        mock_logs_scalars = MagicMock()
        mock_logs_scalars.all.return_value = []
        mock_logs_result.scalars.return_value = mock_logs_scalars

        call_count = [0]

        async def mock_execute(query):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_count_result
            return mock_logs_result

        mock_db_session.execute = mock_execute

        logs, total = await AuditService.get_audit_logs(
            db=mock_db_session, action="nonexistent_action"
        )

        assert total == 0
        assert len(logs) == 0

    @pytest.mark.asyncio
    async def test_get_audit_logs_count_returns_none(self, mock_db_session):
        """Test get_audit_logs when count query returns None (defaults to 0)."""
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = None  # Simulates empty count

        mock_logs_result = MagicMock()
        mock_logs_scalars = MagicMock()
        mock_logs_scalars.all.return_value = []
        mock_logs_result.scalars.return_value = mock_logs_scalars

        call_count = [0]

        async def mock_execute(query):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_count_result
            return mock_logs_result

        mock_db_session.execute = mock_execute

        logs, total = await AuditService.get_audit_logs(db=mock_db_session)

        assert total == 0
        assert len(logs) == 0

    @pytest.mark.asyncio
    async def test_get_audit_logs_with_all_filters(self, mock_db_session):
        """Test get_audit_logs with all filters combined."""
        now = datetime.now(UTC)
        mock_logs = [
            AuditLog(
                id=1,
                timestamp=now,
                action="event_reviewed",
                resource_type="event",
                resource_id="event-123",
                actor="admin",
                status="success",
            ),
        ]

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1

        mock_logs_result = MagicMock()
        mock_logs_scalars = MagicMock()
        mock_logs_scalars.all.return_value = mock_logs
        mock_logs_result.scalars.return_value = mock_logs_scalars

        call_count = [0]

        async def mock_execute(query):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_count_result
            return mock_logs_result

        mock_db_session.execute = mock_execute

        logs, total = await AuditService.get_audit_logs(
            db=mock_db_session,
            action="event_reviewed",
            resource_type="event",
            resource_id="event-123",
            actor="admin",
            status="success",
            start_date=now - timedelta(hours=1),
            end_date=now + timedelta(hours=1),
            limit=50,
            offset=0,
        )

        assert total == 1
        assert len(logs) == 1
        assert logs[0].action == "event_reviewed"

    @pytest.mark.asyncio
    async def test_get_audit_log_by_id_found(self, mock_db_session):
        """Test get_audit_log_by_id when log exists."""
        mock_log = AuditLog(
            id=42,
            timestamp=datetime.now(UTC),
            action="media_exported",
            resource_type="event",
            resource_id="event-999",
            actor="test_user",
            status="success",
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_log

        async def mock_execute(query):
            return mock_result

        mock_db_session.execute = mock_execute

        result = await AuditService.get_audit_log_by_id(db=mock_db_session, audit_id=42)

        assert result is not None
        assert result.id == 42
        assert result.action == "media_exported"

    @pytest.mark.asyncio
    async def test_get_audit_log_by_id_not_found(self, mock_db_session):
        """Test get_audit_log_by_id when log does not exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        async def mock_execute(query):
            return mock_result

        mock_db_session.execute = mock_execute

        result = await AuditService.get_audit_log_by_id(db=mock_db_session, audit_id=99999)

        assert result is None


class TestAuditServiceErrorHandling:
    """Tests for AuditService error handling."""

    @pytest.fixture
    def mock_db_session_with_errors(self):
        """Create a mock database session that raises errors."""
        from sqlalchemy.ext.asyncio import AsyncSession

        mock_session = MagicMock(spec=AsyncSession)
        return mock_session

    @pytest.mark.asyncio
    async def test_log_action_handles_db_flush_error(self, mock_db_session_with_errors):
        """Test log_action handles database flush errors gracefully."""

        async def raise_db_error():
            raise Exception("Database connection lost")

        mock_db_session_with_errors.add = MagicMock()
        mock_db_session_with_errors.flush = raise_db_error

        with pytest.raises(Exception, match="Database connection lost"):
            await AuditService.log_action(
                db=mock_db_session_with_errors,
                action=AuditAction.EVENT_REVIEWED,
                resource_type="event",
                actor="test_user",
            )

    @pytest.mark.asyncio
    async def test_get_audit_logs_handles_execute_error(self, mock_db_session_with_errors):
        """Test get_audit_logs handles query execution errors."""

        async def raise_query_error(query):
            raise Exception("Query timeout")

        mock_db_session_with_errors.execute = raise_query_error

        with pytest.raises(Exception, match="Query timeout"):
            await AuditService.get_audit_logs(db=mock_db_session_with_errors)

    @pytest.mark.asyncio
    async def test_log_action_with_none_actor(self, mock_db_session_with_errors):
        """Test log_action handles None actor value."""

        async def async_flush():
            pass

        mock_db_session_with_errors.add = MagicMock()
        mock_db_session_with_errors.flush = async_flush

        # Should handle None actor gracefully
        result = await AuditService.log_action(
            db=mock_db_session_with_errors,
            action=AuditAction.SETTINGS_CHANGED,
            resource_type="settings",
            actor=None,  # type: ignore
        )

        assert result.actor is None

    @pytest.mark.asyncio
    async def test_log_action_with_empty_details(self, mock_db_session_with_errors):
        """Test log_action handles empty details dict."""

        async def async_flush():
            pass

        mock_db_session_with_errors.add = MagicMock()
        mock_db_session_with_errors.flush = async_flush

        result = await AuditService.log_action(
            db=mock_db_session_with_errors,
            action=AuditAction.EVENT_DISMISSED,
            resource_type="event",
            resource_id="123",
            actor="user",
            details={},
        )

        assert result.details == {}

    @pytest.mark.asyncio
    async def test_get_audit_logs_with_invalid_limit(self, mock_db_session_with_errors):
        """Test get_audit_logs handles invalid limit values."""
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0

        mock_logs_result = MagicMock()
        mock_logs_scalars = MagicMock()
        mock_logs_scalars.all.return_value = []
        mock_logs_result.scalars.return_value = mock_logs_scalars

        call_count = [0]

        async def mock_execute(query):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_count_result
            return mock_logs_result

        mock_db_session_with_errors.execute = mock_execute

        # Should handle negative limit by using 0 or default behavior
        logs, total = await AuditService.get_audit_logs(
            db=mock_db_session_with_errors,
            limit=-1,  # Invalid negative limit
        )

        assert total == 0
        assert len(logs) == 0
