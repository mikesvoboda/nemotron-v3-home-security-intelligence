"""Database connection and session management using SQLAlchemy 2.0 async patterns.

This module provides PostgreSQL database connectivity using asyncpg,
along with SQL utility functions like ILIKE pattern escaping.

Includes event loop tracking to handle pytest-asyncio's per-test event loops.
When the engine is bound to a different event loop than the current one,
it is automatically disposed and recreated to prevent "Future attached to
a different loop" errors.

Slow Query Logging (NEM-1475):
    Queries exceeding SLOW_QUERY_THRESHOLD_MS are logged at WARNING level with
    query text (truncated) and duration. Optionally records Prometheus metrics
    for query duration distribution.
"""

__all__ = [
    # Classes
    "Base",
    # Functions
    "close_db",
    "disable_slow_query_logging",
    "escape_ilike_pattern",
    "get_db",
    "get_engine",
    "get_pool_status",
    "get_session",
    "get_session_factory",
    "init_db",
    "reset_slow_query_logging_state",
    "setup_slow_query_logging",
    "with_session",
]

import asyncio
import hashlib
import time
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import HTTPException
from sqlalchemy import event, text
from sqlalchemy.exc import (
    IntegrityError,
    OperationalError,
    ProgrammingError,
)
from sqlalchemy.exc import (
    TimeoutError as SQLAlchemyTimeoutError,
)
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from backend.core.config import get_settings
from backend.core.logging import get_logger

# Module logger for slow query logging
_logger = get_logger(__name__)

# Advisory lock key for database schema initialization
# This is a stable key derived from a namespace string to ensure all workers
# attempting to initialize the same database use the same lock.
# We use SHA256 truncated to 63 bits (PostgreSQL bigint safe) for the lock key.
_INIT_DB_LOCK_NAMESPACE = "home_security_intelligence.init_db"
_INIT_DB_LOCK_KEY = int(hashlib.sha256(_INIT_DB_LOCK_NAMESPACE.encode()).hexdigest()[:15], 16)


def escape_ilike_pattern(value: str | None) -> str:
    """Escape special characters in a string for safe use in ILIKE patterns.

    PostgreSQL ILIKE uses '%' and '_' as wildcards and '\\' as escape character.
    This function escapes these characters to prevent pattern injection attacks
    where user input containing these characters could cause unexpected matching.

    Args:
        value: The user-provided string to escape. If None, returns empty string.
               If not a string, converts to string first.

    Returns:
        The escaped string safe for use in ILIKE patterns

    Example:
        >>> escape_ilike_pattern("100% complete")
        '100\\\\% complete'
        >>> escape_ilike_pattern("file_name")
        'file\\\\_name'
        >>> escape_ilike_pattern("path\\\\to\\\\file")
        'path\\\\\\\\to\\\\\\\\file'
        >>> escape_ilike_pattern(None)
        ''
        >>> escape_ilike_pattern(123)
        '123'
    """
    # Handle None input - return empty string
    if value is None:
        return ""

    # Handle non-string input - convert to string
    if not isinstance(value, str):
        value = str(value)

    # Escape backslash first (it's the escape character itself)
    # Then escape % and _ wildcards
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


# Global engine and session factory
_engine: AsyncEngine | None = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None

# Track which event loop the engine was created in
# This is used to detect when pytest-asyncio creates a new loop per test
# and automatically recreate the engine to prevent "Future attached to different loop" errors
_bound_loop_id: int | None = None


def get_engine() -> AsyncEngine:
    """Get or create the global async database engine.

    Returns:
        AsyncEngine: The SQLAlchemy async engine instance.

    Raises:
        RuntimeError: If database has not been initialized.
    """
    if _engine is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get the global async session factory.

    Returns:
        async_sessionmaker: Factory for creating async database sessions.

    Raises:
        RuntimeError: If database has not been initialized.
    """
    if _async_session_factory is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _async_session_factory


async def init_db() -> None:
    """Initialize the database engine and create all tables.

    This function should be called once during application startup.
    It creates the async engine with PostgreSQL connection pooling,
    and creates all tables defined in the Base metadata.

    Uses a PostgreSQL advisory lock to prevent deadlocks when multiple
    workers start simultaneously and all try to create indexes on the
    same tables. Only one worker will actually create the schema; others
    will skip schema creation if they cannot acquire the lock.

    Requires PostgreSQL with asyncpg driver (postgresql+asyncpg://).

    Note: This function tracks the event loop where the engine was created.
    If called from a different event loop (e.g., pytest-asyncio's per-test loops),
    the existing engine is automatically disposed and recreated.
    """
    global _engine, _async_session_factory, _bound_loop_id  # noqa: PLW0603

    # Get current event loop ID
    try:
        current_loop = asyncio.get_running_loop()
        current_loop_id = id(current_loop)
    except RuntimeError:
        current_loop_id = None

    # If engine exists but was created in a different event loop,
    # dispose it first to avoid "Future attached to different loop" errors
    if _engine is not None and _bound_loop_id is not None and _bound_loop_id != current_loop_id:
        try:
            # Reset globals before disposal to avoid issues
            old_engine = _engine
            _engine = None
            _async_session_factory = None
            _bound_loop_id = None
            # Try to dispose - this may fail if loop is already closed
            await old_engine.dispose()
        except (RuntimeError, OSError) as e:
            # RuntimeError: event loop issues (old loop closed, etc.)
            # OSError: connection cleanup failures
            # If disposal fails, that's okay - we've already cleared the globals
            # This can happen when the old loop is closed or when there are
            # pending async operations that can't complete
            import logging

            logging.getLogger(__name__).debug(f"Engine disposal failed (expected): {e}")

    settings = get_settings()
    db_url = settings.database_url

    # Validate PostgreSQL URL format
    if not db_url.startswith("postgresql+asyncpg://"):
        raise ValueError(
            f"Invalid database URL. Expected postgresql+asyncpg:// format, got: {db_url}"
        )

    # PostgreSQL connection pooling configuration
    # These settings optimize for concurrent access and are configurable via Settings
    # Default: pool_size=20, max_overflow=30 (50 max connections)
    # Previous default: pool_size=10, max_overflow=20 (30 max connections)
    # Increased to handle multiple background workers (detection, analysis, timeout,
    # metrics, GPU monitor, system broadcaster) plus API requests
    engine_kwargs: dict[str, Any] = {
        "echo": settings.debug,
        "future": True,
        "pool_size": settings.database_pool_size,
        "max_overflow": settings.database_pool_overflow,
        "pool_timeout": settings.database_pool_timeout,
        "pool_recycle": settings.database_pool_recycle,
        "pool_pre_ping": True,  # Verify connections before use
    }

    # Create async engine
    _engine = create_async_engine(db_url, **engine_kwargs)

    # Store the event loop ID where this engine was created
    _bound_loop_id = current_loop_id

    # Create session factory
    _async_session_factory = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    # Import all models to ensure they're registered with Base.metadata
    from backend.models import Camera, Detection, Event, GPUStats, Zone  # noqa: F401

    # Create all tables with advisory lock to prevent deadlock on concurrent index creation
    # Use the Base from models, not the one defined in this module
    from backend.models.camera import Base as ModelsBase

    async with _engine.begin() as conn:
        # Try to acquire advisory lock - if another worker is already creating schema,
        # this will return False and we skip schema creation.
        # pg_try_advisory_lock returns true if lock was acquired, false otherwise.
        # Note: _INIT_DB_LOCK_KEY is a module-level constant, not user input (safe from SQL injection)
        lock_sql = text(f"SELECT pg_try_advisory_lock({_INIT_DB_LOCK_KEY})")  # nosemgrep
        result = await conn.execute(lock_sql)
        lock_acquired = result.scalar()

        if lock_acquired:
            try:
                # We have the lock - proceed with schema creation
                await conn.run_sync(ModelsBase.metadata.create_all)
            finally:
                # Always release the lock, even if schema creation fails
                unlock_sql = text(f"SELECT pg_advisory_unlock({_INIT_DB_LOCK_KEY})")  # nosemgrep
                await conn.execute(unlock_sql)
        # If lock not acquired, another worker is handling schema creation
        # The tables will be available after that worker completes


async def close_db() -> None:
    """Close the database engine and cleanup resources.

    This function should be called during application shutdown.
    """
    global _engine, _async_session_factory, _bound_loop_id  # noqa: PLW0603

    if _engine is not None:
        try:
            await _engine.dispose()
        except ValueError as e:
            # Handle the case where greenlet is not available (e.g., Python 3.14+)
            # This can happen when the engine was created in a different context
            # or when greenlet is not installed. We still need to reset the globals.
            if "greenlet" in str(e):
                pass  # Gracefully handle missing greenlet
            else:
                raise
        finally:
            _engine = None
            _async_session_factory = None
            _bound_loop_id = None


def _check_loop_mismatch() -> bool:
    """Check if the current event loop differs from where the engine was created.

    Returns:
        True if there's a mismatch (engine bound to different loop), False otherwise.
    """
    if _engine is None or _bound_loop_id is None:
        return False

    try:
        current_loop = asyncio.get_running_loop()
        return id(current_loop) != _bound_loop_id
    except RuntimeError:
        return False


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession]:
    """Get an async database session as a context manager.

    Automatically handles event loop mismatches by reinitializing the
    database engine when the current loop differs from where the engine
    was created (common in pytest-asyncio with function-scoped loops).

    Includes structured logging for database errors:
    - IntegrityError: WARNING (expected, e.g., duplicate key, FK violation)
    - OperationalError: ERROR (infrastructure issue)
    - SQLAlchemyTimeoutError: ERROR (performance/infrastructure issue)
    - ProgrammingError: ERROR with stack trace (indicates bug in application code)
    - Other exceptions: ERROR with exception details

    Usage:
        async with get_session() as session:
            result = await session.execute(select(Model))
            models = result.scalars().all()

    Yields:
        AsyncSession: An async SQLAlchemy session.

    Raises:
        RuntimeError: If database has not been initialized.
        IntegrityError: On constraint violations (logged at WARNING).
        OperationalError: On connection/infrastructure issues (logged at ERROR).
        SQLAlchemyTimeoutError: On database timeout (logged at ERROR).
        ProgrammingError: On SQL syntax errors or bugs (logged at ERROR with traceback).
    """
    # Check for event loop mismatch and auto-reinitialize if needed
    if _check_loop_mismatch():
        await init_db()

    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except IntegrityError as e:
            await session.rollback()
            # Extract constraint name from the original database error if available
            constraint_name = getattr(e.orig, "constraint_name", None)
            if constraint_name is None and e.orig is not None and hasattr(e.orig, "diag"):
                # PostgreSQL asyncpg errors store constraint info in diag
                diag = getattr(e.orig, "diag", None)
                if diag is not None:
                    constraint_name = getattr(diag, "constraint_name", None)
            _logger.warning(
                "Database integrity error",
                extra={
                    "error_type": "integrity_error",
                    "constraint": constraint_name,
                    "detail": str(e.orig) if e.orig else str(e),
                },
            )
            raise
        except OperationalError as e:
            await session.rollback()
            _logger.error(
                "Database operational error",
                extra={
                    "error_type": "operational_error",
                    "detail": str(e.orig) if e.orig else str(e),
                },
            )
            raise
        except SQLAlchemyTimeoutError as e:
            await session.rollback()
            _logger.error(
                "Database timeout error",
                extra={
                    "error_type": "timeout_error",
                    "detail": str(e),
                },
            )
            raise
        except ProgrammingError as e:
            await session.rollback()
            # ProgrammingError indicates a bug in application code (bad SQL, wrong column names, etc.)
            # Log with exception to capture full stack trace for debugging
            _logger.exception(
                "Database programming error (possible bug in application code)",
                extra={
                    "error_type": "programming_error",
                    "detail": str(e.orig) if e.orig else str(e),
                },
            )
            raise
        except HTTPException:
            # HTTPException is an expected application-level exception (e.g., 404 not found)
            # Do not log or rollback - let it propagate to FastAPI's exception handlers
            raise
        except Exception as e:
            await session.rollback()
            # Catch-all for unexpected database errors
            _logger.exception(
                "Unexpected database error",
                extra={
                    "error_type": "unexpected_error",
                    "exception_class": type(e).__name__,
                },
            )
            raise


async def with_session[T](
    operation: Callable[[AsyncSession], Awaitable[T]],
) -> T:
    """Execute an async operation with a managed database session.

    This is a convenience helper that wraps an async operation in a database
    session context. It handles session lifecycle management including:
    - Automatic session creation and cleanup
    - Transaction commit on success
    - Transaction rollback on failure
    - Event loop mismatch detection and re-initialization

    Args:
        operation: An async callable that takes an AsyncSession and returns
            a value of type T. This is typically a lambda or async function
            that performs database operations.

    Returns:
        The result of the operation.

    Raises:
        RuntimeError: If database has not been initialized.
        Any exception raised by the operation (after rollback).

    Example:
        >>> # Simple usage with a lambda
        >>> result = await with_session(
        ...     lambda s: detector.detect_objects(image, session=s)
        ... )

        >>> # Usage with an async function
        >>> async def fetch_camera(session: AsyncSession) -> Camera:
        ...     result = await session.execute(
        ...         select(Camera).where(Camera.name == "front_door")
        ...     )
        ...     return result.scalar_one()
        >>> camera = await with_session(fetch_camera)

        >>> # Usage with a partial application
        >>> from functools import partial
        >>> get_user = partial(get_user_by_id, user_id=123)
        >>> user = await with_session(get_user)
    """
    async with get_session() as session:
        return await operation(session)


async def get_db() -> AsyncGenerator[AsyncSession]:
    """FastAPI dependency for database sessions.

    This function is designed to be used with FastAPI's Depends():

    Includes structured logging for database errors:
    - IntegrityError: WARNING (expected, e.g., duplicate key, FK violation)
    - OperationalError: ERROR (infrastructure issue)
    - SQLAlchemyTimeoutError: ERROR (performance/infrastructure issue)
    - ProgrammingError: ERROR with stack trace (indicates bug in application code)
    - Other exceptions: ERROR with exception details

    Usage:
        @app.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(Item))
            return result.scalars().all()

    Yields:
        AsyncSession: An async SQLAlchemy session.
    """
    # Check for event loop mismatch and auto-reinitialize if needed
    if _check_loop_mismatch():
        await init_db()

    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except IntegrityError as e:
            await session.rollback()
            # Extract constraint name from the original database error if available
            constraint_name = getattr(e.orig, "constraint_name", None)
            if constraint_name is None and e.orig is not None and hasattr(e.orig, "diag"):
                # PostgreSQL asyncpg errors store constraint info in diag
                diag = getattr(e.orig, "diag", None)
                if diag is not None:
                    constraint_name = getattr(diag, "constraint_name", None)
            _logger.warning(
                "Database integrity error",
                extra={
                    "error_type": "integrity_error",
                    "constraint": constraint_name,
                    "detail": str(e.orig) if e.orig else str(e),
                },
            )
            raise
        except OperationalError as e:
            await session.rollback()
            _logger.error(
                "Database operational error",
                extra={
                    "error_type": "operational_error",
                    "detail": str(e.orig) if e.orig else str(e),
                },
            )
            raise
        except SQLAlchemyTimeoutError as e:
            await session.rollback()
            _logger.error(
                "Database timeout error",
                extra={
                    "error_type": "timeout_error",
                    "detail": str(e),
                },
            )
            raise
        except ProgrammingError as e:
            await session.rollback()
            # ProgrammingError indicates a bug in application code (bad SQL, wrong column names, etc.)
            # Log with exception to capture full stack trace for debugging
            _logger.exception(
                "Database programming error (possible bug in application code)",
                extra={
                    "error_type": "programming_error",
                    "detail": str(e.orig) if e.orig else str(e),
                },
            )
            raise
        except HTTPException:
            # HTTPException is an expected application-level exception (e.g., 404 not found)
            # Do not log or rollback - let it propagate to FastAPI's exception handlers
            raise
        except Exception as e:
            await session.rollback()
            # Catch-all for unexpected database errors
            _logger.exception(
                "Unexpected database error",
                extra={
                    "error_type": "unexpected_error",
                    "exception_class": type(e).__name__,
                },
            )
            raise
        finally:
            await session.close()


async def get_pool_status() -> dict[str, Any]:
    """Get connection pool status metrics.

    Returns detailed information about the SQLAlchemy connection pool including:
    - pool_size: Number of connections maintained in the pool
    - overflow: Number of overflow connections currently in use
    - checkedin: Number of connections available in the pool
    - checkedout: Number of connections currently in use
    - total_connections: Total connections (pool_size + overflow)

    Returns:
        dict: Pool status metrics. If database is not initialized or uses NullPool,
        appropriate error information is included.

    Example:
        >>> status = await get_pool_status()
        >>> print(f"Active connections: {status['checkedout']}")
        >>> print(f"Available: {status['checkedin']}")
    """
    if _engine is None:
        return {
            "pool_size": 0,
            "overflow": 0,
            "checkedin": 0,
            "checkedout": 0,
            "total_connections": 0,
            "error": "Database not initialized",
        }

    pool = _engine.pool

    try:
        # QueuePool and derived pools have these methods
        # The base Pool type doesn't expose these, but QueuePool (our actual implementation) does
        pool_size = pool.size()  # type: ignore[attr-defined]
        overflow = pool.overflow()  # type: ignore[attr-defined]
        checkedin = pool.checkedin()  # type: ignore[attr-defined]
        checkedout = pool.checkedout()  # type: ignore[attr-defined]

        return {
            "pool_size": pool_size,
            "overflow": overflow,
            "checkedin": checkedin,
            "checkedout": checkedout,
            "total_connections": pool_size + overflow,
        }
    except AttributeError:
        # NullPool or other pool types without these methods
        return {
            "pool_size": 0,
            "overflow": 0,
            "checkedin": 0,
            "checkedout": 0,
            "total_connections": 0,
            "pooling_disabled": True,
        }


# =============================================================================
# Slow Query Logging (NEM-1475)
# =============================================================================

# Track whether slow query logging has been set up to avoid duplicate listeners
_slow_query_logging_enabled = False


def _before_cursor_execute(
    conn: Any,
    _cursor: Any,
    _statement: str,
    _parameters: Any,
    _context: Any,
    _executemany: bool,
) -> None:
    """SQLAlchemy event listener called before query execution.

    Records the query start time in the connection's info dict for later
    duration calculation.

    Args:
        conn: The database connection
        _cursor: The database cursor (unused, required by SQLAlchemy event signature)
        _statement: The SQL statement (unused here, used in after_cursor_execute)
        _parameters: Query parameters (unused, required by SQLAlchemy event signature)
        _context: Execution context (unused, required by SQLAlchemy event signature)
        _executemany: Whether this is an executemany call (unused, required by event signature)
    """
    conn.info["query_start_time"] = time.perf_counter()


def _sanitize_single_value(
    value: Any,
    max_string_length: int,
) -> Any:
    """Sanitize a single parameter value for logging.

    Args:
        value: The value to sanitize
        max_string_length: Maximum string length before truncation

    Returns:
        Sanitized value
    """
    if isinstance(value, str) and len(value) > max_string_length:
        return value[:max_string_length] + "..."
    if isinstance(value, bytes):
        return f"<bytes length={len(value)}>"
    return value


def _is_sensitive_key(key: str) -> bool:
    """Check if a parameter key contains sensitive data indicators."""
    sensitive_patterns = ("password", "secret", "token", "key", "auth")
    return any(pattern in key.lower() for pattern in sensitive_patterns)


def _sanitize_query_parameters(
    parameters: Any,
    max_string_length: int = 100,
    max_items: int = 10,
) -> dict[str, Any] | list[Any] | str:
    """Sanitize query parameters for safe logging.

    NEM-1503: Sanitizes parameters to prevent logging sensitive data while
    maintaining debugging utility. Truncates long strings and limits collection sizes.

    Args:
        parameters: The query parameters (dict, tuple, list, or scalar)
        max_string_length: Maximum length for string values before truncation
        max_items: Maximum number of items to include from collections

    Returns:
        Sanitized parameters safe for logging
    """
    if parameters is None:
        return {}

    # Handle dict-style parameters
    if isinstance(parameters, dict):
        result: dict[str, Any] = {}
        for i, (key, value) in enumerate(parameters.items()):
            if i >= max_items:
                result["..."] = f"({len(parameters) - max_items} more items)"
                break
            key_str = str(key)
            if _is_sensitive_key(key_str):
                result[key_str] = "[REDACTED]"
            else:
                result[key_str] = _sanitize_single_value(value, max_string_length)
        return result

    # Handle tuple/list-style positional parameters
    if isinstance(parameters, (list, tuple)):
        result_list: list[Any] = []
        for i, value in enumerate(parameters):
            if i >= max_items:
                result_list.append(f"...({len(parameters) - max_items} more items)")
                break
            result_list.append(_sanitize_single_value(value, max_string_length))
        return result_list

    # Handle single scalar value
    return str(_sanitize_single_value(parameters, max_string_length))


def _after_cursor_execute(
    conn: Any,
    _cursor: Any,
    statement: str,
    parameters: Any,
    _context: Any,
    executemany: bool,
) -> None:
    """SQLAlchemy event listener called after query execution.

    Calculates query duration and logs a warning if it exceeds the configured
    threshold. Also records metrics for all queries.

    NEM-1503: Now includes sanitized query parameters in slow query logs.

    Args:
        conn: The database connection
        _cursor: The database cursor (unused, required by SQLAlchemy event signature)
        statement: The SQL statement that was executed
        parameters: Query parameters (included in slow query logs)
        _context: Execution context (unused, required by SQLAlchemy event signature)
        executemany: Whether this was an executemany call
    """
    start_time = conn.info.get("query_start_time")
    if start_time is None:
        return

    duration_seconds = time.perf_counter() - start_time
    duration_ms = duration_seconds * 1000

    # Record metrics for all queries
    try:
        from backend.core.metrics import observe_db_query_duration, record_slow_query

        observe_db_query_duration(duration_seconds)
    except ImportError:
        # Metrics module not available (e.g., during testing without full setup).
        # Query execution should not fail just because metrics are unavailable.
        # See: NEM-2540 for rationale
        pass

    # Check if query exceeds slow query threshold
    settings = get_settings()
    threshold_ms = settings.slow_query_threshold_ms

    if duration_ms > threshold_ms:
        # Record slow query metric
        try:
            record_slow_query()
        except (ImportError, NameError):
            # Metrics not available - slow query logging continues without metric recording.
            # See: NEM-2540 for rationale
            pass

        # Truncate query for logging (max 500 chars)
        truncated_query = statement[:500]
        if len(statement) > 500:
            truncated_query += "..."

        # NEM-1503: Include sanitized parameters for debugging
        sanitized_params = _sanitize_query_parameters(parameters)

        _logger.warning(
            "Slow query detected",
            extra={
                "query": truncated_query,
                "parameters": sanitized_params,
                "duration_ms": round(duration_ms, 2),
                "threshold_ms": threshold_ms,
                "executemany": executemany,
            },
        )


def setup_slow_query_logging(engine: AsyncEngine | None = None) -> bool:
    """Set up SQLAlchemy event listeners for slow query logging.

    Attaches before_cursor_execute and after_cursor_execute event listeners
    to the engine's sync_engine to track query durations and log slow queries.

    Args:
        engine: Optional AsyncEngine to attach listeners to. If None, uses
            the global engine from get_engine().

    Returns:
        True if listeners were successfully attached, False otherwise.

    Note:
        This function is idempotent - calling it multiple times will not
        attach duplicate listeners. The listeners are attached to the
        sync_engine underlying the AsyncEngine.

    Example:
        >>> await init_db()
        >>> setup_slow_query_logging()
        True
    """
    global _slow_query_logging_enabled  # noqa: PLW0603

    if _slow_query_logging_enabled:
        _logger.debug("Slow query logging already enabled")
        return True

    target_engine = engine or _engine
    if target_engine is None:
        _logger.warning("Cannot setup slow query logging: no engine available")
        return False

    try:
        # Get the underlying sync engine from the async engine
        sync_engine = target_engine.sync_engine

        # Attach event listeners
        event.listen(sync_engine, "before_cursor_execute", _before_cursor_execute)
        event.listen(sync_engine, "after_cursor_execute", _after_cursor_execute)

        _slow_query_logging_enabled = True
        _logger.info(
            "Slow query logging enabled",
            extra={"threshold_ms": get_settings().slow_query_threshold_ms},
        )
        return True
    except Exception as e:
        _logger.error(f"Failed to setup slow query logging: {e}")
        return False


def disable_slow_query_logging(engine: AsyncEngine | None = None) -> bool:
    """Remove slow query logging event listeners.

    Args:
        engine: Optional AsyncEngine to remove listeners from. If None, uses
            the global engine from get_engine().

    Returns:
        True if listeners were successfully removed, False otherwise.
    """
    global _slow_query_logging_enabled  # noqa: PLW0603

    if not _slow_query_logging_enabled:
        return True

    target_engine = engine or _engine
    if target_engine is None:
        _slow_query_logging_enabled = False
        return True

    try:
        sync_engine = target_engine.sync_engine

        event.remove(sync_engine, "before_cursor_execute", _before_cursor_execute)
        event.remove(sync_engine, "after_cursor_execute", _after_cursor_execute)

        _slow_query_logging_enabled = False
        _logger.info("Slow query logging disabled")
        return True
    except Exception as e:
        _logger.error(f"Failed to disable slow query logging: {e}")
        return False


def reset_slow_query_logging_state() -> None:
    """Reset the slow query logging state flag.

    This is primarily used for testing to reset state between tests.
    """
    global _slow_query_logging_enabled  # noqa: PLW0603
    _slow_query_logging_enabled = False
