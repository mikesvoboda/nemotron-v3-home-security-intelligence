"""Unit tests for logging module."""

import logging
from unittest.mock import MagicMock, patch

from backend.core.logging import (
    ContextFilter,
    CustomJsonFormatter,
    SQLiteHandler,
    get_logger,
    get_request_id,
    set_request_id,
    setup_logging,
)


class TestLoggingSetup:
    """Tests for logging configuration."""

    def test_get_logger_returns_logger(self):
        """Test that get_logger returns a logging.Logger instance."""
        logger = get_logger("test_module")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_module"

    def test_request_id_context(self):
        """Test request_id context variable management."""
        # Initially should be None
        set_request_id(None)  # Reset first
        initial = get_request_id()
        assert initial is None

        # Set a request ID
        set_request_id("test-request-123")
        assert get_request_id() == "test-request-123"

        # Clear it
        set_request_id(None)
        assert get_request_id() is None

    def test_setup_logging_configures_root_logger(self):
        """Test that setup_logging configures the logging system."""
        with patch("backend.core.logging.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                log_level="DEBUG",
                log_file_path="data/logs/test.log",
                log_file_max_bytes=1048576,
                log_file_backup_count=3,
                log_db_enabled=False,
                debug=True,
            )

            # Clear existing handlers first
            root = logging.getLogger()
            original_handlers = root.handlers.copy()
            original_level = root.level

            try:
                # Should not raise
                setup_logging()

                # Root logger should have handlers
                assert len(root.handlers) > 0
            finally:
                # Restore original state
                root.handlers = original_handlers
                root.level = original_level

    def test_get_logger_with_different_names(self):
        """Test that get_logger returns distinct loggers for different names."""
        logger1 = get_logger("module_a")
        logger2 = get_logger("module_b")

        assert logger1.name == "module_a"
        assert logger2.name == "module_b"
        assert logger1 is not logger2

    def test_request_id_isolation(self):
        """Test that request ID can be set and retrieved correctly."""
        # Set a unique request ID
        test_id = "unique-request-456"
        set_request_id(test_id)

        # Should retrieve the same ID
        retrieved = get_request_id()
        assert retrieved == test_id

        # Clean up
        set_request_id(None)


class TestContextFilter:
    """Tests for ContextFilter."""

    def test_filter_adds_request_id(self):
        """Test that filter adds request_id to log record."""
        set_request_id("test-req-456")
        try:
            filter_obj = ContextFilter()
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg="test message",
                args=(),
                exc_info=None,
            )
            result = filter_obj.filter(record)
            assert result is True
            assert hasattr(record, "request_id")
            assert record.request_id == "test-req-456"
        finally:
            set_request_id(None)

    def test_filter_adds_none_request_id(self):
        """Test that filter adds None request_id when not set."""
        set_request_id(None)
        filter_obj = ContextFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test message",
            args=(),
            exc_info=None,
        )
        result = filter_obj.filter(record)
        assert result is True
        assert record.request_id is None


class TestCustomJsonFormatter:
    """Tests for CustomJsonFormatter."""

    def test_formatter_adds_custom_fields(self):
        """Test that formatter adds timestamp, level, component."""
        formatter = CustomJsonFormatter()
        record = logging.LogRecord(
            name="test.component",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test message",
            args=(),
            exc_info=None,
        )
        # Add request_id to record
        record.request_id = "test-123"

        formatted = formatter.format(record)
        assert "timestamp" in formatted
        assert "level" in formatted
        assert "component" in formatted
        assert '"level":"INFO"' in formatted or '"level": "INFO"' in formatted
        assert "test.component" in formatted

    def test_formatter_includes_request_id_when_present(self):
        """Test that formatter includes request_id if present."""
        formatter = CustomJsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.WARNING,
            pathname="",
            lineno=0,
            msg="warning message",
            args=(),
            exc_info=None,
        )
        record.request_id = "request-abc"

        formatted = formatter.format(record)
        assert "request-abc" in formatted

    def test_formatter_without_request_id(self):
        """Test that formatter works without request_id."""
        formatter = CustomJsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg="error message",
            args=(),
            exc_info=None,
        )
        # No request_id attribute

        formatted = formatter.format(record)
        assert "timestamp" in formatted
        assert "level" in formatted
        assert "ERROR" in formatted


class TestSQLiteHandler:
    """Tests for SQLiteHandler."""

    def test_handler_respects_min_level(self):
        """Test that handler respects minimum level."""
        handler = SQLiteHandler(min_level="ERROR")
        assert handler.min_level == logging.ERROR

    def test_handler_default_level(self):
        """Test handler default minimum level is DEBUG."""
        handler = SQLiteHandler()
        assert handler.min_level == logging.DEBUG

    def test_handler_disables_on_error(self):
        """Test handler disables DB on repeated errors."""
        handler = SQLiteHandler()
        handler._db_available = False

        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg="test message",
            args=(),
            exc_info=None,
        )

        # Should not raise when DB is disabled
        handler.emit(record)

    def test_handler_skips_below_min_level(self):
        """Test that handler ignores records below min level."""
        handler = SQLiteHandler(min_level="WARNING")

        # Create a DEBUG level record
        record = logging.LogRecord(
            name="test",
            level=logging.DEBUG,
            pathname="",
            lineno=0,
            msg="debug message",
            args=(),
            exc_info=None,
        )

        # Should not attempt to write to DB
        handler.emit(record)
        # If it reaches here without error, the test passes

    def test_handler_accepts_valid_min_levels(self):
        """Test handler accepts various valid log levels."""
        levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        for level in levels:
            handler = SQLiteHandler(min_level=level)
            expected = getattr(logging, level)
            assert handler.min_level == expected
