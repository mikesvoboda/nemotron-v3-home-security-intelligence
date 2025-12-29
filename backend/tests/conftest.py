"""Pytest configuration and shared fixtures.

This module provides shared test fixtures for all backend tests:
- isolated_db: Function-scoped isolated database for unit tests
- test_db: Callable session factory for unit tests
- integration_env: Environment setup for integration tests
- integration_db: Initialized database for integration tests
- mock_redis: Mock Redis client for integration tests
- db_session: Database session for integration tests
- client: httpx AsyncClient for API integration tests

See backend/tests/AGENTS.md for full documentation on test conventions.
"""

from __future__ import annotations

import os
import socket
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest
from testcontainers.postgres import PostgresContainer

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator

# Add backend to path for imports
backend_path = Path(__file__).parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


# Default development PostgreSQL URL (matches docker-compose.yml)
DEFAULT_DEV_POSTGRES_URL = (
    "postgresql+asyncpg://security:security_dev_password@localhost:5432/security"
)


def _check_postgres_connection(host: str = "localhost", port: int = 5432) -> bool:
    """Check if PostgreSQL is reachable on the given host/port."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False


# Module-level PostgreSQL container shared across all tests in a session
_postgres_container: PostgresContainer | None = None


def pytest_configure(config):
    """Start PostgreSQL container once for the entire test session.

    Also configures pytest-xdist to use loadgroup scheduling when
    running tests in parallel, which respects xdist_group markers.
    This ensures tests marked with @pytest.mark.xdist_group run
    sequentially on the same worker.

    Skipped when:
    - TEST_DATABASE_URL environment variable is set (explicit override)
    - Local PostgreSQL is already running on port 5432 (Podman/Docker)
    """
    global _postgres_container  # noqa: PLW0603

    # Configure xdist to use loadgroup scheduling if xdist is active
    # This ensures tests with xdist_group markers run on the same worker
    # Must be done after command line parsing but before test collection
    if hasattr(config, "workerinput"):
        # We're a worker, don't reconfigure
        pass
    elif hasattr(config.option, "dist"):
        # Override to loadgroup to respect xdist_group markers
        # This is necessary because -n X implicitly sets --dist=load
        config.option.dist = "loadgroup"

    # Skip if explicit database URL is provided
    if os.environ.get("TEST_DATABASE_URL"):
        return

    # Skip if local PostgreSQL is already running (development environment)
    if _check_postgres_connection():
        return

    # Try to start testcontainer, skip if Docker/Podman not available
    try:
        _postgres_container = PostgresContainer("postgres:16-alpine", driver="asyncpg")
        _postgres_container.start()
    except Exception as e:
        # Log warning but don't fail - tests will use local PostgreSQL if available
        print(
            f"Warning: Could not start PostgreSQL testcontainer: {e}. "
            "Start PostgreSQL via 'podman-compose up -d postgres' or set TEST_DATABASE_URL."
        )


def pytest_unconfigure(config):
    """Stop PostgreSQL container after all tests complete."""
    global _postgres_container  # noqa: PLW0603
    if _postgres_container:
        try:
            _postgres_container.stop()
        except Exception:  # noqa: S110
            pass  # Ignore errors on cleanup - container may already be stopped
        finally:
            _postgres_container = None


def get_test_db_url() -> str:
    """Get the PostgreSQL test database URL.

    Priority order:
    1. TEST_DATABASE_URL environment variable (explicit override)
    2. Local PostgreSQL on port 5432 (development with Podman/Docker)
    3. Testcontainer (CI or when Docker available)

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

    # 3. Fall back to testcontainer
    if _postgres_container is not None:
        # Get the connection URL and ensure it uses asyncpg driver
        url = _postgres_container.get_connection_url()
        # Replace psycopg2 driver with asyncpg
        return url.replace("postgresql+psycopg2://", "postgresql+asyncpg://")

    raise RuntimeError(
        "PostgreSQL not available for testing. Options:\n"
        "1. Start PostgreSQL via 'podman-compose up -d postgres' (development)\n"
        "2. Set TEST_DATABASE_URL environment variable\n"
        "3. Ensure Docker/Podman is available for testcontainers"
    )


# Track if schema has been reset this worker process to avoid redundant operations
_schema_reset_done: bool = False


async def _ensure_clean_db(use_lock: bool = True) -> None:
    """Ensure database has tables and is ready for tests.

    This function creates tables if they don't exist (under advisory lock for
    coordination across parallel pytest-xdist workers).

    Test isolation is achieved through:
    1. Savepoint/rollback in the session fixture (transaction isolation)
    2. Using unique_id() for test data (prevents cross-test conflicts)

    We intentionally do NOT truncate tables here because:
    - TRUNCATE requires AccessExclusiveLock which conflicts with concurrent operations
    - Savepoint rollback provides proper isolation within each test
    - unique_id() prevents primary key conflicts between parallel tests
    """
    # Just ensure schema exists
    await _reset_db_schema(use_lock=use_lock)


async def _reset_db_schema(use_lock: bool = True) -> None:
    """Drop and recreate all tables to ensure fresh schema.

    This is called once per worker process to ensure the database schema matches
    the current SQLAlchemy models. Uses PostgreSQL advisory locks to coordinate
    across parallel pytest-xdist workers.

    Args:
        use_lock: If True, use PostgreSQL advisory lock to coordinate across workers.
                  Set to False for single-threaded test runs or when lock is not needed.
    """
    global _schema_reset_done  # noqa: PLW0603

    if _schema_reset_done:
        return

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

    async with engine.begin() as conn:
        if use_lock:
            # Use PostgreSQL advisory lock to ensure only one worker does schema reset
            # Lock ID 12345 is arbitrary but must be consistent across all workers
            # pg_advisory_lock is a session-level lock that blocks until acquired
            await conn.execute(text("SELECT pg_advisory_lock(12345)"))
            try:
                # Check if tables exist - if they do with correct schema, skip reset
                # This prevents unnecessary drops when another worker already created them
                result = await conn.execute(
                    text(
                        "SELECT EXISTS ("
                        "SELECT FROM information_schema.tables "
                        "WHERE table_schema = 'public' AND table_name = 'cameras'"
                        ")"
                    )
                )
                tables_exist = result.scalar()

                if not tables_exist:
                    # Tables don't exist - create them
                    await conn.run_sync(ModelsBase.metadata.create_all)
                # If tables exist, assume schema is correct (another worker created them)
            finally:
                # Release the lock
                await conn.execute(text("SELECT pg_advisory_unlock(12345)"))
        else:
            # No lock needed - just create tables if they don't exist
            await conn.run_sync(ModelsBase.metadata.create_all)


@pytest.fixture(scope="function")
async def isolated_db():
    """Create an isolated test database for each test.

    This fixture:
    - Uses the shared PostgreSQL testcontainer or local PostgreSQL
    - Sets the DATABASE_URL environment variable
    - Clears the settings cache
    - Ensures tables exist (created once per worker, coordinated via advisory lock)
    - Yields control to the test
    - Cleans up and restores the original state

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

    # Cleanup
    await close_db()

    # Restore original state
    if original_db_url:
        os.environ["DATABASE_URL"] = original_db_url
    else:
        os.environ.pop("DATABASE_URL", None)

    # Clear cache one more time to ensure clean state
    get_settings.cache_clear()


@pytest.fixture
async def session(isolated_db):
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
def reset_settings_cache():
    """Automatically reset settings cache before each test.

    This ensures no global state leaks between tests.
    Note: We don't auto-close database here since some tests
    explicitly test the behavior when database is not initialized.
    """
    from backend.core.config import get_settings

    # Clear settings cache before test
    get_settings.cache_clear()

    yield

    # Clear settings cache after test
    get_settings.cache_clear()


@pytest.fixture
async def test_db():
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

    # Cleanup
    await close_db()

    # Restore original state
    if original_db_url:
        os.environ["DATABASE_URL"] = original_db_url
    else:
        os.environ.pop("DATABASE_URL", None)

    # Clear cache one more time to ensure clean state
    get_settings.cache_clear()


# =============================================================================
# Integration Test Fixtures
# =============================================================================
# These fixtures are shared across all integration and E2E tests.
# They provide consistent database setup, Redis mocking, and HTTP client access.


@pytest.fixture
def integration_env() -> Generator[str]:
    """Set DATABASE_URL/REDIS_URL to a PostgreSQL test database.

    This fixture ONLY sets environment variables and clears cached settings.
    Use `integration_db` if the test needs the database initialized.

    All integration tests should use this fixture (directly or via integration_db)
    to ensure proper isolation and cleanup.
    """
    from backend.core.config import get_settings

    original_db_url = os.environ.get("DATABASE_URL")
    original_redis_url = os.environ.get("REDIS_URL")
    original_runtime_env_path = os.environ.get("HSI_RUNTIME_ENV_PATH")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Get PostgreSQL URL from testcontainer
        test_db_url = get_test_db_url()
        runtime_env_path = str(Path(tmpdir) / "runtime.env")

        os.environ["DATABASE_URL"] = test_db_url
        # Use Redis database 15 for test isolation. This keeps test data separate
        # from development (database 0). FLUSHDB in pre-commit hooks only affects DB 15.
        # See backend/tests/AGENTS.md for full documentation on test database isolation.
        os.environ["REDIS_URL"] = "redis://localhost:6379/15"
        os.environ["HSI_RUNTIME_ENV_PATH"] = runtime_env_path

        get_settings.cache_clear()

        try:
            yield test_db_url
        finally:
            # Restore env
            if original_db_url is not None:
                os.environ["DATABASE_URL"] = original_db_url
            else:
                os.environ.pop("DATABASE_URL", None)

            if original_redis_url is not None:
                os.environ["REDIS_URL"] = original_redis_url
            else:
                os.environ.pop("REDIS_URL", None)

            if original_runtime_env_path is not None:
                os.environ["HSI_RUNTIME_ENV_PATH"] = original_runtime_env_path
            else:
                os.environ.pop("HSI_RUNTIME_ENV_PATH", None)

            get_settings.cache_clear()


@pytest.fixture
async def integration_db(integration_env: str) -> AsyncGenerator[str]:
    """Initialize a PostgreSQL test database for integration/E2E tests.

    This fixture:
    - Depends on integration_env for environment setup
    - Closes any existing database connections
    - Drops and recreates all tables for fresh schema
    - Yields the database URL
    - Cleans up after the test

    Use this fixture for any test that needs database access.
    """
    from backend.core.config import get_settings
    from backend.core.database import close_db, init_db

    # Ensure clean state
    get_settings.cache_clear()
    await close_db()

    # Initialize database (creates engine)
    await init_db()

    # Reset schema to ensure it matches current models
    await _reset_db_schema()

    try:
        yield integration_env
    finally:
        await close_db()
        get_settings.cache_clear()


@pytest.fixture
async def mock_redis() -> AsyncGenerator[AsyncMock]:
    """Mock Redis operations so integration tests don't require an actual Redis server.

    This fixture provides a mock Redis client with common operations pre-configured:
    - health_check: Returns healthy status

    The mock is patched into backend.core.redis module.
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


@pytest.fixture
async def db_session(integration_db: str):
    """Yield a live AsyncSession bound to the integration test database.

    Use this fixture when you need direct database session access in tests.
    The session is automatically committed and closed after the test.
    """
    from backend.core.database import get_session

    async with get_session() as session:
        yield session


@pytest.fixture
async def client(integration_db: str, mock_redis: AsyncMock) -> AsyncGenerator:
    """Async HTTP client bound to the FastAPI app (no network, no server startup).

    Notes:
    - The DB is pre-initialized by `integration_db`.
    - We patch app lifespan DB init/close to avoid double initialization.
    - We patch Redis init/close in `backend.main` so lifespan does not connect.

    Use this fixture for testing API endpoints.
    """
    from httpx import ASGITransport, AsyncClient

    # Import the app only after env is set up.
    from backend.main import app

    with (
        patch("backend.main.init_db", return_value=None),
        patch("backend.main.close_db", return_value=None),
        patch("backend.main.init_redis", return_value=mock_redis),
        patch("backend.main.close_redis", return_value=None),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac


def unique_id(prefix: str = "test") -> str:
    """Generate a unique ID for test objects to prevent conflicts in parallel execution.

    Args:
        prefix: Optional prefix for the ID (default: "test")

    Returns:
        A unique string ID like "test_abc12345"
    """
    import uuid

    return f"{prefix}_{uuid.uuid4().hex[:8]}"
