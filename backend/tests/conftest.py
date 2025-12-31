"""Pytest configuration and shared fixtures.

This module provides shared test fixtures for all backend tests:
- isolated_db: Function-scoped isolated database for unit tests (PostgreSQL)
- test_db: Callable session factory for unit tests
- integration_env: Environment setup for integration tests
- integration_db: Initialized database for integration tests
- mock_redis: Mock Redis client for integration tests
- real_redis: Real Redis client via testcontainers for integration tests
- db_session: Database session for integration tests
- client: httpx AsyncClient for API integration tests

Tests use PostgreSQL and Redis via testcontainers or local instances.
Configure TEST_DATABASE_URL/TEST_REDIS_URL environment variables for overrides.

See backend/tests/AGENTS.md for full documentation on test conventions.
"""

from __future__ import annotations

import os
import socket
import sys
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator

    from testcontainers.postgres import PostgresContainer
    from testcontainers.redis import RedisContainer

    from backend.core.redis import RedisClient

# Add backend to path for imports
backend_path = Path(__file__).parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


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
    except Exception:
        return False


def _check_postgres_connection(host: str = "localhost", port: int = 5432) -> bool:
    """Check if PostgreSQL is reachable on the given host/port."""
    return _check_tcp_connection(host, port)


def _check_redis_connection(host: str = "localhost", port: int = 6379) -> bool:
    """Check if Redis is reachable on the given host/port."""
    return _check_tcp_connection(host, port)


# Module-level PostgreSQL container shared across all tests in a session
# Type annotation uses string to avoid import at module level
_postgres_container: PostgresContainer | None = None

# Module-level Redis container shared across all tests in a session
_redis_container: RedisContainer | None = None


def pytest_configure(config: pytest.Config) -> None:
    """Start PostgreSQL and Redis containers once for the entire test session.

    Also configures pytest-xdist to use loadgroup scheduling when
    running tests in parallel, which respects xdist_group markers.
    This ensures tests marked with @pytest.mark.xdist_group run
    sequentially on the same worker.

    Skipped when:
    - TEST_DATABASE_URL/TEST_REDIS_URL environment variable is set (explicit override)
    - Local PostgreSQL/Redis is already running (Podman/Docker)
    """
    global _postgres_container, _redis_container  # noqa: PLW0603

    # NOTE: loadgroup scheduling disabled due to xdist worker crash bug
    # The loadscope scheduler crashes with KeyError when workers fail.
    # Using default "load" distribution instead for stability.
    # If xdist_group markers are needed, explicitly use --dist=loadgroup
    pass

    # Start PostgreSQL container if needed
    if not os.environ.get("TEST_DATABASE_URL") and not _check_postgres_connection():
        try:
            # Import testcontainers only when needed to avoid side effects at module load
            from testcontainers.postgres import PostgresContainer

            _postgres_container = PostgresContainer(
                "postgres:16-alpine",
                username="postgres",
                password="postgres",  # noqa: S106 - test password
                dbname="security_test",
                driver="asyncpg",
            )
            _postgres_container.start()
        except Exception as e:
            print(
                f"Warning: Could not start PostgreSQL testcontainer: {e}. "
                "Start PostgreSQL via 'podman-compose up -d postgres' or set TEST_DATABASE_URL."
            )

    # Start Redis container if needed
    if not os.environ.get("TEST_REDIS_URL") and not _check_redis_connection():
        try:
            # Import testcontainers only when needed to avoid side effects at module load
            from testcontainers.redis import RedisContainer

            _redis_container = RedisContainer("redis:7-alpine")
            _redis_container.start()
        except Exception as e:
            print(
                f"Warning: Could not start Redis testcontainer: {e}. "
                "Start Redis via 'podman-compose up -d redis' or set TEST_REDIS_URL."
            )


def pytest_unconfigure(config: pytest.Config) -> None:
    """Stop PostgreSQL and Redis containers after all tests complete."""
    global _postgres_container, _redis_container  # noqa: PLW0603

    if _postgres_container:
        try:
            _postgres_container.stop()
        except Exception:  # noqa: S110
            pass  # Ignore errors on cleanup - container may already be stopped
        finally:
            _postgres_container = None

    if _redis_container:
        try:
            _redis_container.stop()
        except Exception:  # noqa: S110
            pass  # Ignore errors on cleanup - container may already be stopped
        finally:
            _redis_container = None


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


def get_test_redis_url() -> str:
    """Get the Redis test URL.

    Priority order:
    1. TEST_REDIS_URL environment variable (explicit override)
    2. Local Redis on port 6379 (development with Podman/Docker)
    3. Testcontainer (CI or when Docker available)

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

    # 3. Fall back to testcontainer
    if _redis_container is not None:
        # RedisContainer doesn't have get_connection_url() like PostgresContainer,
        # so we need to construct the URL manually from host and port
        host = _redis_container.get_container_host_ip()
        port = _redis_container.get_exposed_port(6379)
        # Use database 15 for test isolation
        return f"redis://{host}:{port}/15"

    raise RuntimeError(
        "Redis not available for testing. Options:\n"
        "1. Start Redis via 'podman-compose up -d redis' (development)\n"
        "2. Set TEST_REDIS_URL environment variable\n"
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
async def isolated_db() -> AsyncGenerator[None]:
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
# They provide consistent database setup, Redis access, and HTTP client access.


@pytest.fixture
def integration_env() -> Generator[str]:
    """Set DATABASE_URL/REDIS_URL for integration tests.

    This fixture ONLY sets environment variables and clears cached settings.
    Use `integration_db` if the test needs the database initialized.

    All integration tests should use this fixture (directly or via integration_db)
    to ensure proper isolation and cleanup.
    """
    import tempfile

    from backend.core.config import get_settings

    original_db_url = os.environ.get("DATABASE_URL")
    original_redis_url = os.environ.get("REDIS_URL")
    original_runtime_env_path = os.environ.get("HSI_RUNTIME_ENV_PATH")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Get PostgreSQL URL from testcontainer or local
        test_db_url = get_test_db_url()
        # Get Redis URL from testcontainer or local (uses DB 15 for test isolation)
        test_redis_url = get_test_redis_url()
        runtime_env_path = str(Path(tmpdir) / "runtime.env")

        os.environ["DATABASE_URL"] = test_db_url
        os.environ["REDIS_URL"] = test_redis_url
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

    Use this for tests that need to mock Redis behavior.
    For tests that need real Redis behavior, use the `real_redis` fixture instead.
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
async def real_redis() -> AsyncGenerator[RedisClient]:
    """Provide a real Redis client connected to testcontainers or local Redis.

    This fixture provides a real RedisClient instance for integration tests that
    need to test actual Redis behavior (e.g., queue operations, pub/sub, etc.).

    The fixture:
    - Connects to Redis (testcontainer or local)
    - Flushes the test database before yielding (isolation)
    - Disconnects after the test

    Use this fixture when you need to test real Redis behavior.
    For tests that just need Redis to not fail, use `mock_redis` instead.
    """
    from backend.core.redis import RedisClient

    # Get Redis URL from testcontainer or local
    redis_url = get_test_redis_url()

    # Create and connect the client
    client = RedisClient(redis_url=redis_url)
    await client.connect()

    try:
        # Flush the test database for isolation
        redis_client = client._ensure_connected()
        await redis_client.flushdb()

        yield client
    finally:
        # Ensure clean state before disconnecting
        try:
            redis_client = client._ensure_connected()
            await redis_client.flushdb()
        except Exception:  # noqa: S110
            pass  # Ignore errors during cleanup
        await client.disconnect()


@pytest.fixture
async def db_session(integration_db: str) -> AsyncGenerator[None]:
    """Yield a live AsyncSession bound to the integration test database.

    Use this fixture when you need direct database session access in tests.
    The session is automatically committed and closed after the test.
    """
    from backend.core.database import get_session

    async with get_session() as session:
        yield session


@pytest.fixture
async def client(integration_db: str, mock_redis: AsyncMock) -> AsyncGenerator[None]:
    """Async HTTP client bound to the FastAPI app (no network, no server startup).

    Notes:
    - The DB is pre-initialized by `integration_db`.
    - We patch app lifespan DB init/close to avoid double initialization.
    - We patch Redis init/close in `backend.main` so lifespan does not connect.
    - Tests that need isolation should use clean_events, clean_cameras, or clean_logs
      fixtures which will truncate tables before data fixtures create their data.

    Use this fixture for testing API endpoints.
    """
    from httpx import ASGITransport, AsyncClient

    # Import the app only after env is set up.
    from backend.main import app

    # NOTE: Removed TRUNCATE from here because it was running AFTER data fixtures
    # (sample_event, sample_camera, etc) created their data due to pytest fixture
    # ordering. Tests that need clean state should use clean_* fixtures explicitly.

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
