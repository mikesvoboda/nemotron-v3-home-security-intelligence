"""EXPLAIN ANALYZE logging for slow query performance monitoring.

This module provides automatic detection and logging of slow database queries
with EXPLAIN ANALYZE output for performance debugging. It uses SQLAlchemy's
event system to intercept query execution and measure timing.

Key features:
- Configurable threshold for slow query detection (default: 100ms)
- Only runs EXPLAIN on SELECT queries (INSERT/UPDATE/DELETE excluded)
- Structured JSON logging with query text, parameters, timing, and EXPLAIN output
- Can be enabled/disabled via settings for production control
- Graceful error handling to avoid crashing on EXPLAIN failures

Usage:
    from backend.core.database import get_engine
    from backend.core.query_explain import setup_explain_logging

    # During application startup
    engine = get_engine()
    setup_explain_logging(engine.sync_engine)

Environment variables:
    SLOW_QUERY_THRESHOLD_MS: Threshold in milliseconds (default: 100)
    SLOW_QUERY_EXPLAIN_ENABLED: Enable/disable EXPLAIN logging (default: true)
"""

import logging
import time
from typing import Any

from sqlalchemy import event, text
from sqlalchemy.engine import Engine

from backend.core.config import get_settings

# Logger for this module
_logger = logging.getLogger(__name__)

# Sensitive parameter names that should be redacted in logs
SENSITIVE_PARAM_NAMES = frozenset(
    {
        "password",
        "secret",
        "token",
        "key",
        "api_key",
        "auth",
        "credential",
        "passwd",
        "pwd",
    }
)


class QueryExplainLogger:
    """Logger for slow queries with EXPLAIN ANALYZE output.

    This class provides SQLAlchemy event listeners that track query execution
    time and log EXPLAIN ANALYZE output for queries exceeding a configurable
    threshold.

    The logger only runs EXPLAIN on SELECT queries to avoid side effects
    from running EXPLAIN on INSERT/UPDATE/DELETE statements.

    Attributes:
        threshold_ms: Threshold in milliseconds for slow query detection.
        enabled: Whether EXPLAIN logging is enabled.
    """

    def __init__(self) -> None:
        """Initialize the query explain logger with settings.

        Reads configuration from settings:
        - slow_query_threshold_ms: Threshold for slow query detection
        - slow_query_explain_enabled: Enable/disable the logger
        """
        settings = get_settings()
        self.threshold_ms: float = getattr(settings, "slow_query_threshold_ms", 100.0)
        self.enabled: bool = getattr(settings, "slow_query_explain_enabled", True)

    def _get_logger(self) -> logging.Logger:
        """Get the logger instance for this module.

        Returns:
            Logger instance for query_explain module.
        """
        return _logger

    def _is_select_query(self, statement: str) -> bool:
        """Check if a SQL statement is a SELECT query.

        Only SELECT queries should have EXPLAIN run on them since
        INSERT/UPDATE/DELETE have side effects.

        Args:
            statement: SQL statement string.

        Returns:
            True if the statement is a SELECT query.
        """
        # Normalize whitespace and check for SELECT or WITH (CTE) followed by SELECT
        normalized = statement.strip().upper()

        # Direct SELECT query
        if normalized.startswith("SELECT"):
            return True

        # WITH (CTE) queries that contain SELECT
        return normalized.startswith("WITH") and "SELECT" in normalized

    def _sanitize_parameters(
        self, parameters: dict[str, Any] | tuple | None
    ) -> dict[str, Any] | str:
        """Sanitize query parameters to redact sensitive values.

        Args:
            parameters: Query parameters (dict or tuple).

        Returns:
            Sanitized parameters safe for logging.
        """
        if parameters is None:
            return {}

        if isinstance(parameters, tuple):
            # For tuple parameters, we can't know which are sensitive
            return f"<{len(parameters)} parameters>"

        sanitized = {}
        for key, value in parameters.items():
            key_lower = key.lower()
            # Check if the parameter name contains any sensitive keywords
            is_sensitive = any(sensitive in key_lower for sensitive in SENSITIVE_PARAM_NAMES)
            if is_sensitive:
                sanitized[key] = "[REDACTED]"
            else:
                sanitized[key] = value

        return sanitized

    def _log_slow_query(
        self,
        query: str,
        parameters: dict[str, Any] | tuple | None,
        elapsed_ms: float,
        explain_output: list[str],
    ) -> None:
        """Log a slow query with EXPLAIN ANALYZE output.

        Uses structured logging with extra fields for JSON log parsers.

        Args:
            query: The SQL query text.
            parameters: Query parameters (may be redacted).
            elapsed_ms: Query execution time in milliseconds.
            explain_output: List of EXPLAIN ANALYZE output lines.
        """
        logger = self._get_logger()

        # Sanitize parameters for logging
        safe_params = self._sanitize_parameters(parameters)

        # Build structured log message
        log_message = f"Slow query detected ({elapsed_ms:.2f}ms): {query[:200]}..."

        # Log with structured extra data for JSON logging
        logger.warning(
            log_message,
            extra={
                "query": query,
                "parameters": safe_params,
                "elapsed_ms": elapsed_ms,
                "threshold_ms": self.threshold_ms,
                "explain": explain_output,
            },
        )

    def _run_explain(
        self,
        conn: Any,
        statement: str,
        parameters: dict[str, Any] | tuple | None,
    ) -> list[str]:
        """Run EXPLAIN ANALYZE on a query and return the output.

        Args:
            conn: Database connection.
            statement: SQL statement to explain.
            parameters: Query parameters.

        Returns:
            List of EXPLAIN ANALYZE output lines.
        """
        try:
            # Build EXPLAIN ANALYZE query
            # Note: The statement comes from SQLAlchemy's internal query execution,
            # not from user input, so it's safe to use text() here.
            explain_query = f"EXPLAIN ANALYZE {statement}"

            # Execute EXPLAIN - using text() is safe here since the statement
            # originates from SQLAlchemy's query compiler, not user input
            explain_text = text(explain_query)  # nosemgrep
            result = conn.execute(explain_text, parameters or {})
            rows = result.fetchall()

            # Extract output lines
            return [row[0] for row in rows]
        except Exception as e:
            _logger.debug(f"Failed to run EXPLAIN ANALYZE: {e}")
            return [f"EXPLAIN failed: {e}"]

    def before_cursor_execute(
        self,
        _conn: Any,
        _cursor: Any,
        _statement: str,
        _parameters: dict[str, Any] | tuple | None,
        context: Any,
        _executemany: bool,
    ) -> None:
        """SQLAlchemy event listener called before query execution.

        Records the start time in the execution context for later comparison.

        Note: The underscore-prefixed parameters are required by SQLAlchemy's
        event listener API but not used in this implementation.

        Args:
            _conn: Database connection (required by SQLAlchemy event API).
            _cursor: Database cursor (required by SQLAlchemy event API).
            _statement: SQL statement (required by SQLAlchemy event API).
            _parameters: Query parameters (required by SQLAlchemy event API).
            context: Execution context.
            _executemany: Whether this is an executemany operation (required by SQLAlchemy event API).
        """
        context._query_start_time = time.time()

    def after_cursor_execute(
        self,
        conn: Any,
        _cursor: Any,
        statement: str,
        parameters: dict[str, Any] | tuple | None,
        context: Any,
        _executemany: bool,
    ) -> None:
        """SQLAlchemy event listener called after query execution.

        Calculates elapsed time and logs EXPLAIN output for slow SELECT queries.

        Note: Some parameters (cursor, executemany) are required by SQLAlchemy's
        event listener API but not used in this implementation.

        Args:
            conn: Database connection.
            _cursor: Database cursor (required by SQLAlchemy event API).
            statement: SQL statement.
            parameters: Query parameters.
            context: Execution context.
            _executemany: Whether this is an executemany operation (required by SQLAlchemy event API).
        """
        # Check if start time was recorded
        if not hasattr(context, "_query_start_time"):
            return

        # Calculate elapsed time
        elapsed_seconds = time.time() - context._query_start_time
        elapsed_ms = elapsed_seconds * 1000

        # Check if we should log this query
        if not self.enabled:
            return

        if elapsed_ms < self.threshold_ms:
            return

        if not self._is_select_query(statement):
            return

        # Run EXPLAIN and log
        try:
            explain_output = self._run_explain(conn, statement, parameters)
            self._log_slow_query(
                query=statement,
                parameters=parameters,
                elapsed_ms=elapsed_ms,
                explain_output=explain_output,
            )
        except Exception as e:
            # Don't let logging failures crash the application
            _logger.warning(
                f"Failed to log slow query: {e}",
                extra={"error": str(e), "query": statement[:200]},
            )

    def register(self, engine: Engine) -> None:
        """Register event listeners with a SQLAlchemy engine.

        Args:
            engine: SQLAlchemy Engine instance.
        """
        event.listen(engine, "before_cursor_execute", self.before_cursor_execute)
        event.listen(engine, "after_cursor_execute", self.after_cursor_execute)


def setup_explain_logging(engine: Engine) -> QueryExplainLogger:
    """Set up EXPLAIN ANALYZE logging for slow queries.

    This is a convenience function that creates a QueryExplainLogger
    and registers it with the given engine.

    Args:
        engine: SQLAlchemy Engine instance (sync engine).

    Returns:
        The configured QueryExplainLogger instance.

    Example:
        from backend.core.database import get_engine
        from backend.core.query_explain import setup_explain_logging

        engine = get_engine()
        setup_explain_logging(engine.sync_engine)
    """
    logger = QueryExplainLogger()
    logger.register(engine)
    _logger.info(
        f"EXPLAIN logging enabled: threshold={logger.threshold_ms}ms, enabled={logger.enabled}"
    )
    return logger
