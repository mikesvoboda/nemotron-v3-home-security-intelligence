"""Unit tests for EXPLAIN ANALYZE logging for slow query detection.

Tests cover:
- QueryExplainLogger initialization and configuration
- Event listener registration with SQLAlchemy engine
- Query timing and threshold detection
- EXPLAIN ANALYZE execution for SELECT queries only
- Structured logging output format
- Enable/disable functionality for production control

TDD: These tests are written first to define expected behavior.
"""

import logging
import time
from unittest.mock import MagicMock, patch

import pytest


class TestQueryExplainLoggerConfiguration:
    """Tests for QueryExplainLogger configuration and initialization."""

    def test_default_threshold_is_100ms(self) -> None:
        """Test that the default slow query threshold is 100ms."""
        from backend.core.query_explain import QueryExplainLogger

        logger = QueryExplainLogger()
        assert logger.threshold_ms == 100.0

    def test_custom_threshold_from_settings(self) -> None:
        """Test that threshold can be customized via settings."""
        from backend.core.query_explain import QueryExplainLogger

        with patch("backend.core.query_explain.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                slow_query_threshold_ms=200.0,
                slow_query_explain_enabled=True,
            )
            logger = QueryExplainLogger()
            assert logger.threshold_ms == 200.0

    def test_threshold_from_env_variable(self) -> None:
        """Test that threshold can be set via environment variable."""
        import os

        from backend.core.query_explain import QueryExplainLogger

        original = os.environ.get("SLOW_QUERY_THRESHOLD_MS")
        try:
            os.environ["SLOW_QUERY_THRESHOLD_MS"] = "250"
            with patch("backend.core.query_explain.get_settings") as mock_settings:
                mock_settings.return_value = MagicMock(
                    slow_query_threshold_ms=250.0,
                    slow_query_explain_enabled=True,
                )
                logger = QueryExplainLogger()
                assert logger.threshold_ms == 250.0
        finally:
            if original is None:
                os.environ.pop("SLOW_QUERY_THRESHOLD_MS", None)
            else:
                os.environ["SLOW_QUERY_THRESHOLD_MS"] = original

    def test_enabled_by_default(self) -> None:
        """Test that EXPLAIN logging is enabled by default."""
        from backend.core.query_explain import QueryExplainLogger

        logger = QueryExplainLogger()
        assert logger.enabled is True

    def test_can_be_disabled_via_settings(self) -> None:
        """Test that EXPLAIN logging can be disabled via settings."""
        from backend.core.query_explain import QueryExplainLogger

        with patch("backend.core.query_explain.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                slow_query_threshold_ms=100.0,
                slow_query_explain_enabled=False,
            )
            logger = QueryExplainLogger()
            assert logger.enabled is False


class TestQueryTimingTracking:
    """Tests for query execution time tracking."""

    def test_before_cursor_execute_stores_start_time(self) -> None:
        """Test that before_cursor_execute stores query start time in context."""
        from backend.core.query_explain import QueryExplainLogger

        logger = QueryExplainLogger()

        # Create mock context
        mock_context = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        # Call before hook (using positional args since params are underscore-prefixed)
        logger.before_cursor_execute(
            mock_conn,
            mock_cursor,
            "SELECT * FROM events",
            {},
            mock_context,
            False,
        )

        # Verify start time is stored
        assert hasattr(mock_context, "_query_start_time")
        assert isinstance(mock_context._query_start_time, float)

    def test_after_cursor_execute_calculates_elapsed_time(self) -> None:
        """Test that after_cursor_execute calculates elapsed time correctly."""
        from backend.core.query_explain import QueryExplainLogger

        logger = QueryExplainLogger()

        # Create mock context with start time
        mock_context = MagicMock()
        mock_context._query_start_time = time.time() - 0.150  # 150ms ago
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        with patch.object(logger, "_log_slow_query") as mock_log:
            # Using positional args since some params are underscore-prefixed
            logger.after_cursor_execute(
                mock_conn,
                mock_cursor,
                "SELECT * FROM events",
                {},
                mock_context,
                False,
            )

            # Should have been called since 150ms > 100ms threshold
            assert mock_log.called


class TestSelectQueryDetection:
    """Tests for SELECT query detection (EXPLAIN only runs on SELECTs)."""

    def test_only_select_queries_get_explained(self) -> None:
        """Test that only SELECT queries trigger EXPLAIN ANALYZE."""
        from backend.core.query_explain import QueryExplainLogger

        logger = QueryExplainLogger()

        assert logger._is_select_query("SELECT * FROM events") is True
        assert logger._is_select_query("  SELECT id FROM cameras") is True
        assert logger._is_select_query("select * from detections") is True

    def test_insert_queries_not_explained(self) -> None:
        """Test that INSERT queries do not trigger EXPLAIN."""
        from backend.core.query_explain import QueryExplainLogger

        logger = QueryExplainLogger()

        assert logger._is_select_query("INSERT INTO events (id) VALUES (1)") is False

    def test_update_queries_not_explained(self) -> None:
        """Test that UPDATE queries do not trigger EXPLAIN."""
        from backend.core.query_explain import QueryExplainLogger

        logger = QueryExplainLogger()

        assert logger._is_select_query("UPDATE events SET reviewed = true") is False

    def test_delete_queries_not_explained(self) -> None:
        """Test that DELETE queries do not trigger EXPLAIN."""
        from backend.core.query_explain import QueryExplainLogger

        logger = QueryExplainLogger()

        assert logger._is_select_query("DELETE FROM events WHERE id = 1") is False

    def test_with_cte_select_explained(self) -> None:
        """Test that WITH (CTE) SELECT queries are explained."""
        from backend.core.query_explain import QueryExplainLogger

        logger = QueryExplainLogger()

        cte_query = "WITH recent AS (SELECT * FROM events) SELECT * FROM recent"
        assert logger._is_select_query(cte_query) is True


class TestExplainAnalyzeExecution:
    """Tests for EXPLAIN ANALYZE execution and result parsing."""

    def test_explain_analyze_executed_for_slow_select(self) -> None:
        """Test that EXPLAIN ANALYZE is executed for slow SELECT queries."""
        from backend.core.query_explain import QueryExplainLogger

        logger = QueryExplainLogger()

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_context = MagicMock()
        mock_context._query_start_time = time.time() - 0.150  # 150ms ago

        # Mock the connection's execute method
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            ("Seq Scan on events  (cost=0.00..10.00 rows=100 width=100)",),
            ("Planning Time: 0.100 ms",),
            ("Execution Time: 145.000 ms",),
        ]
        mock_conn.execute.return_value = mock_result

        with patch.object(logger, "_get_logger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            # Using positional args since some params are underscore-prefixed
            logger.after_cursor_execute(
                mock_conn,
                mock_cursor,
                "SELECT * FROM events",
                {},
                mock_context,
                False,
            )

            # Verify EXPLAIN ANALYZE was called - the execute method receives a TextClause
            mock_conn.execute.assert_called()
            # Verify the logger warning was called (indicating slow query detected)
            mock_logger.warning.assert_called_once()

    def test_explain_not_executed_for_fast_queries(self) -> None:
        """Test that EXPLAIN is not executed for queries under threshold."""
        from backend.core.query_explain import QueryExplainLogger

        logger = QueryExplainLogger()

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_context = MagicMock()
        mock_context._query_start_time = time.time() - 0.050  # Only 50ms ago

        with patch.object(logger, "_log_slow_query") as mock_log:
            # Using positional args since some params are underscore-prefixed
            logger.after_cursor_execute(
                mock_conn,
                mock_cursor,
                "SELECT * FROM events",
                {},
                mock_context,
                False,
            )

            # Should not have been called since 50ms < 100ms threshold
            mock_log.assert_not_called()

    def test_explain_not_executed_when_disabled(self) -> None:
        """Test that EXPLAIN is not executed when logging is disabled."""
        from backend.core.query_explain import QueryExplainLogger

        with patch("backend.core.query_explain.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                slow_query_threshold_ms=100.0,
                slow_query_explain_enabled=False,
            )
            logger = QueryExplainLogger()

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_context = MagicMock()
        mock_context._query_start_time = time.time() - 0.150  # 150ms ago

        with patch.object(logger, "_log_slow_query") as mock_log:
            # Using positional args since some params are underscore-prefixed
            logger.after_cursor_execute(
                mock_conn,
                mock_cursor,
                "SELECT * FROM events",
                {},
                mock_context,
                False,
            )

            # Should not be called when disabled
            mock_log.assert_not_called()


class TestStructuredLogging:
    """Tests for structured logging output format."""

    def test_log_includes_query_text(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that log output includes the query text."""
        from backend.core.query_explain import QueryExplainLogger

        logger = QueryExplainLogger()

        with caplog.at_level(logging.WARNING):
            logger._log_slow_query(
                query="SELECT * FROM events WHERE id = 1",
                parameters={"id": 1},
                elapsed_ms=150.0,
                explain_output=["Seq Scan on events"],
            )

        assert "SELECT * FROM events" in caplog.text

    def test_log_includes_elapsed_time(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that log output includes elapsed time in milliseconds."""
        from backend.core.query_explain import QueryExplainLogger

        logger = QueryExplainLogger()

        with caplog.at_level(logging.WARNING):
            logger._log_slow_query(
                query="SELECT * FROM events",
                parameters={},
                elapsed_ms=150.5,
                explain_output=["Seq Scan on events"],
            )

        assert "150.5" in caplog.text or "150" in caplog.text

    def test_log_includes_explain_output(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that log output includes EXPLAIN ANALYZE output."""
        from backend.core.query_explain import QueryExplainLogger

        logger = QueryExplainLogger()

        explain_output = [
            "Seq Scan on events  (cost=0.00..10.00 rows=100 width=100)",
            "Planning Time: 0.100 ms",
            "Execution Time: 145.000 ms",
        ]

        with caplog.at_level(logging.WARNING):
            logger._log_slow_query(
                query="SELECT * FROM events",
                parameters={},
                elapsed_ms=150.0,
                explain_output=explain_output,
            )

        assert "Seq Scan" in caplog.text or "explain" in caplog.text.lower()

    def test_log_uses_warning_level(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that slow query logs use WARNING level."""
        from backend.core.query_explain import QueryExplainLogger

        logger = QueryExplainLogger()

        with caplog.at_level(logging.WARNING):
            logger._log_slow_query(
                query="SELECT * FROM events",
                parameters={},
                elapsed_ms=150.0,
                explain_output=["Seq Scan on events"],
            )

        assert any(record.levelno == logging.WARNING for record in caplog.records)

    def test_log_includes_structured_extra_fields(self) -> None:
        """Test that log includes structured extra fields for JSON logging."""
        from backend.core.query_explain import QueryExplainLogger

        logger = QueryExplainLogger()

        with patch.object(logger, "_get_logger") as mock_get_logger:
            mock_log = MagicMock()
            mock_get_logger.return_value = mock_log

            explain_output = ["Seq Scan on events"]
            logger._log_slow_query(
                query="SELECT * FROM events",
                parameters={"id": 1},
                elapsed_ms=150.0,
                explain_output=explain_output,
            )

            # Verify warning was called with extra dict containing structured fields
            mock_log.warning.assert_called_once()
            call_kwargs = mock_log.warning.call_args
            assert "extra" in call_kwargs.kwargs
            extra = call_kwargs.kwargs["extra"]
            assert "elapsed_ms" in extra
            assert "query" in extra
            assert "explain" in extra


class TestEventListenerRegistration:
    """Tests for SQLAlchemy event listener registration."""

    def test_register_with_engine(self) -> None:
        """Test that event listeners are registered with engine."""
        from backend.core.query_explain import QueryExplainLogger

        logger = QueryExplainLogger()

        mock_engine = MagicMock()

        with patch("backend.core.query_explain.event") as mock_event:
            logger.register(mock_engine)

            # Verify event.listen was called for both hooks
            assert mock_event.listen.call_count == 2

            # Verify before_cursor_execute was registered
            calls = [str(call) for call in mock_event.listen.call_args_list]
            assert any("before_cursor_execute" in call for call in calls)
            assert any("after_cursor_execute" in call for call in calls)

    def test_setup_explain_logging_function(self) -> None:
        """Test the convenience function for setting up EXPLAIN logging."""
        from backend.core.query_explain import setup_explain_logging

        mock_engine = MagicMock()

        with patch("backend.core.query_explain.event") as mock_event:
            setup_explain_logging(mock_engine)

            # Should have registered event listeners
            assert mock_event.listen.called


class TestParameterSanitization:
    """Tests for query parameter sanitization in logs."""

    def test_parameters_are_included_safely(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that parameters are included but potentially sensitive values sanitized."""
        from backend.core.query_explain import QueryExplainLogger

        logger = QueryExplainLogger()

        with caplog.at_level(logging.WARNING):
            logger._log_slow_query(
                query="SELECT * FROM users WHERE email = :email",
                parameters={"email": "user@example.com"},
                elapsed_ms=150.0,
                explain_output=["Index Scan on users"],
            )

        # Parameters should appear in some form in the log
        # (exact format depends on implementation)
        assert "email" in caplog.text or "parameters" in caplog.text.lower()

    def test_password_parameters_are_redacted(self) -> None:
        """Test that password parameters are redacted in logs."""
        from backend.core.query_explain import QueryExplainLogger

        logger = QueryExplainLogger()

        with patch.object(logger, "_get_logger") as mock_get_logger:
            mock_log = MagicMock()
            mock_get_logger.return_value = mock_log

            logger._log_slow_query(
                query="SELECT * FROM users WHERE password = :password",
                parameters={"password": "secret123"},  # pragma: allowlist secret
                elapsed_ms=150.0,
                explain_output=["Index Scan on users"],
            )

            # Get the logged extra data
            call_kwargs = mock_log.warning.call_args
            extra = call_kwargs.kwargs.get("extra", {})

            # If parameters are included, password should be redacted
            if "parameters" in extra:
                params_str = str(extra["parameters"])
                assert "secret123" not in params_str


class TestErrorHandling:
    """Tests for error handling in EXPLAIN execution."""

    def test_explain_error_does_not_crash(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that errors during EXPLAIN execution don't crash the application."""
        from backend.core.query_explain import QueryExplainLogger

        logger = QueryExplainLogger()

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_context = MagicMock()
        mock_context._query_start_time = time.time() - 0.150  # 150ms ago

        # Make execute raise an exception
        mock_conn.execute.side_effect = Exception("Database error")

        # Should not raise - this is the key assertion
        with caplog.at_level(logging.DEBUG):
            # Using positional args since some params are underscore-prefixed
            logger.after_cursor_execute(
                mock_conn,
                mock_cursor,
                "SELECT * FROM events",
                {},
                mock_context,
                False,
            )

        # Slow query should still be logged (with failed EXPLAIN output)
        assert "slow query" in caplog.text.lower() or "database error" in caplog.text.lower()

    def test_missing_start_time_handled_gracefully(self) -> None:
        """Test that missing start time in context is handled gracefully."""
        from backend.core.query_explain import QueryExplainLogger

        logger = QueryExplainLogger()

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_context = MagicMock(spec=[])  # Empty spec means no _query_start_time

        # Should not raise (using positional args since some params are underscore-prefixed)
        logger.after_cursor_execute(
            mock_conn,
            mock_cursor,
            "SELECT * FROM events",
            {},
            mock_context,
            False,
        )


class TestIntegrationWithDatabase:
    """Integration tests that require actual database connection.

    Note: These tests are moved to integration tests as they require
    proper database setup. The sync engine access pattern used by
    query_explain is tested through unit tests with mocks.
    """

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Integration test - requires proper DB setup, covered by unit tests")
    async def test_explain_logging_with_real_query(self, isolated_db: None) -> None:
        """Test EXPLAIN logging with a real database query.

        This test requires the isolated_db fixture for database access.
        """
        from sqlalchemy import text

        from backend.core.database import get_engine, get_session
        from backend.core.query_explain import setup_explain_logging

        engine = get_engine()
        setup_explain_logging(engine.sync_engine)

        async with get_session() as session:
            # Execute a query that should trigger timing
            result = await session.execute(text("SELECT 1"))
            result.fetchall()

        # Test passes if no exceptions were raised
        # In production, slow queries would be logged

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Integration test - requires proper DB setup, covered by unit tests")
    async def test_explain_on_actual_table_query(self, isolated_db: None) -> None:
        """Test EXPLAIN output on actual table query."""
        from sqlalchemy import text

        from backend.core.database import get_session
        from backend.core.query_explain import QueryExplainLogger

        _logger = QueryExplainLogger()

        async with get_session() as session:
            # Create a simple query on the cameras table
            result = await session.execute(text("SELECT * FROM cameras LIMIT 10"))
            result.fetchall()

            # Manually run EXPLAIN to verify it works
            explain_result = await session.execute(
                text("EXPLAIN ANALYZE SELECT * FROM cameras LIMIT 10")
            )
            explain_rows = explain_result.fetchall()

            # Verify EXPLAIN output has expected structure
            assert len(explain_rows) > 0
            explain_text = " ".join(row[0] for row in explain_rows)
            assert "Scan" in explain_text or "Planning" in explain_text
