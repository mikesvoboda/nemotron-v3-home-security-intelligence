"""Unit tests for logging module."""

import logging
from unittest.mock import MagicMock, patch

from backend.core.logging import get_logger, get_request_id, set_request_id, setup_logging


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
