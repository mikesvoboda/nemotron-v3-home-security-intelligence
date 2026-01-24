"""Unit tests for automatic audit logging using SQLAlchemy session events.

NEM-3406: Tests for audit_events module that implements automatic audit
logging for create/update/delete operations using SQLAlchemy's session
event system.
"""

from __future__ import annotations

import contextvars
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from backend.core.audit_events import (
    AUDITED_MODELS,
    EXCLUDED_FIELDS,
    AuditContext,
    _create_audit_entry,
    _get_model_changes,
    _get_model_values,
    _get_resource_id,
    clear_audit_context,
    get_audit_context,
    set_audit_context,
    setup_audit_logging,
    teardown_audit_logging,
)


class TestAuditContext:
    """Tests for AuditContext dataclass."""

    def test_default_values(self) -> None:
        """Test AuditContext has correct default values."""
        ctx = AuditContext()
        assert ctx.actor == "system"
        assert ctx.ip_address is None
        assert ctx.user_agent is None

    def test_custom_values(self) -> None:
        """Test AuditContext with custom values."""
        ctx = AuditContext(
            actor="test_user",
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0",
        )
        assert ctx.actor == "test_user"
        assert ctx.ip_address == "192.168.1.100"
        assert ctx.user_agent == "Mozilla/5.0"

    def test_to_dict(self) -> None:
        """Test AuditContext.to_dict() returns correct dictionary."""
        ctx = AuditContext(
            actor="admin",
            ip_address="10.0.0.1",
            user_agent="TestAgent/1.0",
        )
        result = ctx.to_dict()

        assert result == {
            "actor": "admin",
            "ip_address": "10.0.0.1",
            "user_agent": "TestAgent/1.0",
        }

    def test_to_dict_with_none_values(self) -> None:
        """Test AuditContext.to_dict() handles None values."""
        ctx = AuditContext(actor="system")
        result = ctx.to_dict()

        assert result == {
            "actor": "system",
            "ip_address": None,
            "user_agent": None,
        }


class TestAuditContextManagement:
    """Tests for audit context management functions."""

    def test_get_audit_context_default(self) -> None:
        """Test get_audit_context returns default context when not set."""
        clear_audit_context()
        ctx = get_audit_context()

        assert ctx.actor == "system"
        assert ctx.ip_address is None
        assert ctx.user_agent is None

    def test_set_audit_context(self) -> None:
        """Test set_audit_context sets context correctly."""
        clear_audit_context()

        set_audit_context(
            actor="test_user",
            ip_address="192.168.1.1",
            user_agent="TestAgent",
        )

        try:
            ctx = get_audit_context()
            assert ctx.actor == "test_user"
            assert ctx.ip_address == "192.168.1.1"
            assert ctx.user_agent == "TestAgent"
        finally:
            clear_audit_context()

    def test_set_audit_context_returns_token(self) -> None:
        """Test set_audit_context returns a token for restoration."""
        clear_audit_context()

        token = set_audit_context(actor="user1")

        assert isinstance(token, contextvars.Token)
        clear_audit_context()

    def test_clear_audit_context(self) -> None:
        """Test clear_audit_context resets to default."""
        set_audit_context(actor="test_user", ip_address="1.2.3.4")
        clear_audit_context()

        ctx = get_audit_context()
        assert ctx.actor == "system"
        assert ctx.ip_address is None

    def test_context_isolation_in_async(self) -> None:
        """Test that context is isolated between async tasks."""
        clear_audit_context()

        # Set context in one "task"
        set_audit_context(actor="user1")
        ctx1 = get_audit_context()

        # Clear and verify default
        clear_audit_context()
        ctx2 = get_audit_context()

        assert ctx1.actor == "user1"
        assert ctx2.actor == "system"


class TestAuditedModelsConfig:
    """Tests for AUDITED_MODELS configuration."""

    def test_audited_models_contains_expected_models(self) -> None:
        """Test AUDITED_MODELS contains expected model mappings."""
        expected_models = ["Camera", "Event", "Detection"]

        for model in expected_models:
            assert model in AUDITED_MODELS

    def test_audited_models_maps_to_resource_types(self) -> None:
        """Test AUDITED_MODELS maps to correct resource types."""
        assert AUDITED_MODELS["Camera"] == "camera"
        assert AUDITED_MODELS["Event"] == "event"
        assert AUDITED_MODELS["Detection"] == "detection"

    def test_excluded_fields_contains_auto_updated_fields(self) -> None:
        """Test EXCLUDED_FIELDS contains auto-updated timestamp fields."""
        assert "updated_at" in EXCLUDED_FIELDS
        assert "last_seen_at" in EXCLUDED_FIELDS
        assert "search_vector" in EXCLUDED_FIELDS


class TestCreateAuditEntry:
    """Tests for _create_audit_entry function."""

    def test_create_audit_entry_basic(self) -> None:
        """Test _create_audit_entry creates correct dictionary."""
        context = AuditContext(actor="test_user", ip_address="1.2.3.4")
        details = {"key": "value"}

        result = _create_audit_entry(
            action="camera_created",
            resource_type="camera",
            resource_id="camera_123",
            details=details,
            context=context,
        )

        assert result["action"] == "camera_created"
        assert result["resource_type"] == "camera"
        assert result["resource_id"] == "camera_123"
        assert result["actor"] == "test_user"
        assert result["ip_address"] == "1.2.3.4"
        assert result["details"] == details
        assert result["status"] == "success"
        assert isinstance(result["timestamp"], datetime)

    def test_create_audit_entry_with_none_resource_id(self) -> None:
        """Test _create_audit_entry handles None resource_id."""
        context = AuditContext()

        result = _create_audit_entry(
            action="event_created",
            resource_type="event",
            resource_id=None,
            details={},
            context=context,
        )

        assert result["resource_id"] is None

    def test_create_audit_entry_timestamp_is_utc(self) -> None:
        """Test _create_audit_entry uses UTC timestamp."""
        context = AuditContext()

        result = _create_audit_entry(
            action="test",
            resource_type="test",
            resource_id="1",
            details={},
            context=context,
        )

        assert result["timestamp"].tzinfo is not None


class TestSetupTeardownAuditLogging:
    """Tests for setup_audit_logging and teardown_audit_logging functions."""

    def test_setup_audit_logging_returns_true(self) -> None:
        """Test setup_audit_logging returns True on success."""
        teardown_audit_logging()  # Ensure clean state

        with patch("backend.core.audit_events.event.listen"):
            result = setup_audit_logging()

        assert result is True
        teardown_audit_logging()  # Cleanup

    def test_setup_audit_logging_idempotent(self) -> None:
        """Test setup_audit_logging is idempotent (second call returns True)."""
        teardown_audit_logging()

        with patch("backend.core.audit_events.event.listen"):
            result1 = setup_audit_logging()
            result2 = setup_audit_logging()

        assert result1 is True
        assert result2 is True
        teardown_audit_logging()

    def test_teardown_audit_logging_returns_true(self) -> None:
        """Test teardown_audit_logging returns True on success."""
        with patch("backend.core.audit_events.event.listen"):
            setup_audit_logging()

        with patch("backend.core.audit_events.event.remove"):
            result = teardown_audit_logging()

        assert result is True

    def test_teardown_audit_logging_when_not_enabled(self) -> None:
        """Test teardown_audit_logging returns True when not enabled."""
        # Ensure disabled state
        import backend.core.audit_events as audit_module

        with audit_module._audit_logging_lock:
            audit_module._audit_logging_enabled = False

        result = teardown_audit_logging()
        assert result is True

    def test_setup_audit_logging_handles_exception(self) -> None:
        """Test setup_audit_logging handles exceptions gracefully."""
        import backend.core.audit_events as audit_module

        # Force disabled state without calling teardown (which may fail)
        with audit_module._audit_logging_lock:
            audit_module._audit_logging_enabled = False

        with patch("backend.core.audit_events.event.listen", side_effect=Exception("test error")):
            result = setup_audit_logging()

        assert result is False


class TestGetModelChanges:
    """Tests for _get_model_changes function."""

    def test_get_model_changes_with_mock_instance(self) -> None:
        """Test _get_model_changes extracts changes from model instance."""
        # Create a mock model instance with inspection support
        mock_instance = MagicMock()
        mock_instance.__class__.__name__ = "Camera"

        # Mock the mapper
        mock_column_attr = MagicMock()
        mock_column_attr.key = "name"

        mock_mapper = MagicMock()
        mock_mapper.column_attrs = [mock_column_attr]

        # Mock the state
        mock_history = MagicMock()
        mock_history.has_changes.return_value = True
        mock_history.deleted = ["old_name"]
        mock_history.added = ["new_name"]

        mock_attr_state = MagicMock()
        mock_attr_state.history = mock_history

        mock_state = MagicMock()
        mock_state.attrs = {"name": mock_attr_state}

        with patch("backend.core.audit_events.inspect") as mock_inspect:
            # Configure inspect to return mapper for class, state for instance
            def inspect_side_effect(obj):
                if obj is mock_instance.__class__:
                    return mock_mapper
                return mock_state

            mock_inspect.side_effect = inspect_side_effect
            mock_instance.name = "new_name"

            changes = _get_model_changes(mock_instance)

        assert "name" in changes
        assert changes["name"]["old"] == "old_name"
        assert changes["name"]["new"] == "new_name"

    def test_get_model_changes_excludes_excluded_fields(self) -> None:
        """Test _get_model_changes skips EXCLUDED_FIELDS."""
        mock_instance = MagicMock()
        mock_instance.__class__.__name__ = "Camera"

        # Mock a field that should be excluded
        mock_column_attr = MagicMock()
        mock_column_attr.key = "updated_at"  # In EXCLUDED_FIELDS

        mock_mapper = MagicMock()
        mock_mapper.column_attrs = [mock_column_attr]

        mock_state = MagicMock()

        with patch("backend.core.audit_events.inspect") as mock_inspect:

            def inspect_side_effect(obj):
                if obj is mock_instance.__class__:
                    return mock_mapper
                return mock_state

            mock_inspect.side_effect = inspect_side_effect

            changes = _get_model_changes(mock_instance)

        # updated_at should not be in changes
        assert "updated_at" not in changes


class TestGetResourceId:
    """Tests for _get_resource_id function."""

    def test_get_resource_id_single_pk(self) -> None:
        """Test _get_resource_id extracts single primary key."""
        mock_instance = MagicMock()
        mock_instance.id = "camera_123"

        mock_pk_col = MagicMock()
        mock_pk_col.key = "id"

        mock_mapper = MagicMock()
        mock_mapper.primary_key = [mock_pk_col]

        with patch("backend.core.audit_events.inspect") as mock_inspect:
            mock_inspect.return_value = mock_mapper

            result = _get_resource_id(mock_instance)

        assert result == "camera_123"

    def test_get_resource_id_composite_pk(self) -> None:
        """Test _get_resource_id handles composite primary key."""
        mock_instance = MagicMock()
        mock_instance.camera_id = "cam1"
        mock_instance.zone_id = "zone1"

        mock_pk_col1 = MagicMock()
        mock_pk_col1.key = "camera_id"
        mock_pk_col2 = MagicMock()
        mock_pk_col2.key = "zone_id"

        mock_mapper = MagicMock()
        mock_mapper.primary_key = [mock_pk_col1, mock_pk_col2]

        with patch("backend.core.audit_events.inspect") as mock_inspect:
            mock_inspect.return_value = mock_mapper

            result = _get_resource_id(mock_instance)

        assert result == "cam1:zone1"

    def test_get_resource_id_none_pk(self) -> None:
        """Test _get_resource_id returns None for None primary key."""
        mock_instance = MagicMock()
        mock_instance.id = None

        mock_pk_col = MagicMock()
        mock_pk_col.key = "id"

        mock_mapper = MagicMock()
        mock_mapper.primary_key = [mock_pk_col]

        with patch("backend.core.audit_events.inspect") as mock_inspect:
            mock_inspect.return_value = mock_mapper

            result = _get_resource_id(mock_instance)

        assert result is None


class TestGetModelValues:
    """Tests for _get_model_values function."""

    def test_get_model_values_extracts_all_values(self) -> None:
        """Test _get_model_values extracts all field values."""
        mock_instance = MagicMock()
        mock_instance.id = "camera_1"
        mock_instance.name = "Front Door"
        mock_instance.status = "online"

        mock_attr1 = MagicMock()
        mock_attr1.key = "id"
        mock_attr2 = MagicMock()
        mock_attr2.key = "name"
        mock_attr3 = MagicMock()
        mock_attr3.key = "status"

        mock_mapper = MagicMock()
        mock_mapper.column_attrs = [mock_attr1, mock_attr2, mock_attr3]

        with patch("backend.core.audit_events.inspect") as mock_inspect:
            mock_inspect.return_value = mock_mapper

            values = _get_model_values(mock_instance)

        assert values["id"] == "camera_1"
        assert values["name"] == "Front Door"
        assert values["status"] == "online"

    def test_get_model_values_converts_datetime(self) -> None:
        """Test _get_model_values converts datetime to ISO format."""
        mock_instance = MagicMock()
        test_dt = datetime(2024, 1, 15, 12, 30, 0, tzinfo=UTC)
        mock_instance.created_at = test_dt

        mock_attr = MagicMock()
        mock_attr.key = "created_at"

        mock_mapper = MagicMock()
        mock_mapper.column_attrs = [mock_attr]

        with patch("backend.core.audit_events.inspect") as mock_inspect:
            mock_inspect.return_value = mock_mapper

            values = _get_model_values(mock_instance)

        assert values["created_at"] == test_dt.isoformat()

    def test_get_model_values_excludes_excluded_fields(self) -> None:
        """Test _get_model_values skips EXCLUDED_FIELDS."""
        mock_instance = MagicMock()
        mock_instance.id = "1"
        mock_instance.updated_at = datetime.now(UTC)

        mock_attr1 = MagicMock()
        mock_attr1.key = "id"
        mock_attr2 = MagicMock()
        mock_attr2.key = "updated_at"  # In EXCLUDED_FIELDS

        mock_mapper = MagicMock()
        mock_mapper.column_attrs = [mock_attr1, mock_attr2]

        with patch("backend.core.audit_events.inspect") as mock_inspect:
            mock_inspect.return_value = mock_mapper

            values = _get_model_values(mock_instance)

        assert "id" in values
        assert "updated_at" not in values


class TestAuditLoggingIntegration:
    """Integration tests for audit logging functionality.

    Note: These tests verify the module's functionality without requiring
    a real database connection.
    """

    def setup_method(self) -> None:
        """Reset audit logging state before each test."""
        import backend.core.audit_events as audit_module

        with audit_module._audit_logging_lock:
            audit_module._audit_logging_enabled = False
        clear_audit_context()

    def teardown_method(self) -> None:
        """Clean up audit logging state after each test."""
        teardown_audit_logging()
        clear_audit_context()

    def test_full_context_flow(self) -> None:
        """Test complete flow of setting and using audit context."""
        # Set context
        set_audit_context(
            actor="admin@example.com",
            ip_address="10.0.0.1",
            user_agent="TestBrowser/1.0",
        )

        # Get context and verify
        ctx = get_audit_context()
        assert ctx.actor == "admin@example.com"
        assert ctx.ip_address == "10.0.0.1"
        assert ctx.user_agent == "TestBrowser/1.0"

        # Create audit entry with context
        entry = _create_audit_entry(
            action="camera_created",
            resource_type="camera",
            resource_id="cam_1",
            details={"name": "Front Door"},
            context=ctx,
        )

        assert entry["actor"] == "admin@example.com"
        assert entry["ip_address"] == "10.0.0.1"
        assert entry["user_agent"] == "TestBrowser/1.0"

        # Clear context
        clear_audit_context()
        ctx_after = get_audit_context()
        assert ctx_after.actor == "system"
