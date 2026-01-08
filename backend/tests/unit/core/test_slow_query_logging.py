"""Unit tests for slow query logging functionality (NEM-1475).

Tests cover:
- Event listener registration and removal
- Slow query detection and logging
- Query duration metrics recording
- Query truncation for long statements
- Idempotent setup behavior
"""

from unittest.mock import MagicMock, patch

import pytest


class TestBeforeCursorExecute:
    """Tests for _before_cursor_execute event listener."""

    def test_records_query_start_time(self) -> None:
        """Test that before_cursor_execute records start time in connection info."""
        from backend.core.database import _before_cursor_execute

        # Create mock connection with info dict
        mock_conn = MagicMock()
        mock_conn.info = {}

        # Call the listener using positional arguments (parameter names have underscore prefix)
        _before_cursor_execute(
            mock_conn,  # conn
            MagicMock(),  # _cursor
            "SELECT 1",  # _statement
            None,  # _parameters
            None,  # _context
            False,  # _executemany
        )

        # Verify start time was recorded
        assert "query_start_time" in mock_conn.info
        assert isinstance(mock_conn.info["query_start_time"], float)
        assert mock_conn.info["query_start_time"] > 0


class TestAfterCursorExecute:
    """Tests for _after_cursor_execute event listener."""

    def test_handles_missing_start_time(self) -> None:
        """Test that after_cursor_execute handles missing start time gracefully."""
        from backend.core.database import _after_cursor_execute

        # Create mock connection without start time
        mock_conn = MagicMock()
        mock_conn.info = {}

        # Should not raise (use positional args since some params have underscore prefix)
        _after_cursor_execute(
            mock_conn,  # conn
            MagicMock(),  # _cursor
            "SELECT 1",  # statement
            None,  # _parameters
            None,  # _context
            False,  # executemany
        )

    def test_logs_slow_query_above_threshold(self) -> None:
        """Test that queries exceeding threshold are logged."""
        import time

        from backend.core.database import _after_cursor_execute

        # Create mock connection with start time in the past
        mock_conn = MagicMock()
        # Set start time 200ms ago (above default 100ms threshold)
        mock_conn.info = {"query_start_time": time.perf_counter() - 0.2}

        with (
            patch("backend.core.database.get_settings") as mock_settings,
            patch("backend.core.database._logger") as mock_logger,
            patch("backend.core.metrics.observe_db_query_duration"),
            patch("backend.core.metrics.record_slow_query"),
        ):
            mock_settings.return_value = MagicMock(slow_query_threshold_ms=100.0)

            _after_cursor_execute(
                mock_conn,  # conn
                MagicMock(),  # _cursor
                "SELECT * FROM events WHERE id = 1",  # statement
                None,  # _parameters
                None,  # _context
                False,  # executemany
            )

            # Verify warning was logged
            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args
            assert call_args[0][0] == "Slow query detected"
            assert "extra" in call_args[1]
            assert "query" in call_args[1]["extra"]
            assert "duration_ms" in call_args[1]["extra"]

    def test_does_not_log_fast_query(self) -> None:
        """Test that queries below threshold are not logged."""
        import time

        from backend.core.database import _after_cursor_execute

        # Create mock connection with very recent start time
        mock_conn = MagicMock()
        mock_conn.info = {"query_start_time": time.perf_counter()}

        with (
            patch("backend.core.database.get_settings") as mock_settings,
            patch("backend.core.database._logger") as mock_logger,
            patch("backend.core.metrics.observe_db_query_duration"),
        ):
            mock_settings.return_value = MagicMock(slow_query_threshold_ms=100.0)

            _after_cursor_execute(
                mock_conn,  # conn
                MagicMock(),  # _cursor
                "SELECT 1",  # statement
                None,  # _parameters
                None,  # _context
                False,  # executemany
            )

            # Verify warning was NOT logged
            mock_logger.warning.assert_not_called()

    def test_truncates_long_queries(self) -> None:
        """Test that long query statements are truncated to 500 chars."""
        import time

        from backend.core.database import _after_cursor_execute

        # Create mock connection with start time in the past
        mock_conn = MagicMock()
        mock_conn.info = {"query_start_time": time.perf_counter() - 0.2}

        # Create a very long query
        long_query = "SELECT " + "x" * 600 + " FROM table"

        with (
            patch("backend.core.database.get_settings") as mock_settings,
            patch("backend.core.database._logger") as mock_logger,
            patch("backend.core.metrics.observe_db_query_duration"),
            patch("backend.core.metrics.record_slow_query"),
        ):
            mock_settings.return_value = MagicMock(slow_query_threshold_ms=100.0)

            _after_cursor_execute(
                mock_conn,  # conn
                MagicMock(),  # _cursor
                long_query,  # statement
                None,  # _parameters
                None,  # _context
                False,  # executemany
            )

            # Verify query was truncated
            call_args = mock_logger.warning.call_args
            logged_query = call_args[1]["extra"]["query"]
            assert len(logged_query) == 503  # 500 chars + "..."
            assert logged_query.endswith("...")

    def test_records_metrics_for_all_queries(self) -> None:
        """Test that metrics are recorded for all queries, not just slow ones."""
        import time

        from backend.core.database import _after_cursor_execute

        mock_conn = MagicMock()
        mock_conn.info = {"query_start_time": time.perf_counter()}

        with (
            patch("backend.core.database.get_settings") as mock_settings,
            patch("backend.core.metrics.observe_db_query_duration") as mock_observe,
        ):
            mock_settings.return_value = MagicMock(slow_query_threshold_ms=100.0)

            _after_cursor_execute(
                mock_conn,  # conn
                MagicMock(),  # _cursor
                "SELECT 1",  # statement
                None,  # _parameters
                None,  # _context
                False,  # executemany
            )

            # Verify metrics were recorded
            mock_observe.assert_called_once()
            # Duration should be very small (close to 0)
            recorded_duration = mock_observe.call_args[0][0]
            assert recorded_duration >= 0
            assert recorded_duration < 0.1  # Less than 100ms

    def test_records_slow_query_metric(self) -> None:
        """Test that slow query counter is incremented for slow queries."""
        import time

        from backend.core.database import _after_cursor_execute

        mock_conn = MagicMock()
        mock_conn.info = {"query_start_time": time.perf_counter() - 0.2}

        with (
            patch("backend.core.database.get_settings") as mock_settings,
            patch("backend.core.database._logger"),
            patch("backend.core.metrics.observe_db_query_duration"),
            patch("backend.core.metrics.record_slow_query") as mock_record_slow,
        ):
            mock_settings.return_value = MagicMock(slow_query_threshold_ms=100.0)

            _after_cursor_execute(
                mock_conn,  # conn
                MagicMock(),  # _cursor
                "SELECT 1",  # statement
                None,  # _parameters
                None,  # _context
                False,  # executemany
            )

            # Verify slow query counter was incremented
            mock_record_slow.assert_called_once()


class TestSetupSlowQueryLogging:
    """Tests for setup_slow_query_logging function."""

    def setup_method(self) -> None:
        """Reset slow query logging state before each test."""
        from backend.core.database import reset_slow_query_logging_state

        reset_slow_query_logging_state()

    def teardown_method(self) -> None:
        """Clean up after each test."""
        from backend.core.database import reset_slow_query_logging_state

        reset_slow_query_logging_state()

    def test_returns_false_when_no_engine(self) -> None:
        """Test that setup returns False when no engine is available."""
        import backend.core.database as db_module
        from backend.core.database import setup_slow_query_logging

        # Save original state
        original_engine = db_module._engine

        try:
            db_module._engine = None

            result = setup_slow_query_logging()

            assert result is False
        finally:
            db_module._engine = original_engine

    def test_attaches_event_listeners(self) -> None:
        """Test that event listeners are attached to sync engine."""
        import backend.core.database as db_module
        from backend.core.database import setup_slow_query_logging

        # Create mock async engine with sync_engine
        mock_sync_engine = MagicMock()
        mock_async_engine = MagicMock()
        mock_async_engine.sync_engine = mock_sync_engine

        # Save original state
        original_engine = db_module._engine

        try:
            db_module._engine = mock_async_engine

            with patch("backend.core.database.event.listen") as mock_listen:
                result = setup_slow_query_logging()

                assert result is True
                # Verify both listeners were attached
                assert mock_listen.call_count == 2
                calls = mock_listen.call_args_list
                assert calls[0][0][1] == "before_cursor_execute"
                assert calls[1][0][1] == "after_cursor_execute"
        finally:
            db_module._engine = original_engine

    def test_is_idempotent(self) -> None:
        """Test that calling setup multiple times doesn't attach duplicate listeners."""
        import backend.core.database as db_module
        from backend.core.database import setup_slow_query_logging

        mock_sync_engine = MagicMock()
        mock_async_engine = MagicMock()
        mock_async_engine.sync_engine = mock_sync_engine

        original_engine = db_module._engine

        try:
            db_module._engine = mock_async_engine

            with patch("backend.core.database.event.listen") as mock_listen:
                # First call
                result1 = setup_slow_query_logging()
                assert result1 is True
                first_call_count = mock_listen.call_count

                # Second call
                result2 = setup_slow_query_logging()
                assert result2 is True

                # Should not have added more listeners
                assert mock_listen.call_count == first_call_count
        finally:
            db_module._engine = original_engine

    def test_accepts_custom_engine(self) -> None:
        """Test that setup accepts a custom engine parameter."""
        from backend.core.database import (
            reset_slow_query_logging_state,
            setup_slow_query_logging,
        )

        reset_slow_query_logging_state()

        mock_sync_engine = MagicMock()
        mock_async_engine = MagicMock()
        mock_async_engine.sync_engine = mock_sync_engine

        with patch("backend.core.database.event.listen") as mock_listen:
            result = setup_slow_query_logging(engine=mock_async_engine)

            assert result is True
            # Listeners should be attached to the provided engine's sync_engine
            calls = mock_listen.call_args_list
            assert calls[0][0][0] is mock_sync_engine


class TestDisableSlowQueryLogging:
    """Tests for disable_slow_query_logging function."""

    def setup_method(self) -> None:
        """Reset slow query logging state before each test."""
        from backend.core.database import reset_slow_query_logging_state

        reset_slow_query_logging_state()

    def teardown_method(self) -> None:
        """Clean up after each test."""
        from backend.core.database import reset_slow_query_logging_state

        reset_slow_query_logging_state()

    def test_returns_true_when_not_enabled(self) -> None:
        """Test that disable returns True when logging is not enabled."""
        from backend.core.database import disable_slow_query_logging

        result = disable_slow_query_logging()
        assert result is True

    def test_removes_event_listeners(self) -> None:
        """Test that event listeners are removed from sync engine."""
        import backend.core.database as db_module
        from backend.core.database import (
            disable_slow_query_logging,
            setup_slow_query_logging,
        )

        mock_sync_engine = MagicMock()
        mock_async_engine = MagicMock()
        mock_async_engine.sync_engine = mock_sync_engine

        original_engine = db_module._engine

        try:
            db_module._engine = mock_async_engine

            with (
                patch("backend.core.database.event.listen"),
                patch("backend.core.database.event.remove") as mock_remove,
            ):
                # First enable
                setup_slow_query_logging()

                # Then disable
                result = disable_slow_query_logging()

                assert result is True
                # Verify both listeners were removed
                assert mock_remove.call_count == 2
        finally:
            db_module._engine = original_engine


class TestResetSlowQueryLoggingState:
    """Tests for reset_slow_query_logging_state function."""

    def test_resets_enabled_flag(self) -> None:
        """Test that reset clears the enabled flag."""
        import backend.core.database as db_module
        from backend.core.database import reset_slow_query_logging_state

        # Manually set the flag
        db_module._slow_query_logging_enabled = True

        reset_slow_query_logging_state()

        assert db_module._slow_query_logging_enabled is False


class TestSlowQueryThresholdConfig:
    """Tests for slow_query_threshold_ms configuration setting."""

    def test_default_threshold_value(self) -> None:
        """Test that default slow query threshold is 100ms."""
        from backend.core.config import Settings

        settings = Settings(
            database_url="postgresql+asyncpg://user:pass@localhost/db",  # pragma: allowlist secret
        )
        assert settings.slow_query_threshold_ms == 100.0

    def test_custom_threshold_value(self) -> None:
        """Test that slow query threshold can be customized."""
        from backend.core.config import Settings

        settings = Settings(
            database_url="postgresql+asyncpg://user:pass@localhost/db",  # pragma: allowlist secret
            slow_query_threshold_ms=250.0,
        )
        assert settings.slow_query_threshold_ms == 250.0

    def test_threshold_validation_min(self) -> None:
        """Test that slow query threshold has minimum validation."""
        from pydantic import ValidationError

        from backend.core.config import Settings

        with pytest.raises(ValidationError):
            Settings(
                database_url="postgresql+asyncpg://user:pass@localhost/db",  # pragma: allowlist secret
                slow_query_threshold_ms=5.0,  # Below minimum of 10
            )

    def test_threshold_validation_max(self) -> None:
        """Test that slow query threshold has maximum validation."""
        from pydantic import ValidationError

        from backend.core.config import Settings

        with pytest.raises(ValidationError):
            Settings(
                database_url="postgresql+asyncpg://user:pass@localhost/db",  # pragma: allowlist secret
                slow_query_threshold_ms=15000.0,  # Above maximum of 10000
            )


class TestSlowQueryExplainConfig:
    """Tests for slow_query_explain_enabled configuration setting."""

    def test_default_explain_enabled(self) -> None:
        """Test that EXPLAIN logging is enabled by default."""
        from backend.core.config import Settings

        settings = Settings(
            database_url="postgresql+asyncpg://user:pass@localhost/db",  # pragma: allowlist secret
        )
        assert settings.slow_query_explain_enabled is True

    def test_explain_can_be_disabled(self) -> None:
        """Test that EXPLAIN logging can be disabled."""
        from backend.core.config import Settings

        settings = Settings(
            database_url="postgresql+asyncpg://user:pass@localhost/db",  # pragma: allowlist secret
            slow_query_explain_enabled=False,
        )
        assert settings.slow_query_explain_enabled is False
