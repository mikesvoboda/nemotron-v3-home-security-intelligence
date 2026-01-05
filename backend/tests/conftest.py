"""Pytest configuration and shared fixtures.

This module provides shared test fixtures for all backend tests:
- isolated_db: Function-scoped isolated database for unit tests (PostgreSQL)
- test_db: Callable session factory for unit tests
- mock_redis: Mock Redis client for unit tests

Integration tests use module-scoped containers defined in backend/tests/integration/conftest.py
for full test isolation without race conditions.

Tests use PostgreSQL and Redis via testcontainers or local instances.
Configure TEST_DATABASE_URL/TEST_REDIS_URL environment variables for overrides.

See backend/tests/AGENTS.md for full documentation on test conventions.
"""

from __future__ import annotations

import logging
import os
import socket
import sys
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest

# NEM-1061: Logger for test cleanup handlers
logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator


# Add backend to path for imports
backend_path = Path(__file__).parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


# =============================================================================
# Hypothesis Configuration
# =============================================================================
# Property-based testing profiles for different execution contexts.
# Usage:
#   pytest --hypothesis-profile=ci       # Fast CI runs (fewer examples)
#   pytest --hypothesis-profile=dev      # Development (default, more examples)
#   pytest --hypothesis-profile=nightly  # Nightly runs (thorough testing)
#   pytest --hypothesis-profile=debug    # Debugging (verbose, reproducible)


def _configure_hypothesis_profiles() -> None:
    """Configure Hypothesis profiles for property-based testing.

    Profiles:
    - ci: Fast profile for CI pipelines (fewer examples, shorter deadlines)
    - dev: Default development profile (balanced exploration)
    - nightly: Thorough profile for nightly runs (more examples, find edge cases)
    - debug: Debugging profile (verbose, deterministic, fewer examples)
    """
    from hypothesis import Phase, Verbosity, settings

    # CI Profile: Fast execution for pull request checks
    # - 25 examples per test (vs 100 default) for speed
    # - 200ms deadline to catch obvious performance issues
    # - Skip shrinking to save time (CI just needs pass/fail)
    settings.register_profile(
        "ci",
        max_examples=25,
        deadline=200,  # milliseconds
        suppress_health_check=[],
        print_blob=True,  # Print reproducible example on failure
        phases=[Phase.explicit, Phase.reuse, Phase.generate],  # Skip shrinking
    )

    # Dev Profile: Default development settings
    # - 50 examples per test (balanced exploration)
    # - 500ms deadline for reasonable performance
    # - Full phase execution including shrinking
    settings.register_profile(
        "dev",
        max_examples=50,
        deadline=500,  # milliseconds
        suppress_health_check=[],
        print_blob=True,
    )

    # Nightly Profile: Thorough testing for edge case discovery
    # - 200 examples per test (thorough exploration)
    # - 2000ms deadline (allow slower operations)
    # - Full phases including extensive shrinking
    settings.register_profile(
        "nightly",
        max_examples=200,
        deadline=2000,  # milliseconds
        suppress_health_check=[],
        print_blob=True,
        phases=[Phase.explicit, Phase.reuse, Phase.generate, Phase.target, Phase.shrink],
    )

    # Debug Profile: For investigating specific failures
    # - 10 examples (focus on reproduction)
    # - No deadline (allow debugging pauses)
    # - Verbose output for understanding test execution
    # - Deterministic with seed for reproducibility
    settings.register_profile(
        "debug",
        max_examples=10,
        deadline=None,  # No deadline for debugging
        verbosity=Verbosity.verbose,
        print_blob=True,
        phases=[Phase.explicit, Phase.reuse, Phase.generate, Phase.shrink],
    )

    # Set default profile based on environment
    # CI environments typically set CI=true
    import os

    if os.environ.get("CI"):
        settings.load_profile("ci")
    else:
        settings.load_profile("dev")


def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest before test collection.

    Sets environment variables needed before any test modules are imported.
    Also configures Hypothesis profiles for property-based testing.
    """
    # Force pure-Python protobuf implementation for Python 3.14+ compatibility.
    # The C++ extension fails with "Metaclasses with custom tp_new are not supported."
    # See: https://bugzilla.redhat.com/show_bug.cgi?id=2356165
    os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")

    # Set default DATABASE_URL for test collection (required by pydantic Settings)
    # This is needed because some modules import settings at module level
    os.environ.setdefault(
        "DATABASE_URL",
        "postgresql+asyncpg://security:security_dev_password@localhost:5432/security",
    )

    # Configure Hypothesis profiles for property-based testing
    # See: https://hypothesis.readthedocs.io/en/latest/settings.html
    _configure_hypothesis_profiles()


# Default development PostgreSQL URL (matches docker-compose.yml)
DEFAULT_DEV_POSTGRES_URL = (
    "postgresql+asyncpg://security:security_dev_password@localhost:5432/security"
)

# Default development Redis URL (matches docker-compose.yml, using DB 15 for test isolation)
DEFAULT_DEV_REDIS_URL = "redis://localhost:6379/15"


def _check_tcp_connection(host: str = "localhost", port: int = 5432) -> bool:
    """Check if a TCP service is reachable on the given host/port."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception as e:
        # NEM-1061: Log suppressed exception for debugging
        logger.debug(
            "TCP connection check failed",
            extra={"host": host, "port": port, "error": str(e)},
        )
        return False


def _check_postgres_connection(host: str = "localhost", port: int = 5432) -> bool:
    """Check if PostgreSQL is reachable on the given host/port."""
    return _check_tcp_connection(host, port)


def _check_redis_connection(host: str = "localhost", port: int = 6379) -> bool:
    """Check if Redis is reachable on the given host/port."""
    return _check_tcp_connection(host, port)


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Assign timeouts based on test location and markers.

    Timeout hierarchy (highest priority first):
    1. CLI --timeout=0 disables all timeouts (for CI)
    2. Explicit @pytest.mark.timeout(N) on test - unchanged
    3. @pytest.mark.slow marker - 30 seconds
    4. Integration tests (in integration/ directory) - 5 seconds
    5. Default from pyproject.toml - 1 second
    """
    import pytest

    # Check if timeouts are disabled via CLI (--timeout=0)
    # This is used in CI where environment is slower
    cli_timeout = config.getoption("timeout", default=None)
    if cli_timeout == 0:
        # Don't add any timeout markers - let pytest-timeout handle it
        return

    for item in items:
        # Skip if test has explicit timeout marker
        if item.get_closest_marker("timeout"):
            continue

        # Slow-marked tests get 30s
        if item.get_closest_marker("slow"):
            item.add_marker(pytest.mark.timeout(30))
            continue

        # Integration tests get 5s
        if "/integration/" in str(item.fspath):
            item.add_marker(pytest.mark.timeout(5))
            continue

        # Unit tests use default (1s from pyproject.toml)


def get_test_db_url() -> str:
    """Get the PostgreSQL test database URL for unit tests.

    Priority order:
    1. TEST_DATABASE_URL environment variable (explicit override)
    2. Local PostgreSQL on port 5432 (development with Podman/Docker)

    For integration tests, use the module-scoped containers in
    backend/tests/integration/conftest.py instead.

    Returns:
        str: PostgreSQL connection URL with asyncpg driver

    Raises:
        RuntimeError: If no PostgreSQL instance is available
    """
    # 1. Check for explicit environment variable override
    env_url = os.environ.get("TEST_DATABASE_URL")
    if env_url:
        # Ensure asyncpg driver
        if "postgresql://" in env_url and "asyncpg" not in env_url:
            env_url = env_url.replace("postgresql://", "postgresql+asyncpg://")
        return env_url

    # 2. Check for local PostgreSQL (development environment with Podman/Docker)
    if _check_postgres_connection():
        return DEFAULT_DEV_POSTGRES_URL

    raise RuntimeError(
        "PostgreSQL not available for unit testing. Options:\n"
        "1. Start PostgreSQL via 'podman-compose up -d postgres' (development)\n"
        "2. Set TEST_DATABASE_URL environment variable\n"
        "Note: Integration tests use module-scoped testcontainers."
    )


def get_test_redis_url() -> str:
    """Get the Redis test URL for unit tests.

    Priority order:
    1. TEST_REDIS_URL environment variable (explicit override)
    2. Local Redis on port 6379 (development with Podman/Docker)

    For integration tests, use the module-scoped containers in
    backend/tests/integration/conftest.py instead.

    Returns:
        str: Redis connection URL with database 15 for test isolation

    Raises:
        RuntimeError: If no Redis instance is available
    """
    # 1. Check for explicit environment variable override
    env_url = os.environ.get("TEST_REDIS_URL")
    if env_url:
        return env_url

    # 2. Check for local Redis (development environment with Podman/Docker)
    if _check_redis_connection():
        return DEFAULT_DEV_REDIS_URL

    raise RuntimeError(
        "Redis not available for unit testing. Options:\n"
        "1. Start Redis via 'podman-compose up -d redis' (development)\n"
        "2. Set TEST_REDIS_URL environment variable\n"
        "Note: Integration tests use module-scoped testcontainers."
    )


# Track if schema has been reset this worker process to avoid redundant operations
_schema_reset_done: bool = False


async def _ensure_clean_db() -> None:
    """Ensure database has tables and is ready for tests.

    This function creates tables if they don't exist.

    Test isolation is achieved through:
    1. Savepoint/rollback in the session fixture (transaction isolation)
    2. Using unique_id() for test data (prevents cross-test conflicts)

    Note: Integration tests use module-scoped containers which provide
    full isolation without needing advisory locks.
    """
    await _reset_db_schema()


async def _reset_db_schema() -> None:
    """Create all tables and add any missing columns to match current models.

    This is called once per database to ensure the database schema matches
    the current SQLAlchemy models. Uses create_all for new tables and
    explicit ALTER TABLE for missing columns.

    Uses a PostgreSQL advisory lock to prevent deadlocks when multiple pytest-xdist
    workers attempt to modify schema concurrently. The lock key is different from
    the one used in init_db to avoid conflicts.
    """
    global _schema_reset_done  # noqa: PLW0603

    if _schema_reset_done:
        return

    import hashlib

    from sqlalchemy import text

    from backend.core.database import get_engine

    # Import all models to ensure they're registered with Base.metadata
    from backend.models import Camera, Detection, Event, GPUStats  # noqa: F401
    from backend.models.camera import Base as ModelsBase

    engine = get_engine()
    if engine is None:
        return

    # Mark as done FIRST to prevent re-entry from concurrent coroutines
    _schema_reset_done = True

    # Advisory lock key for test schema reset (different from init_db lock key)
    # This prevents concurrent DDL operations that could cause deadlocks
    _TEST_SCHEMA_LOCK_NAMESPACE = "home_security_intelligence.test_schema_reset"
    _TEST_SCHEMA_LOCK_KEY = int(
        hashlib.sha256(_TEST_SCHEMA_LOCK_NAMESPACE.encode()).hexdigest()[:15], 16
    )

    async with engine.begin() as conn:
        # Acquire advisory lock to serialize DDL operations across pytest-xdist workers
        # Using pg_advisory_lock (blocking) to ensure all workers wait rather than skip
        lock_sql = text(f"SELECT pg_advisory_lock({_TEST_SCHEMA_LOCK_KEY})")  # nosemgrep
        await conn.execute(lock_sql)

        try:
            # Create tables if they don't exist
            await conn.run_sync(ModelsBase.metadata.create_all)

            # Add any missing columns that create_all doesn't handle
            # This handles schema drift without dropping data
            # Using IF NOT EXISTS makes this idempotent and safe to run in parallel
            await conn.execute(text("ALTER TABLE events ADD COLUMN IF NOT EXISTS llm_prompt TEXT"))
            await conn.execute(
                text("ALTER TABLE detections ADD COLUMN IF NOT EXISTS enrichment_data JSONB")
            )

            # Add unique indexes for cameras table (migration adds these for production)
            # First, clean up any duplicate cameras that might prevent index creation
            # Delete duplicate cameras by name (keep oldest)
            await conn.execute(
                text(
                    """
                    DELETE FROM cameras
                    WHERE id IN (
                        SELECT id FROM (
                            SELECT id,
                                   ROW_NUMBER() OVER (
                                       PARTITION BY name
                                       ORDER BY created_at ASC, id ASC
                                   ) as rn
                            FROM cameras
                        ) ranked
                        WHERE rn > 1
                    )
                    """
                )
            )

            # Delete duplicate cameras by folder_path (keep oldest)
            await conn.execute(
                text(
                    """
                    DELETE FROM cameras
                    WHERE id IN (
                        SELECT id FROM (
                            SELECT id,
                                   ROW_NUMBER() OVER (
                                       PARTITION BY folder_path
                                       ORDER BY created_at ASC, id ASC
                                   ) as rn
                            FROM cameras
                        ) ranked
                        WHERE rn > 1
                    )
                    """
                )
            )

            # Now create unique indexes (using IF NOT EXISTS for idempotency)
            await conn.execute(
                text("CREATE UNIQUE INDEX IF NOT EXISTS idx_cameras_name_unique ON cameras (name)")
            )
            await conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_cameras_folder_path_unique ON cameras (folder_path)"
                )
            )
        finally:
            # Always release the advisory lock
            unlock_sql = text(f"SELECT pg_advisory_unlock({_TEST_SCHEMA_LOCK_KEY})")  # nosemgrep
            await conn.execute(unlock_sql)


def _get_table_deletion_order(metadata: object) -> list[str]:
    """Compute the correct table deletion order based on foreign key relationships.

    Uses a topological sort to determine the order in which tables should be deleted
    to respect foreign key constraints. Tables that reference other tables must be
    deleted before the tables they reference.

    Args:
        metadata: SQLAlchemy MetaData object containing table definitions

    Returns:
        List of table names in the order they should be deleted (leaf tables first,
        parent tables last)
    """
    from collections import defaultdict

    # Build a dependency graph: table -> set of tables it references
    # A table "depends on" another if it has a FK pointing to it
    dependencies: dict[str, set[str]] = defaultdict(set)
    all_tables: set[str] = set()

    for table in metadata.tables.values():  # type: ignore[attr-defined]
        table_name = table.name
        all_tables.add(table_name)
        for fk in table.foreign_keys:
            # fk.column.table.name is the table being referenced
            referenced_table = fk.column.table.name
            dependencies[table_name].add(referenced_table)
            all_tables.add(referenced_table)

    # Topological sort using Kahn's algorithm
    # We want tables with dependencies to come FIRST (delete children before parents)
    # So we invert the typical topological sort order

    # Build reverse dependency graph: table -> tables that depend on it
    dependents: dict[str, set[str]] = defaultdict(set)
    for table, deps in dependencies.items():
        for dep in deps:
            dependents[dep].add(table)

    # Start with tables that have dependents but no dependencies (parent tables)
    # and tables with no relationships at all
    # We'll process in reverse order to get children first

    # Count how many tables each table references (in-degree in dependency graph)
    in_degree: dict[str, int] = {table: len(dependencies[table]) for table in all_tables}

    # Tables with no dependencies can be processed first in normal topo sort
    # But we want children first, so we'll collect all and reverse
    result: list[str] = []
    queue: list[str] = [table for table in all_tables if in_degree[table] == 0]

    while queue:
        # Process a table with no remaining dependencies
        table = queue.pop(0)
        result.append(table)

        # Remove this table from dependencies of other tables
        for dependent in dependents[table]:
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(dependent)

    # Reverse to get deletion order (children/leaf tables first, parents last)
    result.reverse()

    # Handle any remaining tables (circular dependencies - shouldn't happen with proper schema)
    remaining = all_tables - set(result)
    if remaining:
        logger.warning(
            "Circular dependencies detected in schema",
            extra={"remaining_tables": sorted(remaining)},
        )
        result.extend(sorted(remaining))

    return result


async def _cleanup_test_cameras() -> None:
    """Delete all test camera data created by tests using isolated_db.

    This helper function cleans up all camera-related data in correct order
    (respecting foreign key constraints) to prevent orphaned entries from
    accumulating in the database.

    Uses automatic FK ordering based on SQLAlchemy metadata to determine
    the correct deletion order. Tables with foreign key references are
    deleted before the tables they reference.

    Uses DELETE instead of TRUNCATE to avoid AccessExclusiveLock deadlocks.
    """
    from sqlalchemy import text

    from backend.core.database import get_engine, get_session
    from backend.models.camera import Base as ModelsBase

    try:
        engine = get_engine()
        if engine is None:
            return

        # Get the correct deletion order from FK relationships
        deletion_order = _get_table_deletion_order(ModelsBase.metadata)

        async with get_session() as session:
            # Delete all test-related data in correct order (respecting FK constraints)
            # Order is automatically determined from foreign key relationships
            for table_name in deletion_order:
                # Safe: table_name comes from SQLAlchemy metadata, not user input
                await session.execute(text(f"DELETE FROM {table_name}"))  # noqa: S608 nosemgrep

            await session.commit()
    except Exception as e:
        # NEM-1061: Log suppressed exception for debugging
        logger.debug(
            "Test cleanup failed during table deletion",
            extra={"error": str(e), "error_type": type(e).__name__},
        )


@pytest.fixture(scope="function")
async def isolated_db() -> AsyncGenerator[None]:
    """Create an isolated test database for each test.

    This fixture:
    - Uses the shared PostgreSQL testcontainer or local PostgreSQL
    - Sets the DATABASE_URL environment variable
    - Clears the settings cache
    - Ensures tables exist (created once per worker, coordinated via advisory lock)
    - Yields control to the test
    - Cleans up test data and restores the original state

    Note: For true isolation in parallel tests, use the `session` fixture
    which provides transaction-based rollback isolation. Tests should use
    unique IDs (via unique_id() helper) to avoid conflicts with parallel tests.
    """
    from backend.core.config import get_settings
    from backend.core.database import close_db, init_db

    # Save original state
    original_db_url = os.environ.get("DATABASE_URL")

    # Clear the settings cache to force reload
    get_settings.cache_clear()

    # Get base PostgreSQL URL from testcontainer or local PostgreSQL
    test_db_url = get_test_db_url()

    # Set test database URL
    os.environ["DATABASE_URL"] = test_db_url

    # Clear cache again after setting env var
    get_settings.cache_clear()

    # Ensure database is closed before initializing
    await close_db()

    # Initialize database (creates engine and tables)
    await init_db()

    # Ensure schema exists and is ready for tests
    # This is coordinated across workers via advisory lock
    await _ensure_clean_db()

    yield

    # Clean up test data before closing database
    await _cleanup_test_cameras()

    # Close database connection
    await close_db()

    # Restore original state
    if original_db_url:
        os.environ["DATABASE_URL"] = original_db_url
    else:
        os.environ.pop("DATABASE_URL", None)

    # Clear cache one more time to ensure clean state
    get_settings.cache_clear()


@pytest.fixture
async def session(isolated_db: None) -> AsyncGenerator[None]:
    """Create an isolated database session with transaction rollback for each test.

    This fixture provides true isolation in parallel test execution by:
    1. Starting a savepoint before each test
    2. Rolling back to the savepoint after each test

    All data created during the test is automatically rolled back, ensuring
    parallel tests don't see each other's data.

    Usage:
        @pytest.mark.asyncio
        async def test_something(session):
            camera = Camera(id="test", name="Test")
            session.add(camera)
            await session.flush()
            # Test assertions...
            # Data is automatically rolled back after test
    """
    from sqlalchemy import text

    from backend.core.database import get_session

    async with get_session() as sess:
        # Start a savepoint that we'll roll back to after the test
        # This ensures test isolation without needing TRUNCATE
        await sess.execute(text("SAVEPOINT test_savepoint"))

        try:
            yield sess
        finally:
            # Roll back to savepoint to undo all changes from this test
            await sess.execute(text("ROLLBACK TO SAVEPOINT test_savepoint"))


@pytest.fixture(autouse=True)
def reset_settings_cache() -> Generator[None]:
    """Automatically reset settings cache and ensure required env vars before each test.

    This ensures:
    1. No global state leaks between tests
    2. Required environment variables (DATABASE_URL, REDIS_URL) have valid defaults
       so unit tests that instantiate classes calling get_settings() don't fail

    Note: We don't auto-close database here since some tests
    explicitly test the behavior when database is not initialized.
    """
    from backend.core.config import get_settings

    # Save original env vars to restore after test
    original_db_url = os.environ.get("DATABASE_URL")
    original_redis_url = os.environ.get("REDIS_URL")

    # Set default test values if not already set
    # This prevents Settings validation errors in unit tests that don't need a real DB
    if not os.environ.get("DATABASE_URL"):
        os.environ["DATABASE_URL"] = DEFAULT_DEV_POSTGRES_URL
    if not os.environ.get("REDIS_URL"):
        os.environ["REDIS_URL"] = DEFAULT_DEV_REDIS_URL

    # Clear settings cache before test
    get_settings.cache_clear()

    yield

    # Restore original env vars (or remove if they weren't set)
    if original_db_url is None:
        os.environ.pop("DATABASE_URL", None)
    else:
        os.environ["DATABASE_URL"] = original_db_url

    if original_redis_url is None:
        os.environ.pop("REDIS_URL", None)
    else:
        os.environ["REDIS_URL"] = original_redis_url

    # Clear settings cache after test
    get_settings.cache_clear()


@pytest.fixture
async def test_db() -> AsyncGenerator[None]:
    """Create test database session factory for unit tests.

    This fixture provides a callable that returns a context manager for database sessions.
    It sets up a PostgreSQL test database with fresh schema and ensures cleanup.

    Usage:
        async with test_db() as session:
            # Use session for database operations
            ...
    """

    from backend.core.config import get_settings
    from backend.core.database import close_db, get_session, init_db

    # Save original state
    original_db_url = os.environ.get("DATABASE_URL")

    # Clear the settings cache to force reload
    get_settings.cache_clear()

    # Get PostgreSQL URL from testcontainer or local PostgreSQL
    test_db_url = get_test_db_url()

    # Set test database URL
    os.environ["DATABASE_URL"] = test_db_url

    # Clear cache again after setting env var
    get_settings.cache_clear()

    # Ensure database is closed before initializing
    await close_db()

    # Initialize database (creates engine)
    await init_db()

    # Reset schema to ensure it matches current models
    await _reset_db_schema()

    # Return the get_session function as a callable
    yield get_session

    # Clean up test data before closing database
    await _cleanup_test_cameras()

    # Close database connection
    await close_db()

    # Restore original state
    if original_db_url:
        os.environ["DATABASE_URL"] = original_db_url
    else:
        os.environ.pop("DATABASE_URL", None)

    # Clear cache one more time to ensure clean state
    get_settings.cache_clear()


# =============================================================================
# Shared Utility Fixtures
# =============================================================================
# These fixtures are available to all tests (unit and integration).
# Integration tests use module-scoped fixtures from backend/tests/integration/conftest.py


@pytest.fixture
async def mock_redis() -> AsyncGenerator[AsyncMock]:
    """Mock Redis operations for tests that don't need real Redis.

    This fixture provides a mock Redis client with common operations pre-configured:
    - health_check: Returns healthy status

    The mock is patched into backend.core.redis module.

    Use this for unit tests that need to mock Redis behavior.
    Integration tests should use the mock_redis or real_redis fixtures
    from backend/tests/integration/conftest.py instead.
    """
    mock_redis_client = AsyncMock()
    mock_redis_client.health_check.return_value = {
        "status": "healthy",
        "connected": True,
        "redis_version": "7.0.0",
    }

    # Patch the shared singleton, initializer, and closer.
    with (
        patch("backend.core.redis._redis_client", mock_redis_client),
        patch("backend.core.redis.init_redis", return_value=mock_redis_client),
        patch("backend.core.redis.close_redis", return_value=None),
    ):
        yield mock_redis_client


def unique_id(prefix: str = "test") -> str:
    """Generate a unique ID for test objects to prevent conflicts in parallel execution.

    Args:
        prefix: Optional prefix for the ID (default: "test")

    Returns:
        A unique string ID like "test_abc12345"
    """
    import uuid

    return f"{prefix}_{uuid.uuid4().hex[:8]}"
