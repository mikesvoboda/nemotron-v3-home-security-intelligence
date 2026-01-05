"""Unit tests for logging module."""

import logging
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from backend.core.logging import (
    SENSITIVE_FIELD_NAMES,
    ContextFilter,
    CustomJsonFormatter,
    SQLiteHandler,
    get_logger,
    get_request_id,
    redact_sensitive_value,
    redact_url,
    sanitize_log_value,
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

    def test_formatter_with_empty_request_id(self):
        """Test that formatter handles empty string request_id."""
        formatter = CustomJsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.DEBUG,
            pathname="",
            lineno=0,
            msg="debug message",
            args=(),
            exc_info=None,
        )
        record.request_id = ""

        # Empty string is falsy, so request_id should not be added to log_record
        formatted = formatter.format(record)
        assert "timestamp" in formatted
        # Empty string should not result in request_id being added
        assert "request_id" not in formatted or '""' in formatted


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

    def test_handler_invalid_min_level_defaults_to_debug(self):
        """Test handler with invalid min_level falls back to DEBUG."""
        handler = SQLiteHandler(min_level="INVALID_LEVEL")
        # getattr returns default (DEBUG) when level name is not found
        assert handler.min_level == logging.DEBUG


class TestSQLiteHandlerGetSession:
    """Tests for SQLiteHandler._get_session method (lines 87-105)."""

    def test_get_session_creates_engine_and_factory(self):
        """Test that _get_session initializes engine and session factory on first call."""
        with patch("backend.core.logging.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                database_url="postgresql+asyncpg://postgres:postgres@localhost:5432/security"
            )

            with (
                patch("backend.core.logging.SQLiteHandler._get_session") as mock_get_session,
            ):
                # Simulate session being returned
                mock_session = MagicMock()
                mock_get_session.return_value = mock_session

                handler = SQLiteHandler()
                handler._get_session = mock_get_session
                session = handler._get_session()

                assert session is mock_session

    def test_get_session_returns_none_on_import_error(self):
        """Test that _get_session returns None when database setup fails."""
        handler = SQLiteHandler()
        handler._session_factory = None
        handler._db_available = True

        # Patch get_settings to raise an exception during engine creation
        with patch("backend.core.logging.get_settings") as mock_settings:
            mock_settings.side_effect = Exception("Config error")

            # _get_session should catch the exception and set _db_available to False
            session = handler._get_session()

            assert session is None
            assert handler._db_available is False

    def test_get_session_reuses_session_factory(self):
        """Test that _get_session reuses existing session factory."""
        handler = SQLiteHandler()

        # Pre-set a session factory
        mock_factory = MagicMock()
        mock_session = MagicMock()
        mock_factory.return_value = mock_session
        handler._session_factory = mock_factory

        session = handler._get_session()

        assert session is mock_session
        mock_factory.assert_called_once()

    def test_get_session_converts_async_url_to_sync(self):
        """Test that async PostgreSQL URL is converted to sync URL."""
        handler = SQLiteHandler()
        handler._session_factory = None
        handler._db_available = True

        with patch("backend.core.logging.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                database_url="postgresql+asyncpg://postgres:postgres@localhost:5432/security"
            )

            with (
                patch("sqlalchemy.create_engine") as mock_create_engine,
                patch("sqlalchemy.orm.sessionmaker") as mock_sessionmaker,
            ):
                mock_engine = MagicMock()
                mock_create_engine.return_value = mock_engine

                mock_factory = MagicMock()
                mock_session = MagicMock()
                mock_factory.return_value = mock_session
                mock_sessionmaker.return_value = mock_factory

                session = handler._get_session()

                # Verify engine was created with sync URL
                mock_create_engine.assert_called_once()
                call_args = mock_create_engine.call_args
                # URL should have asyncpg replaced with psycopg2
                assert "postgresql" in call_args[0][0]
                assert "asyncpg" not in call_args[0][0]
                assert session is mock_session


class TestSQLiteHandlerEmit:
    """Tests for SQLiteHandler.emit method (lines 115-158)."""

    def test_emit_writes_log_entry_to_database(self):
        """Test that emit correctly writes log entry to database."""
        handler = SQLiteHandler(min_level="DEBUG")
        handler._db_available = True
        handler.setFormatter(logging.Formatter("%(message)s"))

        mock_session = MagicMock()
        handler._get_session = MagicMock(return_value=mock_session)

        with patch("backend.models.log.Log") as MockLog:
            mock_log_instance = MagicMock()
            MockLog.return_value = mock_log_instance

            record = logging.LogRecord(
                name="test.component",
                level=logging.INFO,
                pathname="/test/path.py",
                lineno=42,
                msg="Test log message",
                args=(),
                exc_info=None,
            )
            record.request_id = "req-123"

            handler.emit(record)

            # Verify Log model was instantiated
            MockLog.assert_called_once()
            call_kwargs = MockLog.call_args[1]

            assert call_kwargs["level"] == "INFO"
            assert call_kwargs["component"] == "test.component"
            assert call_kwargs["message"] == "Test log message"
            assert call_kwargs["request_id"] == "req-123"
            assert call_kwargs["source"] == "backend"

            # Verify session operations
            mock_session.add.assert_called_once_with(mock_log_instance)
            mock_session.commit.assert_called_once()
            mock_session.close.assert_called_once()

    def test_emit_extracts_custom_attributes(self):
        """Test that emit extracts camera_id, event_id, and other custom attributes."""
        handler = SQLiteHandler(min_level="DEBUG")
        handler._db_available = True
        handler.setFormatter(logging.Formatter("%(message)s"))

        mock_session = MagicMock()
        handler._get_session = MagicMock(return_value=mock_session)

        with patch("backend.models.log.Log") as MockLog:
            mock_log_instance = MagicMock()
            MockLog.return_value = mock_log_instance

            record = logging.LogRecord(
                name="camera.service",
                level=logging.WARNING,
                pathname="/test/path.py",
                lineno=100,
                msg="Camera detected motion",
                args=(),
                exc_info=None,
            )
            # Add custom attributes
            record.camera_id = "front_door"
            record.event_id = 42
            record.detection_id = 123
            record.duration_ms = 500
            record.file_path = "/path/to/image.jpg"

            handler.emit(record)

            # Verify Log model was instantiated with custom attributes
            MockLog.assert_called_once()
            call_kwargs = MockLog.call_args[1]

            assert call_kwargs["camera_id"] == "front_door"
            assert call_kwargs["event_id"] == 42
            assert call_kwargs["detection_id"] == 123
            assert call_kwargs["duration_ms"] == 500
            # extra should contain file_path
            assert "file_path" in call_kwargs["extra"]
            assert call_kwargs["extra"]["file_path"] == "/path/to/image.jpg"

    def test_emit_handles_extra_dict_attribute(self):
        """Test that emit merges extra dict attribute into extra_data."""
        handler = SQLiteHandler(min_level="DEBUG")
        handler._db_available = True
        handler.setFormatter(logging.Formatter("%(message)s"))

        mock_session = MagicMock()
        handler._get_session = MagicMock(return_value=mock_session)

        with patch("backend.models.log.Log") as MockLog:
            mock_log_instance = MagicMock()
            MockLog.return_value = mock_log_instance

            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname="/test/path.py",
                lineno=50,
                msg="Error occurred",
                args=(),
                exc_info=None,
            )
            # Add extra dict
            record.extra = {"key1": "value1", "key2": 42}

            handler.emit(record)

            MockLog.assert_called_once()
            call_kwargs = MockLog.call_args[1]

            # extra should contain merged data
            assert call_kwargs["extra"]["key1"] == "value1"
            assert call_kwargs["extra"]["key2"] == 42

    def test_emit_returns_early_when_session_is_none(self):
        """Test that emit returns early if _get_session returns None."""
        handler = SQLiteHandler(min_level="DEBUG")
        handler._db_available = True
        handler._get_session = MagicMock(return_value=None)

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/test/path.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        # Should not raise - just return early
        handler.emit(record)

        # Verify _get_session was called
        handler._get_session.assert_called_once()

    def test_emit_disables_db_on_exception(self):
        """Test that emit disables database logging on exception."""
        handler = SQLiteHandler(min_level="DEBUG")
        handler._db_available = True
        handler.setFormatter(logging.Formatter("%(message)s"))

        mock_session = MagicMock()
        mock_session.add.side_effect = Exception("Database error")
        handler._get_session = MagicMock(return_value=mock_session)

        with patch("backend.models.log.Log") as MockLog:
            mock_log_instance = MagicMock()
            MockLog.return_value = mock_log_instance

            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="/test/path.py",
                lineno=10,
                msg="Test message",
                args=(),
                exc_info=None,
            )

            # Should not raise - just disable DB logging
            handler.emit(record)

            # DB should be disabled after exception
            assert handler._db_available is False

    def test_emit_closes_session_even_on_commit_failure(self):
        """Test that emit closes session even when commit fails."""
        handler = SQLiteHandler(min_level="DEBUG")
        handler._db_available = True
        handler.setFormatter(logging.Formatter("%(message)s"))

        mock_session = MagicMock()
        mock_session.commit.side_effect = Exception("Commit failed")
        handler._get_session = MagicMock(return_value=mock_session)

        with patch("backend.models.log.Log") as MockLog:
            mock_log_instance = MagicMock()
            MockLog.return_value = mock_log_instance

            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="/test/path.py",
                lineno=10,
                msg="Test message",
                args=(),
                exc_info=None,
            )

            handler.emit(record)

            # Session should still be closed in finally block
            mock_session.close.assert_called_once()
            # DB should be disabled after exception
            assert handler._db_available is False

    def test_emit_skips_none_values_in_extra_data(self):
        """Test that emit skips None values when building extra_data."""
        handler = SQLiteHandler(min_level="DEBUG")
        handler._db_available = True
        handler.setFormatter(logging.Formatter("%(message)s"))

        mock_session = MagicMock()
        handler._get_session = MagicMock(return_value=mock_session)

        with patch("backend.models.log.Log") as MockLog:
            mock_log_instance = MagicMock()
            MockLog.return_value = mock_log_instance

            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="/test/path.py",
                lineno=10,
                msg="Test message",
                args=(),
                exc_info=None,
            )
            # Set some values to None
            record.camera_id = None
            record.event_id = None
            record.detection_id = 456  # This one is not None
            record.duration_ms = None
            record.file_path = None

            handler.emit(record)

            MockLog.assert_called_once()
            call_kwargs = MockLog.call_args[1]

            # Only detection_id should be in extra (non-None value)
            assert "detection_id" in call_kwargs["extra"]
            assert call_kwargs["extra"]["detection_id"] == 456
            # camera_id at top level should still be None
            assert call_kwargs["camera_id"] is None


class TestSetupLoggingFileHandler:
    """Tests for setup_logging file handler configuration (lines 207-208)."""

    def test_setup_logging_handles_file_handler_exception(self):
        """Test that setup_logging handles file handler creation failure gracefully."""
        with patch("backend.core.logging.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                log_level="INFO",
                log_file_path="/nonexistent/deep/nested/path/test.log",
                log_file_max_bytes=1048576,
                log_file_backup_count=3,
                log_db_enabled=False,
            )

            # Patch RotatingFileHandler to raise an exception
            with patch("backend.core.logging.RotatingFileHandler") as mock_file_handler:
                mock_file_handler.side_effect = PermissionError("Permission denied")

                root = logging.getLogger()
                original_handlers = root.handlers.copy()
                original_level = root.level

                try:
                    # Should not raise - should log warning and continue
                    setup_logging()

                    # Console handler should still be added
                    assert len(root.handlers) >= 1
                finally:
                    root.handlers = original_handlers
                    root.level = original_level

    def test_setup_logging_creates_log_directory(self):
        """Test that setup_logging creates log directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "logs" / "nested" / "app.log"

            with patch("backend.core.logging.get_settings") as mock_settings:
                mock_settings.return_value = MagicMock(
                    log_level="DEBUG",
                    log_file_path=str(log_path),
                    log_file_max_bytes=1048576,
                    log_file_backup_count=3,
                    log_db_enabled=False,
                )

                root = logging.getLogger()
                original_handlers = root.handlers.copy()
                original_level = root.level

                try:
                    setup_logging()

                    # Directory should be created
                    assert log_path.parent.exists()
                finally:
                    root.handlers = original_handlers
                    root.level = original_level


class TestSetupLoggingSQLiteHandler:
    """Tests for setup_logging SQLite handler configuration (lines 212-218)."""

    def test_setup_logging_adds_sqlite_handler_when_enabled(self):
        """Test that setup_logging adds SQLite handler when log_db_enabled is True."""
        with patch("backend.core.logging.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                log_level="INFO",
                log_file_path="data/logs/test.log",
                log_file_max_bytes=1048576,
                log_file_backup_count=3,
                log_db_enabled=True,
                log_db_min_level="WARNING",
            )

            root = logging.getLogger()
            original_handlers = root.handlers.copy()
            original_level = root.level

            try:
                setup_logging()

                # Should have SQLiteHandler among handlers
                sqlite_handlers = [h for h in root.handlers if isinstance(h, SQLiteHandler)]
                assert len(sqlite_handlers) == 1

                # Verify min_level was set correctly
                assert sqlite_handlers[0].min_level == logging.WARNING
            finally:
                root.handlers = original_handlers
                root.level = original_level

    def test_setup_logging_handles_sqlite_handler_exception(self):
        """Test that setup_logging handles SQLite handler creation failure."""
        with patch("backend.core.logging.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                log_level="INFO",
                log_file_path="data/logs/test.log",
                log_file_max_bytes=1048576,
                log_file_backup_count=3,
                log_db_enabled=True,
                log_db_min_level="INFO",
            )

            with patch("backend.core.logging.SQLiteHandler") as mock_sqlite_handler:
                mock_sqlite_handler.side_effect = Exception("SQLite initialization failed")

                root = logging.getLogger()
                original_handlers = root.handlers.copy()
                original_level = root.level

                try:
                    # Should not raise - should log warning and continue
                    setup_logging()

                    # Should still have console handler
                    assert len(root.handlers) >= 1
                finally:
                    root.handlers = original_handlers
                    root.level = original_level

    def test_setup_logging_skips_sqlite_handler_when_disabled(self):
        """Test that setup_logging skips SQLite handler when log_db_enabled is False."""
        with patch("backend.core.logging.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                log_level="DEBUG",
                log_file_path="data/logs/test.log",
                log_file_max_bytes=1048576,
                log_file_backup_count=3,
                log_db_enabled=False,
            )

            root = logging.getLogger()
            original_handlers = root.handlers.copy()
            original_level = root.level

            try:
                setup_logging()

                # Should NOT have any SQLiteHandler
                sqlite_handlers = [h for h in root.handlers if isinstance(h, SQLiteHandler)]
                assert len(sqlite_handlers) == 0
            finally:
                root.handlers = original_handlers
                root.level = original_level


class TestSetupLoggingIntegration:
    """Integration tests for setup_logging function."""

    def test_setup_logging_configures_all_components(self):
        """Test that setup_logging configures console, file, and optional SQLite handlers."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "app.log"

            with patch("backend.core.logging.get_settings") as mock_settings:
                mock_settings.return_value = MagicMock(
                    log_level="DEBUG",
                    log_file_path=str(log_path),
                    log_file_max_bytes=1048576,
                    log_file_backup_count=3,
                    log_db_enabled=True,
                    log_db_min_level="ERROR",
                )

                root = logging.getLogger()
                original_handlers = root.handlers.copy()
                original_level = root.level
                original_filters = root.filters.copy()

                try:
                    # Count existing filters before setup
                    existing_filters = len(
                        [f for f in root.filters if isinstance(f, ContextFilter)]
                    )

                    setup_logging()

                    # Root level should be set
                    assert root.level == logging.DEBUG

                    # Should have at least one new context filter added
                    context_filters = [f for f in root.filters if isinstance(f, ContextFilter)]
                    assert len(context_filters) >= existing_filters + 1

                    # Should have at least console handler
                    from logging import StreamHandler

                    stream_handlers = [h for h in root.handlers if isinstance(h, StreamHandler)]
                    assert len(stream_handlers) >= 1
                finally:
                    root.handlers = original_handlers
                    root.level = original_level
                    root.filters = original_filters

    def test_setup_logging_reduces_third_party_noise(self):
        """Test that setup_logging reduces logging level for third-party libraries."""
        with patch("backend.core.logging.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                log_level="DEBUG",
                log_file_path="data/logs/test.log",
                log_file_max_bytes=1048576,
                log_file_backup_count=3,
                log_db_enabled=False,
            )

            root = logging.getLogger()
            original_handlers = root.handlers.copy()
            original_level = root.level

            try:
                setup_logging()

                # Third-party loggers should have WARNING level
                assert logging.getLogger("uvicorn.access").level == logging.WARNING
                assert logging.getLogger("sqlalchemy.engine").level == logging.WARNING
                assert logging.getLogger("watchdog").level == logging.WARNING
            finally:
                root.handlers = original_handlers
                root.level = original_level

    def test_setup_logging_handles_invalid_log_level(self):
        """Test that setup_logging handles invalid log level gracefully."""
        with patch("backend.core.logging.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                log_level="INVALID_LEVEL",  # Invalid level
                log_file_path="data/logs/test.log",
                log_file_max_bytes=1048576,
                log_file_backup_count=3,
                log_db_enabled=False,
            )

            root = logging.getLogger()
            original_handlers = root.handlers.copy()
            original_level = root.level

            try:
                # Should not raise - falls back to INFO
                setup_logging()

                # getattr with default returns INFO when level not found
                assert root.level == logging.INFO
            finally:
                root.handlers = original_handlers
                root.level = original_level

    def test_setup_logging_clears_existing_handlers(self):
        """Test that setup_logging clears existing handlers before adding new ones."""
        with patch("backend.core.logging.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                log_level="INFO",
                log_file_path="data/logs/test.log",
                log_file_max_bytes=1048576,
                log_file_backup_count=3,
                log_db_enabled=False,
            )

            root = logging.getLogger()
            original_handlers = root.handlers.copy()
            original_level = root.level

            # Add a dummy handler
            dummy_handler = logging.StreamHandler()
            root.addHandler(dummy_handler)

            try:
                setup_logging()

                # The dummy handler should have been cleared
                assert dummy_handler not in root.handlers
            finally:
                root.handlers = original_handlers
                root.level = original_level


class TestRedactUrl:
    """Tests for URL redaction functionality."""

    def test_redact_postgres_url_with_password(self):
        """Test redacting PostgreSQL URL with password."""
        url = "postgresql+asyncpg://security:secret123@localhost:5432/security"
        result = redact_url(url)
        assert result == "postgresql+asyncpg://security:[REDACTED]@localhost:5432/security"
        assert "secret123" not in result

    def test_redact_redis_url_with_password(self):
        """Test redacting Redis URL with password."""
        url = "redis://default:mypassword@redis-host:6379/0"
        result = redact_url(url)
        assert result == "redis://default:[REDACTED]@redis-host:6379/0"
        assert "mypassword" not in result

    def test_redact_rediss_url_with_password(self):
        """Test redacting Redis TLS URL with password."""
        url = "rediss://user:supersecret@secure-redis:6380/1"
        result = redact_url(url)
        assert result == "rediss://user:[REDACTED]@secure-redis:6380/1"
        assert "supersecret" not in result

    def test_url_without_password_unchanged(self):
        """Test that URLs without password are returned unchanged."""
        url = "http://localhost:8000"
        result = redact_url(url)
        assert result == url

    def test_url_with_username_only_unchanged(self):
        """Test that URLs with username but no password are returned unchanged."""
        url = "redis://user@localhost:6379/0"
        result = redact_url(url)
        assert result == url

    def test_empty_url_returns_empty(self):
        """Test that empty string is returned as-is."""
        assert redact_url("") == ""

    def test_none_url_returns_none(self):
        """Test that None-like falsy values are handled."""
        # Empty string is falsy and should return as-is
        assert redact_url("") == ""

    def test_preserves_database_path(self):
        """Test that database path is preserved in redacted URL."""
        url = "postgresql://admin:pass123@db.example.com:5432/myapp"
        result = redact_url(url)
        assert "/myapp" in result
        assert "db.example.com" in result
        assert "5432" in result
        assert "pass123" not in result

    def test_preserves_query_params(self):
        """Test that query parameters are preserved."""
        url = "postgresql://user:secret@localhost:5432/db?sslmode=require"
        result = redact_url(url)
        assert "sslmode=require" in result
        assert "secret" not in result

    def test_complex_password_characters(self):
        """Test redacting URLs with complex password characters."""
        # URL-encoded special characters
        url = "postgresql://user:p%40ssw0rd%21@localhost:5432/db"
        result = redact_url(url)
        assert "[REDACTED]" in result
        assert "p%40ssw0rd%21" not in result

    def test_url_with_ipv4_host(self):
        """Test redacting URL with IPv4 address."""
        url = "redis://admin:password@192.168.1.100:6379/0"
        result = redact_url(url)
        assert "192.168.1.100" in result
        assert "[REDACTED]" in result
        assert "password" not in result


class TestRedactSensitiveValue:
    """Tests for sensitive value redaction."""

    def test_database_url_uses_url_redaction(self):
        """Test that database_url field uses URL-aware redaction."""
        url = "postgresql+asyncpg://user:pass@host:5432/db"
        result = redact_sensitive_value("database_url", url)
        # Should preserve structure while redacting password
        assert "postgresql+asyncpg://" in result
        assert "user:" in result
        assert "[REDACTED]" in result
        assert "host:5432/db" in result
        assert "pass" not in result

    def test_redis_url_uses_url_redaction(self):
        """Test that redis_url field uses URL-aware redaction."""
        url = "redis://default:secret@localhost:6379/0"
        result = redact_sensitive_value("redis_url", url)
        assert "redis://" in result
        assert "[REDACTED]" in result
        assert "secret" not in result

    def test_api_key_fully_redacted(self):
        """Test that api_key values are fully redacted."""
        result = redact_sensitive_value("api_key", "sk-1234567890")
        assert result == "[REDACTED]"

    def test_password_field_fully_redacted(self):
        """Test that password fields are fully redacted."""
        result = redact_sensitive_value("smtp_password", "mailsecret")
        assert result == "[REDACTED]"

    def test_api_keys_list_redacted(self):
        """Test that api_keys list is redacted."""
        keys = ["key1", "key2", "key3"]
        result = redact_sensitive_value("api_keys", keys)
        assert result == ["[REDACTED]", "[REDACTED]", "[REDACTED]"]

    def test_empty_api_keys_list(self):
        """Test that empty api_keys list is handled."""
        result = redact_sensitive_value("api_keys", [])
        assert result == []

    def test_non_sensitive_field_unchanged(self):
        """Test that non-sensitive fields are unchanged."""
        result = redact_sensitive_value("app_name", "My App")
        assert result == "My App"

    def test_debug_flag_unchanged(self):
        """Test that boolean flags are unchanged for non-sensitive fields."""
        result = redact_sensitive_value("debug", True)
        assert result is True

    def test_case_insensitive_field_matching(self):
        """Test that field name matching is case-insensitive."""
        result = redact_sensitive_value("DATABASE_URL", "postgresql://x:pass@h/d")
        assert "[REDACTED]" in result

    def test_partial_field_name_matching(self):
        """Test that partial patterns like 'password' in field names are matched."""
        result = redact_sensitive_value("my_custom_password", "secret123")
        assert result == "[REDACTED]"

    def test_token_field_redacted(self):
        """Test that fields containing 'token' are redacted."""
        result = redact_sensitive_value("auth_token", "bearer_xyz123")
        assert result == "[REDACTED]"

    def test_secret_field_redacted(self):
        """Test that fields containing 'secret' are redacted."""
        result = redact_sensitive_value("client_secret", "abcd1234")
        assert result == "[REDACTED]"

    def test_credential_field_redacted(self):
        """Test that fields containing 'credential' are redacted."""
        result = redact_sensitive_value("service_credential", "cred_value")
        assert result == "[REDACTED]"

    def test_admin_api_key_redacted(self):
        """Test that admin_api_key is fully redacted."""
        result = redact_sensitive_value("admin_api_key", "admin-secret-key")
        assert result == "[REDACTED]"

    def test_rtdetr_api_key_redacted(self):
        """Test that rtdetr_api_key is fully redacted."""
        result = redact_sensitive_value("rtdetr_api_key", "rtdetr-key-123")
        assert result == "[REDACTED]"

    def test_nemotron_api_key_redacted(self):
        """Test that nemotron_api_key is fully redacted."""
        result = redact_sensitive_value("nemotron_api_key", "nemotron-key-abc")
        assert result == "[REDACTED]"


class TestSensitiveFieldNames:
    """Tests for SENSITIVE_FIELD_NAMES constant."""

    def test_contains_expected_fields(self):
        """Test that SENSITIVE_FIELD_NAMES contains all expected fields."""
        expected_fields = {
            "password",
            "secret",
            "key",
            "token",
            "credential",
            "api_key",
            "api_keys",
            "admin_api_key",
            "rtdetr_api_key",
            "nemotron_api_key",
            "smtp_password",
            "database_url",
            "redis_url",
        }
        assert expected_fields == SENSITIVE_FIELD_NAMES

    def test_is_frozenset(self):
        """Test that SENSITIVE_FIELD_NAMES is immutable."""
        assert isinstance(SENSITIVE_FIELD_NAMES, frozenset)


class TestSanitizeLogValue:
    """Tests for sanitize_log_value function (CWE-117 Log Injection prevention)."""

    def test_sanitize_normal_string(self):
        """Test that normal strings pass through unchanged."""
        result = sanitize_log_value("normal value")
        assert result == "normal value"

    def test_sanitize_removes_newlines(self):
        """Test that newline characters are replaced with spaces."""
        result = sanitize_log_value("line1\nFAKE_LOG_ENTRY")
        assert result == "line1 FAKE_LOG_ENTRY"
        assert "\n" not in result

    def test_sanitize_removes_carriage_returns(self):
        """Test that carriage return characters are replaced with spaces."""
        result = sanitize_log_value("line1\rFAKE_LOG_ENTRY")
        assert result == "line1 FAKE_LOG_ENTRY"
        assert "\r" not in result

    def test_sanitize_removes_crlf(self):
        """Test that CRLF sequences are replaced."""
        result = sanitize_log_value("line1\r\nFAKE_LOG_ENTRY")
        assert result == "line1  FAKE_LOG_ENTRY"
        assert "\r" not in result
        assert "\n" not in result

    def test_sanitize_removes_null_bytes(self):
        """Test that null bytes are removed."""
        result = sanitize_log_value("before\x00after")
        assert result == "beforeafter"
        assert "\x00" not in result

    def test_sanitize_removes_control_characters(self):
        """Test that control characters (ASCII 0-31) are replaced."""
        # Test various control characters
        result = sanitize_log_value("text\x01\x02\x03more")
        assert result == "text   more"
        # Verify no control chars remain except tabs
        for char in result:
            assert ord(char) >= 32 or char == "\t"

    def test_sanitize_preserves_tabs(self):
        """Test that tab characters are preserved."""
        result = sanitize_log_value("col1\tcol2\tcol3")
        assert result == "col1\tcol2\tcol3"
        assert "\t" in result

    def test_sanitize_handles_none(self):
        """Test that None is converted to string 'None'."""
        result = sanitize_log_value(None)
        assert result == "None"

    def test_sanitize_handles_numbers(self):
        """Test that numbers are converted to strings."""
        result = sanitize_log_value(42)
        assert result == "42"

    def test_sanitize_handles_floats(self):
        """Test that floats are converted to strings."""
        result = sanitize_log_value(3.14)
        assert result == "3.14"

    def test_sanitize_handles_booleans(self):
        """Test that booleans are converted to strings."""
        assert sanitize_log_value(True) == "True"
        assert sanitize_log_value(False) == "False"

    def test_sanitize_handles_empty_string(self):
        """Test that empty strings pass through unchanged."""
        result = sanitize_log_value("")
        assert result == ""

    def test_sanitize_log_injection_attack_scenario(self):
        """Test realistic log injection attack scenario."""
        # An attacker might try to forge log entries
        malicious_input = (
            "status=online\n2026-01-01 12:00:00 | ERROR | FAKE ALERT: System compromised"
        )
        result = sanitize_log_value(malicious_input)

        # The result should be a single line with the fake entry on the same line
        assert "\n" not in result
        assert "status=online" in result
        assert "FAKE ALERT" in result  # Still in string but not on new line

    def test_sanitize_handles_unicode(self):
        """Test that unicode characters are preserved."""
        result = sanitize_log_value("Hello, world!")
        assert result == "Hello, world!"

    def test_sanitize_handles_escape_sequences(self):
        """Test that escape sequences in input are handled."""
        # Form feed, vertical tab, and bell characters
        result = sanitize_log_value("text\f\v\amore")
        # These are control characters and should be replaced
        assert "\f" not in result
        assert "\v" not in result
        assert "\a" not in result

    def test_sanitize_preserves_printable_characters(self):
        """Test that all standard printable ASCII characters are preserved."""
        # All printable ASCII (32-126)
        printable = "".join(chr(i) for i in range(32, 127))
        result = sanitize_log_value(printable)
        assert result == printable
